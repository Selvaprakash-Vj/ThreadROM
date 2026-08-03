"""Validate preload-only external force equilibrium."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import cast


def _mapping_items(
    payload: Mapping[str, object],
    key: str,
) -> tuple[Mapping[str, object], ...]:
    value = payload.get(key)

    if not isinstance(value, list):
        raise TypeError(f"Expected '{key}' to be a list.")

    items: list[Mapping[str, object]] = []

    for item in value:
        if not isinstance(item, dict):
            raise TypeError(f"Expected every '{key}' item to be a mapping.")

        items.append(cast(Mapping[str, object], item))

    return tuple(items)


def _number(
    payload: Mapping[str, object],
    key: str,
) -> float:
    value = payload.get(key)

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"Expected numeric value: {key}")

    return float(value)


def _integer(
    payload: Mapping[str, object],
    key: str,
) -> int:
    value = payload.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Expected integer value: {key}")

    return value


def _load_json_mapping(
    path: Path,
) -> Mapping[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)

    payload: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object in {path}.")

    return cast(Mapping[str, object], payload)


def validate_external_equilibrium(
    progress_payload: Mapping[str, object],
    total_force_payload: Mapping[str, object],
    *,
    support_set_name: str,
    force_absolute_tolerance_n: float = 1.0e-3,
    time_absolute_tolerance: float = 1.0e-9,
) -> dict[str, object]:
    """Validate near-zero external reaction during preload.

    Bolt pretension is an internal self-equilibrated action. Therefore,
    the externally constrained support reaction should remain near zero
    when no additional external service load is applied.
    """

    if not support_set_name.strip():
        raise ValueError("Support set name cannot be blank.")

    if force_absolute_tolerance_n < 0.0:
        raise ValueError("Force tolerance cannot be negative.")

    if time_absolute_tolerance < 0.0:
        raise ValueError("Time tolerance cannot be negative.")

    accepted_items = _mapping_items(
        progress_payload,
        "accepted_increments",
    )

    force_items = _mapping_items(
        total_force_payload,
        "records",
    )

    requested_set = support_set_name.casefold()

    support_records = tuple(
        item
        for item in force_items
        if (
            isinstance(item.get("set_name"), str)
            and cast(str, item["set_name"]).casefold() == requested_set
        )
    )

    validations: list[dict[str, object]] = []

    matched_force_indices: set[int] = set()

    for accepted in accepted_items:
        step = _integer(accepted, "step")
        increment = _integer(accepted, "increment")
        accepted_time = _number(
            accepted,
            "step_time",
        )

        match_index: int | None = None
        match_record: Mapping[str, object] | None = None

        for force_index, force_record in enumerate(support_records):
            if force_index in matched_force_indices:
                continue

            force_time = _number(
                force_record,
                "time",
            )

            if not math.isclose(
                force_time,
                accepted_time,
                rel_tol=0.0,
                abs_tol=time_absolute_tolerance,
            ):
                continue

            record_increment = force_record.get("increment")

            if record_increment is not None and (
                isinstance(record_increment, bool) or not isinstance(record_increment, int)
            ):
                raise TypeError("Total-force increment must be an integer or null.")

            if isinstance(record_increment, int) and record_increment != increment:
                continue

            match_index = force_index
            match_record = force_record
            break

        if match_record is None or match_index is None:
            validations.append(
                {
                    "step": step,
                    "increment": increment,
                    "accepted_time": accepted_time,
                    "status": "pending",
                    "reason": (
                        "Accepted increment has no matching complete support-force DAT record."
                    ),
                }
            )
            continue

        matched_force_indices.add(match_index)

        components = match_record.get("force_components_n")

        if not isinstance(components, list) or len(components) != 3:
            raise TypeError("Expected three support-force components.")

        parsed_components: list[float] = []

        for component in components:
            if isinstance(component, bool) or not isinstance(
                component,
                (int, float),
            ):
                raise TypeError("Support-force components must be numeric.")

            parsed_components.append(float(component))

        force_x_n, force_y_n, force_z_n = parsed_components

        maximum_absolute_component_n = max(
            abs(force_x_n),
            abs(force_y_n),
            abs(force_z_n),
        )

        status = "pass" if maximum_absolute_component_n <= force_absolute_tolerance_n else "fail"

        validations.append(
            {
                "step": step,
                "increment": increment,
                "accepted_time": accepted_time,
                "dat_time": _number(
                    match_record,
                    "time",
                ),
                "support_set_name": (support_set_name),
                "force_components_n": [
                    force_x_n,
                    force_y_n,
                    force_z_n,
                ],
                "maximum_absolute_component_n": (maximum_absolute_component_n),
                "status": status,
            }
        )

    orphan_records = [
        dict(record)
        for force_index, record in enumerate(support_records)
        if force_index not in matched_force_indices
    ]

    passed_count = sum(validation["status"] == "pass" for validation in validations)

    failed_count = sum(validation["status"] == "fail" for validation in validations)

    pending_count = sum(validation["status"] == "pending" for validation in validations)

    if failed_count:
        overall_status = "fail"
    elif pending_count:
        overall_status = "pending"
    else:
        overall_status = "pass"

    return {
        "schema_version": 1,
        "validation_scope": (
            "Preload-only external support equilibrium. "
            "Pretension-reference force is internal and "
            "is not balanced against support reaction."
        ),
        "support_set_name": support_set_name,
        "accepted_increment_count": len(accepted_items),
        "support_force_record_count": len(support_records),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "pending_count": pending_count,
        "orphan_record_count": len(orphan_records),
        "overall_status": overall_status,
        "tolerances": {
            "force_absolute_n": (force_absolute_tolerance_n),
            "time_absolute": (time_absolute_tolerance),
        },
        "validations": validations,
        "orphan_records": orphan_records,
        "limitations": [
            (
                "This validates only the printed support "
                "set, not every constrained guidance "
                "reference."
            ),
            ("It does not validate internal contact-force transfer or per-interface equilibrium."),
        ],
    }


def write_external_equilibrium_json(
    progress_path: Path,
    total_force_path: Path,
    output_path: Path,
    *,
    support_set_name: str,
    force_absolute_tolerance_n: float = 1.0e-3,
    time_absolute_tolerance: float = 1.0e-9,
) -> dict[str, object]:
    """Validate two governed artifacts and write JSON."""

    payload = validate_external_equilibrium(
        _load_json_mapping(progress_path),
        _load_json_mapping(total_force_path),
        support_set_name=support_set_name,
        force_absolute_tolerance_n=(force_absolute_tolerance_n),
        time_absolute_tolerance=(time_absolute_tolerance),
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return payload

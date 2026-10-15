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
        accepted_time = (
            _number(accepted, "total_time")
            if "total_time" in accepted
            else _number(accepted, "step_time")
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



def validate_translational_constraint_equilibrium(
    progress_payload: Mapping[str, object],
    total_force_payload: Mapping[str, object],
    *,
    force_set_names: tuple[str, ...],
    force_absolute_tolerance_n: float = 1.0e-3,
    time_absolute_tolerance: float = 1.0e-9,
) -> dict[str, object]:
    """Validate complete governed translational reaction equilibrium.

    ``force_set_names`` is an explicit caller-governed list of reaction
    sets that represent translational constraints. Generalized rotational
    MPC reactions are intentionally outside this force balance and require
    separate moment/generalized-reaction assessment.
    """

    if not force_set_names:
        raise ValueError(
            "At least one translational force set is required."
        )

    normalized_names = tuple(
        name.strip()
        for name in force_set_names
    )

    if any(not name for name in normalized_names):
        raise ValueError(
            "Translational force-set names cannot be blank."
        )

    folded_names = tuple(
        name.casefold()
        for name in normalized_names
    )

    if len(set(folded_names)) != len(folded_names):
        raise ValueError(
            "Translational force-set names must be unique."
        )

    if force_absolute_tolerance_n < 0.0:
        raise ValueError(
            "Force tolerance cannot be negative."
        )

    if time_absolute_tolerance < 0.0:
        raise ValueError(
            "Time tolerance cannot be negative."
        )

    accepted_items = _mapping_items(
        progress_payload,
        "accepted_increments",
    )

    force_items = _mapping_items(
        total_force_payload,
        "records",
    )

    requested_names = set(folded_names)

    requested_records = tuple(
        item
        for item in force_items
        if (
            isinstance(item.get("set_name"), str)
            and cast(
                str,
                item["set_name"],
            ).casefold() in requested_names
        )
    )

    validations: list[dict[str, object]] = []
    matched_force_indices: set[int] = set()

    for accepted in accepted_items:
        step = _integer(
            accepted,
            "step",
        )

        increment = _integer(
            accepted,
            "increment",
        )

        accepted_time = (
            _number(
                accepted,
                "total_time",
            )
            if "total_time" in accepted
            else _number(
                accepted,
                "step_time",
            )
        )

        staged_matches: list[
            tuple[
                int,
                str,
                Mapping[str, object],
            ]
        ] = []

        missing_names: list[str] = []

        for requested_name, requested_folded in zip(
            normalized_names,
            folded_names,
        ):
            candidates: list[
                tuple[int, Mapping[str, object]]
            ] = []

            for force_index, force_record in enumerate(
                force_items
            ):
                if force_index in matched_force_indices:
                    continue

                set_name = force_record.get(
                    "set_name"
                )

                if (
                    not isinstance(set_name, str)
                    or set_name.casefold()
                    != requested_folded
                ):
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

                record_increment = force_record.get(
                    "increment"
                )

                if (
                    record_increment is not None
                    and (
                        isinstance(
                            record_increment,
                            bool,
                        )
                        or not isinstance(
                            record_increment,
                            int,
                        )
                    )
                ):
                    raise TypeError(
                        "Total-force increment must be "
                        "an integer or null."
                    )

                if (
                    isinstance(
                        record_increment,
                        int,
                    )
                    and record_increment
                    != increment
                ):
                    continue

                candidates.append(
                    (
                        force_index,
                        force_record,
                    )
                )

            if len(candidates) > 1:
                raise RuntimeError(
                    "Ambiguous translational reaction "
                    f"record for set {requested_name!r} "
                    f"at accepted time {accepted_time}."
                )

            if not candidates:
                missing_names.append(
                    requested_name
                )
                continue

            force_index, force_record = (
                candidates[0]
            )

            staged_matches.append(
                (
                    force_index,
                    requested_name,
                    force_record,
                )
            )

        if missing_names:
            validations.append(
                {
                    "step": step,
                    "increment": increment,
                    "accepted_time": (
                        accepted_time
                    ),
                    "status": "pending",
                    "reason": (
                        "Accepted increment lacks "
                        "complete translational "
                        "reaction evidence."
                    ),
                    "missing_force_set_names": (
                        missing_names
                    ),
                }
            )
            continue

        total_x_n = 0.0
        total_y_n = 0.0
        total_z_n = 0.0

        component_records: list[
            dict[str, object]
        ] = []

        for (
            force_index,
            requested_name,
            force_record,
        ) in staged_matches:
            components = force_record.get(
                "force_components_n"
            )

            if (
                not isinstance(
                    components,
                    list,
                )
                or len(components) != 3
            ):
                raise TypeError(
                    "Expected three translational "
                    "force components."
                )

            parsed_components: list[
                float
            ] = []

            for component in components:
                if (
                    isinstance(
                        component,
                        bool,
                    )
                    or not isinstance(
                        component,
                        (int, float),
                    )
                ):
                    raise TypeError(
                        "Translational force "
                        "components must be numeric."
                    )

                parsed_components.append(
                    float(component)
                )

            force_x_n, force_y_n, force_z_n = (
                parsed_components
            )

            total_x_n += force_x_n
            total_y_n += force_y_n
            total_z_n += force_z_n

            component_records.append(
                {
                    "set_name": (
                        requested_name
                    ),
                    "force_components_n": [
                        force_x_n,
                        force_y_n,
                        force_z_n,
                    ],
                }
            )

            matched_force_indices.add(
                force_index
            )

        resultant_n = math.sqrt(
            total_x_n * total_x_n
            + total_y_n * total_y_n
            + total_z_n * total_z_n
        )

        maximum_absolute_component_n = max(
            abs(total_x_n),
            abs(total_y_n),
            abs(total_z_n),
        )

        status = (
            "pass"
            if resultant_n
            <= force_absolute_tolerance_n
            else "fail"
        )

        validations.append(
            {
                "step": step,
                "increment": increment,
                "accepted_time": (
                    accepted_time
                ),
                "force_set_names": list(
                    normalized_names
                ),
                "component_records": (
                    component_records
                ),
                "summed_force_components_n": [
                    total_x_n,
                    total_y_n,
                    total_z_n,
                ],
                "maximum_absolute_component_n": (
                    maximum_absolute_component_n
                ),
                "resultant_force_n": (
                    resultant_n
                ),
                "status": status,
            }
        )

    orphan_records = [
        dict(record)
        for force_index, record in enumerate(
            force_items
        )
        if (
            force_index
            not in matched_force_indices
            and isinstance(
                record.get("set_name"),
                str,
            )
            and cast(
                str,
                record["set_name"],
            ).casefold()
            in requested_names
        )
    ]

    passed_count = sum(
        validation["status"] == "pass"
        for validation in validations
    )

    failed_count = sum(
        validation["status"] == "fail"
        for validation in validations
    )

    pending_count = sum(
        validation["status"] == "pending"
        for validation in validations
    )

    if failed_count:
        overall_status = "fail"
    elif pending_count:
        overall_status = "pending"
    else:
        overall_status = "pass"

    passed_resultants = [
        float(validation["resultant_force_n"])
        for validation in validations
        if "resultant_force_n"
        in validation
    ]

    return {
        "schema_version": 2,
        "validation_scope": (
            "Preload-only complete translational "
            "constraint-system equilibrium. "
            "Pretension is internal. Rotational "
            "MPC/generalized reactions are outside "
            "this translational force balance."
        ),
        "force_set_names": list(
            normalized_names
        ),
        "accepted_increment_count": len(
            accepted_items
        ),
        "requested_force_record_count": len(
            requested_records
        ),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "pending_count": pending_count,
        "orphan_record_count": len(
            orphan_records
        ),
        "overall_status": overall_status,
        "maximum_resultant_force_n": (
            max(passed_resultants)
            if passed_resultants
            else None
        ),
        "tolerances": {
            "force_absolute_n": (
                force_absolute_tolerance_n
            ),
            "time_absolute": (
                time_absolute_tolerance
            ),
        },
        "validations": validations,
        "orphan_records": orphan_records,
        "limitations": [
            (
                "Only the explicitly governed "
                "translational force sets supplied "
                "by the caller are included."
            ),
            (
                "Rotational MPC/generalized "
                "reaction equilibrium is not "
                "assessed by this validator."
            ),
            (
                "Internal contact-force transfer "
                "and per-interface equilibrium are "
                "assessed separately."
            ),
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


def validate_external_equilibrium_resultant(
    progress_payload: Mapping[str, object],
    total_force_payload: Mapping[str, object],
    *,
    support_set_names: tuple[str, ...],
    force_absolute_tolerance_n: float = 1.0e-3,
    time_absolute_tolerance: float = 1.0e-9,
) -> dict[str, object]:
    """Validate the complete external translational reaction resultant.

    Bolt pretension is an internal self-equilibrated action.  A complete
    translational equilibrium check must therefore sum every governed
    translational constraint reaction that closes the external force
    system.

    Rotational-guidance reference reactions are intentionally excluded
    from this force resultant.
    """

    names = tuple(
        name.strip()
        for name in support_set_names
        if name.strip()
    )

    if not names:
        raise ValueError(
            "At least one translational support set is required."
        )

    folded_names = tuple(
        name.casefold()
        for name in names
    )

    if len(set(folded_names)) != len(folded_names):
        raise ValueError(
            "Translational support-set names must be unique."
        )

    if force_absolute_tolerance_n < 0.0:
        raise ValueError(
            "Force tolerance cannot be negative."
        )

    if time_absolute_tolerance < 0.0:
        raise ValueError(
            "Time tolerance cannot be negative."
        )

    accepted_items = _mapping_items(
        progress_payload,
        "accepted_increments",
    )

    force_items = _mapping_items(
        total_force_payload,
        "records",
    )

    requested = {
        name.casefold(): name
        for name in names
    }

    relevant_force_indices = {
        index
        for index, item in enumerate(force_items)
        if (
            isinstance(
                item.get("set_name"),
                str,
            )
            and cast(
                str,
                item["set_name"],
            ).casefold()
            in requested
        )
    }

    def components(
        item: Mapping[str, object],
    ) -> tuple[float, float, float]:
        raw = item.get(
            "force_components_n"
        )

        if (
            not isinstance(raw, list)
            or len(raw) != 3
        ):
            raise TypeError(
                "Expected three force components."
            )

        values: list[float] = []

        for value in raw:
            if (
                isinstance(value, bool)
                or not isinstance(
                    value,
                    (int, float),
                )
            ):
                raise TypeError(
                    "Force components must be numeric."
                )

            numeric = float(value)

            if not math.isfinite(numeric):
                raise ValueError(
                    "Force components must be finite."
                )

            values.append(numeric)

        return (
            values[0],
            values[1],
            values[2],
        )

    validations: list[
        dict[str, object]
    ] = []

    matched_force_indices: set[int] = set()

    for accepted in accepted_items:
        step = _integer(
            accepted,
            "step",
        )

        increment = _integer(
            accepted,
            "increment",
        )

        accepted_time = (
            _number(
                accepted,
                "total_time",
            )
            if "total_time" in accepted
            else _number(
                accepted,
                "step_time",
            )
        )

        matched: dict[
            str,
            tuple[
                int,
                Mapping[str, object],
            ],
        ] = {}

        missing: list[str] = []

        for name in names:
            folded = name.casefold()

            candidates: list[
                tuple[
                    int,
                    Mapping[str, object],
                ]
            ] = []

            for index, item in enumerate(
                force_items
            ):
                set_name = item.get(
                    "set_name"
                )

                if (
                    not isinstance(
                        set_name,
                        str,
                    )
                    or set_name.casefold()
                    != folded
                ):
                    continue

                dat_time = _number(
                    item,
                    "time",
                )

                if (
                    abs(
                        dat_time
                        - accepted_time
                    )
                    <= time_absolute_tolerance
                ):
                    candidates.append(
                        (
                            index,
                            item,
                        )
                    )

            if len(candidates) > 1:
                raise RuntimeError(
                    "Multiple matching total-force "
                    "records for "
                    f"{name} at time "
                    f"{accepted_time}."
                )

            if not candidates:
                missing.append(name)
                continue

            matched[name] = (
                candidates[0]
            )

        if missing:
            validations.append(
                {
                    "step": step,
                    "increment": increment,
                    "accepted_time": (
                        accepted_time
                    ),
                    "status": "pending",
                    "missing_support_sets": (
                        missing
                    ),
                    "reason": (
                        "Accepted increment lacks "
                        "a complete translational "
                        "reaction record for every "
                        "governed support set."
                    ),
                }
            )

            continue

        resultant = [
            0.0,
            0.0,
            0.0,
        ]

        per_set: dict[
            str,
            list[float],
        ] = {}

        for name in names:
            index, item = matched[name]

            matched_force_indices.add(
                index
            )

            values = components(item)

            per_set[name] = [
                values[0],
                values[1],
                values[2],
            ]

            resultant[0] += values[0]
            resultant[1] += values[1]
            resultant[2] += values[2]

        maximum_absolute_component_n = max(
            abs(resultant[0]),
            abs(resultant[1]),
            abs(resultant[2]),
        )

        status = (
            "pass"
            if (
                maximum_absolute_component_n
                <= force_absolute_tolerance_n
            )
            else "fail"
        )

        validations.append(
            {
                "step": step,
                "increment": increment,
                "accepted_time": (
                    accepted_time
                ),
                "support_set_names": (
                    list(names)
                ),
                "per_set_force_components_n": (
                    per_set
                ),
                "resultant_force_components_n": [
                    resultant[0],
                    resultant[1],
                    resultant[2],
                ],
                "maximum_absolute_component_n": (
                    maximum_absolute_component_n
                ),
                "status": status,
            }
        )

    passed_count = sum(
        item.get("status") == "pass"
        for item in validations
    )

    failed_count = sum(
        item.get("status") == "fail"
        for item in validations
    )

    pending_count = sum(
        item.get("status") == "pending"
        for item in validations
    )

    orphan_indices = sorted(
        relevant_force_indices
        - matched_force_indices
    )

    orphan_records = [
        dict(force_items[index])
        for index in orphan_indices
    ]

    if failed_count:
        overall_status = "fail"
    elif pending_count:
        overall_status = "pending"
    else:
        overall_status = "pass"

    return {
        "schema_version": 2,
        "validation_scope": (
            "Preload-only global external "
            "translational reaction equilibrium "
            "across every governed translational "
            "constraint set. Rotational-guidance "
            "reference reactions are excluded "
            "from the force resultant."
        ),
        "support_set_names": list(names),
        "accepted_increment_count": (
            len(accepted_items)
        ),
        "support_force_record_count": (
            len(relevant_force_indices)
        ),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "pending_count": pending_count,
        "orphan_record_count": (
            len(orphan_records)
        ),
        "overall_status": (
            overall_status
        ),
        "tolerances": {
            "force_absolute_n": (
                force_absolute_tolerance_n
            ),
            "time_absolute": (
                time_absolute_tolerance
            ),
        },
        "validations": validations,
        "orphan_records": orphan_records,
        "limitations": [
            (
                "This validates the complete "
                "external translational force "
                "resultant represented by the "
                "governed translational "
                "constraint sets."
            ),
            (
                "Rotational-guidance reference "
                "reactions are intentionally "
                "excluded from the force "
                "resultant."
            ),
            (
                "This does not replace internal "
                "contact-force transfer or "
                "per-interface equilibrium "
                "checks."
            ),
        ],
    }


def write_external_equilibrium_resultant_json(
    progress_path: Path,
    total_force_path: Path,
    output_path: Path,
    *,
    support_set_names: tuple[str, ...],
    force_absolute_tolerance_n: float = 1.0e-3,
    time_absolute_tolerance: float = 1.0e-9,
) -> dict[str, object]:
    """Write governed global translational-equilibrium evidence."""

    payload = validate_external_equilibrium_resultant(
        _load_json_mapping(
            progress_path
        ),
        _load_json_mapping(
            total_force_path
        ),
        support_set_names=(
            support_set_names
        ),
        force_absolute_tolerance_n=(
            force_absolute_tolerance_n
        ),
        time_absolute_tolerance=(
            time_absolute_tolerance
        ),
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return payload


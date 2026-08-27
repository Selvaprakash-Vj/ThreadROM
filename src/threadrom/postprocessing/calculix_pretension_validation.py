"""Validate CalculiX pretension results against the commanded ramp."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path


def _mapping_items(
    payload: Mapping[str, object],
    key: str,
) -> tuple[Mapping[str, object], ...]:
    """Return a validated list of JSON mappings."""

    value = payload.get(key)

    if not isinstance(value, list):
        raise TypeError(f"Expected '{key}' to be a JSON array.")

    items: list[Mapping[str, object]] = []

    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise TypeError(f"Expected '{key}[{index}]' to be a JSON object.")

        if not all(isinstance(item_key, str) for item_key in item):
            raise ValueError(f"Expected '{key}[{index}]' to contain string keys.")

        items.append(item)

    return tuple(items)


def _integer(
    payload: Mapping[str, object],
    key: str,
) -> int:
    """Return a required integer field."""

    value = payload.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Expected '{key}' to be an integer.")

    return value


def _number(
    payload: Mapping[str, object],
    key: str,
) -> float:
    """Return a required finite numeric field."""

    value = payload.get(key)

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"Expected '{key}' to be numeric.")

    result = float(value)

    if not math.isfinite(result):
        raise ValueError(f"Expected '{key}' to be finite.")

    return result


def _load_json_mapping(
    path: Path,
) -> dict[str, object]:
    """Load a JSON document whose root is an object."""

    payload: object = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise TypeError(f"Expected JSON object in {path}.")

    if not all(isinstance(key, str) for key in payload):
        raise ValueError(f"Expected string JSON keys in {path}.")

    return payload


def validate_pretension_ramp(
    progress_payload: Mapping[str, object],
    pretension_payload: Mapping[str, object],
    *,
    target_preload_n: float,
    force_relative_tolerance: float = 1.0e-6,
    force_absolute_tolerance_n: float = 1.0e-6,
    time_absolute_tolerance: float = 1.0e-9,
) -> dict[str, object]:
    """Validate accepted-increment forces against a linear ramp."""

    if not math.isfinite(target_preload_n):
        raise ValueError("Target preload must be finite.")

    if target_preload_n <= 0.0:
        raise ValueError("Target preload must be positive.")

    if force_relative_tolerance < 0.0:
        raise ValueError("Force relative tolerance cannot be negative.")

    if force_absolute_tolerance_n < 0.0:
        raise ValueError("Force absolute tolerance cannot be negative.")

    if time_absolute_tolerance < 0.0:
        raise ValueError("Time absolute tolerance cannot be negative.")

    accepted_items = _mapping_items(
        progress_payload,
        "accepted_increments",
    )

    pretension_items = _mapping_items(
        pretension_payload,
        "records",
    )

    accepted_step_numbers = {
        _integer(item, "step")
        for item in accepted_items
    }

    use_cumulative_time_ramp = len(accepted_step_numbers) > 1

    final_total_time: float | None = None

    if use_cumulative_time_ramp:
        final_total_time = max(
            _number(item, "total_time")
            for item in accepted_items
        )

        if final_total_time <= 0.0:
            raise ValueError(
                "Final total time must be positive for a multi-step pretension ramp."
            )

    accepted_by_key: dict[
        tuple[int, int],
        Mapping[str, object],
    ] = {}

    for item in accepted_items:
        key = (
            _integer(item, "step"),
            _integer(item, "increment"),
        )

        if key in accepted_by_key:
            raise ValueError(f"Duplicate accepted increment for step {key[0]}, increment {key[1]}.")

        accepted_by_key[key] = item

    pretension_by_key: dict[
        tuple[int, int],
        Mapping[str, object],
    ] = {}

    for item in pretension_items:
        key = (
            _integer(item, "step"),
            _integer(item, "increment"),
        )

        if key in pretension_by_key:
            raise ValueError(f"Duplicate pretension record for step {key[0]}, increment {key[1]}.")

        pretension_by_key[key] = item

    validations: list[dict[str, object]] = []

    passed_count = 0
    failed_count = 0
    pending_count = 0

    for key in sorted(accepted_by_key):
        accepted = accepted_by_key[key]
        pretension = pretension_by_key.get(key)

        step_time = _number(
            accepted,
            "step_time",
        )

        total_time = _number(
            accepted,
            "total_time",
        )

        if use_cumulative_time_ramp:
            assert final_total_time is not None
            expected_preload_n = (
                target_preload_n
                * total_time
                / final_total_time
            )
        else:
            expected_preload_n = target_preload_n * step_time

        if pretension is None:
            pending_count += 1

            validations.append(
                {
                    "step": key[0],
                    "increment": key[1],
                    "status": "pending",
                    "reason": ("Accepted increment has no matching DAT pretension record."),
                    "step_time": step_time,
                    "total_time": total_time,
                    "expected_preload_n": (expected_preload_n),
                    "actual_preload_n": None,
                }
            )

            continue

        actual_preload_n = _number(
            pretension,
            "preload_force_n",
        )

        dat_time = _number(
            pretension,
            "time",
        )

        force_error_n = actual_preload_n - expected_preload_n

        denominator = max(
            abs(expected_preload_n),
            force_absolute_tolerance_n,
            1.0e-30,
        )

        force_relative_error = abs(force_error_n) / denominator

        force_matches = math.isclose(
            actual_preload_n,
            expected_preload_n,
            rel_tol=force_relative_tolerance,
            abs_tol=force_absolute_tolerance_n,
        )

        time_matches = math.isclose(
            dat_time,
            total_time,
            rel_tol=0.0,
            abs_tol=time_absolute_tolerance,
        )

        status = "pass" if force_matches and time_matches else "fail"

        if status == "pass":
            passed_count += 1
        else:
            failed_count += 1

        validations.append(
            {
                "step": key[0],
                "increment": key[1],
                "status": status,
                "step_time": step_time,
                "total_time": total_time,
                "dat_time": dat_time,
                "expected_preload_n": (expected_preload_n),
                "actual_preload_n": (actual_preload_n),
                "force_error_n": force_error_n,
                "force_relative_error": (force_relative_error),
                "force_matches": force_matches,
                "time_matches": time_matches,
                "control_displacement_mm": (pretension.get("control_displacement_mm")),
                "force_displacement_ratio_kn_per_mm": (
                    pretension.get("force_displacement_ratio_kn_per_mm")
                ),
            }
        )

    orphan_keys = sorted(set(pretension_by_key) - set(accepted_by_key))

    orphan_records = [
        {
            "step": step,
            "increment": increment,
            "reason": (
                "DAT pretension record has no matching accepted increment in the progress data."
            ),
        }
        for step, increment in orphan_keys
    ]

    if failed_count > 0:
        overall_status = "fail"
    elif pending_count > 0 or orphan_records or not accepted_items:
        overall_status = "pending"
    else:
        overall_status = "pass"

    return {
        "schema_version": 1,
        "overall_status": overall_status,
        "target_preload_n": target_preload_n,
        "loading_assumption": (
            (
                "Multi-step linear force ramp: expected preload = "
                "target preload x accepted total time / final total time."
            )
            if use_cumulative_time_ramp
            else (
                "Unit linear force ramp: expected preload = "
                "target preload x accepted step time."
            )
        ),
        "tolerances": {
            "force_relative": (force_relative_tolerance),
            "force_absolute_n": (force_absolute_tolerance_n),
            "time_absolute": (time_absolute_tolerance),
        },
        "accepted_increment_count": len(accepted_items),
        "pretension_record_count": len(pretension_items),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "pending_count": pending_count,
        "orphan_record_count": len(orphan_records),
        "validations": validations,
        "orphan_records": orphan_records,
    }


def write_pretension_validation_json(
    progress_path: Path,
    pretension_path: Path,
    output_path: Path,
    *,
    target_preload_n: float,
    force_relative_tolerance: float = 1.0e-6,
    force_absolute_tolerance_n: float = 1.0e-6,
    time_absolute_tolerance: float = 1.0e-9,
) -> dict[str, object]:
    """Validate two result files and write normalized JSON."""

    progress_payload = _load_json_mapping(progress_path)

    pretension_payload = _load_json_mapping(pretension_path)

    payload = validate_pretension_ramp(
        progress_payload,
        pretension_payload,
        target_preload_n=target_preload_n,
        force_relative_tolerance=(force_relative_tolerance),
        force_absolute_tolerance_n=(force_absolute_tolerance_n),
        time_absolute_tolerance=(time_absolute_tolerance),
    )

    serialized_payload = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        serialized_payload,
        encoding="utf-8",
        newline="\n",
    )

    normalized_payload: dict[str, object] = json.loads(serialized_payload)

    return normalized_payload

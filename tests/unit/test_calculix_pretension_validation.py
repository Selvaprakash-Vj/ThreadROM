"""Tests for governed pretension-ramp validation."""

from __future__ import annotations

import json
from pathlib import Path

from threadrom.postprocessing.calculix_pretension_validation import (
    validate_pretension_ramp,
    write_pretension_validation_json,
)


def _progress_payload() -> dict[str, object]:
    return {
        "accepted_increments": [
            {
                "step": 1,
                "increment": 1,
                "step_time": 0.05,
                "total_time": 0.05,
            }
        ]
    }


def _pretension_payload(
    preload_force_n: float = 250.0,
) -> dict[str, object]:
    return {
        "records": [
            {
                "step": 1,
                "increment": 1,
                "time": 0.05,
                "preload_force_n": (preload_force_n),
                "control_displacement_mm": (1.5e-5),
                "force_displacement_ratio_kn_per_mm": (16666.6667),
            }
        ]
    }


def test_exact_ramped_preload_passes() -> None:
    payload = validate_pretension_ramp(
        _progress_payload(),
        _pretension_payload(),
        target_preload_n=5000.0,
    )

    assert payload["overall_status"] == "pass"
    assert payload["passed_count"] == 1
    assert payload["failed_count"] == 0
    assert payload["pending_count"] == 0


def test_force_mismatch_fails() -> None:
    payload = validate_pretension_ramp(
        _progress_payload(),
        _pretension_payload(240.0),
        target_preload_n=5000.0,
    )

    assert payload["overall_status"] == "fail"
    assert payload["passed_count"] == 0
    assert payload["failed_count"] == 1


def test_missing_dat_record_is_pending() -> None:
    payload = validate_pretension_ramp(
        _progress_payload(),
        {"records": []},
        target_preload_n=5000.0,
    )

    assert payload["overall_status"] == "pending"
    assert payload["pending_count"] == 1


def test_orphan_dat_record_is_pending() -> None:
    payload = validate_pretension_ramp(
        {"accepted_increments": []},
        _pretension_payload(),
        target_preload_n=5000.0,
    )

    assert payload["overall_status"] == "pending"
    assert payload["orphan_record_count"] == 1


def test_validation_json_round_trip(
    tmp_path: Path,
) -> None:
    progress_path = tmp_path / "progress.json"
    pretension_path = tmp_path / "pretension.json"
    output_path = tmp_path / "validation.json"

    progress_path.write_text(
        json.dumps(_progress_payload()),
        encoding="utf-8",
    )

    pretension_path.write_text(
        json.dumps(_pretension_payload()),
        encoding="utf-8",
    )

    payload = write_pretension_validation_json(
        progress_path,
        pretension_path,
        output_path,
        target_preload_n=5000.0,
    )

    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert saved == payload
    assert saved["overall_status"] == "pass"


def test_multistep_governed_ramp_uses_cumulative_time() -> None:
    progress = {
        "accepted_increments": [
            {
                "step": 1,
                "increment": 1,
                "step_time": 1.0,
                "total_time": 1.0,
            },
            {
                "step": 2,
                "increment": 1,
                "step_time": 1.0,
                "total_time": 2.0,
            },
            {
                "step": 3,
                "increment": 1,
                "step_time": 1.0,
                "total_time": 3.0,
            },
        ]
    }

    pretension = {
        "records": [
            {
                "step": 1,
                "increment": 1,
                "time": 1.0,
                "preload_force_n": 1000.0,
            },
            {
                "step": 2,
                "increment": 1,
                "time": 2.0,
                "preload_force_n": 2000.0,
            },
            {
                "step": 3,
                "increment": 1,
                "time": 3.0,
                "preload_force_n": 3000.0,
            },
        ]
    }

    payload = validate_pretension_ramp(
        progress,
        pretension,
        target_preload_n=3000.0,
    )

    assert payload["overall_status"] == "pass"
    assert payload["passed_count"] == 3
    assert payload["failed_count"] == 0

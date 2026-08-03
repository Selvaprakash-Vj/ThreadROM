"""Tests for governed analytical thread results."""

import json
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_thread_result import (
    AnalyticalThreadResult,
    evaluate_analytical_thread,
    render_analytical_thread_report,
)


def _benchmark_result() -> AnalyticalThreadResult:
    """Load and evaluate the governed M10 benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    joint = load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")

    return evaluate_analytical_thread(joint)


def test_governed_m10_thread_result() -> None:
    """The canonical joint resolves validated thread mechanics."""

    result = _benchmark_result()
    mechanics = result.mechanics

    assert result.joint_id == "TRM-ANL-000001"
    assert result.bolt_id == "TRM-BLT-000001"
    assert result.nut_id == "TRM-NUT-000001"

    assert mechanics.tensile_stress_area_mm2 == pytest.approx(57.9895969018)

    assert mechanics.external_root_area_mm2 == pytest.approx(52.2923116585)

    assert mechanics.engaged_pitch_count == pytest.approx(8.0 / 1.5)

    assert result.validation.passed
    assert result.validation.failed_check_ids == ()
    assert len(result.validation.checks) == 8


def test_thread_result_json_is_machine_readable() -> None:
    """The result serialises mechanics and validation evidence."""

    result = _benchmark_result()

    payload = json.loads(result.to_json())

    assert payload["joint_id"] == "TRM-ANL-000001"
    assert payload["mechanics"]["starts"] == 1
    assert payload["mechanics"]["pitch_mm"] == pytest.approx(1.5)
    assert payload["mechanics"]["method"] == ("iso_metric_basic_profile_60_deg")

    assert payload["validation"]["passed"] is True
    assert payload["validation"]["method"] == ("deterministic_geometry_invariants_v1")
    assert len(payload["validation"]["checks"]) == 8


def test_thread_report_states_scope_and_validation() -> None:
    """The report includes validation without overclaiming scope."""

    report = render_analytical_thread_report(_benchmark_result())

    assert "# ThreadROM Analytical Thread-Mechanics Report" in report

    assert "| Tensile-stress area | 57.989596902 mm2 |" in report

    assert "- Physics validation: PASS" in report
    assert "- Overall status: PASS" in report
    assert "| diameter_order | PASS |" in report
    assert "| area_order | PASS |" in report

    assert "Tolerance deviations are not yet resolved." in report

    assert "It is not a substitute for a thread-root stress-concentration" in report

    assert "Per-thread load distribution is handled in Checkpoint 7." in report

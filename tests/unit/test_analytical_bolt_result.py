"""Tests for governed analytical bolt-mechanics results."""

import json
from pathlib import Path

import pytest

from threadrom.engineering.analytical_bolt_result import (
    AnalyticalBoltResult,
    evaluate_analytical_bolt,
    render_analytical_bolt_report,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)


def _benchmark_result() -> AnalyticalBoltResult:
    """Load and evaluate the governed M10 benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    joint = load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")

    return evaluate_analytical_bolt(joint)


def test_governed_m10_bolt_result() -> None:
    """The benchmark produces validated axial bolt mechanics."""

    result = _benchmark_result()
    mechanics = result.mechanics

    assert result.joint_id == "TRM-ANL-000001"
    assert result.bolt_id == "TRM-BLT-000001"

    assert mechanics.axial_stiffness_n_per_mm == pytest.approx(405927.1783129)

    assert mechanics.total_elongation_mm == pytest.approx(0.0123174802455)

    assert mechanics.nominal_tensile_stress_mpa == pytest.approx(86.2223617188)

    assert result.validation.passed
    assert result.validation.failed_check_ids == ()
    assert len(result.validation.checks) == 10


def test_bolt_result_json_contains_validation_evidence() -> None:
    """JSON includes stored and derived validation quantities."""

    payload = json.loads(_benchmark_result().to_json())

    assert payload["joint_id"] == "TRM-ANL-000001"
    assert payload["mechanics"]["method"] == "segmented"
    assert len(payload["mechanics"]["segments"]) == 3

    assert payload["validation"]["passed"] is True
    assert payload["validation"]["failed_check_ids"] == []
    assert payload["validation"]["method"] == ("linear_axial_mechanics_invariants_v1")


def test_bolt_report_contains_results_and_scope() -> None:
    """The report states results and avoids local-stress overclaims."""

    report = render_analytical_bolt_report(_benchmark_result())

    assert "# ThreadROM Analytical Bolt-Mechanics Report" in report

    assert "- Physics validation: PASS" in report

    assert "| Axial stiffness | 405927.178312" in report

    assert "| Nominal tensile-area stress | 86.222361719 MPa |" in report

    assert "| compliance_sum | PASS |" in report
    assert "| strain_energy_identity | PASS |" in report

    normalized_report = " ".join(report.split())

    assert "is not a prediction of the local thread-root von Mises stress" in normalized_report

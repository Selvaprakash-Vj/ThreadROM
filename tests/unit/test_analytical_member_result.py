"""Tests for governed analytical member-mechanics results."""

import json
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_member_result import (
    AnalyticalMemberResult,
    evaluate_analytical_member,
    render_analytical_member_report,
)


def _benchmark_result() -> AnalyticalMemberResult:
    """Load and evaluate the governed M10 member benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    joint = load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")

    return evaluate_analytical_member(joint)


def test_governed_m10_member_result() -> None:
    """The benchmark produces validated member mechanics."""

    result = _benchmark_result()
    mechanics = result.mechanics

    assert result.joint_id == "TRM-ANL-000001"

    assert mechanics.method == ("uniform_annular_cylinder")

    assert mechanics.axial_stiffness_n_per_mm == pytest.approx(6424164.2775094)

    assert mechanics.total_shortening_mm == pytest.approx(0.000778311354444)

    assert mechanics.maximum_compressive_stress_mpa == pytest.approx(8.1722692217)

    assert result.validation.passed
    assert result.validation.failed_check_ids == ()
    assert len(result.validation.checks) == 13


def test_member_result_json_contains_validation_evidence() -> None:
    """JSON includes mechanics and derived validation fields."""

    payload = json.loads(_benchmark_result().to_json())

    assert payload["joint_id"] == "TRM-ANL-000001"
    assert payload["mechanics"]["method"] == ("uniform_annular_cylinder")
    assert len(payload["mechanics"]["layers"]) == 2

    assert payload["validation"]["passed"] is True
    assert payload["validation"]["failed_check_ids"] == []
    assert payload["validation"]["method"] == ("linear_member_compression_invariants_v1")


def test_member_report_contains_results_and_scope() -> None:
    """The report states results without local-stress overclaims."""

    report = render_analytical_member_report(_benchmark_result())

    normalized_report = " ".join(report.split())

    assert "# ThreadROM Analytical Member-Mechanics Report" in report

    assert "- Physics validation: PASS" in report

    assert "| Axial stiffness | 6424164.277509" in report

    assert "| Head-side mean bearing pressure | 47.157020175 MPa |" in report

    assert "| compliance_sum | PASS |" in report
    assert "| head_bearing_pressure | PASS |" in report

    assert (
        "Layer stress is an analytical area-average value, "
        "not a local FEM contact or notch stress." in normalized_report
    )

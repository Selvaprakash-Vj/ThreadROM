"""Tests for governed analytical joint-behaviour results."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_joint_result import (
    AnalyticalJointResult,
    evaluate_analytical_joint,
    render_analytical_joint_report,
)


def _benchmark_joint():
    """Load the governed M10 analytical benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def _benchmark_result() -> AnalyticalJointResult:
    """Evaluate the governed M10 benchmark."""

    return evaluate_analytical_joint(_benchmark_joint())


def test_governed_joint_result() -> None:
    """The benchmark produces validated joint behaviour."""

    result = _benchmark_result()

    assert result.joint_id == "TRM-ANL-000001"

    assert len(result.envelope.points) == 3
    assert result.envelope.cyclic_responses == ()

    assert result.envelope.highest_bolt_force_n == pytest.approx(5000.0)

    assert result.strength.highest_nominal_tensile_stress_mpa == pytest.approx(86.2223617188)

    assert result.validation.passed
    assert result.validation.failed_check_ids == ()
    assert len(result.validation.checks) == 14


def test_joint_result_json_contains_validation_evidence() -> None:
    """JSON contains envelope, strength and validation evidence."""

    payload = json.loads(_benchmark_result().to_json())

    assert payload["joint_id"] == "TRM-ANL-000001"

    assert len(payload["envelope"]["points"]) == 3

    assert payload["strength"]["method"] == "linear_axial_section_stress_envelope_v1"

    assert payload["validation"]["passed"] is True

    assert payload["validation"]["failed_check_ids"] == []

    assert payload["validation"]["method"] == "piecewise_two_spring_joint_invariants_v1"


def test_joint_report_contains_results_and_scope() -> None:
    """The report states results without local-stress overclaims."""

    report = render_analytical_joint_report(_benchmark_result())

    normalized_report = " ".join(report.split())

    assert "# ThreadROM Analytical Joint-Behaviour Report" in report

    assert "- Physics validation: PASS" in report

    assert "| Highest bolt force | 5000.000000000 N |" in report

    assert "| external_load_equilibrium | PASS |" in report

    assert "not a local thread-root notch stress" in normalized_report

    assert "fatigue life is not evaluated" in normalized_report


def test_cyclic_and_separated_states_are_reported() -> None:
    """Configured cyclic separation appears in the report."""

    joint = _benchmark_joint()

    modified = replace(
        joint,
        loading=replace(
            joint.loading,
            external_axial_load_n=6000.0,
            cyclic_minimum_axial_load_n=1000.0,
            cyclic_maximum_axial_load_n=6000.0,
            preload_scatter_fraction=0.1,
        ),
    )

    result = evaluate_analytical_joint(modified)

    report = render_analytical_joint_report(result)

    assert result.envelope.any_separation

    assert "| Separation in configured envelope | YES |" in report

    assert "cyclic_minimum" in report
    assert "cyclic_maximum" in report
    assert "separated" in report

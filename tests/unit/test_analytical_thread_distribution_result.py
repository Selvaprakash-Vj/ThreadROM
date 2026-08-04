"""Tests for governed analytical thread-distribution results."""

import json
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_thread_distribution_result import (
    AnalyticalThreadDistributionResult,
    evaluate_analytical_thread_distribution,
    render_analytical_thread_distribution_report,
)


def _benchmark_joint():
    """Load the governed M10 analytical benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def _benchmark_result() -> AnalyticalThreadDistributionResult:
    """Evaluate the governed M10 thread distribution."""

    return evaluate_analytical_thread_distribution(_benchmark_joint())


def test_governed_distribution_result() -> None:
    """The benchmark produces validated per-turn loads."""

    result = _benchmark_result()
    distribution = result.distribution

    assert result.joint_id == "TRM-ANL-000001"

    assert distribution.active_turn_count == 6

    assert distribution.maximum_loaded_turn_number == 1

    assert distribution.first_turn_load_n == pytest.approx(1072.3548670254)

    assert distribution.first_turn_load_share == pytest.approx(0.214470973405)

    assert distribution.load_conservation_error_n == pytest.approx(
        0.0,
        abs=1.0e-8,
    )

    assert result.validation.passed
    assert result.validation.failed_check_ids == ()
    assert len(result.validation.checks) == 14


def test_distribution_result_json_contains_evidence() -> None:
    """JSON contains turns, stiffness and validation evidence."""

    payload = json.loads(_benchmark_result().to_json())

    assert payload["joint_id"] == "TRM-ANL-000001"

    assert payload["distribution"]["method"] == "two_axial_bars_centroid_springs_v1"

    assert len(payload["distribution"]["turn_loads"]) == 6

    assert payload["distribution"]["maximum_loaded_turn_number"] == 1

    assert payload["validation"]["passed"] is True

    assert payload["validation"]["failed_check_ids"] == []

    assert payload["validation"]["method"] == "discrete_thread_spring_invariants_v1"


def test_distribution_report_contains_results_and_scope() -> None:
    """The report includes results and provisional-model limits."""

    report = render_analytical_thread_distribution_report(_benchmark_result())

    normalized_report = " ".join(report.split())

    assert "# ThreadROM Analytical Thread-Load Distribution Report" in report

    assert "- Physics validation: PASS" in report

    assert "| First-turn load share | 21.447097% |" in report

    assert "| load_conservation | PASS |" in report

    assert "pending Checkpoint 8 verification" in normalized_report

    assert "integrated normal contact force" in normalized_report


def test_transferred_load_override_preserves_shares() -> None:
    """A different linear load scales forces but not shares."""

    baseline = _benchmark_result()

    doubled = evaluate_analytical_thread_distribution(
        _benchmark_joint(),
        total_transferred_load_n=10000.0,
    )

    assert doubled.distribution.first_turn_load_share == pytest.approx(
        baseline.distribution.first_turn_load_share
    )

    assert doubled.distribution.first_turn_load_n == pytest.approx(
        2.0 * baseline.distribution.first_turn_load_n
    )

    assert doubled.validation.passed

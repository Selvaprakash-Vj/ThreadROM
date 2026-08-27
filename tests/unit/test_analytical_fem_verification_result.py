"""Tests for analytical-to-FEM verification result artifacts."""

from dataclasses import replace
from pathlib import Path

from threadrom.engineering.analytical_fem_verification import (
    EvidenceStatus,
    load_analytical_fem_verification_definition,
)
from threadrom.engineering.analytical_fem_verification_result import (
    build_analytical_fem_verification_result,
    render_analytical_fem_verification_markdown,
    write_analytical_fem_verification_artifacts,
)


def _definition():
    """Load the governed verification definition."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_fem_verification_definition(
        project_root / "config" / "analytical_fem_verification.toml"
    )


def test_governed_result_is_inconclusive() -> None:
    """The governed solver outcome remains explicitly inconclusive."""

    result = build_analytical_fem_verification_result(
        _definition()
    )

    assert result.overall_status == "inconclusive"
    assert result.resolved_target_count == 0
    assert result.unresolved_target_count == 8

    assert result.status_counts == {
        "pass": 0,
        "fail": 0,
        "inconclusive_solver": 6,
        "pending_solver": 0,
        "pending_extractor": 0,
        "dedicated_simulation_required": 2,
    }


def test_inconclusive_solver_controls_overall_status() -> None:
    """One inconclusive target controls the overall classification."""

    definition = _definition()

    inconclusive_target = replace(
        definition.targets[0],
        evidence_status=EvidenceStatus.INCONCLUSIVE_SOLVER,
        evidence_artifact=Path(
            "evidence/inconclusive_solver.json"
        ),
    )

    pending_targets = tuple(
        replace(
            target,
            evidence_status=EvidenceStatus.PENDING_SOLVER,
            evidence_artifact=None,
        )
        for target in definition.targets[1:]
    )

    result = build_analytical_fem_verification_result(
        replace(
            definition,
            targets=(
                inconclusive_target,
                *pending_targets,
            ),
        )
    )

    assert result.overall_status == "inconclusive"
    assert result.resolved_target_count == 0
    assert result.unresolved_target_count == 8
    assert result.status_counts["inconclusive_solver"] == 1
    assert result.status_counts["pending_solver"] == 7


def test_payload_preserves_target_contracts() -> None:
    """The serialized result preserves all target definitions."""

    result = build_analytical_fem_verification_result(
        _definition()
    )

    payload = result.to_payload()

    assert payload["schema_version"] == 1
    assert payload["verification_id"] == "TRM-VER-000001"
    assert payload["simulation_id"] == "TRM-SIM-000010"
    assert payload["overall_status"] == "inconclusive"
    assert payload["target_count"] == 8

    targets = payload["targets"]

    assert isinstance(targets, list)
    assert targets[0]["target_id"] == "pretension_ramp"
    assert (
        targets[-1]["target_id"]
        == "first_thread_load_share"
    )


def test_markdown_states_inconclusive_without_false_failure() -> None:
    """The report distinguishes inconclusiveness from failure."""

    result = build_analytical_fem_verification_result(
        _definition()
    )

    markdown = render_analytical_fem_verification_markdown(
        result
    )

    assert "Overall status | INCONCLUSIVE" in markdown
    assert "A `pending` result is not a failed" in markdown
    assert "An `inconclusive_solver` result means" in markdown
    assert "`first_thread_load_share`" in markdown
    assert "PASS or FAIL classifications require" in markdown
    assert "???" not in markdown


def test_artifacts_are_written(
    tmp_path: Path,
) -> None:
    """JSON and Markdown artifacts are written deterministically."""

    definition = replace(
        _definition(),
        json_relative_path=Path("verification.json"),
        report_relative_path=Path("verification.md"),
    )

    result = build_analytical_fem_verification_result(
        definition
    )

    json_path, report_path = (
        write_analytical_fem_verification_artifacts(
            tmp_path,
            result,
        )
    )

    assert json_path.exists()
    assert report_path.exists()

    json_text = json_path.read_text(encoding="utf-8")
    report_text = report_path.read_text(encoding="utf-8")

    assert '"overall_status": "inconclusive"' in json_text
    assert '"simulation_id": "TRM-SIM-000010"' in json_text
    assert "# TRM-VER-000001" in report_text
    assert "Overall status | INCONCLUSIVE" in report_text


def test_numerical_relative_comparison_passes_within_tolerance() -> None:
    """A FEM value within the governed relative tolerance passes."""

    from threadrom.engineering.analytical_fem_verification import (
        AcceptanceMetric,
    )
    from threadrom.engineering.analytical_fem_verification_result import (
        evaluate_numerical_comparison,
    )

    evaluation = evaluate_numerical_comparison(
        analytical_value=100.0,
        fem_value=105.0,
        acceptance_metric=AcceptanceMetric.RELATIVE,
        relative_tolerance=0.10,
        absolute_tolerance=None,
    )

    assert evaluation.analytical_value == 100.0
    assert evaluation.fem_value == 105.0
    assert abs(evaluation.absolute_error - 5.0) < 1.0e-12
    assert abs(evaluation.relative_error - 0.05) < 1.0e-12
    assert evaluation.passed is True


def test_numerical_absolute_comparison_passes_within_tolerance() -> None:
    """A FEM value within the governed absolute tolerance passes."""

    from threadrom.engineering.analytical_fem_verification import (
        AcceptanceMetric,
    )
    from threadrom.engineering.analytical_fem_verification_result import (
        evaluate_numerical_comparison,
    )

    evaluation = evaluate_numerical_comparison(
        analytical_value=0.0,
        fem_value=5.0e-4,
        acceptance_metric=AcceptanceMetric.ABSOLUTE,
        relative_tolerance=None,
        absolute_tolerance=1.0e-3,
    )

    assert evaluation.analytical_value == 0.0
    assert evaluation.fem_value == 5.0e-4
    assert abs(evaluation.absolute_error - 5.0e-4) < 1.0e-12
    assert evaluation.relative_error == float("inf")
    assert evaluation.passed is True


def test_numerical_relative_or_absolute_passes_if_either_limit_passes() -> None:
    """Relative-or-absolute acceptance passes when either criterion passes."""

    from threadrom.engineering.analytical_fem_verification import (
        AcceptanceMetric,
    )
    from threadrom.engineering.analytical_fem_verification_result import (
        evaluate_numerical_comparison,
    )

    evaluation = evaluate_numerical_comparison(
        analytical_value=1000.0,
        fem_value=1000.5,
        acceptance_metric=AcceptanceMetric.RELATIVE_OR_ABSOLUTE,
        relative_tolerance=1.0e-6,
        absolute_tolerance=1.0,
    )

    assert abs(evaluation.absolute_error - 0.5) < 1.0e-12
    assert abs(evaluation.relative_error - 5.0e-4) < 1.0e-12
    assert evaluation.passed is True


def test_numerical_relative_comparison_fails_outside_tolerance() -> None:
    """A FEM value outside the governed relative tolerance fails."""

    from threadrom.engineering.analytical_fem_verification import (
        AcceptanceMetric,
    )
    from threadrom.engineering.analytical_fem_verification_result import (
        evaluate_numerical_comparison,
    )

    evaluation = evaluate_numerical_comparison(
        analytical_value=100.0,
        fem_value=125.0,
        acceptance_metric=AcceptanceMetric.RELATIVE,
        relative_tolerance=0.10,
        absolute_tolerance=None,
    )

    assert evaluation.absolute_error == 25.0
    assert evaluation.relative_error == 0.25
    assert evaluation.passed is False


def test_target_evaluation_combines_contract_with_fem_value() -> None:
    """A governed target can be evaluated from an actual FEM value."""

    from threadrom.engineering.analytical_fem_verification_result import (
        evaluate_verification_target,
    )

    definition = _definition()
    target = definition.target_by_id("bolt_stiffness")

    evaluation = evaluate_verification_target(
        target=target,
        fem_value=400000.0,
        evidence_artifact=Path("evidence/bolt_stiffness.json"),
    )

    assert evaluation.target_id == "bolt_stiffness"
    assert evaluation.analytical_value == target.analytical_value
    assert evaluation.fem_value == 400000.0
    assert evaluation.absolute_error is not None
    assert evaluation.relative_error is not None
    assert evaluation.passed is True
    assert evaluation.evidence_status is EvidenceStatus.PASS
    assert evaluation.evidence_artifact == Path(
        "evidence/bolt_stiffness.json"
    )

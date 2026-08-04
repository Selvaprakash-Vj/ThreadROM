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

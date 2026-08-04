"""Tests for the governed analytical-to-FEM verification matrix."""

from pathlib import Path

import pytest

from threadrom.engineering.analytical_fem_verification import (
    AcceptanceMetric,
    EvidenceStatus,
    VerificationTargetDefinition,
    load_analytical_fem_verification_definition,
)


def _governed_definition():
    """Load the governed Phase 1 verification matrix."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_fem_verification_definition(
        project_root / "config" / "analytical_fem_verification.toml"
    )


def test_governed_verification_matrix_identity() -> None:
    """The governed matrix resolves its controlled identity."""

    definition = _governed_definition()

    assert definition.verification_id == "TRM-VER-000001"
    assert definition.analytical_joint_id == "TRM-ANL-000001"
    assert definition.simulation_id == "TRM-SIM-000010"
    assert definition.mesh_level == "coarse"
    assert definition.element_type == "C3D10"

    assert len(definition.targets) == 8


def test_governed_evidence_status_counts() -> None:
    """Current evidence limitations are represented explicitly."""

    counts = _governed_definition().status_counts

    assert counts[EvidenceStatus.PASS] == 0
    assert counts[EvidenceStatus.FAIL] == 0
    assert counts[EvidenceStatus.INCONCLUSIVE_SOLVER] == 6
    assert counts[EvidenceStatus.PENDING_SOLVER] == 0
    assert counts[EvidenceStatus.PENDING_EXTRACTOR] == 0
    assert counts[EvidenceStatus.DEDICATED_SIMULATION_REQUIRED] == 2


def test_governed_analytical_targets() -> None:
    """Core analytical predictions are preserved exactly."""

    definition = _governed_definition()

    bolt_stiffness = definition.target_by_id("bolt_stiffness")
    member_stiffness = definition.target_by_id("member_stiffness")
    thread_share = definition.target_by_id(
        "first_thread_load_share"
    )

    assert bolt_stiffness.analytical_value == pytest.approx(
        405927.1783129164
    )

    assert member_stiffness.analytical_value == pytest.approx(
        6424164.277509429
    )

    assert thread_share.analytical_value == pytest.approx(
        21.447097340508284
    )

    assert (
        thread_share.evidence_status
        is EvidenceStatus.DEDICATED_SIMULATION_REQUIRED
    )


def test_pass_target_requires_evidence_artifact() -> None:
    """A pass or fail status cannot exist without evidence."""

    with pytest.raises(
        ValueError,
        match="requires an evidence artifact",
    ):
        VerificationTargetDefinition(
            target_id="invalid",
            quantity="Invalid quantity",
            analytical_value=1.0,
            unit="N",
            fem_observable="Observable",
            extraction_source="Source",
            evidence_status=EvidenceStatus.PASS,
            acceptance_metric=AcceptanceMetric.ABSOLUTE,
            relative_tolerance=None,
            absolute_tolerance=0.1,
            evidence_artifact=None,
            notes="Invalid target used by the test.",
        )


def test_inconclusive_solver_target_requires_evidence_artifact() -> None:
    """An inconclusive solver result requires preserved evidence."""

    with pytest.raises(
        ValueError,
        match="requires an evidence artifact",
    ):
        VerificationTargetDefinition(
            target_id="inconclusive",
            quantity="Inconclusive solver quantity",
            analytical_value=1.0,
            unit="N",
            fem_observable="Observable",
            extraction_source="Source",
            evidence_status=EvidenceStatus.INCONCLUSIVE_SOLVER,
            acceptance_metric=AcceptanceMetric.ABSOLUTE,
            relative_tolerance=None,
            absolute_tolerance=0.1,
            evidence_artifact=None,
            notes="Invalid target used by the test.",
        )


def test_relative_metric_requires_relative_tolerance() -> None:
    """Relative acceptance cannot silently omit its limit."""

    with pytest.raises(
        ValueError,
        match="requires a relative tolerance",
    ):
        VerificationTargetDefinition(
            target_id="invalid",
            quantity="Invalid quantity",
            analytical_value=1.0,
            unit="N",
            fem_observable="Observable",
            extraction_source="Source",
            evidence_status=EvidenceStatus.PENDING_EXTRACTOR,
            acceptance_metric=AcceptanceMetric.RELATIVE,
            relative_tolerance=None,
            absolute_tolerance=None,
            evidence_artifact=None,
            notes="Invalid target used by the test.",
        )


def test_unknown_target_id_is_rejected() -> None:
    """Target lookup fails clearly for unknown identifiers."""

    with pytest.raises(
        KeyError,
        match="Unknown verification target",
    ):
        _governed_definition().target_by_id("not_a_target")

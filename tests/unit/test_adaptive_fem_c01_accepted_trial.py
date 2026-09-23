from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import threadrom.factory.adaptive_fem_c01_live_port as live_port
import threadrom.factory.production_doe_c01_physics as physics

from threadrom.factory.adaptive_fem_c01_live_port import (
    C01LiveFactoryPort,
)
from threadrom.factory.adaptive_fem_lifecycle import (
    FEMLifecycleSnapshot,
    PhysicsDisposition,
    RunPhase,
)
from threadrom.factory.adaptive_fem_supervisor import (
    SupervisorStop,
    drive_fem_supervisor,
)


def make_trial2_port(monkeypatch):
    """Synthetic accepted Trial-2 state; no actual C01 files."""

    snapshot = FEMLifecycleSnapshot(
        run_id="synthetic_cal_02",
        trial_index=2,
        maximum_trials=6,
        phase=RunPhase.COMPLETED,
        completed_evidence_verified=True,
        physics=PhysicsDisposition.NOT_ASSESSED,
    )

    state = {"snapshot": snapshot}

    port = object.__new__(C01LiveFactoryPort)
    port.root = Path.cwd()
    port.case_id = "D-INT-012"
    port.case = SimpleNamespace(
        case_run_id="synthetic_case_run",
    )

    monkeypatch.setattr(
        port,
        "snapshot",
        lambda: state["snapshot"],
    )

    return port, state, snapshot


def test_accepted_trial2_reaches_supervisor_certification_boundary(
    monkeypatch,
):
    port, state, initial = make_trial2_port(monkeypatch)

    assessor_calls = []
    persisted = []

    def synthetic_assessor(*, repo_root, case_id):
        assessor_calls.append(case_id)

        assert repo_root == port.root
        assert case_id == "D-INT-012"

        return {
            "run_id": initial.run_id,
            "physics_gates":
                "PASS_PENDING_INDEPENDENT_CERTIFICATION",
        }

    def synthetic_persistence(**kwargs):
        persisted.append(kwargs)

        assert kwargs["case_id"] == "D-INT-012"
        assert kwargs["case_run_id"] == "synthetic_case_run"
        assert kwargs["run_id"] == initial.run_id
        assert kwargs["trial_index"] == 2

        state["snapshot"] = replace(
            initial,
            physics=PhysicsDisposition.ACCEPTED,
        )

    monkeypatch.setattr(
        physics,
        "assess_c01_saved_trial",
        synthetic_assessor,
    )

    monkeypatch.setattr(
        live_port,
        "persist_preliminary_c01_assessment",
        synthetic_persistence,
    )

    first = drive_fem_supervisor(port)

    assert first.stop is SupervisorStop.WAIT_PHYSICS_CERTIFICATE

    assert assessor_calls == ["D-INT-012"]
    assert len(persisted) == 1

    assert persisted[0]["trial_index"] == 2
    assert persisted[0]["run_id"] == initial.run_id

    assert state["snapshot"].physics is PhysicsDisposition.ACCEPTED
    assert not state["snapshot"].full_physics_acceptance_verified

    # Simulate a separately issued and verified certificate.
    # The supervisor must not issue one itself.

    state["snapshot"] = replace(
        state["snapshot"],
        full_physics_acceptance_verified=True,
    )

    second = drive_fem_supervisor(port)

    assert second.stop is SupervisorStop.COMPLETE
    assert second.last_run_id == initial.run_id

    # Recovery must not assess the accepted run again.

    assert assessor_calls == ["D-INT-012"]
    assert len(persisted) == 1


def test_trial2_mismatched_run_id_refuses_persistence(
    monkeypatch,
):
    port, state, initial = make_trial2_port(monkeypatch)

    persisted = []

    monkeypatch.setattr(
        physics,
        "assess_c01_saved_trial",
        lambda **kwargs: {
            "run_id": "synthetic_wrong_run",
        },
    )

    monkeypatch.setattr(
        live_port,
        "persist_preliminary_c01_assessment",
        lambda **kwargs: persisted.append(kwargs),
    )

    with pytest.raises(
        RuntimeError,
        match="Physics evidence changed",
    ):
        port.assess_verified_physics(initial)

    assert persisted == []
    assert state["snapshot"] == initial


def test_trial2_changed_predecessor_refuses_persistence(
    monkeypatch,
):
    port, state, initial = make_trial2_port(monkeypatch)

    persisted = []

    def assessor_with_changed_predecessor(**kwargs):
        state["snapshot"] = replace(
            initial,
            run_id="synthetic_cal_03",
            trial_index=3,
        )

        return {
            "run_id": initial.run_id,
        }

    monkeypatch.setattr(
        physics,
        "assess_c01_saved_trial",
        assessor_with_changed_predecessor,
    )

    monkeypatch.setattr(
        live_port,
        "persist_preliminary_c01_assessment",
        lambda **kwargs: persisted.append(kwargs),
    )

    with pytest.raises(
        RuntimeError,
        match="Physics predecessor changed",
    ):
        port.assess_verified_physics(initial)

    assert persisted == []


def test_trial2_unassessed_snapshot_must_match(
    monkeypatch,
):
    port, state, initial = make_trial2_port(monkeypatch)

    persisted = []

    monkeypatch.setattr(
        live_port,
        "persist_preliminary_c01_assessment",
        lambda **kwargs: persisted.append(kwargs),
    )

    stale = replace(
        initial,
        run_id="synthetic_old_run",
    )

    with pytest.raises(
        RuntimeError,
        match="Physics snapshot changed",
    ):
        port.assess_verified_physics(stale)

    assert persisted == []
    assert state["snapshot"] == initial

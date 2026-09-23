
from types import SimpleNamespace

import pytest

import threadrom.factory.governed_fem_campaign as campaign

from threadrom.factory.adaptive_fem_lifecycle import (
    FEMLifecycleSnapshot,
    PhysicsDisposition,
    RunPhase,
)
from threadrom.factory.adaptive_fem_supervisor import (
    SupervisorStop,
)


def certified_port(case_id):
    snapshot = FEMLifecycleSnapshot(
        run_id=f"{case_id}_cal_02",
        trial_index=2,
        maximum_trials=6,
        phase=RunPhase.COMPLETED,
        completed_evidence_verified=True,
        physics=PhysicsDisposition.ACCEPTED,
        full_physics_acceptance_verified=True,
    )

    return SimpleNamespace(
        case_id=case_id,
        snapshot=lambda: snapshot,
    )


def test_read_only_dispatch_is_case_independent(monkeypatch):
    def forbidden_supervisor(*args, **kwargs):
        raise AssertionError(
            "Read-only campaign invoked the supervisor."
        )

    monkeypatch.setattr(
        campaign,
        "drive_fem_supervisor",
        forbidden_supervisor,
    )

    registry = {
        "SIZE-A": lambda: certified_port("SIZE-A"),
        "SIZE-B": lambda: certified_port("SIZE-B"),
    }

    result = campaign.run_governed_campaign_cycle(
        case_ids=("SIZE-A", "SIZE-B"),
        registrations=registry,
    )

    assert result.all_done
    assert not result.blocked
    assert len(result.cases) == 2

    assert all(
        item.actions_performed == 0
        for item in result.cases
    )


def test_execution_uses_existing_supervisor(monkeypatch):
    calls = []

    def synthetic_supervisor(port, *, max_actions):
        calls.append((port.case_id, max_actions))

        return SimpleNamespace(
            stop=SupervisorStop.COMPLETE,
            last_run_id=port.snapshot().run_id,
            actions_performed=0,
        )

    monkeypatch.setattr(
        campaign,
        "drive_fem_supervisor",
        synthetic_supervisor,
    )

    result = campaign.run_governed_campaign_cycle(
        case_ids=("SIZE-A", "SIZE-B"),
        registrations={
            name: (lambda case_id=name: certified_port(case_id))
            for name in ("SIZE-A", "SIZE-B")
        },
        execute=True,
        max_actions_per_case=5,
    )

    assert calls == [
        ("SIZE-A", 5),
        ("SIZE-B", 5),
    ]

    assert result.all_done
    assert not result.blocked


def test_unregistered_case_fails_closed():
    with pytest.raises(
        ValueError,
        match="Unregistered governed cases",
    ):
        campaign.run_governed_campaign_cycle(
            case_ids=("UNSUPPORTED",),
            registrations={
                "SUPPORTED": lambda: certified_port("SUPPORTED")
            },
            execute=True,
        )


def test_duplicate_case_selection_fails_closed():
    with pytest.raises(
        ValueError,
        match="Duplicate governed case",
    ):
        campaign.run_governed_campaign_cycle(
            case_ids=("SIZE-A", "SIZE-A"),
            registrations={
                "SIZE-A": lambda: certified_port("SIZE-A")
            },
        )


def test_wrong_registered_case_identity_fails_closed():
    with pytest.raises(
        RuntimeError,
        match="different case",
    ):
        campaign.run_governed_campaign_cycle(
            case_ids=("SIZE-A",),
            registrations={
                "SIZE-A": lambda: certified_port("SIZE-B")
            },
        )


def test_empty_campaign_and_invalid_budget_rejected():
    with pytest.raises(ValueError, match="No governed cases"):
        campaign.run_governed_campaign_cycle(
            case_ids=(),
            registrations={},
        )

    with pytest.raises(ValueError, match="Action budget"):
        campaign.run_governed_campaign_cycle(
            case_ids=("SIZE-A",),
            registrations={
                "SIZE-A": lambda: certified_port("SIZE-A")
            },
            max_actions_per_case=0,
        )

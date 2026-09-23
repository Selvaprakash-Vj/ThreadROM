"""Synthetic integration tests for the migrated C01 campaign driver."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

import threadrom.factory.governed_fem_campaign as shared_campaign

from threadrom.factory.adaptive_fem_lifecycle import (
    FEMLifecycleSnapshot,
    PhysicsDisposition,
    RunPhase,
)
from threadrom.factory.adaptive_fem_supervisor import SupervisorStop


ROOT = Path(__file__).resolve().parents[2]

DRIVER_PATH = (
    ROOT
    / "scripts/run_phase3_production_doe_adaptive_campaign.py"
)


def load_driver():
    spec = importlib.util.spec_from_file_location(
        "threadrom_cp1_campaign_driver_test",
        DRIVER_PATH,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def make_synthetic_port(case_id):
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


def test_migrated_driver_uses_shared_orchestration(
    monkeypatch,
):
    driver = load_driver()

    case_ids = ("SYNTHETIC-A", "SYNTHETIC-B")
    ports = {
        case_id: make_synthetic_port(case_id)
        for case_id in case_ids
    }

    supervisor_calls = []
    retirement_calls = []

    monkeypatch.setattr(
        driver,
        "GATE0_CASE_IDS",
        case_ids,
    )

    monkeypatch.setattr(
        driver,
        "C01LiveFactoryPort",
        lambda *, repo_root, case_id: ports[case_id],
    )

    def synthetic_supervisor(port, *, max_actions):
        assert port is ports[port.case_id]

        supervisor_calls.append(
            (port.case_id, max_actions)
        )

        return SimpleNamespace(
            stop=SupervisorStop.COMPLETE,
            last_run_id=port.snapshot().run_id,
            actions_performed=0,
        )

    monkeypatch.setattr(
        shared_campaign,
        "drive_fem_supervisor",
        synthetic_supervisor,
    )

    # Any remaining direct supervisor call in the campaign
    # driver is forbidden. Execution must use the shared layer.

    def forbidden_direct_supervisor(*args, **kwargs):
        raise AssertionError(
            "Campaign driver bypassed shared orchestration."
        )

    monkeypatch.setattr(
        driver,
        "drive_fem_supervisor",
        forbidden_direct_supervisor,
    )

    def synthetic_retirement(**kwargs):
        retirement_calls.append(kwargs)

        assert kwargs["expected_permit_sha256"] is None
        assert kwargs["port"] in ports.values()

        return SimpleNamespace(status="HOLD_NO_PERMIT")

    monkeypatch.setattr(
        driver,
        "retire_c01_certified_rout",
        synthetic_retirement,
    )

    all_done, blocked = driver.run_cycle(
        execute=True,
        max_actions=5,
    )

    assert all_done is True
    assert blocked is False

    assert supervisor_calls == [
        ("SYNTHETIC-A", 5),
        ("SYNTHETIC-B", 5),
    ]

    assert len(retirement_calls) == 2

    assert all(
        item["expected_permit_sha256"] is None
        for item in retirement_calls
    )


def test_migrated_driver_waits_without_retirement(
    monkeypatch,
):
    driver = load_driver()

    case_id = "SYNTHETIC-PENDING"
    port = make_synthetic_port(case_id)

    monkeypatch.setattr(
        driver,
        "GATE0_CASE_IDS",
        (case_id,),
    )

    monkeypatch.setattr(
        driver,
        "C01LiveFactoryPort",
        lambda **kwargs: port,
    )

    def synthetic_supervisor(port, *, max_actions):
        return SimpleNamespace(
            stop=SupervisorStop.WAIT_PHYSICS_CERTIFICATE,
            last_run_id=port.snapshot().run_id,
            actions_performed=1,
        )

    monkeypatch.setattr(
        shared_campaign,
        "drive_fem_supervisor",
        synthetic_supervisor,
    )

    def forbidden_retirement(**kwargs):
        raise AssertionError(
            "Retirement invoked before certification."
        )

    monkeypatch.setattr(
        driver,
        "retire_c01_certified_rout",
        forbidden_retirement,
    )

    all_done, blocked = driver.run_cycle(
        execute=True,
        max_actions=5,
    )

    assert all_done is False
    assert blocked is False


def test_read_only_driver_never_invokes_supervisor(
    monkeypatch,
):
    driver = load_driver()

    case_id = "SYNTHETIC-READONLY"
    port = make_synthetic_port(case_id)

    monkeypatch.setattr(
        driver,
        "GATE0_CASE_IDS",
        (case_id,),
    )

    monkeypatch.setattr(
        driver,
        "C01LiveFactoryPort",
        lambda **kwargs: port,
    )

    def forbidden_action(*args, **kwargs):
        raise AssertionError(
            "Read-only campaign attempted an execution action."
        )

    monkeypatch.setattr(
        shared_campaign,
        "drive_fem_supervisor",
        forbidden_action,
    )

    monkeypatch.setattr(
        driver,
        "run_governed_campaign_cycle",
        forbidden_action,
    )

    monkeypatch.setattr(
        driver,
        "retire_c01_certified_rout",
        forbidden_action,
    )

    all_done, blocked = driver.run_cycle(
        execute=False,
        max_actions=5,
    )

    assert all_done is True
    assert blocked is False

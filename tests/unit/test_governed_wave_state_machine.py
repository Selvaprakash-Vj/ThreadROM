from __future__ import annotations

import inspect

import pytest

import threadrom.factory.governed_wave_state_machine as module

from threadrom.factory.governed_wave_state_machine import (
    GovernedCaseCampaignSnapshot,
    GovernedWaveAction,
    GovernedWaveCampaignSnapshot,
    GovernedWavePhase,
    GovernedWaveStop,
    decide_governed_wave_campaign,
    drive_governed_wave_campaign,
)


def case(
    number: int,
    *,
    accepted: bool = False,
    running: bool = False,
    blocked: bool = False,
):
    return GovernedCaseCampaignSnapshot(
        case_id=f"CASE-{number:02d}",
        full_physics_accepted=accepted,
        solver_running=running,
        terminal_blocked=blocked,
    )


def wave(
    *cases,
    authority=True,
    closure=False,
):
    return GovernedWaveCampaignSnapshot(
        wave_id="CAMPAIGN-WAVE",
        authority_verified=authority,
        authorized_case_count=len(cases),
        cases=tuple(cases),
        closure_verified=closure,
    )


def test_unverified_authority_fails_closed():
    decision = decide_governed_wave_campaign(
        wave(
            case(1),
            case(2),
            authority=False,
        )
    )

    assert (
        decision.phase
        is GovernedWavePhase.BLOCKED_AUTHORITY
    )
    assert decision.action is GovernedWaveAction.NONE


def test_incomplete_authorized_wave_requests_generic_runner():
    decision = decide_governed_wave_campaign(
        wave(
            case(1),
            case(2, accepted=True),
        )
    )

    assert (
        decision.phase
        is GovernedWavePhase.WORK_REQUIRED
    )
    assert (
        decision.action
        is GovernedWaveAction.EXECUTE_GENERIC_RUNNER
    )


def test_running_solver_blocks_replacement_execution():
    decision = decide_governed_wave_campaign(
        wave(
            case(1, running=True),
            case(2),
        )
    )

    assert (
        decision.phase
        is GovernedWavePhase.WAITING_RUNNING
    )
    assert (
        decision.action
        is GovernedWaveAction.WAIT_FOR_RUNNING_SOLVER
    )


def test_terminal_case_requires_engineering_review():
    decision = decide_governed_wave_campaign(
        wave(
            case(1, blocked=True),
            case(2),
        )
    )

    assert (
        decision.phase
        is GovernedWavePhase.ENGINEERING_REVIEW
    )


def test_terminal_review_has_priority_over_other_incomplete_work():
    decision = decide_governed_wave_campaign(
        wave(
            case(1, blocked=True),
            case(2),
            case(3, accepted=True),
        )
    )

    assert (
        decision.action
        is GovernedWaveAction.REQUIRE_ENGINEERING_REVIEW
    )


def test_all_accepted_stops_at_slice5_closure_boundary():
    decision = decide_governed_wave_campaign(
        wave(
            case(1, accepted=True),
            case(2, accepted=True),
        )
    )

    assert (
        decision.phase
        is GovernedWavePhase.READY_FOR_CLOSURE
    )
    assert (
        decision.action
        is GovernedWaveAction.REQUEST_WAVE_CLOSURE
    )


def test_verified_closure_is_terminal_closed_state():
    decision = decide_governed_wave_campaign(
        wave(
            case(1, accepted=True),
            case(2, accepted=True),
            closure=True,
        )
    )

    assert decision.phase is GovernedWavePhase.CLOSED
    assert decision.action is GovernedWaveAction.NONE


def test_case_count_drift_rejected():
    with pytest.raises(
        ValueError,
        match="case-count drift",
    ):
        GovernedWaveCampaignSnapshot(
            wave_id="WAVE",
            authority_verified=True,
            authorized_case_count=2,
            cases=(
                case(1),
            ),
        )


def test_duplicate_case_identity_rejected():
    duplicate = case(1)

    with pytest.raises(
        ValueError,
        match="Duplicate governed case",
    ):
        wave(
            duplicate,
            duplicate,
        )


@pytest.mark.parametrize(
    "kwargs",
    (
        {
            "accepted": True,
            "running": True,
        },
        {
            "accepted": True,
            "blocked": True,
        },
        {
            "running": True,
            "blocked": True,
        },
    ),
)
def test_contradictory_case_state_rejected(
    kwargs,
):
    with pytest.raises(
        ValueError,
    ):
        case(
            1,
            **kwargs,
        )


def test_closure_before_all_case_acceptance_rejected():
    with pytest.raises(
        ValueError,
        match="closure cannot be verified",
    ):
        wave(
            case(1, accepted=True),
            case(2),
            closure=True,
        )


def test_driver_executes_once_then_reaches_closure_boundary():
    states = [
        wave(
            case(1),
            case(2, accepted=True),
        ),
        wave(
            case(1, accepted=True),
            case(2, accepted=True),
        ),
    ]

    index = 0
    executions = 0

    def snapshot_supplier():
        return states[index]

    def execute():
        nonlocal index
        nonlocal executions

        executions += 1
        index = 1

    result = drive_governed_wave_campaign(
        snapshot_supplier=snapshot_supplier,
        execute_generic_runner_once=execute,
        max_runner_actions=1,
    )

    assert executions == 1
    assert result.actions_performed == 1
    assert (
        result.stop
        is GovernedWaveStop.READY_FOR_CLOSURE
    )


def test_driver_never_executes_when_solver_is_running():
    called = False

    def execute():
        nonlocal called
        called = True

    result = drive_governed_wave_campaign(
        snapshot_supplier=lambda: wave(
            case(1, running=True),
            case(2),
        ),
        execute_generic_runner_once=execute,
    )

    assert called is False
    assert result.stop is GovernedWaveStop.WAIT_RUNNING


def test_driver_never_executes_without_authority():
    called = False

    def execute():
        nonlocal called
        called = True

    result = drive_governed_wave_campaign(
        snapshot_supplier=lambda: wave(
            case(1),
            authority=False,
        ),
        execute_generic_runner_once=execute,
    )

    assert called is False
    assert (
        result.stop
        is GovernedWaveStop.BLOCKED_AUTHORITY
    )


def test_driver_refuses_no_progress_execution():
    snapshot = wave(
        case(1),
    )

    with pytest.raises(
        RuntimeError,
        match="without a durable wave-state transition",
    ):
        drive_governed_wave_campaign(
            snapshot_supplier=lambda: snapshot,
            execute_generic_runner_once=lambda: None,
        )


def test_driver_respects_runner_action_budget():
    states = [
        wave(
            case(1),
            case(2),
        ),
        wave(
            case(1, accepted=True),
            case(2),
        ),
    ]

    index = 0

    def snapshot_supplier():
        return states[index]

    def execute():
        nonlocal index
        index = 1

    result = drive_governed_wave_campaign(
        snapshot_supplier=snapshot_supplier,
        execute_generic_runner_once=execute,
        max_runner_actions=1,
    )

    assert (
        result.stop
        is GovernedWaveStop.ACTION_BUDGET
    )
    assert result.actions_performed == 1


def test_production_module_contains_no_historical_wave_binding():
    source = inspect.getsource(
        module
    )

    for token in (
        "W01",
        "w01",
        "W02",
        "w02",
        "W03",
        "w03",
    ):
        assert token not in source
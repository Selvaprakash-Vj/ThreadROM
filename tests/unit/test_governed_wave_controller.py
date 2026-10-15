from __future__ import annotations

import pytest

from threadrom.factory.governed_wave_controller import (
    drive_runner_backed_governed_wave,
    execute_generic_runner_once,
)
from threadrom.factory.governed_wave_state_machine import (
    GovernedCaseCampaignSnapshot,
    GovernedWaveCampaignSnapshot,
    GovernedWaveStop,
)


class FakeRunner:
    def __init__(
        self,
        result=0,
    ):
        self.result = result
        self.calls = 0

    def execute(self):
        self.calls += 1
        return self.result


def snapshot(
    *,
    accepted=False,
    closure=False,
):
    return GovernedWaveCampaignSnapshot(
        wave_id="TEST-WAVE",
        authority_verified=True,
        authorized_case_count=1,
        cases=(
            GovernedCaseCampaignSnapshot(
                case_id="CASE-01",
                full_physics_accepted=accepted,
            ),
        ),
        closure_verified=closure,
    )


def test_generic_runner_executor_accepts_zero():
    runner = FakeRunner(
        result=0
    )

    execute_generic_runner_once(
        runner
    )

    assert runner.calls == 1


def test_generic_runner_executor_rejects_nonzero():
    runner = FakeRunner(
        result=7
    )

    with pytest.raises(
        RuntimeError,
        match="non-zero status 7",
    ):
        execute_generic_runner_once(
            runner
        )

    assert runner.calls == 1


def test_generic_runner_executor_rejects_non_integer():
    runner = FakeRunner(
        result=None
    )

    with pytest.raises(
        RuntimeError,
        match="non-integer status",
    ):
        execute_generic_runner_once(
            runner
        )


def test_controller_executes_runner_then_reaches_closure():
    runner = FakeRunner()

    states = [
        snapshot(
            accepted=False
        ),
        snapshot(
            accepted=True
        ),
    ]

    index = 0

    original_execute = runner.execute

    def execute():
        nonlocal index

        result = original_execute()
        index = 1

        return result

    runner.execute = execute

    result = drive_runner_backed_governed_wave(
        runner=runner,
        snapshot_supplier=lambda: states[
            index
        ],
        max_runner_actions=1,
    )

    assert runner.calls == 1
    assert (
        result.stop
        is GovernedWaveStop.READY_FOR_CLOSURE
    )
    assert result.actions_performed == 1


def test_controller_does_not_execute_closed_case():
    runner = FakeRunner()

    result = drive_runner_backed_governed_wave(
        runner=runner,
        snapshot_supplier=lambda: snapshot(
            accepted=True
        ),
    )

    assert runner.calls == 0
    assert (
        result.stop
        is GovernedWaveStop.READY_FOR_CLOSURE
    )
"""Composition layer for the autonomous governed wave state machine.

This module connects the pure Slice-4 wave policy to the generic
Slice-3 governed wave runner.

It creates no authority and performs no evidence inference.
The supplied snapshot source must recover durable governed state.
"""

from __future__ import annotations

from typing import Callable, Protocol

from threadrom.factory.governed_wave_state_machine import (
    GovernedWaveCampaignSnapshot,
    GovernedWaveDriveResult,
    drive_governed_wave_campaign,
)


class GenericGovernedWaveRunnerPort(Protocol):
    def execute(self) -> int: ...


def execute_generic_runner_once(
    runner: GenericGovernedWaveRunnerPort,
) -> None:
    """Invoke one bounded generic-runner campaign action.

    The runner remains responsible for all execution authorization,
    duplicate protection, registry transitions and solver admission.
    """

    result = runner.execute()

    if type(result) is not int:
        raise RuntimeError(
            "Generic governed wave runner returned "
            "a non-integer status."
        )

    if result != 0:
        raise RuntimeError(
            "Generic governed wave runner returned "
            f"non-zero status {result}."
        )


def drive_runner_backed_governed_wave(
    *,
    runner: GenericGovernedWaveRunnerPort,
    snapshot_supplier: Callable[
        [],
        GovernedWaveCampaignSnapshot,
    ],
    max_runner_actions: int = 1,
) -> GovernedWaveDriveResult:
    """Drive one governed wave using the Slice-3 generic runner."""

    return drive_governed_wave_campaign(
        snapshot_supplier=snapshot_supplier,
        execute_generic_runner_once=lambda: (
            execute_generic_runner_once(
                runner
            )
        ),
        max_runner_actions=max_runner_actions,
    )
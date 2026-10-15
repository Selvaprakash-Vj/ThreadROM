from __future__ import annotations

import sqlite3

from pathlib import Path

import pytest

import threadrom.factory.governed_wave_controller as controller

from threadrom.factory.governed_wave_contract import (
    build_governed_wave_execution_contract,
)
from threadrom.factory.governed_wave_runner import (
    build_governed_wave_runner,
)
from threadrom.factory.governed_wave_state_machine import (
    GovernedCaseCampaignSnapshot,
    GovernedWaveCampaignSnapshot,
    GovernedWaveStop,
)


ROOT = Path(
    __file__
).resolve().parents[1]


HISTORICAL = {
    "W01": {
        "auth": (
            "7c825c4fc91745ef5c52f36c699ecf9"
            "ac580cd4fb9f62692c387c7ede560217f"
        ),
        "prep": (
            "7e6114c2f78957f01f7ad568a0f90fa"
            "6372ef03e88545ad759b0407b83791b75"
        ),
    },
    "W02": {
        "auth": (
            "19f5fa4bcd31eb8a1bff992f17d2c60"
            "a5ff70fdcf741521cc834401c99e6890a"
        ),
        "prep": (
            "80f14936394ac4cc713f6628f10630e4"
            "805a0531b3624de4cb6f60cc293b8ff2"
        ),
    },
}


def make_contract(
    wave_token: str,
):
    data = HISTORICAL[
        wave_token
    ]

    return build_governed_wave_execution_contract(
        campaign_id="TRM-DDOE-001",
        wave_token=wave_token,
        expected_owner_authorization_sha256=(
            data["auth"]
        ),
        expected_preparation_index_sha256=(
            data["prep"]
        ),
        authorized_case_count=4,
        maximum_concurrent_solver_slots=4,
        maximum_trial_index=6,
    )


def registry_rows(
    database_path: Path,
):
    path = Path(
        database_path
    ).resolve()

    uri = (
        "file:"
        + path.as_posix()
        + "?mode=ro"
    )

    connection = sqlite3.connect(
        uri,
        uri=True,
    )

    try:
        rows = connection.execute(
            """
            SELECT
                case_id,
                case_hash,
                trial_index,
                run_id,
                state
            FROM fem_jobs
            ORDER BY
                case_id,
                trial_index
            """
        ).fetchall()
    finally:
        connection.close()

    return rows


def recover_historical_wave_snapshot(
    *,
    contract,
    runner,
):
    # This is read-only verification of the frozen owner/preparation
    # boundaries before any state-machine interpretation.
    runner.call(
        "verify_owner_authorization"
    )

    contexts = (
        runner.build_case_contexts()
    )

    assert (
        len(contexts)
        == contract.authorized_case_count
    )

    rows = registry_rows(
        contract.factory_database_path
    )

    cases = []

    for context in contexts:
        case_hash = context[
            "case_hash"
        ]

        states = tuple(
            str(
                row[4]
            ).lower()
            for row in rows
            if row[1] == case_hash
        )

        if not states:
            raise RuntimeError(
                f"{context['case_id']}: "
                "no durable factory state."
            )

        accepted = (
            "accepted"
            in states
        )

        running = (
            "running"
            in states
        )

        terminal = (
            not accepted
            and not running
            and any(
                state
                in {
                    "failed",
                    "rejected",
                    "quarantined",
                }
                for state in states
            )
        )

        cases.append(
            GovernedCaseCampaignSnapshot(
                case_id=context[
                    "case_id"
                ],
                full_physics_accepted=accepted,
                solver_running=running,
                terminal_blocked=terminal,
            )
        )

    return GovernedWaveCampaignSnapshot(
        wave_id=contract.wave_id,
        authority_verified=True,
        authorized_case_count=(
            contract.authorized_case_count
        ),
        cases=tuple(
            cases
        ),
        closure_verified=False,
    )


@pytest.mark.parametrize(
    "wave_token",
    (
        "W01",
        "W02",
    ),
)
def test_closed_historical_wave_replays_to_closure_boundary(
    wave_token,
    monkeypatch,
):
    contract = make_contract(
        wave_token
    )

    runner = build_governed_wave_runner(
        repository_root=ROOT,
        contract=contract,
    )

    execute_attempts = 0

    def forbidden_execute(
        _runner,
    ):
        nonlocal execute_attempts

        execute_attempts += 1

        raise AssertionError(
            "Historical replay attempted generic execution."
        )

    monkeypatch.setattr(
        controller,
        "execute_generic_runner_once",
        forbidden_execute,
    )

    def supplier():
        return recover_historical_wave_snapshot(
            contract=contract,
            runner=runner,
        )

    initial = supplier()

    assert (
        initial.accepted_case_count
        == 4
    )
    assert initial.running_case_count == 0
    assert initial.blocked_case_count == 0

    result = (
        controller
        .drive_runner_backed_governed_wave(
            runner=runner,
            snapshot_supplier=supplier,
            max_runner_actions=1,
        )
    )

    assert execute_attempts == 0
    assert result.actions_performed == 0
    assert (
        result.stop
        is GovernedWaveStop.READY_FOR_CLOSURE
    )
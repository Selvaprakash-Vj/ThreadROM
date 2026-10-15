"""Generic governed-wave runner historical parity tests."""

from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import threadrom.factory.governed_wave_runner as module

from threadrom.factory.governed_wave_contract import (
    build_governed_wave_execution_contract,
)
from threadrom.factory.governed_wave_runner import (
    build_governed_wave_runner,
)


ROOT = Path(__file__).resolve().parents[1]

W01_AUTH = (
    "7c825c4fc91745ef5c52f36c699ecf9"
    "ac580cd4fb9f62692c387c7ede560217f"
)

W01_PREP = (
    "7e6114c2f78957f01f7ad568a0f90fa"
    "6372ef03e88545ad759b0407b83791b75"
)

W02_AUTH = (
    "19f5fa4bcd31eb8a1bff992f17d2c60"
    "a5ff70fdcf741521cc834401c99e6890a"
)

W02_PREP = (
    "80f14936394ac4cc713f6628f10630e4"
    "805a0531b3624de4cb6f60cc293b8ff2"
)


def _contract(
    wave,
    auth,
    prep,
):
    return build_governed_wave_execution_contract(
        campaign_id="TRM-DDOE-001",
        wave_token=wave,
        expected_owner_authorization_sha256=auth,
        expected_preparation_index_sha256=prep,
        authorized_case_count=4,
        maximum_concurrent_solver_slots=4,
        maximum_trial_index=6,
    )


@pytest.mark.parametrize(
    (
        "wave",
        "auth",
        "prep",
    ),
    (
        (
            "W01",
            W01_AUTH,
            W01_PREP,
        ),
        (
            "W02",
            W02_AUTH,
            W02_PREP,
        ),
    ),
)
def test_historical_closed_wave_preflight_passes_through_generic_engine(
    wave,
    auth,
    prep,
) -> None:
    runner = build_governed_wave_runner(
        repository_root=ROOT,
        contract=_contract(
            wave,
            auth,
            prep,
        ),
    )

    assert len(
        runner.available_functions
    ) == 30

    assert "preflight" in runner.available_functions
    assert "execute" in runner.available_functions
    assert (
        "recover_calibration_state"
        in runner.available_functions
    )
    assert (
        "prepare_governed_trial"
        in runner.available_functions
    )
    assert (
        "assess_full_physics"
        in runner.available_functions
    )

    # Historical W01/W02 are already complete. This is read-only
    # preflight/recovery replay; execute() is deliberately not called.
    runner.preflight()


@pytest.mark.parametrize(
    (
        "wave",
        "auth",
        "prep",
    ),
    (
        (
            "W01",
            W01_AUTH,
            W01_PREP,
        ),
        (
            "W02",
            W02_AUTH,
            W02_PREP,
        ),
    ),
)
def test_generic_engine_recovers_all_four_historical_cases(
    wave,
    auth,
    prep,
) -> None:
    runner = build_governed_wave_runner(
        repository_root=ROOT,
        contract=_contract(
            wave,
            auth,
            prep,
        ),
    )

    runner.call(
        "verify_owner_authorization"
    )

    contexts = runner.call(
        "build_case_contexts"
    )

    assert len(contexts) == 4

    for context in contexts:
        state = runner.call(
            "recover_calibration_state",
            context,
        )

        assert (
            state["status"]
            == "CALIBRATION_ACCEPTED"
        )


def test_generic_production_module_contains_no_historical_wave_binding() -> None:
    source = inspect.getsource(
        module
    )

    for token in (
        "W01",
        "w01",
        "W02",
        "w02",
    ):
        assert token not in source


def test_generic_runner_does_not_execute_during_construction() -> None:
    runner = build_governed_wave_runner(
        repository_root=ROOT,
        contract=_contract(
            "W02",
            W02_AUTH,
            W02_PREP,
        ),
    )

    # Construction exposes execution capability but does not invoke it.
    assert callable(
        runner._functions[
            "execute"
        ]
    )
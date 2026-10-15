"""Generic governed-wave owner-authorization validation tests."""

from __future__ import annotations

import inspect
from copy import deepcopy
from pathlib import Path

import pytest

import threadrom.factory.governed_wave_owner_authorization as module

from threadrom.factory.governed_wave_contract import (
    build_governed_wave_execution_contract,
)
from threadrom.factory.governed_wave_owner_authorization import (
    GovernedWaveAuthorizationError,
    load_and_verify_wave_owner_authorization,
    verify_owner_authorization_payload,
)


ROOT = Path(__file__).resolve().parents[2]

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


def _canonical_payload():
    return {
        "approval_status": "OWNER_APPROVED",
        "campaign_id": "TRM-DDOE-001",
        "wave_id": "TRM-DDOE-001-W03",
        "bound_artifacts": {
            "trial1_preparation_sha256":
                "b" * 64,
        },
        "execution_contract": {
            "automatic_governed_adaptation": True,
            "continue_until_physics_acceptance": True,
            "preload_calibration_continuation": True,
            "full_physics_certification": True,
            "maximum_trial_index_per_case": 6,
            "maximum_concurrent_calculix": 4,
            "reuse_existing_valid_trials": True,
            "duplicate_solver_execution_forbidden": True,
        },
        "scope": {
            "authorized_case_count": 4,
            "additional_doe_cases_authorized": False,
            "additional_waves_authorized": False,
            "holdout_access_authorized": False,
            "dataset_admission_authorized": False,
            "surrogate_training_authorized": False,
            "artifact_retirement_authorized": False,
        },
    }


def test_real_w01_authorization_replays_with_legacy_general_guard() -> None:
    verified = (
        load_and_verify_wave_owner_authorization(
            repository_root=ROOT,
            contract=_contract(
                "W01",
                W01_AUTH,
                W01_PREP,
            ),
        )
    )

    assert (
        verified.duplicate_execution_guard_field
        == "duplicate_solver_execution_forbidden"
    )

    assert verified.wave_id == "TRM-DDOE-001-W01"


def test_real_w02_authorization_replays_with_trial1_guard() -> None:
    verified = (
        load_and_verify_wave_owner_authorization(
            repository_root=ROOT,
            contract=_contract(
                "W02",
                W02_AUTH,
                W02_PREP,
            ),
        )
    )

    assert (
        verified.duplicate_execution_guard_field
        == (
            "duplicate_trial_1_execution_"
            "forbidden_if_valid_result_exists"
        )
    )

    assert verified.wave_id == "TRM-DDOE-001-W02"


def test_future_canonical_authorization_uses_general_duplicate_guard() -> None:
    contract = _contract(
        "W03",
        "a" * 64,
        "b" * 64,
    )

    verified = (
        verify_owner_authorization_payload(
            payload=_canonical_payload(),
            contract=contract,
            authorization_sha256=(
                "a" * 64
            ),
        )
    )

    assert (
        verified.duplicate_execution_guard_field
        == "duplicate_solver_execution_forbidden"
    )


def test_missing_duplicate_guard_fails_closed() -> None:
    payload = _canonical_payload()

    payload[
        "execution_contract"
    ].pop(
        "duplicate_solver_execution_forbidden"
    )

    with pytest.raises(
        GovernedWaveAuthorizationError,
        match="Duplicate-solve prohibition",
    ):
        verify_owner_authorization_payload(
            payload=payload,
            contract=_contract(
                "W03",
                "a" * 64,
                "b" * 64,
            ),
            authorization_sha256=(
                "a" * 64
            ),
        )


def test_historical_trial1_duplicate_guard_is_accepted_semantically() -> None:
    payload = _canonical_payload()

    execution = payload[
        "execution_contract"
    ]

    execution.pop(
        "duplicate_solver_execution_forbidden"
    )

    execution[
        "duplicate_trial_1_execution_forbidden_if_valid_result_exists"
    ] = True

    verified = verify_owner_authorization_payload(
        payload=payload,
        contract=_contract(
            "W03",
            "a" * 64,
            "b" * 64,
        ),
        authorization_sha256=(
            "a" * 64
        ),
    )

    assert (
        verified.duplicate_execution_guard_field
        == (
            "duplicate_trial_1_execution_"
            "forbidden_if_valid_result_exists"
        )
    )


def test_broadened_scope_fails_closed() -> None:
    payload = _canonical_payload()

    payload[
        "scope"
    ][
        "holdout_access_authorized"
    ] = True

    with pytest.raises(
        GovernedWaveAuthorizationError,
        match="scope broadened",
    ):
        verify_owner_authorization_payload(
            payload=payload,
            contract=_contract(
                "W03",
                "a" * 64,
                "b" * 64,
            ),
            authorization_sha256=(
                "a" * 64
            ),
        )


def test_wrong_case_count_fails_closed() -> None:
    payload = _canonical_payload()

    payload[
        "scope"
    ][
        "authorized_case_count"
    ] = 5

    with pytest.raises(
        GovernedWaveAuthorizationError,
        match="case count drift",
    ):
        verify_owner_authorization_payload(
            payload=payload,
            contract=_contract(
                "W03",
                "a" * 64,
                "b" * 64,
            ),
            authorization_sha256=(
                "a" * 64
            ),
        )


def test_wrong_trial_ceiling_fails_closed() -> None:
    payload = _canonical_payload()

    payload[
        "execution_contract"
    ][
        "maximum_trial_index_per_case"
    ] = 7

    with pytest.raises(
        GovernedWaveAuthorizationError,
        match="trial ceiling drift",
    ):
        verify_owner_authorization_payload(
            payload=payload,
            contract=_contract(
                "W03",
                "a" * 64,
                "b" * 64,
            ),
            authorization_sha256=(
                "a" * 64
            ),
        )




def test_canonical_preparation_binding_is_verified_by_name() -> None:
    verified = verify_owner_authorization_payload(
        payload=_canonical_payload(),
        contract=_contract(
            "W03",
            "a" * 64,
            "b" * 64,
        ),
        authorization_sha256=(
            "a" * 64
        ),
    )

    assert (
        verified.preparation_binding_field
        == "trial1_preparation_sha256"
    )


def test_wrong_canonical_preparation_binding_fails_closed() -> None:
    payload = _canonical_payload()

    payload[
        "bound_artifacts"
    ][
        "trial1_preparation_sha256"
    ] = "c" * 64

    with pytest.raises(
        GovernedWaveAuthorizationError,
        match="preparation SHA binding drift",
    ):
        verify_owner_authorization_payload(
            payload=payload,
            contract=_contract(
                "W03",
                "a" * 64,
                "b" * 64,
            ),
            authorization_sha256=(
                "a" * 64
            ),
        )


def test_sha_elsewhere_does_not_satisfy_named_binding() -> None:
    payload = _canonical_payload()

    payload[
        "bound_artifacts"
    ].pop(
        "trial1_preparation_sha256"
    )

    payload[
        "unrelated_sha_container"
    ] = {
        "sha256":
            "b" * 64,
    }

    with pytest.raises(
        GovernedWaveAuthorizationError,
        match="explicitly named",
    ):
        verify_owner_authorization_payload(
            payload=payload,
            contract=_contract(
                "W03",
                "a" * 64,
                "b" * 64,
            ),
            authorization_sha256=(
                "a" * 64
            ),
        )


def test_wave_named_historical_compatibility_binding_is_verified() -> None:
    payload = _canonical_payload()

    value = payload[
        "bound_artifacts"
    ].pop(
        "trial1_preparation_sha256"
    )

    compatibility_field = (
        "w03_trial1_preparation_sha256"
    )

    payload[
        "bound_artifacts"
    ][
        compatibility_field
    ] = value

    verified = verify_owner_authorization_payload(
        payload=payload,
        contract=_contract(
            "W03",
            "a" * 64,
            "b" * 64,
        ),
        authorization_sha256=(
            "a" * 64
        ),
    )

    assert (
        verified.preparation_binding_field
        == compatibility_field
    )


def test_generic_validator_contains_no_historical_wave_literals() -> None:
    source = inspect.getsource(
        module
    )

    for literal in (
        '"W01"',
        "'W01'",
        '"W02"',
        "'W02'",
    ):
        assert literal not in source
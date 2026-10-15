"""Governed wave execution contract V1 tests."""

from __future__ import annotations

import inspect

import pytest

import threadrom.factory.governed_wave_contract as module

from threadrom.factory.governed_wave_contract import (
    GovernedWaveContractError,
    build_governed_wave_execution_contract,
)


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
    wave_token: str,
    auth: str,
    prep: str,
):
    return build_governed_wave_execution_contract(
        campaign_id="TRM-DDOE-001",
        wave_token=wave_token,
        expected_owner_authorization_sha256=auth,
        expected_preparation_index_sha256=prep,
        authorized_case_count=4,
        maximum_concurrent_solver_slots=4,
        maximum_trial_index=6,
    )


def test_historical_w01_paths_are_derived_exactly() -> None:
    contract = _contract(
        "W01",
        W01_AUTH,
        W01_PREP,
    )

    assert contract.wave_id == "TRM-DDOE-001-W01"

    assert (
        contract.campaign_root.as_posix()
        == (
            "simulations/staging/"
            "phase3_diversified_doe/"
            "TRM-DDOE-001/W01"
        )
    )

    assert (
        contract.factory_database_path.as_posix()
        == (
            "simulations/staging/"
            "phase3_diversified_doe/"
            "TRM-DDOE-001/W01/factory/"
            "w01_trial1_factory.sqlite3"
        )
    )

    assert (
        contract.admission_lock_path.as_posix()
        == (
            "simulations/staging/"
            "phase3_diversified_doe/"
            "TRM-DDOE-001/W01/factory/"
            "w01_adaptive_parallel_admission.lock"
        )
    )

    assert (
        contract.owner_authorization_path.as_posix()
        == (
            "docs/phase3_diversified_doe/"
            "waves/TRM-DDOE-001-W01/"
            "adaptive_campaign_owner_authorization.json"
        )
    )

    assert (
        contract.preparation_index_path.as_posix()
        == (
            "simulations/staging/"
            "phase3_diversified_doe/"
            "TRM-DDOE-001/W01/"
            "w01_trial1_preparation.json"
        )
    )


def test_historical_w02_paths_are_derived_exactly() -> None:
    contract = _contract(
        "W02",
        W02_AUTH,
        W02_PREP,
    )

    assert contract.wave_id == "TRM-DDOE-001-W02"

    assert (
        contract.factory_database_path.name
        == "w02_trial1_factory.sqlite3"
    )

    assert (
        contract.admission_lock_path.name
        == "w02_adaptive_parallel_admission.lock"
    )

    assert (
        contract.preparation_index_path.name
        == "w02_trial1_preparation.json"
    )

    assert (
        contract.expected_owner_authorization_sha256
        == W02_AUTH
    )

    assert (
        contract.expected_preparation_index_sha256
        == W02_PREP
    )


def test_wave_specific_evidence_names_are_derived() -> None:
    contract = _contract(
        "W02",
        W02_AUTH,
        W02_PREP,
    )

    assert (
        contract.adaptive_preparation_filename
        == "w02_adaptive_preparation.json"
    )

    assert (
        contract.adaptive_preparation_schema
        == (
            "threadrom.phase3_diversified_"
            "w02_adaptive_preparation.v1"
        )
    )

    assert (
        contract.adaptive_preparation_disposition
        == "W02_ADAPTIVE_TRIAL_PREPARATION_PASS"
    )

    assert (
        contract.worker_prefix
        == "TRM-DDOE-W02-adaptive-worker-"
    )

    assert (
        contract.physics_assessment_filename
        == "w02_governed_full_physics_assessment_v2.json"
    )

    assert (
        contract.physics_assessment_schema
        == (
            "threadrom.phase3_diversified_"
            "w02_full_physics_assessment.v2"
        )
    )

    assert (
        contract.nonlinear_progress_filename
        == "w02_nonlinear_progress.json"
    )

    assert (
        contract.external_total_force_filename
        == (
            "w02_external_translational_"
            "total_force.json"
        )
    )

    assert (
        contract.external_equilibrium_filename
        == (
            "w02_external_translational_"
            "equilibrium.json"
        )
    )


def test_future_wave_requires_no_new_production_literal() -> None:
    contract = _contract(
        "W03",
        "a" * 64,
        "b" * 64,
    )

    assert contract.wave_id == "TRM-DDOE-001-W03"

    assert (
        contract.factory_database_path.name
        == "w03_trial1_factory.sqlite3"
    )

    assert (
        contract.adaptive_preparation_filename
        == "w03_adaptive_preparation.json"
    )

    assert (
        contract.worker_prefix
        == "TRM-DDOE-W03-adaptive-worker-"
    )

    assert (
        contract.physics_assessment_filename
        == "w03_governed_full_physics_assessment_v2.json"
    )


def test_contract_fingerprint_is_deterministic_and_sensitive() -> None:
    first = _contract(
        "W02",
        W02_AUTH,
        W02_PREP,
    )

    second = _contract(
        "W02",
        W02_AUTH,
        W02_PREP,
    )

    changed = _contract(
        "W03",
        W02_AUTH,
        W02_PREP,
    )

    assert (
        first.contract_sha256
        == second.contract_sha256
    )

    assert (
        first.contract_sha256
        != changed.contract_sha256
    )

    assert len(
        first.contract_sha256
    ) == 64


@pytest.mark.parametrize(
    "wave",
    (
        "W3",
        "w03",
        "W003",
        "../W03",
        "WAA",
    ),
)
def test_malformed_wave_tokens_fail_closed(
    wave,
) -> None:
    with pytest.raises(
        GovernedWaveContractError
    ):
        _contract(
            wave,
            "a" * 64,
            "b" * 64,
        )


def test_unsafe_campaign_id_fails_closed() -> None:
    with pytest.raises(
        GovernedWaveContractError
    ):
        build_governed_wave_execution_contract(
            campaign_id="../TRM-DDOE-001",
            wave_token="W03",
            expected_owner_authorization_sha256=(
                "a" * 64
            ),
            expected_preparation_index_sha256=(
                "b" * 64
            ),
            authorized_case_count=4,
            maximum_concurrent_solver_slots=4,
            maximum_trial_index=6,
        )


def test_invalid_sha_fails_closed() -> None:
    with pytest.raises(
        GovernedWaveContractError
    ):
        build_governed_wave_execution_contract(
            campaign_id="TRM-DDOE-001",
            wave_token="W03",
            expected_owner_authorization_sha256=(
                "NOT-A-SHA"
            ),
            expected_preparation_index_sha256=(
                "b" * 64
            ),
            authorized_case_count=4,
            maximum_concurrent_solver_slots=4,
            maximum_trial_index=6,
        )


def test_positive_limits_are_required() -> None:
    with pytest.raises(
        GovernedWaveContractError
    ):
        build_governed_wave_execution_contract(
            campaign_id="TRM-DDOE-001",
            wave_token="W03",
            expected_owner_authorization_sha256=(
                "a" * 64
            ),
            expected_preparation_index_sha256=(
                "b" * 64
            ),
            authorized_case_count=4,
            maximum_concurrent_solver_slots=0,
            maximum_trial_index=6,
        )


def test_production_contract_contains_no_historical_wave_literals() -> None:
    source = inspect.getsource(
        module
    )

    assert '"W01"' not in source
    assert '"W02"' not in source
    assert "'W01'" not in source
    assert "'W02'" not in source
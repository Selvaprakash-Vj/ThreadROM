from __future__ import annotations

import hashlib

from pathlib import Path

import pytest

from threadrom.factory.governed_wave_closure import (
    GovernedWaveExpectedCase,
    build_governed_wave_closure_record,
    persist_governed_wave_closure,
    recover_governed_wave_acceptance_evidence,
    recover_governed_wave_closure,
)
from threadrom.factory.governed_wave_contract import (
    build_governed_wave_execution_contract,
)
from threadrom.factory.governed_wave_runner import (
    build_governed_wave_runner,
)
from threadrom.factory.governed_wave_state_machine import (
    GovernedCaseCampaignSnapshot,
    GovernedWaveCampaignSnapshot,
    GovernedWavePhase,
    decide_governed_wave_campaign,
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
        "db_sha": (
            "00f6cdff8617689b1d29103acfa1a177"
            "4b6dab7348bd2cac4ccffa533a4c2e34"
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
        "db_sha": (
            "892fe09fdd3d463cbb1888f0184086a9"
            "79b3f52d064f53c7ea4b2f59466fabd1"
        ),
    },
}


def repo_path(
    path,
) -> Path:
    concrete = Path(
        str(
            path
        )
    )

    if not concrete.is_absolute():
        concrete = (
            ROOT
            / concrete
        )

    return concrete.resolve(
        strict=True
    )


def file_sha(
    path,
):
    return hashlib.sha256(
        repo_path(
            path
        ).read_bytes()
    ).hexdigest()


def contract_sha(
    contract,
):
    value = getattr(
        contract,
        "contract_sha256",
    )

    if callable(
        value
    ):
        value = value()

    return str(
        value
    )


@pytest.mark.parametrize(
    "wave_token",
    (
        "W01",
        "W02",
    ),
)
def test_historical_wave_closes_from_real_certificates(
    wave_token,
    tmp_path,
):
    data = HISTORICAL[
        wave_token
    ]

    contract = (
        build_governed_wave_execution_contract(
            campaign_id="TRM-DDOE-001",
            wave_token=wave_token,
            expected_owner_authorization_sha256=(
                data[
                    "auth"
                ]
            ),
            expected_preparation_index_sha256=(
                data[
                    "prep"
                ]
            ),
            authorized_case_count=4,
            maximum_concurrent_solver_slots=4,
            maximum_trial_index=6,
        )
    )

    runner = build_governed_wave_runner(
        repository_root=ROOT,
        contract=contract,
    )

    runner.call(
        "verify_owner_authorization"
    )

    contexts = (
        runner.build_case_contexts()
    )

    expected_cases = tuple(
        GovernedWaveExpectedCase(
            case_id=context[
                "case_id"
            ],
            case_hash=context[
                "case_hash"
            ],
            case_run_id=context[
                "case_run_id"
            ],
        )
        for context in contexts
    )

    before = file_sha(
        contract.factory_database_path
    )

    assert (
        before
        == data[
            "db_sha"
        ]
    )

    evidence = (
        recover_governed_wave_acceptance_evidence(
            repo_root=ROOT,
            wave_id=contract.wave_id,
            factory_database_path=(
                contract.factory_database_path
            ),
            expected_cases=expected_cases,
        )
    )

    assert len(
        evidence.cases
    ) == 4

    assert all(
        case.hard_gate_count
        == 13
        for case in evidence.cases
    )

    assert all(
        case.accepted_increment_count
        == 20
        for case in evidence.cases
    )

    assert all(
        case.rotational_moment_equilibrium_status
        == "not_assessed"
        for case in evidence.cases
    )

    record = (
        build_governed_wave_closure_record(
            evidence=evidence,
            execution_contract_sha256=(
                contract_sha(
                    contract
                )
            ),
            owner_authorization_sha256=(
                data[
                    "auth"
                ]
            ),
            preparation_index_sha256=(
                data[
                    "prep"
                ]
            ),
        )
    )

    closure_path = (
        tmp_path
        / wave_token
        / "wave_closure.json"
    )

    first_sha = (
        persist_governed_wave_closure(
            path=closure_path,
            record=record,
        )
    )

    second_sha = (
        persist_governed_wave_closure(
            path=closure_path,
            record=record,
        )
    )

    assert first_sha == second_sha

    recovered = (
        recover_governed_wave_closure(
            path=closure_path,
            expected_wave_id=(
                contract.wave_id
            ),
            expected_evidence=evidence,
        )
    )

    assert recovered is not None

    snapshot = (
        GovernedWaveCampaignSnapshot(
            wave_id=contract.wave_id,
            authority_verified=True,
            authorized_case_count=4,
            cases=tuple(
                GovernedCaseCampaignSnapshot(
                    case_id=case.case_id,
                    full_physics_accepted=True,
                )
                for case in evidence.cases
            ),
            closure_verified=True,
        )
    )

    decision = (
        decide_governed_wave_campaign(
            snapshot
        )
    )

    assert (
        decision.phase
        is GovernedWavePhase.CLOSED
    )

    after = file_sha(
        contract.factory_database_path
    )

    assert after == before
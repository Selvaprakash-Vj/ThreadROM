from __future__ import annotations

import json
import sqlite3

from pathlib import Path

import pytest

from threadrom.factory.governed_wave_closure import (
    GovernedWaveExpectedCase,
    build_governed_wave_closure_record,
    persist_governed_wave_closure,
    recover_governed_wave_acceptance_evidence,
    recover_governed_wave_closure,
)


CASE_HASH = (
    "a" * 64
)

CASE_RUN = (
    "trm_fem_"
    + CASE_HASH[:12]
)

RUN_ID = (
    CASE_RUN
    + "_cal_02"
)


def make_repo(
    tmp_path: Path,
):
    root = (
        tmp_path
        / "repo"
    )

    root.mkdir()

    db = (
        root
        / "factory.sqlite3"
    )

    certificate = (
        root
        / "run"
        / "certificate.json"
    )

    certificate.parent.mkdir()

    payload = {
        "schema": (
            "threadrom.diversified_governed_physics_certificate.v1"
        ),
        "record_status": "FINAL",
        "disposition": (
            "GOVERNED_FULL_PHYSICS_ACCEPTED"
        ),
        "case_id": "CASE-01",
        "case_hash": CASE_HASH,
        "case_run_id": CASE_RUN,
        "run_id": RUN_ID,
        "trial_index": 2,
        "additional_fem_authorized": False,
        "artifact_retirement_authorized": False,
        "holdout_access_authorized": False,
        "solver_launch_authorized": False,
        "independent_human_review": False,
        "independent_human_review_claimed": False,
        "artifact_sha256": {
            "dat": "b" * 64,
        },
        "source_sha256": {
            "source.py": "c" * 64,
        },
        "assessment": {
            "case_id": "CASE-01",
            "case_hash": CASE_HASH,
            "case_run_id": CASE_RUN,
            "run_id": RUN_ID,
            "trial_index": 2,
            "calibration_disposition": "accept",
            "next_trial_run_id": None,
            "equilibrium_status": "pass",
            "full_physics_passed": True,
            "full_physics_accepted": True,
            "all_hard_gates_passed": True,
            "failed_governed_checks": [],
            "hard_gate_count": 13,
            "hard_gates_passed": 13,
            "accepted_increment_count": 20,
            "rotational_moment_equilibrium_status": (
                "not_assessed"
            ),
        },
    }

    certificate.write_text(
        json.dumps(
            payload
        ),
        encoding="utf-8",
    )

    connection = sqlite3.connect(
        db
    )

    try:
        connection.execute(
            """
            CREATE TABLE fem_jobs (
                case_id TEXT,
                case_hash TEXT,
                trial_index INTEGER,
                run_id TEXT,
                state TEXT,
                acceptance_record TEXT
            )
            """
        )

        connection.execute(
            """
            INSERT INTO fem_jobs (
                case_id,
                case_hash,
                trial_index,
                run_id,
                state,
                acceptance_record
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "CASE-01",
                CASE_HASH,
                2,
                RUN_ID,
                "accepted",
                "run/certificate.json",
            ),
        )

        connection.commit()
    finally:
        connection.close()

    expected = (
        GovernedWaveExpectedCase(
            case_id="CASE-01",
            case_hash=CASE_HASH,
            case_run_id=CASE_RUN,
        ),
    )

    return (
        root,
        db,
        certificate,
        payload,
        expected,
    )


def fake_recoverer(
    **kwargs,
):
    return json.loads(
        (
            Path(
                kwargs[
                    "run_dir"
                ]
            )
            / "certificate.json"
        ).read_text(
            encoding="utf-8"
        )
    )


def test_recovers_one_accepted_case(
    tmp_path,
):
    (
        root,
        db,
        _,
        _,
        expected,
    ) = make_repo(
        tmp_path
    )

    evidence = (
        recover_governed_wave_acceptance_evidence(
            repo_root=root,
            wave_id="WAVE-01",
            factory_database_path=db,
            expected_cases=expected,
            certificate_recoverer=(
                fake_recoverer
            ),
        )
    )

    assert (
        evidence.authorized_case_count
        == 1
    )

    assert len(
        evidence.cases
    ) == 1

    assert (
        evidence.cases[
            0
        ].hard_gate_count
        == 13
    )

    assert (
        evidence.cases[
            0
        ].rotational_moment_equilibrium_status
        == "not_assessed"
    )


def test_missing_accepted_case_fails_closed(
    tmp_path,
):
    (
        root,
        db,
        _,
        _,
        expected,
    ) = make_repo(
        tmp_path
    )

    connection = sqlite3.connect(
        db
    )

    try:
        connection.execute(
            "DELETE FROM fem_jobs"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        RuntimeError,
        match="row count",
    ):
        recover_governed_wave_acceptance_evidence(
            repo_root=root,
            wave_id="WAVE-01",
            factory_database_path=db,
            expected_cases=expected,
            certificate_recoverer=(
                fake_recoverer
            ),
        )


def test_broadened_accepted_cohort_fails_closed(
    tmp_path,
):
    (
        root,
        db,
        _,
        _,
        expected,
    ) = make_repo(
        tmp_path
    )

    connection = sqlite3.connect(
        db
    )

    try:
        connection.execute(
            """
            INSERT INTO fem_jobs
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "OUTSIDE",
                "d" * 64,
                1,
                "trm_fem_"
                + ("d" * 12)
                + "_cal_01",
                "accepted",
                "run/certificate.json",
            ),
        )

        connection.commit()
    finally:
        connection.close()

    with pytest.raises(
        RuntimeError,
        match="row count",
    ):
        recover_governed_wave_acceptance_evidence(
            repo_root=root,
            wave_id="WAVE-01",
            factory_database_path=db,
            expected_cases=expected,
            certificate_recoverer=(
                fake_recoverer
            ),
        )


def test_rotational_certification_claim_fails_closed(
    tmp_path,
):
    (
        root,
        db,
        certificate,
        payload,
        expected,
    ) = make_repo(
        tmp_path
    )

    payload[
        "assessment"
    ][
        "rotational_moment_equilibrium_status"
    ] = "pass"

    certificate.write_text(
        json.dumps(
            payload
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="rotational-moment",
    ):
        recover_governed_wave_acceptance_evidence(
            repo_root=root,
            wave_id="WAVE-01",
            factory_database_path=db,
            expected_cases=expected,
            certificate_recoverer=(
                fake_recoverer
            ),
        )


def test_wave_closure_persist_and_recover(
    tmp_path,
):
    (
        root,
        db,
        _,
        _,
        expected,
    ) = make_repo(
        tmp_path
    )

    evidence = (
        recover_governed_wave_acceptance_evidence(
            repo_root=root,
            wave_id="WAVE-01",
            factory_database_path=db,
            expected_cases=expected,
            certificate_recoverer=(
                fake_recoverer
            ),
        )
    )

    record = (
        build_governed_wave_closure_record(
            evidence=evidence,
            execution_contract_sha256=(
                "1" * 64
            ),
            owner_authorization_sha256=(
                "2" * 64
            ),
            preparation_index_sha256=(
                "3" * 64
            ),
        )
    )

    path = (
        root
        / "closure.json"
    )

    first = (
        persist_governed_wave_closure(
            path=path,
            record=record,
        )
    )

    second = (
        persist_governed_wave_closure(
            path=path,
            record=record,
        )
    )

    assert first == second

    recovered = (
        recover_governed_wave_closure(
            path=path,
            expected_wave_id="WAVE-01",
            expected_evidence=evidence,
        )
    )

    assert recovered is not None
    assert (
        recovered[
            "accepted_case_count"
        ]
        == 1
    )


def test_conflicting_closure_is_rejected(
    tmp_path,
):
    (
        root,
        db,
        _,
        _,
        expected,
    ) = make_repo(
        tmp_path
    )

    evidence = (
        recover_governed_wave_acceptance_evidence(
            repo_root=root,
            wave_id="WAVE-01",
            factory_database_path=db,
            expected_cases=expected,
            certificate_recoverer=(
                fake_recoverer
            ),
        )
    )

    record = (
        build_governed_wave_closure_record(
            evidence=evidence,
            execution_contract_sha256=(
                "1" * 64
            ),
            owner_authorization_sha256=(
                "2" * 64
            ),
            preparation_index_sha256=(
                "3" * 64
            ),
        )
    )

    path = (
        root
        / "closure.json"
    )

    persist_governed_wave_closure(
        path=path,
        record=record,
    )

    path.write_text(
        "{}\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="conflict",
    ):
        persist_governed_wave_closure(
            path=path,
            record=record,
        )
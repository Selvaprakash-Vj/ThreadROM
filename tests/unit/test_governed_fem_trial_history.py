"""Synthetic tests for shared governed FEM history recovery."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from threadrom.factory.production_doe_trial_history import (
    recover_verified_trial_history,
)


CASE_HASH = "a" * 64
CASE_RUN_ID = "trm_fem_" + CASE_HASH[:12]


def recover(
    tmp_path,
    *,
    status="COMPLETED_INPUT_EVIDENCE_VERIFIED",
    maximum_trials=6,
    case_hash=CASE_HASH,
):
    return recover_verified_trial_history(
        repo_root=tmp_path,
        case_id="SYNTHETIC-M12",
        case_hash=case_hash,
        case_run_id=CASE_RUN_ID,
        solver_preparation_root=(
            tmp_path / "synthetic_campaign" / "solver_preparation"
        ),
        verified_initial_trial=SimpleNamespace(
            completion_status=status,
            run_id=CASE_RUN_ID + "_cal_01",
        ),
        maximum_trials=maximum_trials,
    )


def test_pending_initial_trial_is_not_relaunched(tmp_path):
    result = recover(
        tmp_path,
        status="PENDING_COMPLETED_MANIFEST",
    )

    assert result.completed_run_ids == ()
    assert result.next_trial_index == 1
    assert result.state == "WAIT_FOR_TRIAL_1_COMPLETION"


def test_missing_next_trial_requires_preparation(tmp_path):
    result = recover(tmp_path)

    assert result.completed_run_ids == (
        CASE_RUN_ID + "_cal_01",
    )

    assert result.next_trial_index == 2
    assert result.state == "NEXT_TRIAL_NOT_PREPARED"


def test_future_trial_gap_fails_closed(tmp_path):
    case_dir = (
        tmp_path
        / "synthetic_campaign"
        / "solver_preparation"
        / CASE_RUN_ID
    )

    (case_dir / (CASE_RUN_ID + "_cal_03")).mkdir(
        parents=True
    )

    with pytest.raises(
        RuntimeError,
        match="trial-history gap",
    ):
        recover(tmp_path)


def test_existing_trial_without_preparation_fails_closed(
    tmp_path,
):
    case_dir = (
        tmp_path
        / "synthetic_campaign"
        / "solver_preparation"
        / CASE_RUN_ID
    )

    (case_dir / (CASE_RUN_ID + "_cal_02")).mkdir(
        parents=True
    )

    with pytest.raises(
        RuntimeError,
        match="lacks immutable preparation",
    ):
        recover(tmp_path)


def test_invalid_case_identity_is_rejected(tmp_path):
    with pytest.raises(
        RuntimeError,
        match="case hash",
    ):
        recover(
            tmp_path,
            case_hash="invalid",
        )


def test_unverified_initial_evidence_is_rejected(tmp_path):
    with pytest.raises(
        RuntimeError,
        match="Unverified initial-trial",
    ):
        recover(
            tmp_path,
            status="UNVERIFIED",
        )


def test_maximum_trial_policy_is_validated(tmp_path):
    with pytest.raises(
        RuntimeError,
        match="maximum-trial policy",
    ):
        recover(
            tmp_path,
            maximum_trials=0,
        )

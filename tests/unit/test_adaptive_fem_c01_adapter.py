from pathlib import Path
from types import SimpleNamespace

import pytest

from threadrom.factory.adaptive_fem_c01_adapter import (
    decide_c01_lifecycle,
)
from threadrom.factory.adaptive_fem_lifecycle import (
    LifecycleAction as A,
)


CASE = "trm_fem_d667bb1aca27"
TRIAL1 = f"{CASE}_cal_01_wsv21_rfobs1"
TRIAL2 = f"{CASE}_cal_02"


def plan(state, *, completed=1, next_id=TRIAL2):
    return SimpleNamespace(
        state=state,
        completed_trial_count=completed,
        last_completed_run_id=TRIAL1,
        next_trial_run_id=next_id,
        next_delta_temperature_c=(
            -273.2584334536732
            if next_id is not None
            else None
        ),
    )


def decide(tmp_path, value):
    return decide_c01_lifecycle(
        history_plan=value,
        case_run_id=CASE,
        campaign_root=tmp_path,
        maximum_trials=6,
    )


def test_completed_rejected_trial_requests_governed_preparation(
    tmp_path,
):
    result = decide(
        tmp_path,
        plan("NEXT_TRIAL_NOT_PREPARED"),
    )
    assert result.action is A.PREPARE_GOVERNED_ADAPTATION
    assert result.next_trial_index == 2


def test_prepared_trial_requests_governed_launch_not_permission(
    tmp_path,
):
    run_dir = (
        tmp_path / "solver_preparation" / CASE / TRIAL2
    )
    run_dir.mkdir(parents=True)

    result = decide(
        tmp_path,
        plan("PREPARED_NEXT_TRIAL_REQUIRES_AUTHORIZATION"),
    )
    assert result.action is A.REQUEST_GOVERNED_LAUNCH


def test_existing_claim_blocks_new_launch_request(tmp_path):
    run_dir = (
        tmp_path / "solver_preparation" / CASE / TRIAL2
    )
    run_dir.mkdir(parents=True)
    (run_dir / "adaptive_launch_claim.json").write_text(
        "{}", encoding="utf-8"
    )

    result = decide(
        tmp_path,
        plan("PREPARED_NEXT_TRIAL_REQUIRES_AUTHORIZATION"),
    )
    assert result.action is A.ENGINEERING_REVIEW


def test_existing_solver_output_blocks_new_launch_request(tmp_path):
    run_dir = (
        tmp_path / "solver_preparation" / CASE / TRIAL2
    )
    run_dir.mkdir(parents=True)
    (run_dir / f"{TRIAL2}.sta").write_text(
        "partial result", encoding="utf-8"
    )

    result = decide(
        tmp_path,
        plan("PREPARED_NEXT_TRIAL_REQUIRES_AUTHORIZATION"),
    )
    assert result.action is A.ENGINEERING_REVIEW


def test_calibration_acceptance_still_requires_full_physics(
    tmp_path,
):
    result = decide(
        tmp_path,
        plan(
            "CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS",
            next_id=None,
        ),
    )
    assert result.action is A.ASSESS_VERIFIED_PHYSICS
    assert result.action is not A.CERTIFIED_COMPLETE


def test_wrong_next_trial_identity_fails_closed(tmp_path):
    with pytest.raises(RuntimeError, match="identity"):
        decide(
            tmp_path,
            plan(
                "PREPARED_NEXT_TRIAL_REQUIRES_AUTHORIZATION",
                next_id=f"{CASE}_cal_03",
            ),
        )

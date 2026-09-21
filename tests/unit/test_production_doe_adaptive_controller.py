from types import SimpleNamespace

import pytest

from threadrom.factory.preload_calibration_controller import (
    PreloadCalibrationDisposition as D,
)
from threadrom.factory.production_doe_adaptive_controller import (
    AdaptiveCalibrationAction as A,
    plan_adaptive_calibration,
)


CASE = "trm_fem_d667bb1aca27"
TRIAL1 = f"{CASE}_cal_01_wsv21_rfobs1"
TRIAL2 = f"{CASE}_cal_02"


def evaluation(
    disposition=D.CONTINUE,
    *,
    accepted=False,
    current_index=1,
    current_id=TRIAL1,
    next_index=2,
    next_id=TRIAL2,
):
    return SimpleNamespace(
        accepted=accepted,
        decision=SimpleNamespace(disposition=disposition),
        completed_trial=SimpleNamespace(
            trial_index=current_index,
            run_id=current_id,
        ),
        next_trial=(
            None
            if next_index is None
            else SimpleNamespace(
                trial_index=next_index,
                run_id=next_id,
            )
        ),
    )


def plan(value, limit=6):
    return plan_adaptive_calibration(
        case_run_id=CASE,
        evaluation=value,
        maximum_trials=limit,
    )


def test_rfobs1_trial1_plans_trial2_without_authorizing_a_solve():
    result = plan(evaluation())
    assert result.action is A.NEXT_TRIAL_REQUIRES_AUTHORIZATION
    assert result.completed_run_id == TRIAL1
    assert result.next_run_id == TRIAL2


def test_accept_stops_calibration_but_not_full_physics_review():
    result = plan(
        evaluation(D.ACCEPT, accepted=True, next_index=None)
    )
    assert (
        result.action
        is A.CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS
    )
    assert result.next_run_id is None


def test_nonmonotonic_response_fails_closed():
    with pytest.raises(RuntimeError, match="without acceptance"):
        plan(evaluation(D.NON_MONOTONIC_RESPONSE, next_index=None))


def test_continue_without_next_trial_fails_closed():
    with pytest.raises(RuntimeError, match="inconsistent"):
        plan(evaluation(next_index=None))


def test_trial_limit_fails_closed():
    with pytest.raises(RuntimeError, match="limit reached"):
        plan(
            evaluation(
                current_index=6,
                current_id=f"{CASE}_cal_06",
                next_index=7,
                next_id=f"{CASE}_cal_07",
            )
        )


def test_skipped_trial_identity_fails_closed():
    with pytest.raises(RuntimeError, match="governed lineage"):
        plan(evaluation(next_index=3, next_id=f"{CASE}_cal_03"))


def test_false_acceptance_fails_closed():
    with pytest.raises(RuntimeError, match="Inconsistent"):
        plan(
            evaluation(D.ACCEPT, accepted=False, next_index=None)
        )

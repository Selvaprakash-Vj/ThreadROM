import pytest

from threadrom.factory.adaptive_fem_lifecycle import (
    FEMLifecycleSnapshot as S,
    LifecycleAction as A,
    PhysicsDisposition as P,
    RunPhase as R,
    decide_fem_lifecycle,
)


def state(
    phase,
    *,
    trial=1,
    limit=6,
    verified=False,
    physics=P.NOT_ASSESSED,
    rule=None,
    certified=False,
):
    return S(
        run_id="synthetic_fem_trial",
        trial_index=trial,
        maximum_trials=limit,
        phase=phase,
        completed_evidence_verified=verified,
        physics=physics,
        corrective_rule_id=rule,
        full_physics_acceptance_verified=certified,
    )


def test_new_run_requires_preparation():
    assert decide_fem_lifecycle(
        state(R.NOT_PREPARED)
    ).action is A.PREPARE


def test_prepared_run_does_not_gain_execution_authorization():
    assert decide_fem_lifecycle(
        state(R.PREPARED)
    ).action is A.REQUEST_GOVERNED_LAUNCH


def test_running_run_waits():
    assert decide_fem_lifecycle(
        state(R.RUNNING)
    ).action is A.WAIT_FOR_RUNNING_SOLVER


@pytest.mark.parametrize("phase", [R.CLAIMED, R.UNCERTAIN])
def test_uncertain_run_never_restarts_automatically(phase):
    assert decide_fem_lifecycle(
        state(phase)
    ).action is A.ENGINEERING_REVIEW


def test_completed_unverified_run_requires_review():
    assert decide_fem_lifecycle(
        state(R.COMPLETED)
    ).action is A.ENGINEERING_REVIEW


def test_verified_completion_requires_physics_assessment():
    assert decide_fem_lifecycle(
        state(R.COMPLETED, verified=True)
    ).action is A.ASSESS_VERIFIED_PHYSICS


def test_rejected_physics_with_governed_rule_proposes_next_trial():
    decision = decide_fem_lifecycle(
        state(
            R.COMPLETED,
            trial=3,
            verified=True,
            physics=P.ADAPT,
            rule="approved_model_specific_rule",
        )
    )
    assert decision.action is A.PREPARE_GOVERNED_ADAPTATION
    assert decision.next_trial_index == 4
    assert decision.corrective_rule_id == (
        "approved_model_specific_rule"
    )


def test_no_governed_correction_requires_review():
    assert decide_fem_lifecycle(
        state(
            R.COMPLETED,
            verified=True,
            physics=P.ADAPT,
        )
    ).action is A.ENGINEERING_REVIEW


def test_trial_limit_blocks_further_adaptation():
    assert decide_fem_lifecycle(
        state(
            R.COMPLETED,
            trial=6,
            verified=True,
            physics=P.ADAPT,
            rule="approved_rule",
        )
    ).action is A.STOP_TRIAL_LIMIT


def test_physics_acceptance_alone_is_not_certification():
    assert decide_fem_lifecycle(
        state(
            R.COMPLETED,
            verified=True,
            physics=P.ACCEPTED,
        )
    ).action is A.REQUIRE_ACCEPTANCE_CERTIFICATION


def test_full_physics_certification_closes_lifecycle():
    assert decide_fem_lifecycle(
        state(
            R.COMPLETED,
            verified=True,
            physics=P.ACCEPTED,
            certified=True,
        )
    ).action is A.CERTIFIED_COMPLETE


def test_contradictory_acceptance_fails_closed():
    with pytest.raises(RuntimeError, match="conflicts"):
        decide_fem_lifecycle(
            state(
                R.COMPLETED,
                verified=True,
                physics=P.REJECTED,
                certified=True,
            )
        )

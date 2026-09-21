from dataclasses import replace

import pytest

from threadrom.factory.adaptive_fem_lifecycle import (
    FEMLifecycleSnapshot as S,
    PhysicsDisposition as P,
    RunPhase as R,
)
from threadrom.factory.adaptive_fem_supervisor import (
    SupervisorStop,
    drive_fem_supervisor,
)


class SyntheticFactory:
    def __init__(self, *, allow_launch=True, certificate=True):
        self.current = S(
            run_id="synthetic_cal_01",
            trial_index=1,
            maximum_trials=6,
            phase=R.NOT_PREPARED,
        )
        self.allow_launch = allow_launch
        self.certificate = certificate
        self.launch_count = 0

    def snapshot(self):
        return self.current

    def prepare(self, snapshot):
        self.current = replace(snapshot, phase=R.PREPARED)

    def prepare_adaptation(self, snapshot, decision):
        index = decision.next_trial_index
        assert index is not None
        self.current = S(
            run_id=f"synthetic_cal_{index:02d}",
            trial_index=index,
            maximum_trials=6,
            phase=R.PREPARED,
        )

    def launch_authorized(self, snapshot):
        if not self.allow_launch:
            return False
        self.launch_count += 1
        self.current = replace(
            snapshot,
            phase=R.COMPLETED,
            completed_evidence_verified=True,
        )
        return True

    def assess_verified_physics(self, snapshot):
        physics = (
            P.ACCEPTED
            if snapshot.trial_index == 3
            else P.ADAPT
        )
        self.current = replace(
            snapshot,
            physics=physics,
            corrective_rule_id=(
                "governed_synthetic_delta_t"
                if physics is P.ADAPT
                else None
            ),
        )

    def verify_full_physics_certificate(self, snapshot):
        if not self.certificate:
            return False
        self.current = replace(
            snapshot,
            full_physics_acceptance_verified=True,
        )
        return True


def test_automatically_advances_multiple_governed_trials():
    factory = SyntheticFactory()
    result = drive_fem_supervisor(factory)
    assert result.stop is SupervisorStop.COMPLETE
    assert result.last_run_id == "synthetic_cal_03"
    assert factory.launch_count == 3


def test_capacity_or_authorization_deferral_never_launches():
    factory = SyntheticFactory(allow_launch=False)
    result = drive_fem_supervisor(factory)
    assert result.stop is SupervisorStop.WAIT_LAUNCH_GATE
    assert factory.launch_count == 0
    assert factory.snapshot().phase is R.PREPARED


def test_restart_recovers_prepared_state_without_repreparing():
    factory = SyntheticFactory(allow_launch=False)
    first = drive_fem_supervisor(factory)
    assert first.stop is SupervisorStop.WAIT_LAUNCH_GATE

    # Represents a fresh supervisor process reconstructing the
    # same prepared state through its evidence-backed adapter.
    factory.allow_launch = True
    second = drive_fem_supervisor(factory)

    assert second.stop is SupervisorStop.COMPLETE
    assert factory.launch_count == 3


def test_preload_or_physics_assessment_is_not_certification():
    factory = SyntheticFactory(certificate=False)
    result = drive_fem_supervisor(factory)
    assert result.stop is SupervisorStop.WAIT_PHYSICS_CERTIFICATE
    assert factory.launch_count == 3
    assert not factory.snapshot().full_physics_acceptance_verified


def test_uncertain_run_never_launches():
    factory = SyntheticFactory()
    factory.current = replace(
        factory.current,
        phase=R.UNCERTAIN,
    )
    result = drive_fem_supervisor(factory)
    assert result.stop is SupervisorStop.ENGINEERING_REVIEW
    assert factory.launch_count == 0


def test_running_run_waits_without_duplicate_launch():
    factory = SyntheticFactory()
    factory.current = replace(
        factory.current,
        phase=R.RUNNING,
    )
    result = drive_fem_supervisor(factory)
    assert result.stop is SupervisorStop.WAIT_RUNNING
    assert factory.launch_count == 0


def test_action_budget_bounds_supervisor():
    factory = SyntheticFactory()
    result = drive_fem_supervisor(factory, max_actions=2)
    assert result.stop is SupervisorStop.ACTION_BUDGET
    assert result.actions_performed == 2


def test_no_progress_fails_closed():
    factory = SyntheticFactory()
    factory.prepare = lambda snapshot: None
    with pytest.raises(RuntimeError, match="durable lifecycle transition"):
        drive_fem_supervisor(factory)

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RunPhase(str, Enum):
    NOT_PREPARED = "not_prepared"
    PREPARED = "prepared"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    UNCERTAIN = "uncertain"


class PhysicsDisposition(str, Enum):
    NOT_ASSESSED = "not_assessed"
    ACCEPTED = "accepted"
    ADAPT = "adapt"
    REVIEW_REQUIRED = "review_required"
    REJECTED = "rejected"


class LifecycleAction(str, Enum):
    PREPARE = "prepare"
    REQUEST_GOVERNED_LAUNCH = "request_governed_launch"
    WAIT_FOR_RUNNING_SOLVER = "wait_for_running_solver"
    ASSESS_VERIFIED_PHYSICS = "assess_verified_physics"
    PREPARE_GOVERNED_ADAPTATION = "prepare_governed_adaptation"
    REQUIRE_ACCEPTANCE_CERTIFICATION = "require_acceptance_certification"
    CERTIFIED_COMPLETE = "certified_complete"
    STOP_TRIAL_LIMIT = "stop_trial_limit"
    ENGINEERING_REVIEW = "engineering_review"


@dataclass(frozen=True, slots=True)
class FEMLifecycleSnapshot:
    run_id: str
    trial_index: int
    maximum_trials: int
    phase: RunPhase
    completed_evidence_verified: bool = False
    physics: PhysicsDisposition = PhysicsDisposition.NOT_ASSESSED
    corrective_rule_id: str | None = None
    full_physics_acceptance_verified: bool = False


@dataclass(frozen=True, slots=True)
class FEMLifecycleDecision:
    action: LifecycleAction
    next_trial_index: int | None = None
    corrective_rule_id: str | None = None


def decide_fem_lifecycle(
    snapshot: FEMLifecycleSnapshot,
) -> FEMLifecycleDecision:
    """Pure, model-independent planning; never executes or deletes FEM.

    A caller must independently verify evidence, physics certification,
    corrective-rule authorization and launch capacity. A returned action
    is never itself execution authorization.
    """

    if (
        not snapshot.run_id.strip()
        or type(snapshot.trial_index) is not int
        or type(snapshot.maximum_trials) is not int
        or not 1 <= snapshot.trial_index <= snapshot.maximum_trials
    ):
        raise RuntimeError("Invalid governed FEM trial bounds or identity.")

    if (
        snapshot.phase is not RunPhase.COMPLETED
        and (
            snapshot.completed_evidence_verified
            or snapshot.physics is not PhysicsDisposition.NOT_ASSESSED
            or snapshot.full_physics_acceptance_verified
        )
    ):
        raise RuntimeError(
            "Incomplete FEM run has contradictory completion evidence."
        )

    if snapshot.phase is RunPhase.UNCERTAIN:
        return FEMLifecycleDecision(
            LifecycleAction.ENGINEERING_REVIEW
        )

    if snapshot.phase is RunPhase.CLAIMED:
        # A durable claim without a confirmed running process is
        # uncertain, not permission to launch a replacement.
        return FEMLifecycleDecision(
            LifecycleAction.ENGINEERING_REVIEW
        )

    if snapshot.phase is RunPhase.RUNNING:
        return FEMLifecycleDecision(
            LifecycleAction.WAIT_FOR_RUNNING_SOLVER
        )

    if snapshot.phase is RunPhase.NOT_PREPARED:
        return FEMLifecycleDecision(
            LifecycleAction.PREPARE
        )

    if snapshot.phase is RunPhase.PREPARED:
        return FEMLifecycleDecision(
            LifecycleAction.REQUEST_GOVERNED_LAUNCH
        )

    if (
        snapshot.phase is not RunPhase.COMPLETED
        or not snapshot.completed_evidence_verified
    ):
        return FEMLifecycleDecision(
            LifecycleAction.ENGINEERING_REVIEW
        )

    if snapshot.physics is PhysicsDisposition.NOT_ASSESSED:
        return FEMLifecycleDecision(
            LifecycleAction.ASSESS_VERIFIED_PHYSICS
        )

    if snapshot.physics is PhysicsDisposition.ACCEPTED:
        if snapshot.full_physics_acceptance_verified:
            return FEMLifecycleDecision(
                LifecycleAction.CERTIFIED_COMPLETE
            )

        return FEMLifecycleDecision(
            LifecycleAction.REQUIRE_ACCEPTANCE_CERTIFICATION
        )

    if snapshot.full_physics_acceptance_verified:
        raise RuntimeError(
            "Full-physics acceptance conflicts with rejection."
        )

    if snapshot.physics is PhysicsDisposition.ADAPT:
        if (
            not snapshot.corrective_rule_id
            or not snapshot.corrective_rule_id.strip()
        ):
            return FEMLifecycleDecision(
                LifecycleAction.ENGINEERING_REVIEW
            )

        if snapshot.trial_index >= snapshot.maximum_trials:
            return FEMLifecycleDecision(
                LifecycleAction.STOP_TRIAL_LIMIT
            )

        return FEMLifecycleDecision(
            LifecycleAction.PREPARE_GOVERNED_ADAPTATION,
            next_trial_index=snapshot.trial_index + 1,
            corrective_rule_id=snapshot.corrective_rule_id,
        )

    return FEMLifecycleDecision(
        LifecycleAction.ENGINEERING_REVIEW
    )

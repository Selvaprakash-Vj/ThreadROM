from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from threadrom.factory.adaptive_fem_lifecycle import (
    FEMLifecycleDecision,
    FEMLifecycleSnapshot,
    LifecycleAction,
    decide_fem_lifecycle,
)


class SupervisorStop(str, Enum):
    COMPLETE = "complete"
    WAIT_RUNNING = "wait_running"
    WAIT_LAUNCH_GATE = "wait_launch_gate"
    WAIT_PHYSICS_CERTIFICATE = "wait_physics_certificate"
    ENGINEERING_REVIEW = "engineering_review"
    TRIAL_LIMIT = "trial_limit"
    ACTION_BUDGET = "action_budget"


@dataclass(frozen=True, slots=True)
class SupervisorResult:
    stop: SupervisorStop
    actions_performed: int
    last_run_id: str


class FEMFactoryPort(Protocol):
    """Model-specific implementation backed by durable evidence.

    launch_authorized MUST independently verify authorization,
    immutable input identity, duplicate protection and solver capacity.
    A False result means no solver was launched.
    """

    def snapshot(self) -> FEMLifecycleSnapshot: ...

    def prepare(self, snapshot: FEMLifecycleSnapshot) -> None: ...

    def prepare_adaptation(
        self,
        snapshot: FEMLifecycleSnapshot,
        decision: FEMLifecycleDecision,
    ) -> None: ...

    def launch_authorized(
        self,
        snapshot: FEMLifecycleSnapshot,
    ) -> bool: ...

    def assess_verified_physics(
        self,
        snapshot: FEMLifecycleSnapshot,
    ) -> None: ...

    def verify_full_physics_certificate(
        self,
        snapshot: FEMLifecycleSnapshot,
    ) -> bool: ...


def drive_fem_supervisor(
    port: FEMFactoryPort,
    *,
    max_actions: int = 24,
) -> SupervisorResult:
    """Advance governed FEM work until blocked or certified complete.

    Every snapshot must be recovered from durable, verified evidence.
    This function creates no authorization, solver process or files.
    It never retries an uncertain run or deletes an artifact.
    """

    if type(max_actions) is not int or max_actions < 1:
        raise ValueError("max_actions must be a positive integer.")

    performed = 0

    while True:
        before = port.snapshot()
        decision = decide_fem_lifecycle(before)
        action = decision.action

        stops = {
            LifecycleAction.CERTIFIED_COMPLETE:
                SupervisorStop.COMPLETE,
            LifecycleAction.WAIT_FOR_RUNNING_SOLVER:
                SupervisorStop.WAIT_RUNNING,
            LifecycleAction.ENGINEERING_REVIEW:
                SupervisorStop.ENGINEERING_REVIEW,
            LifecycleAction.STOP_TRIAL_LIMIT:
                SupervisorStop.TRIAL_LIMIT,
        }

        if action in stops:
            return SupervisorResult(
                stops[action],
                performed,
                before.run_id,
            )

        if performed >= max_actions:
            return SupervisorResult(
                SupervisorStop.ACTION_BUDGET,
                performed,
                before.run_id,
            )

        if action is LifecycleAction.PREPARE:
            port.prepare(before)

        elif action is LifecycleAction.PREPARE_GOVERNED_ADAPTATION:
            port.prepare_adaptation(before, decision)

        elif action is LifecycleAction.REQUEST_GOVERNED_LAUNCH:
            if not port.launch_authorized(before):
                return SupervisorResult(
                    SupervisorStop.WAIT_LAUNCH_GATE,
                    performed,
                    before.run_id,
                )

        elif action is LifecycleAction.ASSESS_VERIFIED_PHYSICS:
            port.assess_verified_physics(before)

        elif action is LifecycleAction.REQUIRE_ACCEPTANCE_CERTIFICATION:
            if not port.verify_full_physics_certificate(before):
                return SupervisorResult(
                    SupervisorStop.WAIT_PHYSICS_CERTIFICATE,
                    performed,
                    before.run_id,
                )

        else:
            raise RuntimeError(
                f"Unhandled universal FEM action: {action.value}"
            )

        after = port.snapshot()

        if after == before:
            raise RuntimeError(
                "FEM adapter reported success without a durable "
                "lifecycle transition. Refusing repeated execution."
            )

        # Recalculate the decision from verified evidence on EVERY
        # iteration; never assume a previous action succeeded.
        performed += 1

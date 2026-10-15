"""Pure autonomous state machine for one governed FEM wave.

This module owns wave-level continuation policy only.

It does not:
- create execution authorization,
- prepare FEM,
- launch CalculiX,
- certify physics,
- close a wave,
- access holdouts,
- admit ROM data.

The generic governed wave runner remains the execution engine.
Case-level FEM lifecycle authority remains below this layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class GovernedWavePhase(str, Enum):
    BLOCKED_AUTHORITY = "blocked_authority"
    WORK_REQUIRED = "work_required"
    WAITING_RUNNING = "waiting_running"
    ENGINEERING_REVIEW = "engineering_review"
    READY_FOR_CLOSURE = "ready_for_closure"
    CLOSED = "closed"


class GovernedWaveAction(str, Enum):
    NONE = "none"
    EXECUTE_GENERIC_RUNNER = "execute_generic_runner"
    WAIT_FOR_RUNNING_SOLVER = "wait_for_running_solver"
    REQUIRE_ENGINEERING_REVIEW = "require_engineering_review"
    REQUEST_WAVE_CLOSURE = "request_wave_closure"


class GovernedWaveStop(str, Enum):
    BLOCKED_AUTHORITY = "blocked_authority"
    WAIT_RUNNING = "wait_running"
    ENGINEERING_REVIEW = "engineering_review"
    READY_FOR_CLOSURE = "ready_for_closure"
    CLOSED = "closed"
    ACTION_BUDGET = "action_budget"


@dataclass(frozen=True, slots=True)
class GovernedCaseCampaignSnapshot:
    case_id: str
    full_physics_accepted: bool
    solver_running: bool = False
    terminal_blocked: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(
                self.case_id,
                str,
            )
            or not self.case_id.strip()
            or self.case_id != self.case_id.strip()
        ):
            raise ValueError(
                "Invalid governed case identity."
            )

        for name in (
            "full_physics_accepted",
            "solver_running",
            "terminal_blocked",
        ):
            if type(
                getattr(
                    self,
                    name,
                )
            ) is not bool:
                raise TypeError(
                    f"{name} must be bool."
                )

        if (
            self.full_physics_accepted
            and self.solver_running
        ):
            raise ValueError(
                "Accepted case cannot still have a running solver."
            )

        if (
            self.full_physics_accepted
            and self.terminal_blocked
        ):
            raise ValueError(
                "Accepted case cannot also be terminally blocked."
            )

        if (
            self.solver_running
            and self.terminal_blocked
        ):
            raise ValueError(
                "Running case cannot simultaneously require terminal review."
            )

    @property
    def requires_execution(self) -> bool:
        return not (
            self.full_physics_accepted
            or self.solver_running
            or self.terminal_blocked
        )


@dataclass(frozen=True, slots=True)
class GovernedWaveCampaignSnapshot:
    wave_id: str
    authority_verified: bool
    authorized_case_count: int
    cases: tuple[
        GovernedCaseCampaignSnapshot,
        ...,
    ]
    closure_verified: bool = False

    def __post_init__(self) -> None:
        if (
            not isinstance(
                self.wave_id,
                str,
            )
            or not self.wave_id.strip()
            or self.wave_id != self.wave_id.strip()
        ):
            raise ValueError(
                "Invalid governed wave identity."
            )

        if type(
            self.authority_verified
        ) is not bool:
            raise TypeError(
                "authority_verified must be bool."
            )

        if type(
            self.closure_verified
        ) is not bool:
            raise TypeError(
                "closure_verified must be bool."
            )

        if (
            type(
                self.authorized_case_count
            )
            is not int
            or self.authorized_case_count < 1
        ):
            raise ValueError(
                "Authorized case count must be positive."
            )

        if not isinstance(
            self.cases,
            tuple,
        ):
            raise TypeError(
                "cases must be a tuple."
            )

        if (
            len(
                self.cases
            )
            != self.authorized_case_count
        ):
            raise ValueError(
                "Governed wave case-count drift."
            )

        case_ids = tuple(
            case.case_id
            for case in self.cases
        )

        if len(
            case_ids
        ) != len(
            set(
                case_ids
            )
        ):
            raise ValueError(
                "Duplicate governed case identity."
            )

        if (
            self.closure_verified
            and not all(
                case.full_physics_accepted
                for case in self.cases
            )
        ):
            raise ValueError(
                "Wave closure cannot be verified before all cases "
                "have governed full-physics acceptance."
            )

    @property
    def accepted_case_count(self) -> int:
        return sum(
            case.full_physics_accepted
            for case in self.cases
        )

    @property
    def running_case_count(self) -> int:
        return sum(
            case.solver_running
            for case in self.cases
        )

    @property
    def blocked_case_count(self) -> int:
        return sum(
            case.terminal_blocked
            for case in self.cases
        )

    @property
    def work_required_case_count(self) -> int:
        return sum(
            case.requires_execution
            for case in self.cases
        )

    @property
    def all_cases_accepted(self) -> bool:
        return (
            self.accepted_case_count
            == self.authorized_case_count
        )


@dataclass(frozen=True, slots=True)
class GovernedWaveDecision:
    phase: GovernedWavePhase
    action: GovernedWaveAction
    reason: str


@dataclass(frozen=True, slots=True)
class GovernedWaveDriveResult:
    stop: GovernedWaveStop
    actions_performed: int
    final_snapshot: GovernedWaveCampaignSnapshot
    final_decision: GovernedWaveDecision


def decide_governed_wave_campaign(
    snapshot: GovernedWaveCampaignSnapshot,
) -> GovernedWaveDecision:
    """Pure wave-level decision function.

    A decision never grants execution authority.
    """

    if snapshot.closure_verified:
        return GovernedWaveDecision(
            phase=GovernedWavePhase.CLOSED,
            action=GovernedWaveAction.NONE,
            reason="Immutable governed wave closure is verified.",
        )

    if not snapshot.authority_verified:
        return GovernedWaveDecision(
            phase=GovernedWavePhase.BLOCKED_AUTHORITY,
            action=GovernedWaveAction.NONE,
            reason="Owner execution authority is not verified.",
        )

    if snapshot.blocked_case_count:
        return GovernedWaveDecision(
            phase=GovernedWavePhase.ENGINEERING_REVIEW,
            action=(
                GovernedWaveAction
                .REQUIRE_ENGINEERING_REVIEW
            ),
            reason=(
                "At least one governed case reached a terminal "
                "review condition."
            ),
        )

    if snapshot.all_cases_accepted:
        return GovernedWaveDecision(
            phase=GovernedWavePhase.READY_FOR_CLOSURE,
            action=(
                GovernedWaveAction
                .REQUEST_WAVE_CLOSURE
            ),
            reason=(
                "All authorized cases have governed full-physics "
                "acceptance; closure is the next governance boundary."
            ),
        )

    if snapshot.running_case_count:
        return GovernedWaveDecision(
            phase=GovernedWavePhase.WAITING_RUNNING,
            action=(
                GovernedWaveAction
                .WAIT_FOR_RUNNING_SOLVER
            ),
            reason=(
                "At least one governed solver is already running; "
                "replacement execution is forbidden."
            ),
        )

    if snapshot.work_required_case_count:
        return GovernedWaveDecision(
            phase=GovernedWavePhase.WORK_REQUIRED,
            action=(
                GovernedWaveAction
                .EXECUTE_GENERIC_RUNNER
            ),
            reason=(
                "Authorized incomplete cases require continuation "
                "through the generic governed wave runner."
            ),
        )

    raise RuntimeError(
        "Governed wave snapshot has no valid state-machine disposition."
    )


def drive_governed_wave_campaign(
    *,
    snapshot_supplier: Callable[
        [],
        GovernedWaveCampaignSnapshot,
    ],
    execute_generic_runner_once: Callable[
        [],
        None,
    ],
    max_runner_actions: int = 1,
) -> GovernedWaveDriveResult:
    """Autonomously advance a wave until the next governance boundary.

    One generic runner invocation is expected to recover durable history
    and continue its bounded adaptive campaign. The state machine never
    assumes that invocation succeeded: durable state is recovered again.

    Slice 5 owns wave-closure certification, so this driver stops at
    READY_FOR_CLOSURE rather than creating closure evidence itself.
    """

    if (
        type(
            max_runner_actions
        )
        is not int
        or max_runner_actions < 1
    ):
        raise ValueError(
            "max_runner_actions must be a positive integer."
        )

    actions = 0

    while True:
        before = snapshot_supplier()

        if not isinstance(
            before,
            GovernedWaveCampaignSnapshot,
        ):
            raise TypeError(
                "snapshot_supplier returned an invalid wave snapshot."
            )

        decision = decide_governed_wave_campaign(
            before
        )

        stop_by_action = {
            GovernedWaveAction.NONE: (
                GovernedWaveStop.CLOSED
                if decision.phase
                is GovernedWavePhase.CLOSED
                else GovernedWaveStop.BLOCKED_AUTHORITY
            ),
            GovernedWaveAction.WAIT_FOR_RUNNING_SOLVER: (
                GovernedWaveStop.WAIT_RUNNING
            ),
            GovernedWaveAction.REQUIRE_ENGINEERING_REVIEW: (
                GovernedWaveStop.ENGINEERING_REVIEW
            ),
            GovernedWaveAction.REQUEST_WAVE_CLOSURE: (
                GovernedWaveStop.READY_FOR_CLOSURE
            ),
        }

        if decision.action in stop_by_action:
            return GovernedWaveDriveResult(
                stop=stop_by_action[
                    decision.action
                ],
                actions_performed=actions,
                final_snapshot=before,
                final_decision=decision,
            )

        if (
            decision.action
            is not GovernedWaveAction.EXECUTE_GENERIC_RUNNER
        ):
            raise RuntimeError(
                "Unhandled governed wave action."
            )

        if actions >= max_runner_actions:
            return GovernedWaveDriveResult(
                stop=GovernedWaveStop.ACTION_BUDGET,
                actions_performed=actions,
                final_snapshot=before,
                final_decision=decision,
            )

        execute_generic_runner_once()

        after = snapshot_supplier()

        if not isinstance(
            after,
            GovernedWaveCampaignSnapshot,
        ):
            raise TypeError(
                "snapshot_supplier returned an invalid post-action snapshot."
            )

        if after == before:
            raise RuntimeError(
                "Generic governed runner returned without a durable "
                "wave-state transition. Refusing repeated execution."
            )

        actions += 1
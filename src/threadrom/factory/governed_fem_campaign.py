
"""Reusable governed FEM campaign orchestration.

This module does not issue solver authorization, physics certificates,
or artifact-retirement permits. Those remain separate governed
responsibilities of the registered case implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol, Sequence

from threadrom.factory.adaptive_fem_lifecycle import (
    LifecycleAction,
    decide_fem_lifecycle,
)
from threadrom.factory.adaptive_fem_supervisor import (
    SupervisorStop,
    drive_fem_supervisor,
)


class GovernedCasePort(Protocol):
    case_id: str

    def snapshot(self): ...


@dataclass(frozen=True)
class CaseCycleOutcome:
    case_id: str
    run_id: str
    action: str
    stop: SupervisorStop | None
    actions_performed: int


@dataclass(frozen=True)
class CampaignCycleOutcome:
    cases: tuple[CaseCycleOutcome, ...]
    all_done: bool
    blocked: bool


def run_governed_campaign_cycle(
    *,
    case_ids: Sequence[str],
    registrations: Mapping[
        str, Callable[[], GovernedCasePort]
    ],
    execute: bool = False,
    max_actions_per_case: int = 24,
) -> CampaignCycleOutcome:
    """Drive explicitly registered cases through the shared supervisor.

    Registration does not itself grant execution authorization.
    The registered port and downstream execution machinery remain
    responsible for verifying every applicable authorization.
    """

    selected = tuple(case_ids)

    if not selected:
        raise ValueError("No governed cases selected.")

    if max_actions_per_case < 1:
        raise ValueError("Action budget must be positive.")

    if any(
        not isinstance(case_id, str) or not case_id.strip()
        for case_id in selected
    ):
        raise ValueError("Invalid governed case identity.")

    if len(selected) != len(set(selected)):
        raise ValueError("Duplicate governed case selection.")

    missing = [
        case_id
        for case_id in selected
        if case_id not in registrations
    ]

    if missing:
        raise ValueError(
            "Unregistered governed cases: "
            + ", ".join(missing)
        )

    outcomes = []
    all_done = True
    blocked = False

    for case_id in selected:
        port = registrations[case_id]()

        if port.case_id != case_id:
            raise RuntimeError(
                "Registered factory port returned a different case."
            )

        if not execute:
            snapshot = port.snapshot()
            decision = decide_fem_lifecycle(snapshot)

            complete = (
                decision.action
                is LifecycleAction.CERTIFIED_COMPLETE
            )

            if not complete:
                all_done = False

            if decision.action is LifecycleAction.ENGINEERING_REVIEW:
                blocked = True

            outcomes.append(
                CaseCycleOutcome(
                    case_id=case_id,
                    run_id=snapshot.run_id,
                    action=decision.action.value,
                    stop=None,
                    actions_performed=0,
                )
            )

            continue

        # The supervisor remains the single lifecycle authority.
        # Actual launches remain guarded by the registered port.
        result = drive_fem_supervisor(
            port,
            max_actions=max_actions_per_case,
        )

        complete = result.stop is SupervisorStop.COMPLETE

        if not complete:
            all_done = False

        if result.stop in {
            SupervisorStop.ENGINEERING_REVIEW,
            SupervisorStop.TRIAL_LIMIT,
        }:
            blocked = True

        outcomes.append(
            CaseCycleOutcome(
                case_id=case_id,
                run_id=result.last_run_id,
                action=result.stop.value,
                stop=result.stop,
                actions_performed=result.actions_performed,
            )
        )

    return CampaignCycleOutcome(
        cases=tuple(outcomes),
        all_done=all_done,
        blocked=blocked,
    )

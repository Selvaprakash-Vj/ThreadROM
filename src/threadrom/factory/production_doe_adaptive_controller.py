from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from threadrom.factory.preload_calibration_controller import (
    PreloadCalibrationDisposition,
)


class AdaptiveCalibrationAction(str, Enum):
    CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS = (
        "calibration_accepted_pending_full_physics"
    )
    NEXT_TRIAL_REQUIRES_AUTHORIZATION = (
        "next_trial_requires_authorization"
    )


@dataclass(frozen=True, slots=True)
class AdaptiveCalibrationPlan:
    action: AdaptiveCalibrationAction
    completed_run_id: str
    next_run_id: str | None = None


def plan_adaptive_calibration(
    *,
    case_run_id: str,
    evaluation,
    maximum_trials: int,
) -> AdaptiveCalibrationPlan:
    """Plan a C01 calibration continuation. Never authorizes or runs FEM."""

    if not case_run_id.startswith("trm_fem_"):
        raise ValueError("Invalid Production DOE case-run identity.")

    if maximum_trials < 2:
        raise ValueError("Invalid governed calibration trial limit.")

    current = evaluation.completed_trial
    next_trial = evaluation.next_trial
    disposition = evaluation.decision.disposition

    if (
        current.trial_index < 1
        or current.trial_index > maximum_trials
        or not current.run_id.startswith(
            f"{case_run_id}_cal_{current.trial_index:02d}"
        )
    ):
        raise RuntimeError("Completed calibration-trial identity drift.")

    if disposition is PreloadCalibrationDisposition.ACCEPT:
        if not evaluation.accepted or next_trial is not None:
            raise RuntimeError("Inconsistent calibration ACCEPT evidence.")

        return AdaptiveCalibrationPlan(
            action=(
                AdaptiveCalibrationAction
                .CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS
            ),
            completed_run_id=current.run_id,
        )

    if disposition is not PreloadCalibrationDisposition.CONTINUE:
        raise RuntimeError(
            f"Calibration stopped without acceptance: {disposition!s}"
        )

    if evaluation.accepted or next_trial is None:
        raise RuntimeError(
            "CONTINUE has inconsistent acceptance or next-trial evidence."
        )

    if current.trial_index >= maximum_trials:
        raise RuntimeError("Governed calibration trial limit reached.")

    expected_next_index = current.trial_index + 1
    expected_next_run_id = (
        f"{case_run_id}_cal_{expected_next_index:02d}"
    )

    if (
        next_trial.trial_index != expected_next_index
        or next_trial.run_id != expected_next_run_id
    ):
        raise RuntimeError(
            "Next calibration trial does not follow the governed lineage."
        )

    return AdaptiveCalibrationPlan(
        action=(
            AdaptiveCalibrationAction
            .NEXT_TRIAL_REQUIRES_AUTHORIZATION
        ),
        completed_run_id=current.run_id,
        next_run_id=next_trial.run_id,
    )

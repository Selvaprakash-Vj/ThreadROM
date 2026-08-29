"""Governed automatic thermal-preload calibration campaign."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from threadrom.factory.preload_calibration import (
    PreloadCalibrationPoint,
)
from threadrom.factory.preload_calibration_controller import (
    ClampForceMeasurement,
    PreloadCalibrationDecision,
    PreloadCalibrationDisposition,
    evaluate_preload_calibration,
)
from threadrom.factory.preload_calibration_seed import (
    ThermalPreloadCalibrationSeed,
)


class PreloadCalibrationTrialSource(StrEnum):
    """Derivation source for one calibration trial temperature."""

    ANALYTICAL_SEED = "analytical_seed"
    PROPORTIONAL = "proportional"
    FALLBACK_PERTURBATION = "fallback_perturbation"
    SECANT = "secant"


@dataclass(frozen=True, slots=True)
class PreloadCalibrationCampaignPolicy:
    """Algorithmic controls for an automatic calibration campaign."""

    maximum_trials: int = 6
    minimum_second_trial_relative_separation: float = 0.05
    fallback_second_trial_scale: float = 0.80

    def __post_init__(self) -> None:
        if self.maximum_trials < 2:
            raise ValueError(
                "Preload calibration requires at least two "
                "permitted trials."
            )

        if not (
            0.0
            < self.minimum_second_trial_relative_separation
            < 1.0
        ):
            raise ValueError(
                "Minimum second-trial relative separation "
                "must lie in (0, 1)."
            )

        if not (
            0.0
            < self.fallback_second_trial_scale
            < 1.0
        ):
            raise ValueError(
                "Fallback second-trial scale must lie in (0, 1)."
            )


@dataclass(frozen=True, slots=True)
class PreloadCalibrationTrial:
    """One governed thermal-preload FEM calibration trial."""

    trial_index: int
    run_id: str
    delta_temperature_c: float
    source: PreloadCalibrationTrialSource

    def __post_init__(self) -> None:
        if self.trial_index < 1:
            raise ValueError(
                "Calibration trial index must be positive."
            )

        if not self.run_id.strip():
            raise ValueError(
                "Calibration trial run_id must not be blank."
            )

        if (
            not math.isfinite(self.delta_temperature_c)
            or self.delta_temperature_c >= 0.0
        ):
            raise ValueError(
                "Calibration trial temperature must represent "
                "finite contraction."
            )


@dataclass(frozen=True, slots=True)
class PreloadCalibrationTrialEvaluation:
    """Decision and optional automatically derived next trial."""

    decision: PreloadCalibrationDecision
    completed_trial: PreloadCalibrationTrial
    next_trial: PreloadCalibrationTrial | None

    @property
    def accepted(self) -> bool:
        return (
            self.decision.disposition
            is PreloadCalibrationDisposition.ACCEPT
        )


def _trial_run_id(
    *,
    case_run_id: str,
    trial_index: int,
) -> str:
    if not case_run_id.strip():
        raise ValueError(
            "Case FEM run_id must not be blank."
        )

    return (
        f"{case_run_id}_cal_{trial_index:02d}"
    )


def derive_initial_preload_calibration_trial(
    *,
    seed: ThermalPreloadCalibrationSeed,
    case_run_id: str,
) -> PreloadCalibrationTrial:
    """Create trial 1 directly from the analytical compatibility seed."""

    return PreloadCalibrationTrial(
        trial_index=1,
        run_id=_trial_run_id(
            case_run_id=case_run_id,
            trial_index=1,
        ),
        delta_temperature_c=(
            seed.predicted_delta_temperature_c
        ),
        source=(
            PreloadCalibrationTrialSource.ANALYTICAL_SEED
        ),
    )


def _derive_second_trial_delta_temperature(
    *,
    target_force_n: float,
    current_trial: PreloadCalibrationTrial,
    measurement: ClampForceMeasurement,
    policy: PreloadCalibrationCampaignPolicy,
) -> tuple[
    float,
    PreloadCalibrationTrialSource,
]:
    """Derive an independent second point without a manual temperature."""

    proportional = (
        current_trial.delta_temperature_c
        * target_force_n
        / measurement.mean_force_n
    )

    if (
        not math.isfinite(proportional)
        or proportional >= 0.0
    ):
        raise ValueError(
            "Proportional calibration update did not produce "
            "finite thermal contraction."
        )

    relative_separation = abs(
        (
            proportional
            - current_trial.delta_temperature_c
        )
        / current_trial.delta_temperature_c
    )

    if (
        relative_separation
        >= policy.minimum_second_trial_relative_separation
    ):
        return (
            proportional,
            PreloadCalibrationTrialSource.PROPORTIONAL,
        )

    fallback = (
        current_trial.delta_temperature_c
        * policy.fallback_second_trial_scale
    )

    return (
        fallback,
        PreloadCalibrationTrialSource.FALLBACK_PERTURBATION,
    )


def evaluate_preload_calibration_trial(
    *,
    case_run_id: str,
    target_force_n: float,
    target_relative_tolerance: float,
    spread_relative_tolerance: float,
    current_trial: PreloadCalibrationTrial,
    measurement: ClampForceMeasurement,
    previous_trial: PreloadCalibrationTrial | None = None,
    previous_measurement: ClampForceMeasurement | None = None,
    policy: PreloadCalibrationCampaignPolicy = (
        PreloadCalibrationCampaignPolicy()
    ),
) -> PreloadCalibrationTrialEvaluation:
    """Evaluate one solved trial and derive the next trial if required."""

    if (
        (previous_trial is None)
        != (previous_measurement is None)
    ):
        raise ValueError(
            "Previous calibration trial and measurement "
            "must be provided together."
        )

    previous_point = None

    if previous_trial is not None:
        assert previous_measurement is not None

        if (
            previous_trial.trial_index
            >= current_trial.trial_index
        ):
            raise ValueError(
                "Previous calibration trial must precede "
                "the current trial."
            )

        previous_point = PreloadCalibrationPoint(
            delta_temperature_c=(
                previous_trial.delta_temperature_c
            ),
            measured_force_n=(
                previous_measurement.mean_force_n
            ),
        )

    decision = evaluate_preload_calibration(
        target_force_n=target_force_n,
        target_relative_tolerance=(
            target_relative_tolerance
        ),
        spread_relative_tolerance=(
            spread_relative_tolerance
        ),
        measurement=measurement,
        previous_point=previous_point,
        current_delta_temperature_c=(
            current_trial.delta_temperature_c
        ),
    )

    if (
        decision.disposition
        is PreloadCalibrationDisposition.ACCEPT
    ):
        return PreloadCalibrationTrialEvaluation(
            decision=decision,
            completed_trial=current_trial,
            next_trial=None,
        )

    next_index = current_trial.trial_index + 1

    if next_index > policy.maximum_trials:
        raise RuntimeError(
            "Preload calibration exceeded the governed "
            "maximum trial count."
        )

    if previous_point is None:
        (
            next_delta_temperature_c,
            source,
        ) = _derive_second_trial_delta_temperature(
            target_force_n=target_force_n,
            current_trial=current_trial,
            measurement=measurement,
            policy=policy,
        )
    else:
        next_delta_temperature_c = (
            decision.next_delta_temperature_c
        )

        if next_delta_temperature_c is None:
            raise RuntimeError(
                "Secant calibration continuation did not "
                "produce a next trial temperature."
            )

        source = PreloadCalibrationTrialSource.SECANT

    next_trial = PreloadCalibrationTrial(
        trial_index=next_index,
        run_id=_trial_run_id(
            case_run_id=case_run_id,
            trial_index=next_index,
        ),
        delta_temperature_c=(
            next_delta_temperature_c
        ),
        source=source,
    )

    return PreloadCalibrationTrialEvaluation(
        decision=decision,
        completed_trial=current_trial,
        next_trial=next_trial,
    )

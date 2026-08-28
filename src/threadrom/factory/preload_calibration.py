"""Governed thermal-preload calibration mathematics."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PreloadCalibrationPoint:
    """One solved thermal-preload calibration observation."""

    delta_temperature_c: float
    measured_force_n: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.delta_temperature_c):
            raise ValueError(
                "delta_temperature_c must be finite."
            )
        if self.delta_temperature_c >= 0.0:
            raise ValueError(
                "Thermal preload calibration requires contraction."
            )
        if (
            not math.isfinite(self.measured_force_n)
            or self.measured_force_n <= 0.0
        ):
            raise ValueError(
                "measured_force_n must be finite and positive."
            )


@dataclass(frozen=True, slots=True)
class SecantCalibrationResult:
    """Result of a two-point thermal-preload secant update."""

    target_force_n: float
    first: PreloadCalibrationPoint
    second: PreloadCalibrationPoint
    force_slope_n_per_c: float
    predicted_delta_temperature_c: float


def derive_secant_delta_temperature(
    *,
    target_force_n: float,
    first: PreloadCalibrationPoint,
    second: PreloadCalibrationPoint,
) -> SecantCalibrationResult:
    """Predict the thermal contraction needed for target preload.

    The calibration uses solved physical clamp-force observations.
    No geometry-, material-, mesh- or preload-specific temperature
    is embedded in this algorithm.
    """

    if not math.isfinite(target_force_n) or target_force_n <= 0.0:
        raise ValueError(
            "target_force_n must be finite and positive."
        )

    delta_temperature_difference = (
        second.delta_temperature_c
        - first.delta_temperature_c
    )

    if math.isclose(
        delta_temperature_difference,
        0.0,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise ValueError(
            "Calibration temperatures must be distinct."
        )

    force_difference = (
        second.measured_force_n
        - first.measured_force_n
    )

    if math.isclose(
        force_difference,
        0.0,
        rel_tol=0.0,
        abs_tol=1.0e-9,
    ):
        raise ValueError(
            "Calibration forces must be distinct."
        )

    slope = (
        force_difference
        / delta_temperature_difference
    )

    # For positive thermal expansion coefficient, increasing
    # contraction means a more-negative delta T and greater clamp
    # force. Therefore dF/d(deltaT) must be negative.
    if slope >= 0.0:
        raise ValueError(
            "Calibration points have non-physical thermal "
            "preload direction."
        )

    predicted_delta_temperature_c = (
        first.delta_temperature_c
        + (
            target_force_n
            - first.measured_force_n
        )
        / slope
    )

    if (
        not math.isfinite(predicted_delta_temperature_c)
        or predicted_delta_temperature_c >= 0.0
    ):
        raise ValueError(
            "Predicted preload temperature must represent "
            "finite thermal contraction."
        )

    return SecantCalibrationResult(
        target_force_n=target_force_n,
        first=first,
        second=second,
        force_slope_n_per_c=slope,
        predicted_delta_temperature_c=(
            predicted_delta_temperature_c
        ),
    )

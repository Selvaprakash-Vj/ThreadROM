"""Governed preload-calibration measurement and decisions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from threadrom.factory.preload_calibration import (
    PreloadCalibrationPoint,
    derive_secant_delta_temperature,
)


class PreloadCalibrationDisposition(StrEnum):
    """Outcome of one preload-calibration evaluation."""

    ACCEPT = "accept"
    CONTINUE = "continue"


@dataclass(frozen=True, slots=True)
class ClampForceMeasurement:
    """Physical clamp-force resultants from the three planar paths."""

    under_head_force_n: float
    nut_bearing_force_n: float
    member_interface_force_n: float

    def __post_init__(self) -> None:
        values = (
            self.under_head_force_n,
            self.nut_bearing_force_n,
            self.member_interface_force_n,
        )
        if any(
            not math.isfinite(value) or value <= 0.0
            for value in values
        ):
            raise ValueError(
                "Clamp forces must be finite and positive."
            )

    @property
    def mean_force_n(self) -> float:
        return (
            self.under_head_force_n
            + self.nut_bearing_force_n
            + self.member_interface_force_n
        ) / 3.0

    @property
    def spread_n(self) -> float:
        values = (
            self.under_head_force_n,
            self.nut_bearing_force_n,
            self.member_interface_force_n,
        )
        return max(values) - min(values)

    @property
    def spread_relative(self) -> float:
        return self.spread_n / self.mean_force_n


@dataclass(frozen=True, slots=True)
class PreloadCalibrationDecision:
    """Acceptance state for one solved preload trial."""

    disposition: PreloadCalibrationDisposition
    target_force_n: float
    target_relative_tolerance: float
    spread_relative_tolerance: float
    measurement: ClampForceMeasurement
    target_relative_error: float
    next_delta_temperature_c: float | None


def evaluate_preload_calibration(
    *,
    target_force_n: float,
    target_relative_tolerance: float,
    spread_relative_tolerance: float,
    measurement: ClampForceMeasurement,
    previous_point: PreloadCalibrationPoint | None,
    current_delta_temperature_c: float,
) -> PreloadCalibrationDecision:
    """Accept a solved trial or derive the next secant trial."""

    if not math.isfinite(target_force_n) or target_force_n <= 0.0:
        raise ValueError(
            "target_force_n must be finite and positive."
        )

    for name, value in (
        (
            "target_relative_tolerance",
            target_relative_tolerance,
        ),
        (
            "spread_relative_tolerance",
            spread_relative_tolerance,
        ),
    ):
        if not math.isfinite(value) or not 0.0 < value < 1.0:
            raise ValueError(
                f"{name} must be finite and in (0, 1)."
            )

    if (
        not math.isfinite(current_delta_temperature_c)
        or current_delta_temperature_c >= 0.0
    ):
        raise ValueError(
            "current_delta_temperature_c must represent "
            "finite contraction."
        )

    target_relative_error = (
        measurement.mean_force_n - target_force_n
    ) / target_force_n

    force_pass = (
        abs(target_relative_error)
        <= target_relative_tolerance
    )
    spread_pass = (
        measurement.spread_relative
        <= spread_relative_tolerance
    )

    if force_pass and spread_pass:
        return PreloadCalibrationDecision(
            disposition=PreloadCalibrationDisposition.ACCEPT,
            target_force_n=target_force_n,
            target_relative_tolerance=target_relative_tolerance,
            spread_relative_tolerance=spread_relative_tolerance,
            measurement=measurement,
            target_relative_error=target_relative_error,
            next_delta_temperature_c=None,
        )

    if previous_point is None:
        return PreloadCalibrationDecision(
            disposition=PreloadCalibrationDisposition.CONTINUE,
            target_force_n=target_force_n,
            target_relative_tolerance=target_relative_tolerance,
            spread_relative_tolerance=spread_relative_tolerance,
            measurement=measurement,
            target_relative_error=target_relative_error,
            next_delta_temperature_c=None,
        )

    current_point = PreloadCalibrationPoint(
        delta_temperature_c=current_delta_temperature_c,
        measured_force_n=measurement.mean_force_n,
    )

    secant = derive_secant_delta_temperature(
        target_force_n=target_force_n,
        first=previous_point,
        second=current_point,
    )

    return PreloadCalibrationDecision(
        disposition=PreloadCalibrationDisposition.CONTINUE,
        target_force_n=target_force_n,
        target_relative_tolerance=target_relative_tolerance,
        spread_relative_tolerance=spread_relative_tolerance,
        measurement=measurement,
        target_relative_error=target_relative_error,
        next_delta_temperature_c=(
            secant.predicted_delta_temperature_c
        ),
    )

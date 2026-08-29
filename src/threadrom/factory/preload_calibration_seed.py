"""Physics-derived initial thermal-preload calibration seed."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.case.resolved_case import ResolvedCase
from threadrom.engineering.analytical_bolt_mechanics import (
    calculate_analytical_bolt_mechanics,
)
from threadrom.engineering.analytical_member_mechanics import (
    calculate_analytical_member_mechanics,
)
from threadrom.factory.analytical_adapter import (
    build_analytical_joint_input,
)


@dataclass(frozen=True, slots=True)
class ThermalPreloadCalibrationSeed:
    """Deterministic analytical first trial for FEM preload calibration."""

    target_force_n: float
    bolt_compliance_mm_per_n: float
    member_compliance_mm_per_n: float
    total_compliance_mm_per_n: float
    effective_bolt_length_mm: float
    expansion_coefficient_per_c: float
    predicted_delta_temperature_c: float

    def __post_init__(self) -> None:
        positive_values = (
            self.target_force_n,
            self.bolt_compliance_mm_per_n,
            self.member_compliance_mm_per_n,
            self.total_compliance_mm_per_n,
            self.effective_bolt_length_mm,
            self.expansion_coefficient_per_c,
        )

        if any(
            not math.isfinite(value)
            or value <= 0.0
            for value in positive_values
        ):
            raise ValueError(
                "Thermal preload calibration seed inputs "
                "must be finite and positive."
            )

        if (
            not math.isfinite(
                self.predicted_delta_temperature_c
            )
            or self.predicted_delta_temperature_c >= 0.0
        ):
            raise ValueError(
                "Predicted thermal preload seed must represent "
                "finite contraction."
            )


def derive_analytical_thermal_preload_seed(
    resolved: ResolvedCase,
) -> ThermalPreloadCalibrationSeed:
    """Derive the first FEM preload trial from analytical compatibility.

    Compatibility for the clamped linear-elastic approximation is

        alpha * abs(deltaT) * L_eff
            = F_target * (C_bolt + C_member)

    The FEM calibration campaign is responsible for correcting this
    analytical first estimate using solved physical clamp-force data.
    """

    joint = build_analytical_joint_input(
        resolved
    )

    bolt = calculate_analytical_bolt_mechanics(
        joint
    )

    member = calculate_analytical_member_mechanics(
        joint
    )

    coefficient = (
        resolved.bolt_material.thermal_expansion_per_c
    )

    if coefficient is None:
        raise ValueError(
            "Analytical thermal preload seeding requires a governed "
            "bolt thermal expansion coefficient."
        )

    total_compliance_mm_per_n = (
        bolt.total_compliance_mm_per_n
        + member.total_compliance_mm_per_n
    )

    predicted_delta_temperature_c = -(
        resolved.source_case.loading.target_preload_n
        * total_compliance_mm_per_n
        / (
            coefficient
            * bolt.effective_length_mm
        )
    )

    return ThermalPreloadCalibrationSeed(
        target_force_n=(
            resolved.source_case.loading.target_preload_n
        ),
        bolt_compliance_mm_per_n=(
            bolt.total_compliance_mm_per_n
        ),
        member_compliance_mm_per_n=(
            member.total_compliance_mm_per_n
        ),
        total_compliance_mm_per_n=(
            total_compliance_mm_per_n
        ),
        effective_bolt_length_mm=(
            bolt.effective_length_mm
        ),
        expansion_coefficient_per_c=coefficient,
        predicted_delta_temperature_c=(
            predicted_delta_temperature_c
        ),
    )

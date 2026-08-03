"""Physics-consistency validation for analytical member mechanics."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.engineering.analytical_member_mechanics import (
    AnalyticalMemberMechanics,
)


@dataclass(frozen=True)
class MemberMechanicsValidationCheck:
    """One deterministic member-mechanics validation check."""

    check_id: str
    passed: bool
    description: str


@dataclass(frozen=True)
class AnalyticalMemberMechanicsValidation:
    """Validation evidence for one member-mechanics result."""

    method: str
    checks: tuple[MemberMechanicsValidationCheck, ...]

    @property
    def passed(self) -> bool:
        """Return whether every validation check passed."""

        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        """Return the identities of failed checks."""

        return tuple(check.check_id for check in self.checks if not check.passed)

    def require_valid(self) -> None:
        """Raise when any member-mechanics check fails."""

        if self.passed:
            return

        failed = ", ".join(self.failed_check_ids)

        raise ValueError(f"Analytical member-mechanics validation failed: {failed}")


def validate_analytical_member_mechanics(
    mechanics: AnalyticalMemberMechanics,
) -> AnalyticalMemberMechanicsValidation:
    """Validate deterministic member-compression identities."""

    positive_layer_properties = all(
        layer.thickness_mm > 0.0
        and layer.compression_area_mm2 > 0.0
        and layer.youngs_modulus_mpa > 0.0
        and layer.compliance_mm_per_n > 0.0
        for layer in mechanics.layers
    )

    compliance_sum = sum(layer.compliance_mm_per_n for layer in mechanics.layers)

    compliance_sum_consistent = math.isclose(
        mechanics.total_compliance_mm_per_n,
        compliance_sum,
        rel_tol=1.0e-12,
        abs_tol=1.0e-15,
    )

    stiffness_reciprocal_consistent = math.isclose(
        mechanics.axial_stiffness_n_per_mm,
        1.0 / mechanics.total_compliance_mm_per_n,
        rel_tol=1.0e-12,
        abs_tol=1.0e-9,
    )

    expected_shortening = mechanics.preload_n * mechanics.total_compliance_mm_per_n

    force_displacement_consistent = math.isclose(
        mechanics.total_shortening_mm,
        expected_shortening,
        rel_tol=1.0e-12,
        abs_tol=1.0e-15,
    )

    shortening_sum = sum(layer.shortening_mm for layer in mechanics.layers)

    shortening_sum_consistent = math.isclose(
        mechanics.total_shortening_mm,
        shortening_sum,
        rel_tol=1.0e-12,
        abs_tol=1.0e-15,
    )

    expected_energy = 0.5 * mechanics.preload_n * mechanics.total_shortening_mm

    strain_energy_consistent = math.isclose(
        mechanics.total_strain_energy_n_mm,
        expected_energy,
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    thickness_sum = sum(layer.thickness_mm for layer in mechanics.layers)

    thickness_sum_consistent = math.isclose(
        mechanics.total_thickness_mm,
        thickness_sum,
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    minimum_area = min(layer.compression_area_mm2 for layer in mechanics.layers)

    minimum_area_consistent = math.isclose(
        mechanics.minimum_compression_area_mm2,
        minimum_area,
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    maximum_stress = max(layer.compressive_stress_mpa for layer in mechanics.layers)

    maximum_stress_consistent = math.isclose(
        mechanics.maximum_compressive_stress_mpa,
        maximum_stress,
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    positive_bearing_areas = (
        mechanics.head_bearing_area_mm2 > 0.0 and mechanics.nut_bearing_area_mm2 > 0.0
    )

    head_bearing_pressure_consistent = math.isclose(
        mechanics.head_mean_bearing_pressure_mpa,
        (mechanics.preload_n / mechanics.head_bearing_area_mm2),
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    nut_bearing_pressure_consistent = math.isclose(
        mechanics.nut_mean_bearing_pressure_mpa,
        (mechanics.preload_n / mechanics.nut_bearing_area_mm2),
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    checks = (
        MemberMechanicsValidationCheck(
            check_id="nonempty_layers",
            passed=bool(mechanics.layers),
            description=("At least one effective member layer must be present."),
        ),
        MemberMechanicsValidationCheck(
            check_id="positive_layer_properties",
            passed=positive_layer_properties,
            description=(
                "Every member layer must have positive thickness, "
                "compression area, modulus and compliance."
            ),
        ),
        MemberMechanicsValidationCheck(
            check_id="compliance_sum",
            passed=compliance_sum_consistent,
            description=(
                "Total member compliance must equal the sum of the series-layer compliances."
            ),
        ),
        MemberMechanicsValidationCheck(
            check_id="stiffness_reciprocal",
            passed=stiffness_reciprocal_consistent,
            description=("Member stiffness must equal the reciprocal of total compliance."),
        ),
        MemberMechanicsValidationCheck(
            check_id="force_displacement_identity",
            passed=force_displacement_consistent,
            description=(
                "Total shortening must equal preload multiplied by total member compliance."
            ),
        ),
        MemberMechanicsValidationCheck(
            check_id="layer_shortening_sum",
            passed=shortening_sum_consistent,
            description=("Total shortening must equal the sum of all layer shortenings."),
        ),
        MemberMechanicsValidationCheck(
            check_id="strain_energy_identity",
            passed=strain_energy_consistent,
            description=(
                "Linear-elastic member strain energy must equal "
                "one-half force multiplied by shortening."
            ),
        ),
        MemberMechanicsValidationCheck(
            check_id="thickness_sum",
            passed=thickness_sum_consistent,
            description=("Total member thickness must equal the sum of all layer thicknesses."),
        ),
        MemberMechanicsValidationCheck(
            check_id="minimum_compression_area",
            passed=minimum_area_consistent,
            description=(
                "Reported minimum compression area must equal the smallest resolved layer area."
            ),
        ),
        MemberMechanicsValidationCheck(
            check_id="maximum_compressive_stress",
            passed=maximum_stress_consistent,
            description=(
                "Reported maximum compressive stress must equal the maximum resolved layer stress."
            ),
        ),
        MemberMechanicsValidationCheck(
            check_id="positive_bearing_areas",
            passed=positive_bearing_areas,
            description=("Head-side and nut-side bearing areas must be positive."),
        ),
        MemberMechanicsValidationCheck(
            check_id="head_bearing_pressure",
            passed=head_bearing_pressure_consistent,
            description=(
                "Head-side mean bearing pressure must equal preload divided by head bearing area."
            ),
        ),
        MemberMechanicsValidationCheck(
            check_id="nut_bearing_pressure",
            passed=nut_bearing_pressure_consistent,
            description=(
                "Nut-side mean bearing pressure must equal preload divided by nut bearing area."
            ),
        ),
    )

    return AnalyticalMemberMechanicsValidation(
        method="linear_member_compression_invariants_v1",
        checks=checks,
    )

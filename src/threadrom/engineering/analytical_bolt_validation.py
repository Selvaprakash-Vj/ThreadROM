"""Physics-consistency validation for analytical bolt mechanics."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.engineering.analytical_bolt_mechanics import (
    AnalyticalBoltMechanics,
)


@dataclass(frozen=True)
class BoltMechanicsValidationCheck:
    """One deterministic bolt-mechanics validation check."""

    check_id: str
    passed: bool
    description: str


@dataclass(frozen=True)
class AnalyticalBoltMechanicsValidation:
    """Validation evidence for one analytical bolt result."""

    method: str
    checks: tuple[BoltMechanicsValidationCheck, ...]

    @property
    def passed(self) -> bool:
        """Return whether every validation check passed."""

        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        """Return the identities of failed checks."""

        return tuple(check.check_id for check in self.checks if not check.passed)

    def require_valid(self) -> None:
        """Raise when any bolt-mechanics check fails."""

        if self.passed:
            return

        failed = ", ".join(self.failed_check_ids)

        raise ValueError(f"Analytical bolt-mechanics validation failed: {failed}")


def validate_analytical_bolt_mechanics(
    mechanics: AnalyticalBoltMechanics,
) -> AnalyticalBoltMechanicsValidation:
    """Validate deterministic axial-mechanics identities."""

    positive_segment_properties = all(
        segment.length_mm > 0.0
        and segment.area_mm2 > 0.0
        and segment.youngs_modulus_mpa > 0.0
        and segment.compliance_mm_per_n > 0.0
        for segment in mechanics.segments
    )

    compliance_sum = sum(segment.compliance_mm_per_n for segment in mechanics.segments)

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

    expected_elongation = mechanics.preload_n * mechanics.total_compliance_mm_per_n

    force_displacement_consistent = math.isclose(
        mechanics.total_elongation_mm,
        expected_elongation,
        rel_tol=1.0e-12,
        abs_tol=1.0e-15,
    )

    segment_elongation_sum = sum(segment.elongation_mm for segment in mechanics.segments)

    segment_elongation_consistent = math.isclose(
        mechanics.total_elongation_mm,
        segment_elongation_sum,
        rel_tol=1.0e-12,
        abs_tol=1.0e-15,
    )

    expected_energy = 0.5 * mechanics.preload_n * mechanics.total_elongation_mm

    strain_energy_consistent = math.isclose(
        mechanics.total_strain_energy_n_mm,
        expected_energy,
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    effective_length_sum = sum(segment.length_mm for segment in mechanics.segments)

    effective_length_consistent = math.isclose(
        mechanics.effective_length_mm,
        effective_length_sum,
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    maximum_segment_stress = max(segment.axial_stress_mpa for segment in mechanics.segments)

    maximum_stress_consistent = math.isclose(
        mechanics.maximum_segment_stress_mpa,
        maximum_segment_stress,
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    if mechanics.preload_n > 0.0:
        reference_stress_order = (
            mechanics.root_section_reference_stress_mpa > mechanics.nominal_tensile_stress_mpa > 0.0
        )
    else:
        reference_stress_order = (
            mechanics.root_section_reference_stress_mpa == 0.0
            and mechanics.nominal_tensile_stress_mpa == 0.0
        )

    checks = (
        BoltMechanicsValidationCheck(
            check_id="nonempty_segments",
            passed=bool(mechanics.segments),
            description=("At least one effective axial bolt segment must be present."),
        ),
        BoltMechanicsValidationCheck(
            check_id="positive_segment_properties",
            passed=positive_segment_properties,
            description=(
                "Every effective segment must have positive length, area, modulus and compliance."
            ),
        ),
        BoltMechanicsValidationCheck(
            check_id="compliance_sum",
            passed=compliance_sum_consistent,
            description=(
                "Total bolt compliance must equal the sum of the series-segment compliances."
            ),
        ),
        BoltMechanicsValidationCheck(
            check_id="stiffness_reciprocal",
            passed=stiffness_reciprocal_consistent,
            description=("Axial stiffness must equal the reciprocal of total compliance."),
        ),
        BoltMechanicsValidationCheck(
            check_id="force_displacement_identity",
            passed=force_displacement_consistent,
            description=("Total elongation must equal preload multiplied by total compliance."),
        ),
        BoltMechanicsValidationCheck(
            check_id="segment_elongation_sum",
            passed=segment_elongation_consistent,
            description=("Total elongation must equal the sum of all segment elongations."),
        ),
        BoltMechanicsValidationCheck(
            check_id="strain_energy_identity",
            passed=strain_energy_consistent,
            description=(
                "Linear-elastic strain energy must equal one-half force multiplied by elongation."
            ),
        ),
        BoltMechanicsValidationCheck(
            check_id="effective_length_sum",
            passed=effective_length_consistent,
            description=(
                "Effective bolt length must equal the sum of all effective segment lengths."
            ),
        ),
        BoltMechanicsValidationCheck(
            check_id="maximum_segment_stress",
            passed=maximum_stress_consistent,
            description=(
                "Reported maximum segment stress must equal the maximum resolved segment stress."
            ),
        ),
        BoltMechanicsValidationCheck(
            check_id="reference_stress_order",
            passed=reference_stress_order,
            description=(
                "For positive preload, root-section reference stress "
                "must exceed nominal tensile-area stress."
            ),
        ),
    )

    return AnalyticalBoltMechanicsValidation(
        method="linear_axial_mechanics_invariants_v1",
        checks=checks,
    )

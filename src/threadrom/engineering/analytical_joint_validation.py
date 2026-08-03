"""Deterministic validation of analytical joint behaviour."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.engineering.analytical_joint_behaviour import (
    AnalyticalJointState,
    JointContactRegime,
)
from threadrom.engineering.analytical_joint_envelope import (
    AnalyticalJointEnvelope,
    JointCyclicResponse,
)
from threadrom.engineering.analytical_joint_strength import (
    AnalyticalJointStrengthEnvelope,
)


@dataclass(frozen=True)
class JointBehaviourValidationCheck:
    """One deterministic joint-behaviour validation check."""

    check_id: str
    passed: bool
    description: str


@dataclass(frozen=True)
class AnalyticalJointBehaviourValidation:
    """Validation evidence for one complete joint envelope."""

    method: str
    checks: tuple[JointBehaviourValidationCheck, ...]

    @property
    def passed(self) -> bool:
        """Return whether every validation check passed."""

        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        """Return the identities of failed checks."""

        return tuple(check.check_id for check in self.checks if not check.passed)

    def require_valid(self) -> None:
        """Raise when any joint-behaviour check fails."""

        if self.passed:
            return

        failed = ", ".join(self.failed_check_ids)

        raise ValueError(f"Analytical joint-behaviour validation failed: {failed}")


def validate_analytical_joint_behaviour(
    envelope: AnalyticalJointEnvelope,
    strength: AnalyticalJointStrengthEnvelope,
) -> AnalyticalJointBehaviourValidation:
    """Validate deterministic joint-response identities."""

    points_nonempty = bool(envelope.points)

    point_ids_unique = len({point.point_id for point in envelope.points}) == len(envelope.points)

    positive_stiffnesses = all(
        point.state.bolt_stiffness_n_per_mm > 0.0 and point.state.member_stiffness_n_per_mm > 0.0
        for point in envelope.points
    )

    valid_load_fractions = all(
        0.0 <= point.state.basic_load_fraction < 1.0
        and 0.0 <= point.state.effective_load_fraction < 1.0
        for point in envelope.points
    )

    equilibrium_consistent = all(
        math.isclose(
            point.state.external_load_equilibrium_error_n,
            0.0,
            rel_tol=1.0e-12,
            abs_tol=1.0e-9,
        )
        for point in envelope.points
    )

    clamped_states_consistent = all(
        _clamped_state_is_consistent(point.state)
        for point in envelope.points
        if point.state.regime is JointContactRegime.CLAMPED
    )

    separated_states_consistent = all(
        _separated_state_is_consistent(point.state)
        for point in envelope.points
        if point.state.regime is JointContactRegime.SEPARATED
    )

    extrema_consistent = (
        math.isclose(
            envelope.highest_bolt_force_n,
            max(point.state.bolt_force_n for point in envelope.points),
            rel_tol=1.0e-12,
            abs_tol=1.0e-9,
        )
        and math.isclose(
            envelope.lowest_member_compression_force_n,
            min(point.state.member_compression_force_n for point in envelope.points),
            rel_tol=1.0e-12,
            abs_tol=1.0e-9,
        )
        and math.isclose(
            envelope.minimum_separation_margin_n,
            min(point.state.separation_margin_n for point in envelope.points),
            rel_tol=1.0e-12,
            abs_tol=1.0e-9,
        )
        and math.isclose(
            envelope.maximum_joint_opening_mm,
            max(point.state.joint_opening_mm for point in envelope.points),
            rel_tol=1.0e-12,
            abs_tol=1.0e-12,
        )
    )

    separation_flag_consistent = envelope.any_separation == any(
        point.state.regime is JointContactRegime.SEPARATED for point in envelope.points
    )

    cyclic_identities_consistent = all(
        _cyclic_response_is_consistent(response) for response in envelope.cyclic_responses
    )

    strength_identity_consistent = envelope.joint_id == strength.joint_id and math.isclose(
        strength.highest_bolt_force_n,
        envelope.highest_bolt_force_n,
        rel_tol=1.0e-12,
        abs_tol=1.0e-9,
    )

    governing_point_consistent = any(
        point.point_id == strength.governing_point_id
        and math.isclose(
            point.state.bolt_force_n,
            strength.highest_bolt_force_n,
            rel_tol=1.0e-12,
            abs_tol=1.0e-9,
        )
        for point in envelope.points
    )

    stress_identities_consistent = math.isclose(
        strength.highest_nominal_tensile_stress_mpa,
        (strength.highest_bolt_force_n / strength.tensile_stress_area_mm2),
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    ) and math.isclose(
        strength.highest_root_section_reference_stress_mpa,
        (strength.highest_bolt_force_n / strength.external_root_area_mm2),
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    if strength.highest_bolt_force_n > 0.0:
        reference_stress_order = (
            strength.highest_root_section_reference_stress_mpa
            > strength.highest_nominal_tensile_stress_mpa
            > 0.0
        )
    else:
        reference_stress_order = (
            strength.highest_root_section_reference_stress_mpa == 0.0
            and strength.highest_nominal_tensile_stress_mpa == 0.0
        )

    checks = (
        JointBehaviourValidationCheck(
            check_id="nonempty_envelope",
            passed=points_nonempty,
            description=("At least one preload and external-load combination must be evaluated."),
        ),
        JointBehaviourValidationCheck(
            check_id="unique_point_ids",
            passed=point_ids_unique,
            description=("Every joint-envelope point must have a unique identity."),
        ),
        JointBehaviourValidationCheck(
            check_id="positive_stiffnesses",
            passed=positive_stiffnesses,
            description=(
                "Bolt and member stiffnesses must remain positive for every evaluated point."
            ),
        ),
        JointBehaviourValidationCheck(
            check_id="valid_load_fractions",
            passed=valid_load_fractions,
            description=("Basic and effective bolt-load fractions must lie in [0, 1)."),
        ),
        JointBehaviourValidationCheck(
            check_id="external_load_equilibrium",
            passed=equilibrium_consistent,
            description=(
                "Bolt tension minus member compression must equal the external separating load."
            ),
        ),
        JointBehaviourValidationCheck(
            check_id="clamped_state_consistency",
            passed=clamped_states_consistent,
            description=(
                "Clamped states must follow the two-spring "
                "load-sharing equations without joint opening."
            ),
        ),
        JointBehaviourValidationCheck(
            check_id="separated_state_consistency",
            passed=separated_states_consistent,
            description=(
                "Separated states must carry the full external "
                "load in the bolt with zero member compression."
            ),
        ),
        JointBehaviourValidationCheck(
            check_id="envelope_extrema",
            passed=extrema_consistent,
            description=(
                "Reported envelope extrema must equal the extrema of all evaluated points."
            ),
        ),
        JointBehaviourValidationCheck(
            check_id="separation_flag",
            passed=separation_flag_consistent,
            description=("The envelope separation flag must match the evaluated contact regimes."),
        ),
        JointBehaviourValidationCheck(
            check_id="cyclic_response_identities",
            passed=cyclic_identities_consistent,
            description=(
                "Cyclic force means, amplitudes, ranges and "
                "member-force ordering must be consistent."
            ),
        ),
        JointBehaviourValidationCheck(
            check_id="strength_envelope_identity",
            passed=strength_identity_consistent,
            description=(
                "The strength result must use the same joint identity and governing bolt force."
            ),
        ),
        JointBehaviourValidationCheck(
            check_id="governing_point",
            passed=governing_point_consistent,
            description=(
                "The reported governing point must exist and carry the envelope maximum bolt force."
            ),
        ),
        JointBehaviourValidationCheck(
            check_id="section_stress_identities",
            passed=stress_identities_consistent,
            description=(
                "Nominal and root-section reference stresses "
                "must equal force divided by their areas."
            ),
        ),
        JointBehaviourValidationCheck(
            check_id="reference_stress_order",
            passed=reference_stress_order,
            description=(
                "For positive bolt force, root-section reference "
                "stress must exceed nominal tensile-area stress."
            ),
        ),
    )

    return AnalyticalJointBehaviourValidation(
        method="piecewise_two_spring_joint_invariants_v1",
        checks=checks,
    )


def _clamped_state_is_consistent(
    state: AnalyticalJointState,
) -> bool:
    """Return whether one clamped state satisfies its identities."""

    expected_bolt_force_n = (
        state.preload_n + state.effective_load_fraction * state.external_axial_load_n
    )

    expected_member_force_n = (
        state.preload_n - (1.0 - state.effective_load_fraction) * state.external_axial_load_n
    )

    return (
        state.external_axial_load_n <= state.separation_load_n + 1.0e-9
        and state.member_compression_force_n >= -1.0e-9
        and math.isclose(
            state.bolt_force_n,
            expected_bolt_force_n,
            rel_tol=1.0e-12,
            abs_tol=1.0e-9,
        )
        and math.isclose(
            state.member_compression_force_n,
            max(
                0.0,
                expected_member_force_n,
            ),
            rel_tol=1.0e-12,
            abs_tol=1.0e-9,
        )
        and math.isclose(
            state.joint_opening_mm,
            0.0,
            rel_tol=1.0e-12,
            abs_tol=1.0e-12,
        )
    )


def _separated_state_is_consistent(
    state: AnalyticalJointState,
) -> bool:
    """Return whether one separated state satisfies its identities."""

    expected_opening_mm = (
        state.external_axial_load_n - state.separation_load_n
    ) / state.bolt_stiffness_n_per_mm

    return (
        state.external_axial_load_n > state.separation_load_n
        and math.isclose(
            state.bolt_force_n,
            state.external_axial_load_n,
            rel_tol=1.0e-12,
            abs_tol=1.0e-9,
        )
        and math.isclose(
            state.member_compression_force_n,
            0.0,
            rel_tol=1.0e-12,
            abs_tol=1.0e-9,
        )
        and math.isclose(
            state.joint_opening_mm,
            expected_opening_mm,
            rel_tol=1.0e-12,
            abs_tol=1.0e-12,
        )
    )


def _cyclic_response_is_consistent(
    response: JointCyclicResponse,
) -> bool:
    """Return whether one cyclic response satisfies its identities."""

    expected_range_n = response.bolt_force_maximum_n - response.bolt_force_minimum_n

    return (
        response.bolt_force_maximum_n >= response.bolt_force_minimum_n
        and response.member_compression_maximum_n >= response.member_compression_minimum_n
        and math.isclose(
            response.bolt_force_range_n,
            expected_range_n,
            rel_tol=1.0e-12,
            abs_tol=1.0e-9,
        )
        and math.isclose(
            response.bolt_force_amplitude_n,
            0.5 * expected_range_n,
            rel_tol=1.0e-12,
            abs_tol=1.0e-9,
        )
        and math.isclose(
            response.bolt_force_mean_n,
            0.5 * (response.bolt_force_maximum_n + response.bolt_force_minimum_n),
            rel_tol=1.0e-12,
            abs_tol=1.0e-9,
        )
    )

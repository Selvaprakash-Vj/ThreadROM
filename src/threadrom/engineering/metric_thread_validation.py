"""Physics-consistency validation for metric-thread mechanics."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.engineering.metric_thread_mechanics import (
    MetricThreadMechanics,
)


@dataclass(frozen=True)
class ThreadMechanicsValidationCheck:
    """One deterministic thread-mechanics validation check."""

    check_id: str
    passed: bool
    description: str


@dataclass(frozen=True)
class MetricThreadMechanicsValidation:
    """Validation result for one derived metric thread."""

    method: str
    checks: tuple[ThreadMechanicsValidationCheck, ...]

    @property
    def passed(self) -> bool:
        """Return whether every validation check passed."""

        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        """Return the identities of failed checks."""

        return tuple(check.check_id for check in self.checks if not check.passed)

    def require_valid(self) -> None:
        """Raise when any mechanics-consistency check fails."""

        if self.passed:
            return

        failed = ", ".join(self.failed_check_ids)

        raise ValueError(f"Metric-thread mechanics validation failed: {failed}")


def validate_metric_thread_mechanics(
    mechanics: MetricThreadMechanics,
) -> MetricThreadMechanicsValidation:
    """Validate geometric and dimensional mechanics invariants."""

    diameter_order_passed = (
        0.0
        < mechanics.basic_external_minor_diameter_mm
        < mechanics.basic_internal_minor_diameter_mm
        < mechanics.basic_pitch_diameter_mm
        < mechanics.nominal_diameter_mm
    )

    area_order_passed = (
        0.0
        < mechanics.external_root_area_mm2
        < mechanics.tensile_stress_area_mm2
        < mechanics.pitch_diameter_area_mm2
        < mechanics.nominal_area_mm2
    )

    depth_passed = (
        mechanics.external_thread_radial_depth_mm > 0.0
        and mechanics.internal_thread_radial_depth_mm > 0.0
    )

    lead_passed = math.isclose(
        mechanics.lead_mm,
        mechanics.pitch_mm * mechanics.starts,
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    engaged_pitch_count_passed = math.isclose(
        mechanics.engaged_pitch_count,
        (mechanics.engagement_length_mm / mechanics.pitch_mm),
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    engaged_turn_count_passed = math.isclose(
        mechanics.engaged_lead_turn_count,
        (mechanics.engagement_length_mm / mechanics.lead_mm),
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    )

    area_ratio_passed = (
        0.0 < mechanics.root_to_nominal_area_ratio < mechanics.tensile_to_nominal_area_ratio < 1.0
    )

    helix_angle_passed = (
        math.isfinite(mechanics.helix_angle_at_pitch_diameter_deg)
        and mechanics.helix_angle_at_pitch_diameter_deg > 0.0
        and mechanics.helix_angle_at_pitch_diameter_deg < 90.0
    )

    checks = (
        ThreadMechanicsValidationCheck(
            check_id="diameter_order",
            passed=diameter_order_passed,
            description=(
                "External minor, internal minor, pitch and nominal "
                "diameters must be positive and strictly ordered."
            ),
        ),
        ThreadMechanicsValidationCheck(
            check_id="area_order",
            passed=area_order_passed,
            description=(
                "Root, tensile, pitch-diameter and nominal areas "
                "must be positive and strictly ordered."
            ),
        ),
        ThreadMechanicsValidationCheck(
            check_id="positive_thread_depths",
            passed=depth_passed,
            description=("External and internal radial thread depths must be positive."),
        ),
        ThreadMechanicsValidationCheck(
            check_id="lead_consistency",
            passed=lead_passed,
            description=("Thread lead must equal pitch multiplied by the number of starts."),
        ),
        ThreadMechanicsValidationCheck(
            check_id="engaged_pitch_count_consistency",
            passed=engaged_pitch_count_passed,
            description=("Engaged pitch count must equal engagement length divided by pitch."),
        ),
        ThreadMechanicsValidationCheck(
            check_id="engaged_turn_count_consistency",
            passed=engaged_turn_count_passed,
            description=("Engaged lead-turn count must equal engagement length divided by lead."),
        ),
        ThreadMechanicsValidationCheck(
            check_id="area_ratio_bounds",
            passed=area_ratio_passed,
            description=(
                "Root and tensile area ratios must remain "
                "between zero and one and physically ordered."
            ),
        ),
        ThreadMechanicsValidationCheck(
            check_id="helix_angle_bounds",
            passed=helix_angle_passed,
            description=(
                "Pitch-diameter helix angle must be finite and "
                "lie strictly between zero and 90 degrees."
            ),
        ),
    )

    return MetricThreadMechanicsValidation(
        method="deterministic_geometry_invariants_v1",
        checks=checks,
    )

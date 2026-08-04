"""Physics validation for discrete thread-load distributions."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.engineering.analytical_thread_distribution import (
    AnalyticalThreadLoadDistribution,
)


@dataclass(frozen=True)
class ThreadDistributionValidationCheck:
    """One thread-distribution validation check."""

    check_id: str
    description: str
    passed: bool


@dataclass(frozen=True)
class AnalyticalThreadDistributionValidation:
    """Validation evidence for one thread-load distribution."""

    method: str
    checks: tuple[
        ThreadDistributionValidationCheck,
        ...,
    ]

    @property
    def passed(self) -> bool:
        """Return whether all validation checks passed."""

        return all(check.passed for check in self.checks)

    @property
    def failed_check_ids(self) -> tuple[str, ...]:
        """Return identifiers of failed checks."""

        return tuple(check.check_id for check in self.checks if not check.passed)

    def require_valid(self) -> None:
        """Raise when any distribution invariant fails."""

        if self.passed:
            return

        failed = ", ".join(self.failed_check_ids)

        raise ValueError(f"Analytical thread-load distribution validation failed: {failed}")


def validate_thread_load_distribution(
    distribution: AnalyticalThreadLoadDistribution,
) -> AnalyticalThreadDistributionValidation:
    """Validate equilibrium and reporting invariants."""

    total_load_n = distribution.total_transferred_load_n

    force_tolerance_n = max(
        1.0e-8,
        abs(total_load_n) * 1.0e-10,
    )

    share_tolerance = 1.0e-10

    turn_loads = distribution.turn_loads

    resolved_load_n = math.fsum(turn.load_n for turn in turn_loads)

    resolved_share = math.fsum(turn.load_share for turn in turn_loads)

    maximum_turn = (
        max(
            turn_loads,
            key=lambda turn: turn.load_n,
        )
        if turn_loads
        else None
    )

    checks = (
        ThreadDistributionValidationCheck(
            check_id="nonempty_turn_distribution",
            description=("At least one engaged thread turn must carry the transferred load."),
            passed=bool(turn_loads),
        ),
        ThreadDistributionValidationCheck(
            check_id="turn_count_consistency",
            description=(
                "Reported active-turn counts must match the distribution and engagement records."
            ),
            passed=(
                distribution.active_turn_count
                == len(turn_loads)
                == distribution.engagement.active_turn_count
            ),
        ),
        ThreadDistributionValidationCheck(
            check_id="turn_numbering_consistency",
            description=("Thread turns must be numbered consecutively from the nut bearing face."),
            passed=(
                [turn.turn_number for turn in turn_loads]
                == list(
                    range(
                        1,
                        len(turn_loads) + 1,
                    )
                )
            ),
        ),
        ThreadDistributionValidationCheck(
            check_id="positive_thread_stiffness",
            description=(
                "All thread springs and governing transfer stiffnesses must be finite and positive."
            ),
            passed=(
                _positive_finite(
                    distribution.stiffness.combined_distributed_thread_stiffness_n_per_mm2
                )
                and _positive_finite(distribution.stiffness.transfer_parameter_per_mm)
                and all(_positive_finite(turn.spring_stiffness_n_per_mm) for turn in turn_loads)
            ),
        ),
        ThreadDistributionValidationCheck(
            check_id="nonnegative_turn_loads",
            description=("Every active thread turn must carry a finite nonnegative axial load."),
            passed=all(
                math.isfinite(turn.load_n) and turn.load_n >= -force_tolerance_n
                for turn in turn_loads
            ),
        ),
        ThreadDistributionValidationCheck(
            check_id="turn_load_share_identity",
            description=(
                "Each reported load share must equal its "
                "turn load divided by total transferred load."
            ),
            passed=(
                total_load_n > 0.0
                and all(
                    math.isclose(
                        turn.load_share,
                        turn.load_n / total_load_n,
                        rel_tol=1.0e-10,
                        abs_tol=share_tolerance,
                    )
                    for turn in turn_loads
                )
            ),
        ),
        ThreadDistributionValidationCheck(
            check_id="cumulative_force_identities",
            description=(
                "Cumulative load, cumulative share and remaining "
                "bolt force must be internally consistent."
            ),
            passed=_cumulative_fields_are_consistent(
                distribution,
                force_tolerance_n=force_tolerance_n,
                share_tolerance=share_tolerance,
            ),
        ),
        ThreadDistributionValidationCheck(
            check_id="monotonic_cumulative_transfer",
            description=(
                "Cumulative transferred load must not decrease "
                "and remaining bolt force must not increase."
            ),
            passed=_cumulative_fields_are_monotonic(
                distribution,
                force_tolerance_n=force_tolerance_n,
            ),
        ),
        ThreadDistributionValidationCheck(
            check_id="load_conservation",
            description=(
                "Thread-turn loads and load shares must conserve the full transferred axial load."
            ),
            passed=(
                math.isclose(
                    resolved_load_n,
                    total_load_n,
                    rel_tol=1.0e-10,
                    abs_tol=force_tolerance_n,
                )
                and math.isclose(
                    resolved_share,
                    1.0,
                    rel_tol=1.0e-10,
                    abs_tol=share_tolerance,
                )
                and math.isclose(
                    distribution.load_conservation_error_n,
                    resolved_load_n - total_load_n,
                    rel_tol=1.0e-10,
                    abs_tol=force_tolerance_n,
                )
                and math.isclose(
                    distribution.final_remaining_bolt_force_n,
                    total_load_n - resolved_load_n,
                    rel_tol=1.0e-10,
                    abs_tol=force_tolerance_n,
                )
            ),
        ),
        ThreadDistributionValidationCheck(
            check_id="bearing_reaction_equilibrium",
            description=("The nut-bearing reaction must balance the applied bolt load."),
            passed=(
                math.isclose(
                    distribution.nut_bearing_reaction_n,
                    -total_load_n,
                    rel_tol=1.0e-10,
                    abs_tol=force_tolerance_n,
                )
                and math.isclose(
                    distribution.global_equilibrium_error_n,
                    (total_load_n + distribution.nut_bearing_reaction_n),
                    rel_tol=1.0e-10,
                    abs_tol=force_tolerance_n,
                )
                and math.isclose(
                    distribution.global_equilibrium_error_n,
                    0.0,
                    rel_tol=0.0,
                    abs_tol=force_tolerance_n,
                )
            ),
        ),
        ThreadDistributionValidationCheck(
            check_id="first_turn_identity",
            description=(
                "Reported first-turn force and share must match the first turn in the distribution."
            ),
            passed=(
                bool(turn_loads)
                and math.isclose(
                    distribution.first_turn_load_n,
                    turn_loads[0].load_n,
                    rel_tol=1.0e-10,
                    abs_tol=force_tolerance_n,
                )
                and math.isclose(
                    distribution.first_turn_load_share,
                    turn_loads[0].load_share,
                    rel_tol=1.0e-10,
                    abs_tol=share_tolerance,
                )
            ),
        ),
        ThreadDistributionValidationCheck(
            check_id="maximum_turn_identity",
            description=(
                "Reported maximum-loaded turn quantities must match the governing turn record."
            ),
            passed=(
                maximum_turn is not None
                and distribution.maximum_loaded_turn_number == maximum_turn.turn_number
                and math.isclose(
                    distribution.maximum_turn_load_n,
                    maximum_turn.load_n,
                    rel_tol=1.0e-10,
                    abs_tol=force_tolerance_n,
                )
                and math.isclose(
                    distribution.maximum_turn_load_share,
                    maximum_turn.load_share,
                    rel_tol=1.0e-10,
                    abs_tol=share_tolerance,
                )
            ),
        ),
        ThreadDistributionValidationCheck(
            check_id="engagement_fraction_consistency",
            description=(
                "Turn engagement fractions must be valid and sum "
                "to the nominal engaged-pitch count."
            ),
            passed=(
                all(0.0 < turn.engagement_fraction <= 1.0 for turn in turn_loads)
                and math.isclose(
                    math.fsum(turn.engagement_fraction for turn in turn_loads),
                    (distribution.engagement.nominal_engaged_pitch_count),
                    rel_tol=1.0e-10,
                    abs_tol=1.0e-12,
                )
            ),
        ),
        ThreadDistributionValidationCheck(
            check_id="transfer_length_identity",
            description=(
                "The characteristic transfer length must be the "
                "reciprocal of the transfer parameter."
            ),
            passed=(
                _positive_finite(distribution.stiffness.characteristic_transfer_length_mm)
                and math.isclose(
                    (
                        distribution.stiffness.transfer_parameter_per_mm
                        * distribution.stiffness.characteristic_transfer_length_mm
                    ),
                    1.0,
                    rel_tol=1.0e-10,
                    abs_tol=1.0e-12,
                )
            ),
        ),
    )

    return AnalyticalThreadDistributionValidation(
        method=("discrete_thread_spring_invariants_v1"),
        checks=checks,
    )


def _cumulative_fields_are_consistent(
    distribution: AnalyticalThreadLoadDistribution,
    *,
    force_tolerance_n: float,
    share_tolerance: float,
) -> bool:
    """Check cumulative values against recomputed quantities."""

    cumulative_load_n = 0.0
    total_load_n = distribution.total_transferred_load_n

    for turn in distribution.turn_loads:
        cumulative_load_n += turn.load_n

        if not math.isclose(
            turn.cumulative_load_n,
            cumulative_load_n,
            rel_tol=1.0e-10,
            abs_tol=force_tolerance_n,
        ):
            return False

        if not math.isclose(
            turn.cumulative_load_share,
            cumulative_load_n / total_load_n,
            rel_tol=1.0e-10,
            abs_tol=share_tolerance,
        ):
            return False

        if not math.isclose(
            turn.remaining_bolt_force_n,
            total_load_n - cumulative_load_n,
            rel_tol=1.0e-10,
            abs_tol=force_tolerance_n,
        ):
            return False

    return True


def _cumulative_fields_are_monotonic(
    distribution: AnalyticalThreadLoadDistribution,
    *,
    force_tolerance_n: float,
) -> bool:
    """Check monotonic load transfer along the engagement."""

    previous_cumulative_n = 0.0

    previous_remaining_n = distribution.total_transferred_load_n

    for turn in distribution.turn_loads:
        if turn.cumulative_load_n < previous_cumulative_n - force_tolerance_n:
            return False

        if turn.remaining_bolt_force_n > previous_remaining_n + force_tolerance_n:
            return False

        previous_cumulative_n = turn.cumulative_load_n

        previous_remaining_n = turn.remaining_bolt_force_n

    return True


def _positive_finite(value: float) -> bool:
    """Return whether a numerical value is finite and positive."""

    return math.isfinite(value) and value > 0.0

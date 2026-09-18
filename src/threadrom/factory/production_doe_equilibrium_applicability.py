"""Scoped external-equilibrium applicability for Production DOE evidence.

This module does not replace or weaken the governed CalculiX external-
support equilibrium validator.  It classifies whether that support-only
observable is sufficient to make a full-system equilibrium acceptance
claim for a particular Production-DOE output contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class ProductionDoeEquilibriumApplicability(str, Enum):
    """Applicability of support-only equilibrium to Production DOE."""

    FULL_SYSTEM_OBSERVABLE = "full_system_observable"
    DIAGNOSTIC_ONLY_INCOMPLETE_REACTION_SYSTEM = (
        "diagnostic_only_incomplete_reaction_system"
    )


@dataclass(frozen=True)
class ProductionDoeEquilibriumApplicabilityResult:
    """Governed interpretation of one DOE reaction-output contract."""

    applicability: ProductionDoeEquilibriumApplicability
    support_only_result_is_diagnostic: bool
    full_system_pass_claimed: bool
    tolerance_changed: bool
    additional_fem_authorized_by_classifier: bool
    missing_reaction_sets: tuple[str, ...]


def classify_production_doe_equilibrium_applicability(
    *,
    constrained_reaction_sets: Iterable[str],
    reaction_observable_sets: Iterable[str],
) -> ProductionDoeEquilibriumApplicabilityResult:
    """Classify whether the reaction output supports a full-system claim.

    The classifier is intentionally independent of the numerical result
    of the support-only validator.  A failed support-only result must not
    be converted into PASS.  Instead, this function decides whether the
    observable itself represents the complete constrained reaction system.
    """

    constrained = frozenset(
        name.strip().upper()
        for name in constrained_reaction_sets
        if name.strip()
    )

    observable = frozenset(
        name.strip().upper()
        for name in reaction_observable_sets
        if name.strip()
    )

    if not constrained:
        raise ValueError(
            "At least one constrained reaction set is required."
        )

    missing = tuple(
        sorted(
            constrained - observable
        )
    )

    if missing:
        return ProductionDoeEquilibriumApplicabilityResult(
            applicability=(
                ProductionDoeEquilibriumApplicability
                .DIAGNOSTIC_ONLY_INCOMPLETE_REACTION_SYSTEM
            ),
            support_only_result_is_diagnostic=True,
            full_system_pass_claimed=False,
            tolerance_changed=False,
            additional_fem_authorized_by_classifier=False,
            missing_reaction_sets=missing,
        )

    return ProductionDoeEquilibriumApplicabilityResult(
        applicability=(
            ProductionDoeEquilibriumApplicability
            .FULL_SYSTEM_OBSERVABLE
        ),
        support_only_result_is_diagnostic=False,
        full_system_pass_claimed=False,
        tolerance_changed=False,
        additional_fem_authorized_by_classifier=False,
        missing_reaction_sets=(),
    )

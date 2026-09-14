"""Governed provenance for dimensional engineering data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import math


class DimensionEvidenceBasis(StrEnum):
    """Engineering basis from which one dimensional datum is admitted."""

    STANDARD_DERIVED = "standard_derived"
    CERTIFIED_REALIZED_BASELINE = "certified_realized_baseline"


class DimensionVerificationStatus(StrEnum):
    """Independent verification maturity of one dimensional datum."""

    PENDING = "pending"
    VERIFIED = "verified"


@dataclass(frozen=True)
class GovernedDimensionEvidence:
    """One traceable dimensional engineering datum.

    A standard-derived dimension and a certified realised baseline dimension
    are deliberately different evidence classes. Certification of realised
    geometry does not imply that its numerical value is an exact product-
    standard dimension.
    """

    evidence_id: str
    evidence_basis: DimensionEvidenceBasis
    standard_reference: str | None
    thread_designation: str
    quantity_name: str
    value_mm: float
    source_reference: str

    verification_status: DimensionVerificationStatus
    verification_reference: str | None = None
    verified_on: date | None = None

    def __post_init__(self) -> None:
        for value, name in (
            (self.evidence_id, "Evidence identity"),
            (self.thread_designation, "Thread designation"),
            (self.quantity_name, "Quantity name"),
            (self.source_reference, "Source reference"),
        ):
            if not value.strip():
                raise ValueError(
                    f"{name} must not be blank."
                )

        if (
            not math.isfinite(self.value_mm)
            or self.value_mm <= 0.0
        ):
            raise ValueError(
                "Dimensional value must be finite and positive."
            )

        if self.evidence_basis is DimensionEvidenceBasis.STANDARD_DERIVED:
            if (
                self.standard_reference is None
                or not self.standard_reference.strip()
            ):
                raise ValueError(
                    "Standard-derived dimensional evidence requires a "
                    "standard reference."
                )

        elif (
            self.evidence_basis
            is DimensionEvidenceBasis.CERTIFIED_REALIZED_BASELINE
        ):
            if self.standard_reference is not None:
                raise ValueError(
                    "Certified realised baseline dimensional evidence "
                    "must not claim a standard-derived reference."
                )

        if self.verification_status is DimensionVerificationStatus.VERIFIED:
            if (
                self.verification_reference is None
                or not self.verification_reference.strip()
            ):
                raise ValueError(
                    "Verified dimensional evidence requires a "
                    "verification reference."
                )

            if self.verified_on is None:
                raise ValueError(
                    "Verified dimensional evidence requires a "
                    "verification date."
                )

            return

        if (
            self.verification_reference is not None
            or self.verified_on is not None
        ):
            raise ValueError(
                "Pending dimensional evidence cannot claim completed "
                "verification."
            )

    @property
    def is_verified(self) -> bool:
        """Return whether governed verification is complete."""

        return (
            self.verification_status
            is DimensionVerificationStatus.VERIFIED
        )


# Temporary compatibility alias for any code written against the first
# CP11 provenance draft. New code should use GovernedDimensionEvidence.
StandardDimensionEvidence = GovernedDimensionEvidence

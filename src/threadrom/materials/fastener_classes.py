"""Governed fastener property-class models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math


class FastenerComponentKind(StrEnum):
    """Fastener component governed by a property class."""

    BOLT = "bolt"
    NUT = "nut"


@dataclass(frozen=True)
class FastenerPropertyClass:
    """Mechanical strength properties for one fastener property class.

    Strength values are independent of the base material-family record.
    Unknown or not-yet-governed quantities remain explicitly unset rather
    than being inferred.
    """

    component_kind: FastenerComponentKind
    property_class: str
    source_reference: str
    proof_stress_mpa: float | None = None
    yield_strength_mpa: float | None = None
    ultimate_strength_mpa: float | None = None
    governing_standard: str | None = None

    def __post_init__(self) -> None:
        if not self.property_class.strip():
            raise ValueError(
                "Fastener property class must not be blank."
            )

        if not self.source_reference.strip():
            raise ValueError(
                "Fastener property-class source reference must not be blank."
            )

        if (
            self.governing_standard is not None
            and not self.governing_standard.strip()
        ):
            raise ValueError(
                "Governing standard must not be blank when provided."
            )

        strengths = {
            "proof stress": self.proof_stress_mpa,
            "yield strength": self.yield_strength_mpa,
            "ultimate strength": self.ultimate_strength_mpa,
        }

        for name, value in strengths.items():
            if value is not None and (
                not math.isfinite(value) or value <= 0.0
            ):
                raise ValueError(
                    f"{name} must be finite and positive when provided."
                )

        if (
            self.proof_stress_mpa is not None
            and self.yield_strength_mpa is not None
            and self.proof_stress_mpa > self.yield_strength_mpa
        ):
            raise ValueError(
                "Proof stress must not exceed yield strength."
            )

        if (
            self.yield_strength_mpa is not None
            and self.ultimate_strength_mpa is not None
            and self.yield_strength_mpa > self.ultimate_strength_mpa
        ):
            raise ValueError(
                "Yield strength must not exceed ultimate strength."
            )

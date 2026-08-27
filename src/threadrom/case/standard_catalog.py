"""Scalable ISO fastener-standard catalogue primitives.

The catalogue distinguishes knowledge of an ISO standard from dimensional,
CAD, FEM, and certification support. Knowing that a standard exists never
implies that ThreadROM can solve it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class StandardLifecycle(StrEnum):
    """ISO publication lifecycle relevant to ThreadROM."""

    PUBLISHED = "published"
    UNDER_DEVELOPMENT = "under_development"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"


def resolve_standard_lifecycle(
    current_stage: int | None,
) -> StandardLifecycle:
    """Map an ISO harmonized stage code to ThreadROM lifecycle state."""

    if current_stage is None:
        return StandardLifecycle.UNKNOWN

    if current_stage < 0:
        raise ValueError(
            "ISO current stage must be non-negative."
        )

    if current_stage >= 9500:
        return StandardLifecycle.WITHDRAWN

    if current_stage >= 6060:
        return StandardLifecycle.PUBLISHED

    return StandardLifecycle.UNDER_DEVELOPMENT


class StandardRole(StrEnum):
    """Engineering role played by an ISO standard."""

    THREAD_SYSTEM = "thread_system"
    PRODUCT_GEOMETRY = "product_geometry"
    DIMENSIONAL_SUPPORT = "dimensional_support"
    MECHANICAL_PROPERTIES = "mechanical_properties"
    TOLERANCES = "tolerances"
    GENERAL_REQUIREMENTS = "general_requirements"


class FastenerProductKind(StrEnum):
    """Broad product family covered by a standard."""

    THREAD = "thread"
    BOLT = "bolt"
    SCREW = "screw"
    STUD = "stud"
    NUT = "nut"
    SHARED = "shared"


class StandardCapability(StrEnum):
    """Highest ThreadROM capability currently available."""

    METADATA_ONLY = "metadata_only"
    DIMENSIONAL_DATA = "dimensional_data"
    CAD_SUPPORTED = "cad_supported"
    FEM_SUPPORTED = "fem_supported"
    CERTIFIED = "certified"


@dataclass(frozen=True)
class ISOStandardCatalogRecord:
    """One governed ISO standard catalogue entry."""

    reference: str
    title: str
    lifecycle: StandardLifecycle
    role: StandardRole
    product_kind: FastenerProductKind
    ics_code: str
    capability: StandardCapability = StandardCapability.METADATA_ONLY
    iso_deliverable_id: int | None = None
    edition: int | None = None
    current_stage: int | None = None
    publication_date: date | None = None
    owner_committee: str | None = None
    replaces: tuple[int, ...] = ()
    replaced_by: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        for value, name in (
            (self.reference, "ISO reference"),
            (self.title, "ISO title"),
            (self.ics_code, "ICS code"),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be blank.")

        if (
            self.iso_deliverable_id is not None
            and self.iso_deliverable_id <= 0
        ):
            raise ValueError(
                "ISO deliverable ID must be positive when provided."
            )

        if self.edition is not None and self.edition <= 0:
            raise ValueError(
                "ISO edition must be positive when provided."
            )

        if (
            self.current_stage is not None
            and self.current_stage < 0
        ):
            raise ValueError(
                "ISO current stage must be non-negative."
            )

        if (
            self.owner_committee is not None
            and not self.owner_committee.strip()
        ):
            raise ValueError(
                "ISO owner committee must not be blank when provided."
            )

    @property
    def is_current(self) -> bool:
        """Return whether the standard is currently published."""

        return self.lifecycle is StandardLifecycle.PUBLISHED

    @property
    def is_product_standard(self) -> bool:
        """Return whether this standard defines a fastener product."""

        return self.role is StandardRole.PRODUCT_GEOMETRY

    @property
    def selectable_in_standard_mode(self) -> bool:
        """Return whether the future UI may expose this product."""

        return (
            self.is_current
            and self.is_product_standard
            and self.capability
            is not StandardCapability.METADATA_ONLY
        )

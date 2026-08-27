"""Normalized ISO Open Data records used by ThreadROM.

This layer preserves authoritative public ISO catalogue metadata without
guessing engineering roles or ThreadROM support capability. Classification
into product geometry, mechanical-property, tolerance, or other engineering
roles is performed separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from threadrom.case.standard_catalog import (
    StandardLifecycle,
    resolve_standard_lifecycle,
)


@dataclass(frozen=True)
class ISOOpenDataRecord:
    """One normalized ISO Open Data deliverable."""

    iso_deliverable_id: int
    reference: str
    title_en: str
    deliverable_type: str
    edition: int | None
    ics_codes: tuple[str, ...]
    current_stage: int | None
    lifecycle: StandardLifecycle
    publication_date: date | None
    owner_committee: str | None
    replaces: tuple[int, ...]
    replaced_by: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.iso_deliverable_id <= 0:
            raise ValueError(
                "ISO deliverable ID must be positive."
            )

        if not self.reference.strip():
            raise ValueError(
                "ISO reference must not be blank."
            )

        if not self.title_en.strip():
            raise ValueError(
                "ISO English title must not be blank."
            )

        if not self.deliverable_type.strip():
            raise ValueError(
                "ISO deliverable type must not be blank."
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

        expected_lifecycle = resolve_standard_lifecycle(
            self.current_stage
        )

        if self.lifecycle is not expected_lifecycle:
            raise ValueError(
                "ISO lifecycle disagrees with current stage."
            )

        if not self.ics_codes:
            raise ValueError(
                "Normalized ThreadROM ISO records require an ICS code."
            )

        if any(not code.strip() for code in self.ics_codes):
            raise ValueError(
                "ISO ICS codes must not be blank."
            )

        if (
            self.owner_committee is not None
            and not self.owner_committee.strip()
        ):
            raise ValueError(
                "ISO owner committee must not be blank when provided."
            )

        if len(self.ics_codes) != len(set(self.ics_codes)):
            raise ValueError(
                "ISO ICS codes must be unique."
            )

        if len(self.replaces) != len(set(self.replaces)):
            raise ValueError(
                "ISO replacement predecessor IDs must be unique."
            )

        if len(self.replaced_by) != len(set(self.replaced_by)):
            raise ValueError(
                "ISO replacement successor IDs must be unique."
            )

    @property
    def is_published(self) -> bool:
        """Return whether this deliverable remains published."""

        return self.lifecycle is StandardLifecycle.PUBLISHED

    @property
    def is_withdrawn(self) -> bool:
        """Return whether this deliverable has been withdrawn."""

        return self.lifecycle is StandardLifecycle.WITHDRAWN

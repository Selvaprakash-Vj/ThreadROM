"""Governed ISO fastener catalogue inventory.

An inventory is a dated, traceable snapshot of ISO catalogue metadata.
It does not contain copyrighted dimensional tables and does not imply
CAD or FEM support.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from threadrom.case.standard_catalog import ISOStandardCatalogRecord


@dataclass(frozen=True)
class ISOStandardInventory:
    """Traceable snapshot of governed ISO catalogue metadata."""

    inventory_id: str
    verified_on: date
    source_urls: tuple[str, ...]
    records: tuple[ISOStandardCatalogRecord, ...]

    def __post_init__(self) -> None:
        if not self.inventory_id.strip():
            raise ValueError(
                "ISO standard inventory identity must not be blank."
            )

        if not self.source_urls:
            raise ValueError(
                "ISO standard inventory requires at least one source URL."
            )

        if any(not url.strip() for url in self.source_urls):
            raise ValueError(
                "ISO standard inventory source URLs must not be blank."
            )

        references = tuple(
            record.reference for record in self.records
        )

        if len(references) != len(set(references)):
            raise ValueError(
                "ISO standard inventory contains duplicate references."
            )

    def get(
        self,
        reference: str,
    ) -> ISOStandardCatalogRecord:
        """Return one catalogue record by exact ISO reference."""

        for record in self.records:
            if record.reference == reference:
                return record

        raise KeyError(
            f"ISO standard {reference!r} is not in this inventory."
        )

    @property
    def published_records(
        self,
    ) -> tuple[ISOStandardCatalogRecord, ...]:
        """Return current published catalogue records."""

        return tuple(
            record
            for record in self.records
            if record.is_current
        )

    @property
    def product_records(
        self,
    ) -> tuple[ISOStandardCatalogRecord, ...]:
        """Return fastener product-standard records."""

        return tuple(
            record
            for record in self.records
            if record.is_product_standard
        )

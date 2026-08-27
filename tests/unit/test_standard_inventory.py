"""Tests for governed ISO standard inventories."""

from datetime import date

import pytest

from threadrom.case.standard_catalog import (
    FastenerProductKind,
    ISOStandardCatalogRecord,
    StandardCapability,
    StandardLifecycle,
    StandardRole,
)
from threadrom.case.standard_inventory import ISOStandardInventory


def _record(
    reference: str,
    *,
    lifecycle: StandardLifecycle = StandardLifecycle.PUBLISHED,
    role: StandardRole = StandardRole.PRODUCT_GEOMETRY,
) -> ISOStandardCatalogRecord:
    return ISOStandardCatalogRecord(
        reference=reference,
        title=f"Test record for {reference}",
        lifecycle=lifecycle,
        role=role,
        product_kind=(
            FastenerProductKind.BOLT
            if role is StandardRole.PRODUCT_GEOMETRY
            else FastenerProductKind.THREAD
        ),
        ics_code="21.060.10",
        capability=StandardCapability.METADATA_ONLY,
    )


def _inventory() -> ISOStandardInventory:
    return ISOStandardInventory(
        inventory_id="ISO-FASTENERS-2026-08-27",
        verified_on=date(2026, 8, 27),
        source_urls=(
            "https://www.iso.org/",
        ),
        records=(
            _record("ISO 4017:2022"),
            _record(
                "ISO 724:2023",
                role=StandardRole.DIMENSIONAL_SUPPORT,
            ),
            _record(
                "ISO OLD:2000",
                lifecycle=StandardLifecycle.WITHDRAWN,
            ),
        ),
    )


def test_inventory_get_returns_exact_record() -> None:
    """Exact ISO references resolve deterministically."""

    inventory = _inventory()

    assert (
        inventory.get("ISO 4017:2022").reference
        == "ISO 4017:2022"
    )


def test_inventory_get_rejects_unknown_reference() -> None:
    """Unknown ISO references do not silently resolve."""

    with pytest.raises(KeyError):
        _inventory().get("ISO 9999:2099")


def test_published_records_exclude_withdrawn_entries() -> None:
    """Historical records remain stored but not current."""

    references = {
        record.reference
        for record in _inventory().published_records
    }

    assert "ISO 4017:2022" in references
    assert "ISO 724:2023" in references
    assert "ISO OLD:2000" not in references


def test_product_records_exclude_supporting_standards() -> None:
    """Thread/support standards do not masquerade as products."""

    references = {
        record.reference
        for record in _inventory().product_records
    }

    assert "ISO 4017:2022" in references
    assert "ISO OLD:2000" in references
    assert "ISO 724:2023" not in references


def test_duplicate_references_are_rejected() -> None:
    """One inventory cannot contain duplicate ISO identities."""

    record = _record("ISO 4017:2022")

    with pytest.raises(ValueError):
        ISOStandardInventory(
            inventory_id="inventory",
            verified_on=date(2026, 8, 27),
            source_urls=("https://www.iso.org/",),
            records=(record, record),
        )


def test_inventory_requires_source_provenance() -> None:
    """A governed inventory cannot exist without source provenance."""

    with pytest.raises(ValueError):
        ISOStandardInventory(
            inventory_id="inventory",
            verified_on=date(2026, 8, 27),
            source_urls=(),
            records=(),
        )


def test_blank_inventory_identity_is_rejected() -> None:
    """Inventory snapshots require a stable identity."""

    with pytest.raises(ValueError):
        ISOStandardInventory(
            inventory_id="",
            verified_on=date(2026, 8, 27),
            source_urls=("https://www.iso.org/",),
            records=(),
        )


def test_blank_source_url_is_rejected() -> None:
    """Empty provenance entries are invalid."""

    with pytest.raises(ValueError):
        ISOStandardInventory(
            inventory_id="inventory",
            verified_on=date(2026, 8, 27),
            source_urls=(" ",),
            records=(),
        )

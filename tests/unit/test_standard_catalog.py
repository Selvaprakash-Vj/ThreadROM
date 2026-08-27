"""Tests for scalable ISO fastener-standard catalogue primitives."""

import pytest

from threadrom.case.standard_catalog import (
    FastenerProductKind,
    ISOStandardCatalogRecord,
    StandardCapability,
    StandardLifecycle,
    StandardRole,
)


def _product_record(
    *,
    lifecycle: StandardLifecycle = StandardLifecycle.PUBLISHED,
    capability: StandardCapability = StandardCapability.METADATA_ONLY,
) -> ISOStandardCatalogRecord:
    return ISOStandardCatalogRecord(
        reference="ISO 4017:2022",
        title="Fasteners — Hexagon head screws",
        lifecycle=lifecycle,
        role=StandardRole.PRODUCT_GEOMETRY,
        product_kind=FastenerProductKind.SCREW,
        ics_code="21.060.10",
        capability=capability,
    )


def test_published_standard_is_current() -> None:
    """Published ISO records are current catalogue entries."""

    record = _product_record()

    assert record.is_current is True
    assert record.is_product_standard is True


def test_withdrawn_standard_is_not_current() -> None:
    """Withdrawn standards remain traceable but are not current."""

    record = _product_record(
        lifecycle=StandardLifecycle.WITHDRAWN,
    )

    assert record.is_current is False


def test_metadata_only_product_is_not_selectable() -> None:
    """Knowledge of a standard does not imply product support."""

    record = _product_record(
        capability=StandardCapability.METADATA_ONLY,
    )

    assert record.selectable_in_standard_mode is False


def test_dimensional_product_can_be_exposed_for_supported_workflows() -> None:
    """Verified dimensional data crosses the catalogue selection gate."""

    record = _product_record(
        capability=StandardCapability.DIMENSIONAL_DATA,
    )

    assert record.selectable_in_standard_mode is True


def test_nonproduct_support_standard_is_not_product_selectable() -> None:
    """Supporting standards never masquerade as fastener products."""

    record = ISOStandardCatalogRecord(
        reference="ISO 724:2023",
        title="ISO general purpose metric screw threads — Basic dimensions",
        lifecycle=StandardLifecycle.PUBLISHED,
        role=StandardRole.DIMENSIONAL_SUPPORT,
        product_kind=FastenerProductKind.THREAD,
        ics_code="21.040.10",
        capability=StandardCapability.DIMENSIONAL_DATA,
    )

    assert record.is_product_standard is False
    assert record.selectable_in_standard_mode is False


@pytest.mark.parametrize(
    ("reference", "title", "ics_code"),
    [
        ("", "Title", "21.060.10"),
        ("ISO 4017:2022", "", "21.060.10"),
        ("ISO 4017:2022", "Title", ""),
    ],
)
def test_blank_catalog_identity_fields_are_rejected(
    reference: str,
    title: str,
    ics_code: str,
) -> None:
    """Catalogue records require traceable standard identities."""

    with pytest.raises(ValueError):
        ISOStandardCatalogRecord(
            reference=reference,
            title=title,
            lifecycle=StandardLifecycle.PUBLISHED,
            role=StandardRole.PRODUCT_GEOMETRY,
            product_kind=FastenerProductKind.SCREW,
            ics_code=ics_code,
        )

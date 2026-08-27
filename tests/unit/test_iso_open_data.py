"""Tests for normalized ISO Open Data records."""

from datetime import date

import pytest

from threadrom.case.iso_open_data import ISOOpenDataRecord
from threadrom.case.standard_catalog import StandardLifecycle


def _published_record() -> ISOOpenDataRecord:
    """Return one representative normalized published ISO record."""

    return ISOOpenDataRecord(
        iso_deliverable_id=12345,
        reference="ISO 4017:2022",
        title_en="Fasteners - Hexagon head screws",
        deliverable_type="IS",
        edition=6,
        ics_codes=("21.060.10",),
        current_stage=6060,
        lifecycle=StandardLifecycle.PUBLISHED,
        publication_date=date(2022, 6, 1),
        owner_committee="ISO/TC 2/SC 11",
        replaces=(6789,),
        replaced_by=(),
    )


def test_published_record_is_preserved() -> None:
    """Normalized metadata remains available without reinterpretation."""

    record = _published_record()

    assert record.iso_deliverable_id == 12345
    assert record.reference == "ISO 4017:2022"
    assert record.edition == 6
    assert record.ics_codes == ("21.060.10",)
    assert record.is_published is True
    assert record.is_withdrawn is False


def test_review_stage_remains_published() -> None:
    """ISO stage 90.xx remains a published lifecycle state."""

    record = ISOOpenDataRecord(
        iso_deliverable_id=1,
        reference="ISO 261:1998",
        title_en="Metric screw-thread plan",
        deliverable_type="IS",
        edition=2,
        ics_codes=("21.040.10",),
        current_stage=9093,
        lifecycle=StandardLifecycle.PUBLISHED,
        publication_date=date(1998, 12, 1),
        owner_committee="ISO/TC 1",
        replaces=(),
        replaced_by=(),
    )

    assert record.is_published is True


def test_withdrawn_record_is_identified() -> None:
    """Withdrawn ISO deliverables remain traceable."""

    record = ISOOpenDataRecord(
        iso_deliverable_id=2,
        reference="ISO 4017:1988",
        title_en="Historical fastener standard",
        deliverable_type="IS",
        edition=1,
        ics_codes=("21.060.10",),
        current_stage=9599,
        lifecycle=StandardLifecycle.WITHDRAWN,
        publication_date=date(1988, 1, 1),
        owner_committee=None,
        replaces=(),
        replaced_by=(12345,),
    )

    assert record.is_withdrawn is True
    assert record.is_published is False


def test_lifecycle_must_match_iso_stage() -> None:
    """Importer cannot assign a lifecycle inconsistent with ISO stage."""

    with pytest.raises(ValueError):
        ISOOpenDataRecord(
            iso_deliverable_id=1,
            reference="ISO TEST",
            title_en="Test",
            deliverable_type="IS",
            edition=1,
            ics_codes=("21.060.10",),
            current_stage=9599,
            lifecycle=StandardLifecycle.PUBLISHED,
            publication_date=None,
            owner_committee=None,
            replaces=(),
            replaced_by=(),
        )


def test_multiple_ics_codes_are_supported() -> None:
    """A deliverable may belong to more than one ISO classification."""

    record = ISOOpenDataRecord(
        iso_deliverable_id=1,
        reference="ISO TEST",
        title_en="Test",
        deliverable_type="IS",
        edition=1,
        ics_codes=("21.060.10", "21.060.20"),
        current_stage=6060,
        lifecycle=StandardLifecycle.PUBLISHED,
        publication_date=None,
        owner_committee=None,
        replaces=(),
        replaced_by=(),
    )

    assert len(record.ics_codes) == 2


def test_duplicate_ics_codes_are_rejected() -> None:
    """Normalized ISO classifications must be unique."""

    with pytest.raises(ValueError):
        ISOOpenDataRecord(
            iso_deliverable_id=1,
            reference="ISO TEST",
            title_en="Test",
            deliverable_type="IS",
            edition=1,
            ics_codes=("21.060.10", "21.060.10"),
            current_stage=6060,
            lifecycle=StandardLifecycle.PUBLISHED,
            publication_date=None,
            owner_committee=None,
            replaces=(),
            replaced_by=(),
        )


def test_normalized_record_requires_ics_classification() -> None:
    """ThreadROM fastener snapshots require at least one target ICS code."""

    with pytest.raises(ValueError):
        ISOOpenDataRecord(
            iso_deliverable_id=1,
            reference="ISO TEST",
            title_en="Test",
            deliverable_type="IS",
            edition=1,
            ics_codes=(),
            current_stage=6060,
            lifecycle=StandardLifecycle.PUBLISHED,
            publication_date=None,
            owner_committee=None,
            replaces=(),
            replaced_by=(),
        )


def test_duplicate_replacement_ids_are_rejected() -> None:
    """Replacement relationships remain unambiguous."""

    with pytest.raises(ValueError):
        ISOOpenDataRecord(
            iso_deliverable_id=1,
            reference="ISO TEST",
            title_en="Test",
            deliverable_type="IS",
            edition=1,
            ics_codes=("21.060.10",),
            current_stage=6060,
            lifecycle=StandardLifecycle.PUBLISHED,
            publication_date=None,
            owner_committee=None,
            replaces=(5, 5),
            replaced_by=(),
        )


def test_invalid_deliverable_identity_is_rejected() -> None:
    """ISO Open Data identities must be positive."""

    with pytest.raises(ValueError):
        ISOOpenDataRecord(
            iso_deliverable_id=0,
            reference="ISO TEST",
            title_en="Test",
            deliverable_type="IS",
            edition=1,
            ics_codes=("21.060.10",),
            current_stage=6060,
            lifecycle=StandardLifecycle.PUBLISHED,
            publication_date=None,
            owner_committee=None,
            replaces=(),
            replaced_by=(),
        )

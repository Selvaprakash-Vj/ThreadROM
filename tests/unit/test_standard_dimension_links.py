"""Tests linking every governed M10 runtime dimension to evidence."""

from datetime import date

import pytest

from threadrom.case.standard_dimensions import (
    DimensionEvidenceBasis,
    GovernedDimensionEvidence,
)
from threadrom.case.standards import (
    resolve_bolt_standard,
    resolve_metric_thread_standard,
    resolve_nut_standard,
)


VERIFICATION_REFERENCE = (
    "docs/verification/"
    "TRM-STD-000001_M10_DIMENSIONAL_PROVENANCE.md"
)
VERIFICATION_DATE = date(2026, 9, 14)


def _assert_standard_derived_evidence(
    evidence: GovernedDimensionEvidence,
    *,
    quantity_name: str,
    value_mm: float,
    standard_reference: str,
) -> None:
    assert (
        evidence.evidence_basis
        is DimensionEvidenceBasis.STANDARD_DERIVED
    )
    assert evidence.standard_reference == standard_reference
    assert evidence.thread_designation == "M10x1.5"
    assert evidence.quantity_name == quantity_name
    assert evidence.value_mm == pytest.approx(value_mm)
    assert evidence.source_reference.strip()
    assert evidence.verification_reference == VERIFICATION_REFERENCE
    assert evidence.verified_on == VERIFICATION_DATE
    assert evidence.is_verified is True


def _assert_certified_realized_baseline(
    evidence: GovernedDimensionEvidence,
    *,
    quantity_name: str,
    value_mm: float,
) -> None:
    assert (
        evidence.evidence_basis
        is DimensionEvidenceBasis.CERTIFIED_REALIZED_BASELINE
    )
    assert evidence.standard_reference is None
    assert evidence.thread_designation == "M10x1.5"
    assert evidence.quantity_name == quantity_name
    assert evidence.value_mm == pytest.approx(value_mm)
    assert evidence.source_reference.strip()
    assert evidence.verification_reference is not None
    assert evidence.verification_reference.strip()
    assert evidence.is_verified is True


def test_m10_thread_dimensions_are_standard_derived() -> None:
    record = resolve_metric_thread_standard("M10x1.5")

    _assert_standard_derived_evidence(
        record.nominal_diameter_evidence,
        quantity_name="nominal_diameter_mm",
        value_mm=record.nominal_diameter_mm,
        standard_reference="ISO 262:2023",
    )
    _assert_standard_derived_evidence(
        record.pitch_evidence,
        quantity_name="pitch_mm",
        value_mm=record.pitch_mm,
        standard_reference="ISO 262:2023",
    )


def test_m10_bolt_dimensions_are_standard_derived() -> None:
    record = resolve_bolt_standard(
        "ISO 4017:2022",
        "M10x1.5",
    )

    _assert_standard_derived_evidence(
        record.head_across_flats_evidence,
        quantity_name="head_across_flats_mm",
        value_mm=record.head_across_flats_mm,
        standard_reference="ISO 4017:2022",
    )
    _assert_standard_derived_evidence(
        record.head_height_evidence,
        quantity_name="head_height_mm",
        value_mm=record.head_height_mm,
        standard_reference="ISO 4017:2022",
    )


def test_m10_nut_across_flats_is_standard_derived() -> None:
    record = resolve_nut_standard(
        "ISO 4032:2023",
        "M10x1.5",
    )

    _assert_standard_derived_evidence(
        record.across_flats_evidence,
        quantity_name="nut_across_flats_mm",
        value_mm=record.across_flats_mm,
        standard_reference="ISO 4032:2023",
    )


def test_m10_nut_thickness_remains_realized_baseline_only() -> None:
    record = resolve_nut_standard(
        "ISO 4032:2023",
        "M10x1.5",
    )

    _assert_certified_realized_baseline(
        record.thickness_evidence,
        quantity_name="nut_thickness_mm",
        value_mm=record.thickness_mm,
    )

    assert record.thickness_mm == pytest.approx(8.0)


def test_m10_runtime_values_remain_exactly_unchanged() -> None:
    thread = resolve_metric_thread_standard("M10x1.5")
    bolt = resolve_bolt_standard(
        "ISO 4017:2022",
        "M10x1.5",
    )
    nut = resolve_nut_standard(
        "ISO 4032:2023",
        "M10x1.5",
    )

    assert thread.nominal_diameter_mm == pytest.approx(10.0)
    assert thread.pitch_mm == pytest.approx(1.5)

    assert bolt.head_across_flats_mm == pytest.approx(16.0)
    assert bolt.head_height_mm == pytest.approx(6.4)

    assert nut.across_flats_mm == pytest.approx(16.0)
    assert nut.thickness_mm == pytest.approx(8.0)

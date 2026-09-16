"""Contract tests for governed M8/M12 dimensional admission."""

from datetime import date

import pytest

from threadrom.case.standard_dimensions import (
    DimensionEvidenceBasis,
)
from threadrom.case.standards import (
    resolve_bolt_standard,
    resolve_metric_thread_standard,
    resolve_nut_standard,
)


VERIFICATION_REFERENCE = (
    "docs/verification/"
    "TRM-STD-000002_CROSS_SIZE_DIMENSIONAL_PROVENANCE.md"
)
VERIFICATION_DATE = date(2026, 9, 15)


@pytest.mark.parametrize(
    (
        "designation",
        "nominal_diameter_mm",
        "pitch_mm",
    ),
    (
        ("M8x1.25", 8.0, 1.25),
        ("M12x1.75", 12.0, 1.75),
    ),
)
def test_cross_size_thread_records_are_governed(
    designation: str,
    nominal_diameter_mm: float,
    pitch_mm: float,
) -> None:
    record = resolve_metric_thread_standard(designation)

    assert record.nominal_diameter_mm == pytest.approx(
        nominal_diameter_mm
    )
    assert record.pitch_mm == pytest.approx(pitch_mm)

    for evidence in (
        record.nominal_diameter_evidence,
        record.pitch_evidence,
    ):
        assert (
            evidence.evidence_basis
            is DimensionEvidenceBasis.STANDARD_DERIVED
        )
        assert evidence.standard_reference == "ISO 262:2023"
        assert evidence.thread_designation == designation
        assert evidence.verification_reference == VERIFICATION_REFERENCE
        assert evidence.verified_on == VERIFICATION_DATE
        assert evidence.is_verified is True


@pytest.mark.parametrize(
    (
        "designation",
        "across_flats_mm",
        "head_height_mm",
    ),
    (
        ("M8x1.25", 13.0, 5.3),
        ("M12x1.75", 18.0, 7.5),
    ),
)
def test_cross_size_iso4017_bolt_records_are_governed(
    designation: str,
    across_flats_mm: float,
    head_height_mm: float,
) -> None:
    record = resolve_bolt_standard(
        "ISO 4017:2022",
        designation,
    )

    assert record.head_across_flats_mm == pytest.approx(
        across_flats_mm
    )
    assert record.head_height_mm == pytest.approx(
        head_height_mm
    )

    for evidence in (
        record.head_across_flats_evidence,
        record.head_height_evidence,
    ):
        assert (
            evidence.evidence_basis
            is DimensionEvidenceBasis.STANDARD_DERIVED
        )
        assert evidence.standard_reference == "ISO 4017:2022"
        assert evidence.thread_designation == designation
        assert evidence.verification_reference == VERIFICATION_REFERENCE
        assert evidence.verified_on == VERIFICATION_DATE
        assert evidence.is_verified is True


@pytest.mark.parametrize(
    (
        "designation",
        "across_flats_mm",
        "thickness_mm",
        "minimum_mm",
        "maximum_mm",
    ),
    (
        (
            "M8x1.25",
            13.0,
            6.620,
            6.44,
            6.80,
        ),
        (
            "M12x1.75",
            18.0,
            10.585,
            10.37,
            10.80,
        ),
    ),
)
def test_cross_size_iso4032_nut_records_are_governed(
    designation: str,
    across_flats_mm: float,
    thickness_mm: float,
    minimum_mm: float,
    maximum_mm: float,
) -> None:
    record = resolve_nut_standard(
        "ISO 4032:2023",
        designation,
    )

    assert record.across_flats_mm == pytest.approx(
        across_flats_mm
    )
    assert record.thickness_mm == pytest.approx(
        thickness_mm
    )

    af_evidence = record.across_flats_evidence
    thickness_evidence = record.thickness_evidence

    assert (
        af_evidence.evidence_basis
        is DimensionEvidenceBasis.STANDARD_DERIVED
    )
    assert af_evidence.standard_reference == "ISO 4032:2023"
    assert af_evidence.thread_designation == designation
    assert af_evidence.verification_reference == VERIFICATION_REFERENCE
    assert af_evidence.verified_on == VERIFICATION_DATE

    assert (
        thickness_evidence.evidence_basis
        is DimensionEvidenceBasis.STANDARD_RANGE_SELECTED
    )
    assert (
        thickness_evidence.standard_reference
        == "ISO 4032:2023"
    )
    assert thickness_evidence.thread_designation == designation
    assert thickness_evidence.standard_minimum_mm == pytest.approx(
        minimum_mm
    )
    assert thickness_evidence.standard_maximum_mm == pytest.approx(
        maximum_mm
    )
    assert (
        thickness_evidence.selection_rule
        == "midpoint_of_verified_standard_range"
    )
    assert (
        thickness_evidence.verification_reference
        == VERIFICATION_REFERENCE
    )
    assert thickness_evidence.verified_on == VERIFICATION_DATE
    assert thickness_evidence.is_verified is True

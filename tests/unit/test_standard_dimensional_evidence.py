from datetime import date

import pytest

from threadrom.case.standard_dimensions import (
    DimensionEvidenceBasis,
    DimensionVerificationStatus,
    GovernedDimensionEvidence,
)


def _verified_standard_dimension() -> GovernedDimensionEvidence:
    return GovernedDimensionEvidence(
        evidence_id="TRM-DIM-000001",
        evidence_basis=DimensionEvidenceBasis.STANDARD_DERIVED,
        standard_reference="ISO 4017:2022",
        thread_designation="M10x1.5",
        quantity_name="head_across_flats_mm",
        value_mm=16.0,
        source_reference="governed-standard-source",
        verification_status=DimensionVerificationStatus.VERIFIED,
        verification_reference="independent-check",
        verified_on=date(2026, 9, 13),
    )


def _verified_realized_baseline() -> GovernedDimensionEvidence:
    return GovernedDimensionEvidence(
        evidence_id="TRM-DIM-000002",
        evidence_basis=(
            DimensionEvidenceBasis.CERTIFIED_REALIZED_BASELINE
        ),
        standard_reference=None,
        thread_designation="M10x1.5",
        quantity_name="nut_thickness_mm",
        value_mm=8.0,
        source_reference=(
            "config/nut_geometry.toml [nut].thickness_mm"
        ),
        verification_status=DimensionVerificationStatus.VERIFIED,
        verification_reference=(
            "docs/verification/"
            "PHASE_2_FINAL_20KN_CERTIFICATION.md"
        ),
        verified_on=date(2026, 8, 27),
    )


def test_verified_standard_dimension_preserves_provenance() -> None:
    record = _verified_standard_dimension()

    assert record.evidence_id == "TRM-DIM-000001"
    assert (
        record.evidence_basis
        is DimensionEvidenceBasis.STANDARD_DERIVED
    )
    assert record.standard_reference == "ISO 4017:2022"
    assert record.thread_designation == "M10x1.5"
    assert record.quantity_name == "head_across_flats_mm"
    assert record.value_mm == pytest.approx(16.0)
    assert record.is_verified is True


def test_certified_realized_baseline_is_not_standard_derived() -> None:
    record = _verified_realized_baseline()

    assert (
        record.evidence_basis
        is DimensionEvidenceBasis.CERTIFIED_REALIZED_BASELINE
    )
    assert record.standard_reference is None
    assert record.thread_designation == "M10x1.5"
    assert record.quantity_name == "nut_thickness_mm"
    assert record.value_mm == pytest.approx(8.0)
    assert record.is_verified is True


@pytest.mark.parametrize(
    "field_name",
    (
        "evidence_id",
        "thread_designation",
        "quantity_name",
        "source_reference",
    ),
)
def test_required_identity_and_source_fields_cannot_be_blank(
    field_name: str,
) -> None:
    values = {
        "evidence_id": "TRM-DIM-000001",
        "evidence_basis": DimensionEvidenceBasis.STANDARD_DERIVED,
        "standard_reference": "ISO 4017:2022",
        "thread_designation": "M10x1.5",
        "quantity_name": "head_across_flats_mm",
        "value_mm": 16.0,
        "source_reference": "source",
        "verification_status": DimensionVerificationStatus.PENDING,
        "verification_reference": None,
        "verified_on": None,
    }

    values[field_name] = ""

    with pytest.raises(ValueError):
        GovernedDimensionEvidence(**values)


def test_standard_derived_dimension_requires_standard_reference() -> None:
    with pytest.raises(
        ValueError,
        match="standard reference",
    ):
        GovernedDimensionEvidence(
            evidence_id="TRM-DIM-000001",
            evidence_basis=DimensionEvidenceBasis.STANDARD_DERIVED,
            standard_reference=None,
            thread_designation="M10x1.5",
            quantity_name="head_across_flats_mm",
            value_mm=16.0,
            source_reference="source",
            verification_status=DimensionVerificationStatus.PENDING,
        )


def test_realized_baseline_cannot_claim_standard_derived_reference() -> None:
    with pytest.raises(
        ValueError,
        match="standard",
    ):
        GovernedDimensionEvidence(
            evidence_id="TRM-DIM-000002",
            evidence_basis=(
                DimensionEvidenceBasis.CERTIFIED_REALIZED_BASELINE
            ),
            standard_reference="ISO 4032:2023",
            thread_designation="M10x1.5",
            quantity_name="nut_thickness_mm",
            value_mm=8.0,
            source_reference="config/nut_geometry.toml",
            verification_status=DimensionVerificationStatus.PENDING,
        )


@pytest.mark.parametrize(
    "value",
    (0.0, -1.0, float("inf"), float("-inf"), float("nan")),
)
def test_dimension_value_must_be_finite_and_positive(
    value: float,
) -> None:
    with pytest.raises(ValueError):
        GovernedDimensionEvidence(
            evidence_id="TRM-DIM-000001",
            evidence_basis=DimensionEvidenceBasis.STANDARD_DERIVED,
            standard_reference="ISO 4017:2022",
            thread_designation="M10x1.5",
            quantity_name="head_across_flats_mm",
            value_mm=value,
            source_reference="source",
            verification_status=DimensionVerificationStatus.PENDING,
        )


def test_verified_dimension_requires_verification_reference() -> None:
    with pytest.raises(
        ValueError,
        match="verification reference",
    ):
        GovernedDimensionEvidence(
            evidence_id="TRM-DIM-000001",
            evidence_basis=DimensionEvidenceBasis.STANDARD_DERIVED,
            standard_reference="ISO 4017:2022",
            thread_designation="M10x1.5",
            quantity_name="head_across_flats_mm",
            value_mm=16.0,
            source_reference="source",
            verification_status=DimensionVerificationStatus.VERIFIED,
            verification_reference=None,
            verified_on=date(2026, 9, 13),
        )


def test_verified_dimension_requires_verification_date() -> None:
    with pytest.raises(
        ValueError,
        match="verification date",
    ):
        GovernedDimensionEvidence(
            evidence_id="TRM-DIM-000001",
            evidence_basis=DimensionEvidenceBasis.STANDARD_DERIVED,
            standard_reference="ISO 4017:2022",
            thread_designation="M10x1.5",
            quantity_name="head_across_flats_mm",
            value_mm=16.0,
            source_reference="source",
            verification_status=DimensionVerificationStatus.VERIFIED,
            verification_reference="independent-check",
            verified_on=None,
        )


def test_pending_dimension_cannot_claim_completed_verification() -> None:
    with pytest.raises(ValueError):
        GovernedDimensionEvidence(
            evidence_id="TRM-DIM-000001",
            evidence_basis=DimensionEvidenceBasis.STANDARD_DERIVED,
            standard_reference="ISO 4017:2022",
            thread_designation="M10x1.5",
            quantity_name="head_across_flats_mm",
            value_mm=16.0,
            source_reference="source",
            verification_status=DimensionVerificationStatus.PENDING,
            verification_reference="independent-check",
            verified_on=date(2026, 9, 13),
        )

"""Contract tests for dimensions selected from a standard range."""

from datetime import date

import pytest

from threadrom.case.standard_dimensions import (
    DimensionEvidenceBasis,
    DimensionVerificationStatus,
    GovernedDimensionEvidence,
)


VERIFY_REF = (
    "docs/verification/"
    "TRM-STD-000002_CROSS_SIZE_DIMENSIONAL_PROVENANCE.md"
)


def _range_evidence(
    *,
    value_mm: float = 6.62,
    minimum_mm: float = 6.44,
    maximum_mm: float = 6.80,
) -> GovernedDimensionEvidence:
    return GovernedDimensionEvidence(
        evidence_id="TRM-DIM-M8-TEST",
        evidence_basis=(
            DimensionEvidenceBasis.STANDARD_RANGE_SELECTED
        ),
        standard_reference="ISO 4032:2023",
        thread_designation="M8x1.25",
        quantity_name="nut_thickness_mm",
        value_mm=value_mm,
        source_reference="independent ISO 4032 dimensional verification",
        standard_minimum_mm=minimum_mm,
        standard_maximum_mm=maximum_mm,
        selection_rule="governed_representative_value",
        verification_status=(
            DimensionVerificationStatus.VERIFIED
        ),
        verification_reference=VERIFY_REF,
        verified_on=date(2026, 9, 15),
    )


def test_standard_range_selected_evidence_is_supported() -> None:
    evidence = _range_evidence()

    assert (
        evidence.evidence_basis
        is DimensionEvidenceBasis.STANDARD_RANGE_SELECTED
    )
    assert evidence.standard_reference == "ISO 4032:2023"
    assert evidence.standard_minimum_mm == pytest.approx(6.44)
    assert evidence.standard_maximum_mm == pytest.approx(6.80)
    assert evidence.selection_rule == "governed_representative_value"
    assert evidence.is_verified is True


def test_standard_range_value_must_lie_inside_standard_range() -> None:
    with pytest.raises(
        ValueError,
        match="within",
    ):
        _range_evidence(value_mm=6.20)


def test_standard_range_limits_must_be_ordered() -> None:
    with pytest.raises(
        ValueError,
        match="range",
    ):
        _range_evidence(
            minimum_mm=6.80,
            maximum_mm=6.44,
        )


def test_exact_standard_dimension_cannot_claim_range_selection() -> None:
    with pytest.raises(ValueError):
        GovernedDimensionEvidence(
            evidence_id="TRM-DIM-EXACT-TEST",
            evidence_basis=(
                DimensionEvidenceBasis.STANDARD_DERIVED
            ),
            standard_reference="ISO 4017:2022",
            thread_designation="M8x1.25",
            quantity_name="head_height_mm",
            value_mm=5.3,
            source_reference="governed verification",
            standard_minimum_mm=5.15,
            standard_maximum_mm=5.45,
            selection_rule="midpoint",
            verification_status=(
                DimensionVerificationStatus.VERIFIED
            ),
            verification_reference=VERIFY_REF,
            verified_on=date(2026, 9, 15),
        )


def test_realized_baseline_cannot_claim_standard_range() -> None:
    with pytest.raises(ValueError):
        GovernedDimensionEvidence(
            evidence_id="TRM-DIM-BASELINE-TEST",
            evidence_basis=(
                DimensionEvidenceBasis.CERTIFIED_REALIZED_BASELINE
            ),
            standard_reference=None,
            thread_designation="M10x1.5",
            quantity_name="nut_thickness_mm",
            value_mm=8.0,
            source_reference="certified M10 geometry",
            standard_minimum_mm=8.04,
            standard_maximum_mm=8.40,
            selection_rule="legacy",
            verification_status=(
                DimensionVerificationStatus.VERIFIED
            ),
            verification_reference=VERIFY_REF,
            verified_on=date(2026, 9, 15),
        )

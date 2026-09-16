"""Governed fastener-standard reference data for Phase-3 resolution.

Only values already established by the certified ThreadROM baseline are
registered here. Additional product sizes/standards must be added with
traceable reference data and validation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from threadrom.case.standard_dimensions import (
    DimensionEvidenceBasis,
    DimensionVerificationStatus,
    GovernedDimensionEvidence,
)


_PHASE2_CERTIFICATION = (
    "docs/verification/PHASE_2_FINAL_20KN_CERTIFICATION.md"
)
_PHASE2_CERTIFICATION_DATE = date(2026, 8, 27)


@dataclass(frozen=True)
class MetricThreadStandardRecord:
    """Resolved basic designation data for one governed metric thread."""

    designation: str
    nominal_diameter_mm: float
    pitch_mm: float
    nominal_diameter_evidence: GovernedDimensionEvidence
    pitch_evidence: GovernedDimensionEvidence


@dataclass(frozen=True)
class BoltStandardRecord:
    """Governed product dimensions required by the current bolt CAD."""

    product_standard: str
    thread_designation: str
    head_across_flats_mm: float
    head_height_mm: float
    head_across_flats_evidence: GovernedDimensionEvidence
    head_height_evidence: GovernedDimensionEvidence


@dataclass(frozen=True)
class NutStandardRecord:
    """Governed product dimensions required by the current nut CAD."""

    product_standard: str
    thread_designation: str
    across_flats_mm: float
    thickness_mm: float
    across_flats_evidence: GovernedDimensionEvidence
    thickness_evidence: GovernedDimensionEvidence


_M10_STANDARD_VERIFICATION = (
    "docs/verification/"
    "TRM-STD-000001_M10_DIMENSIONAL_PROVENANCE.md"
)
_M10_STANDARD_VERIFICATION_DATE = date(2026, 9, 14)

_CROSS_SIZE_STANDARD_VERIFICATION = (
    "docs/verification/"
    "TRM-STD-000002_CROSS_SIZE_DIMENSIONAL_PROVENANCE.md"
)
_CROSS_SIZE_STANDARD_VERIFICATION_DATE = date(2026, 9, 15)


def _verified_standard_dimension(
    *,
    evidence_id: str,
    standard_reference: str,
    thread_designation: str,
    quantity_name: str,
    value_mm: float,
    source_reference: str,
    verification_reference: str,
    verified_on: date,
) -> GovernedDimensionEvidence:
    """Create independently verified standard-derived dimensional evidence."""

    return GovernedDimensionEvidence(
        evidence_id=evidence_id,
        evidence_basis=DimensionEvidenceBasis.STANDARD_DERIVED,
        standard_reference=standard_reference,
        thread_designation=thread_designation,
        quantity_name=quantity_name,
        value_mm=value_mm,
        source_reference=source_reference,
        verification_status=DimensionVerificationStatus.VERIFIED,
        verification_reference=verification_reference,
        verified_on=verified_on,
    )


def _verified_standard_range_dimension(
    *,
    evidence_id: str,
    standard_reference: str,
    thread_designation: str,
    quantity_name: str,
    value_mm: float,
    source_reference: str,
    standard_minimum_mm: float,
    standard_maximum_mm: float,
    selection_rule: str,
    verification_reference: str,
    verified_on: date,
) -> GovernedDimensionEvidence:
    """Create a governed value selected from a verified standard range."""

    return GovernedDimensionEvidence(
        evidence_id=evidence_id,
        evidence_basis=DimensionEvidenceBasis.STANDARD_RANGE_SELECTED,
        standard_reference=standard_reference,
        thread_designation=thread_designation,
        quantity_name=quantity_name,
        value_mm=value_mm,
        source_reference=source_reference,
        verification_status=DimensionVerificationStatus.VERIFIED,
        verification_reference=verification_reference,
        verified_on=verified_on,
        standard_minimum_mm=standard_minimum_mm,
        standard_maximum_mm=standard_maximum_mm,
        selection_rule=selection_rule,
    )


def _certified_m10_baseline_dimension(
    *,
    evidence_id: str,
    quantity_name: str,
    value_mm: float,
    source_reference: str,
) -> GovernedDimensionEvidence:
    """Create evidence for one realised dimension of the certified M10 anchor."""

    return GovernedDimensionEvidence(
        evidence_id=evidence_id,
        evidence_basis=(
            DimensionEvidenceBasis.CERTIFIED_REALIZED_BASELINE
        ),
        standard_reference=None,
        thread_designation="M10x1.5",
        quantity_name=quantity_name,
        value_mm=value_mm,
        source_reference=source_reference,
        verification_status=DimensionVerificationStatus.VERIFIED,
        verification_reference=_PHASE2_CERTIFICATION,
        verified_on=_PHASE2_CERTIFICATION_DATE,
    )


_M10_NOMINAL_DIAMETER_EVIDENCE = _verified_standard_dimension(
    thread_designation="M10x1.5",
    evidence_id="TRM-DIM-M10-000001",
    standard_reference="ISO 262:2023",
    quantity_name="nominal_diameter_mm",
    value_mm=10.0,
    source_reference=(
        "config/baseline_fastener.toml [thread].nominal_diameter_mm"
    ),    verification_reference=_M10_STANDARD_VERIFICATION,
    verified_on=_M10_STANDARD_VERIFICATION_DATE,
)

_M10_PITCH_EVIDENCE = _verified_standard_dimension(
    thread_designation="M10x1.5",
    evidence_id="TRM-DIM-M10-000002",
    standard_reference="ISO 262:2023",
    quantity_name="pitch_mm",
    value_mm=1.5,
    source_reference=(
        "config/baseline_fastener.toml [thread].pitch_mm"
    ),    verification_reference=_M10_STANDARD_VERIFICATION,
    verified_on=_M10_STANDARD_VERIFICATION_DATE,
)

_M10_BOLT_AF_EVIDENCE = _verified_standard_dimension(
    thread_designation="M10x1.5",
    evidence_id="TRM-DIM-M10-000003",
    standard_reference="ISO 4017:2022",
    quantity_name="head_across_flats_mm",
    value_mm=16.0,
    source_reference=(
        "config/baseline_geometry.toml "
        "[bolt_blank].head_across_flats_mm"
    ),    verification_reference=_M10_STANDARD_VERIFICATION,
    verified_on=_M10_STANDARD_VERIFICATION_DATE,
)

_M10_BOLT_HEAD_HEIGHT_EVIDENCE = _verified_standard_dimension(
    thread_designation="M10x1.5",
    evidence_id="TRM-DIM-M10-000004",
    standard_reference="ISO 4017:2022",
    quantity_name="head_height_mm",
    value_mm=6.4,
    source_reference=(
        "config/baseline_geometry.toml "
        "[bolt_blank].head_height_mm"
    ),    verification_reference=_M10_STANDARD_VERIFICATION,
    verified_on=_M10_STANDARD_VERIFICATION_DATE,
)

_M10_NUT_AF_EVIDENCE = _verified_standard_dimension(
    thread_designation="M10x1.5",
    evidence_id="TRM-DIM-M10-000005",
    standard_reference="ISO 4032:2023",
    quantity_name="nut_across_flats_mm",
    value_mm=16.0,
    source_reference=(
        "config/nut_geometry.toml [nut].across_flats_mm"
    ),    verification_reference=_M10_STANDARD_VERIFICATION,
    verified_on=_M10_STANDARD_VERIFICATION_DATE,
)

_M10_NUT_THICKNESS_EVIDENCE = _certified_m10_baseline_dimension(
    evidence_id="TRM-DIM-M10-000006",
    quantity_name="nut_thickness_mm",
    value_mm=8.0,
    source_reference=(
        "config/nut_geometry.toml [nut].thickness_mm"
    ),
)


_M8_NOMINAL_DIAMETER_EVIDENCE = _verified_standard_dimension(
    evidence_id="TRM-DIM-M8-000001",
    standard_reference="ISO 262:2023",
    thread_designation="M8x1.25",
    quantity_name="nominal_diameter_mm",
    value_mm=8.0,
    source_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verification_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verified_on=_CROSS_SIZE_STANDARD_VERIFICATION_DATE,
)

_M8_PITCH_EVIDENCE = _verified_standard_dimension(
    evidence_id="TRM-DIM-M8-000002",
    standard_reference="ISO 262:2023",
    thread_designation="M8x1.25",
    quantity_name="pitch_mm",
    value_mm=1.25,
    source_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verification_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verified_on=_CROSS_SIZE_STANDARD_VERIFICATION_DATE,
)

_M8_BOLT_AF_EVIDENCE = _verified_standard_dimension(
    evidence_id="TRM-DIM-M8-000003",
    standard_reference="ISO 4017:2022",
    thread_designation="M8x1.25",
    quantity_name="head_across_flats_mm",
    value_mm=13.0,
    source_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verification_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verified_on=_CROSS_SIZE_STANDARD_VERIFICATION_DATE,
)

_M8_BOLT_HEAD_HEIGHT_EVIDENCE = _verified_standard_dimension(
    evidence_id="TRM-DIM-M8-000004",
    standard_reference="ISO 4017:2022",
    thread_designation="M8x1.25",
    quantity_name="head_height_mm",
    value_mm=5.3,
    source_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verification_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verified_on=_CROSS_SIZE_STANDARD_VERIFICATION_DATE,
)

_M8_NUT_AF_EVIDENCE = _verified_standard_dimension(
    evidence_id="TRM-DIM-M8-000005",
    standard_reference="ISO 4032:2023",
    thread_designation="M8x1.25",
    quantity_name="nut_across_flats_mm",
    value_mm=13.0,
    source_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verification_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verified_on=_CROSS_SIZE_STANDARD_VERIFICATION_DATE,
)

_M8_NUT_THICKNESS_EVIDENCE = _verified_standard_range_dimension(
    evidence_id="TRM-DIM-M8-000006",
    standard_reference="ISO 4032:2023",
    thread_designation="M8x1.25",
    quantity_name="nut_thickness_mm",
    value_mm=6.620,
    source_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    standard_minimum_mm=6.44,
    standard_maximum_mm=6.80,
    selection_rule="midpoint_of_verified_standard_range",
    verification_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verified_on=_CROSS_SIZE_STANDARD_VERIFICATION_DATE,
)

_M12_NOMINAL_DIAMETER_EVIDENCE = _verified_standard_dimension(
    evidence_id="TRM-DIM-M12-000001",
    standard_reference="ISO 262:2023",
    thread_designation="M12x1.75",
    quantity_name="nominal_diameter_mm",
    value_mm=12.0,
    source_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verification_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verified_on=_CROSS_SIZE_STANDARD_VERIFICATION_DATE,
)

_M12_PITCH_EVIDENCE = _verified_standard_dimension(
    evidence_id="TRM-DIM-M12-000002",
    standard_reference="ISO 262:2023",
    thread_designation="M12x1.75",
    quantity_name="pitch_mm",
    value_mm=1.75,
    source_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verification_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verified_on=_CROSS_SIZE_STANDARD_VERIFICATION_DATE,
)

_M12_BOLT_AF_EVIDENCE = _verified_standard_dimension(
    evidence_id="TRM-DIM-M12-000003",
    standard_reference="ISO 4017:2022",
    thread_designation="M12x1.75",
    quantity_name="head_across_flats_mm",
    value_mm=18.0,
    source_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verification_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verified_on=_CROSS_SIZE_STANDARD_VERIFICATION_DATE,
)

_M12_BOLT_HEAD_HEIGHT_EVIDENCE = _verified_standard_dimension(
    evidence_id="TRM-DIM-M12-000004",
    standard_reference="ISO 4017:2022",
    thread_designation="M12x1.75",
    quantity_name="head_height_mm",
    value_mm=7.5,
    source_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verification_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verified_on=_CROSS_SIZE_STANDARD_VERIFICATION_DATE,
)

_M12_NUT_AF_EVIDENCE = _verified_standard_dimension(
    evidence_id="TRM-DIM-M12-000005",
    standard_reference="ISO 4032:2023",
    thread_designation="M12x1.75",
    quantity_name="nut_across_flats_mm",
    value_mm=18.0,
    source_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verification_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verified_on=_CROSS_SIZE_STANDARD_VERIFICATION_DATE,
)

_M12_NUT_THICKNESS_EVIDENCE = _verified_standard_range_dimension(
    evidence_id="TRM-DIM-M12-000006",
    standard_reference="ISO 4032:2023",
    thread_designation="M12x1.75",
    quantity_name="nut_thickness_mm",
    value_mm=10.585,
    source_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    standard_minimum_mm=10.37,
    standard_maximum_mm=10.80,
    selection_rule="midpoint_of_verified_standard_range",
    verification_reference=_CROSS_SIZE_STANDARD_VERIFICATION,
    verified_on=_CROSS_SIZE_STANDARD_VERIFICATION_DATE,
)


_THREAD_RECORDS = {
    "M8x1.25": MetricThreadStandardRecord(
        designation="M8x1.25",
        nominal_diameter_mm=8.0,
        pitch_mm=1.25,
        nominal_diameter_evidence=_M8_NOMINAL_DIAMETER_EVIDENCE,
        pitch_evidence=_M8_PITCH_EVIDENCE,
    ),
    "M10x1.5": MetricThreadStandardRecord(
        designation="M10x1.5",
        nominal_diameter_mm=10.0,
        pitch_mm=1.5,
        nominal_diameter_evidence=_M10_NOMINAL_DIAMETER_EVIDENCE,
        pitch_evidence=_M10_PITCH_EVIDENCE,
    ),
    "M12x1.75": MetricThreadStandardRecord(
        designation="M12x1.75",
        nominal_diameter_mm=12.0,
        pitch_mm=1.75,
        nominal_diameter_evidence=_M12_NOMINAL_DIAMETER_EVIDENCE,
        pitch_evidence=_M12_PITCH_EVIDENCE,
    ),
}


_BOLT_RECORDS = {
    ("ISO 4017:2022", "M8x1.25"): BoltStandardRecord(
        product_standard="ISO 4017:2022",
        thread_designation="M8x1.25",
        head_across_flats_mm=13.0,
        head_height_mm=5.3,
        head_across_flats_evidence=_M8_BOLT_AF_EVIDENCE,
        head_height_evidence=_M8_BOLT_HEAD_HEIGHT_EVIDENCE,
    ),
    ("ISO 4017:2022", "M10x1.5"): BoltStandardRecord(
        product_standard="ISO 4017:2022",
        thread_designation="M10x1.5",
        head_across_flats_mm=16.0,
        head_height_mm=6.4,
        head_across_flats_evidence=_M10_BOLT_AF_EVIDENCE,
        head_height_evidence=_M10_BOLT_HEAD_HEIGHT_EVIDENCE,
    ),
    ("ISO 4017:2022", "M12x1.75"): BoltStandardRecord(
        product_standard="ISO 4017:2022",
        thread_designation="M12x1.75",
        head_across_flats_mm=18.0,
        head_height_mm=7.5,
        head_across_flats_evidence=_M12_BOLT_AF_EVIDENCE,
        head_height_evidence=_M12_BOLT_HEAD_HEIGHT_EVIDENCE,
    ),
}


_NUT_RECORDS = {
    ("ISO 4032:2023", "M8x1.25"): NutStandardRecord(
        product_standard="ISO 4032:2023",
        thread_designation="M8x1.25",
        across_flats_mm=13.0,
        thickness_mm=6.620,
        across_flats_evidence=_M8_NUT_AF_EVIDENCE,
        thickness_evidence=_M8_NUT_THICKNESS_EVIDENCE,
    ),
    ("ISO 4032:2023", "M10x1.5"): NutStandardRecord(
        product_standard="ISO 4032:2023",
        thread_designation="M10x1.5",
        across_flats_mm=16.0,
        thickness_mm=8.0,
        across_flats_evidence=_M10_NUT_AF_EVIDENCE,
        thickness_evidence=_M10_NUT_THICKNESS_EVIDENCE,
    ),
    ("ISO 4032:2023", "M12x1.75"): NutStandardRecord(
        product_standard="ISO 4032:2023",
        thread_designation="M12x1.75",
        across_flats_mm=18.0,
        thickness_mm=10.585,
        across_flats_evidence=_M12_NUT_AF_EVIDENCE,
        thickness_evidence=_M12_NUT_THICKNESS_EVIDENCE,
    ),
}


def resolve_metric_thread_standard(
    designation: str,
) -> MetricThreadStandardRecord:
    """Resolve one currently governed metric-thread designation."""

    try:
        return _THREAD_RECORDS[designation]
    except KeyError as exc:
        raise ValueError(
            "No governed metric-thread standard record exists for "
            f"{designation!r}."
        ) from exc


def resolve_bolt_standard(
    product_standard: str,
    thread_designation: str,
) -> BoltStandardRecord:
    """Resolve governed bolt-product dimensions."""

    key = (product_standard, thread_designation)

    try:
        return _BOLT_RECORDS[key]
    except KeyError as exc:
        raise ValueError(
            "No governed bolt-standard record exists for "
            f"{product_standard!r}, {thread_designation!r}."
        ) from exc


def resolve_nut_standard(
    product_standard: str,
    thread_designation: str,
) -> NutStandardRecord:
    """Resolve governed nut-product dimensions."""

    key = (product_standard, thread_designation)

    try:
        return _NUT_RECORDS[key]
    except KeyError as exc:
        raise ValueError(
            "No governed nut-standard record exists for "
            f"{product_standard!r}, {thread_designation!r}."
        ) from exc

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


_M10_NOMINAL_DIAMETER_EVIDENCE = _certified_m10_baseline_dimension(
    evidence_id="TRM-DIM-M10-000001",
    quantity_name="nominal_diameter_mm",
    value_mm=10.0,
    source_reference=(
        "config/baseline_fastener.toml [thread].nominal_diameter_mm"
    ),
)

_M10_PITCH_EVIDENCE = _certified_m10_baseline_dimension(
    evidence_id="TRM-DIM-M10-000002",
    quantity_name="pitch_mm",
    value_mm=1.5,
    source_reference=(
        "config/baseline_fastener.toml [thread].pitch_mm"
    ),
)

_M10_BOLT_AF_EVIDENCE = _certified_m10_baseline_dimension(
    evidence_id="TRM-DIM-M10-000003",
    quantity_name="head_across_flats_mm",
    value_mm=16.0,
    source_reference=(
        "config/baseline_geometry.toml "
        "[bolt_blank].head_across_flats_mm"
    ),
)

_M10_BOLT_HEAD_HEIGHT_EVIDENCE = _certified_m10_baseline_dimension(
    evidence_id="TRM-DIM-M10-000004",
    quantity_name="head_height_mm",
    value_mm=6.4,
    source_reference=(
        "config/baseline_geometry.toml "
        "[bolt_blank].head_height_mm"
    ),
)

_M10_NUT_AF_EVIDENCE = _certified_m10_baseline_dimension(
    evidence_id="TRM-DIM-M10-000005",
    quantity_name="nut_across_flats_mm",
    value_mm=16.0,
    source_reference=(
        "config/nut_geometry.toml [nut].across_flats_mm"
    ),
)

_M10_NUT_THICKNESS_EVIDENCE = _certified_m10_baseline_dimension(
    evidence_id="TRM-DIM-M10-000006",
    quantity_name="nut_thickness_mm",
    value_mm=8.0,
    source_reference=(
        "config/nut_geometry.toml [nut].thickness_mm"
    ),
)


_THREAD_RECORDS = {
    "M10x1.5": MetricThreadStandardRecord(
        designation="M10x1.5",
        nominal_diameter_mm=10.0,
        pitch_mm=1.5,
        nominal_diameter_evidence=_M10_NOMINAL_DIAMETER_EVIDENCE,
        pitch_evidence=_M10_PITCH_EVIDENCE,
    ),
}


_BOLT_RECORDS = {
    ("ISO 4017:2022", "M10x1.5"): BoltStandardRecord(
        product_standard="ISO 4017:2022",
        thread_designation="M10x1.5",
        head_across_flats_mm=16.0,
        head_height_mm=6.4,
        head_across_flats_evidence=_M10_BOLT_AF_EVIDENCE,
        head_height_evidence=_M10_BOLT_HEAD_HEIGHT_EVIDENCE,
    ),
}


_NUT_RECORDS = {
    ("ISO 4032:2023", "M10x1.5"): NutStandardRecord(
        product_standard="ISO 4032:2023",
        thread_designation="M10x1.5",
        across_flats_mm=16.0,
        thickness_mm=8.0,
        across_flats_evidence=_M10_NUT_AF_EVIDENCE,
        thickness_evidence=_M10_NUT_THICKNESS_EVIDENCE,
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

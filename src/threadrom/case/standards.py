"""Governed fastener-standard reference data for Phase-3 resolution.

Only values already established by the certified ThreadROM baseline are
registered here. Additional product sizes/standards must be added with
traceable reference data and validation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricThreadStandardRecord:
    """Resolved basic designation data for one governed metric thread."""

    designation: str
    nominal_diameter_mm: float
    pitch_mm: float


@dataclass(frozen=True)
class BoltStandardRecord:
    """Governed product dimensions required by the current bolt CAD."""

    product_standard: str
    thread_designation: str
    head_across_flats_mm: float
    head_height_mm: float


@dataclass(frozen=True)
class NutStandardRecord:
    """Governed product dimensions required by the current nut CAD."""

    product_standard: str
    thread_designation: str
    across_flats_mm: float
    thickness_mm: float


_THREAD_RECORDS = {
    "M10x1.5": MetricThreadStandardRecord(
        designation="M10x1.5",
        nominal_diameter_mm=10.0,
        pitch_mm=1.5,
    ),
}


_BOLT_RECORDS = {
    ("ISO 4017:2022", "M10x1.5"): BoltStandardRecord(
        product_standard="ISO 4017:2022",
        thread_designation="M10x1.5",
        head_across_flats_mm=16.0,
        head_height_mm=6.4,
    ),
}


_NUT_RECORDS = {
    ("ISO 4032:2023", "M10x1.5"): NutStandardRecord(
        product_standard="ISO 4032:2023",
        thread_designation="M10x1.5",
        across_flats_mm=16.0,
        thickness_mm=8.0,
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

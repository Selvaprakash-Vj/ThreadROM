"""Deterministic serialization and fingerprinting of resolved engineering state."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Any

from threadrom.case.resolved_case import ResolvedCase


RESOLUTION_SCHEMA_VERSION = 1


def _canonicalize(value: Any) -> Any:
    """Convert governed engineering values into stable JSON-compatible data."""

    if is_dataclass(value):
        return {
            field.name: _canonicalize(
                getattr(value, field.name)
            )
            for field in fields(value)
        }

    if isinstance(value, Enum):
        return _canonicalize(value.value)

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Path):
        return value.as_posix()

    if isinstance(value, tuple | list):
        return [
            _canonicalize(item)
            for item in value
        ]

    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(
                value.items(),
                key=lambda pair: str(pair[0]),
            )
        }

    if isinstance(value, bool | int | float | str) or value is None:
        return value

    raise TypeError(
        "Unsupported value in canonical resolution payload: "
        f"{type(value).__name__}."
    )


def _canonical_assembly_payload(
    resolved: ResolvedCase,
) -> dict[str, object]:
    """Return physical resolved-assembly state without derived labels."""

    assembly = resolved.assembly

    return {
        "bolt_length_mm": float(assembly.bolt_length_mm),
        "pitch_mm": float(assembly.pitch_mm),
        "upper_member_thickness_mm": float(
            assembly.upper_member_thickness_mm
        ),
        "lower_member_thickness_mm": float(
            assembly.lower_member_thickness_mm
        ),
        "total_grip_length_mm": float(
            assembly.total_grip_length_mm
        ),
        "nut_thickness_mm": float(
            assembly.nut_thickness_mm
        ),
        "thread_engagement_length_mm": float(
            assembly.thread_engagement_length_mm
        ),
        "protrusion_length_mm": float(
            assembly.protrusion_length_mm
        ),
        "clearance_hole_diameter_mm": float(
            assembly.clearance_hole_diameter_mm
        ),
        "outer_diameter_mm": float(
            assembly.outer_diameter_mm
        ),
    }


def canonical_resolution_payload(
    resolved: ResolvedCase,
) -> dict[str, object]:
    """Return the canonical governed realization of one product request.

    The product-level request itself is represented by ``case_hash``.
    Human-facing case metadata is therefore not duplicated here.

    The remaining payload binds the exact resolved standards dimensions,
    dimensional provenance, derived thread/assembly data, materials, and
    fastener property-class data that downstream engineering stages consume.
    """

    return {
        "resolution_schema_version": RESOLUTION_SCHEMA_VERSION,
        "case_hash": resolved.case_hash,
        "thread_standard": _canonicalize(
            resolved.thread_standard
        ),
        "thread_basic_dimensions": _canonicalize(
            resolved.thread_basic_dimensions
        ),
        "bolt_standard": _canonicalize(
            resolved.bolt_standard
        ),
        "nut_standard": _canonicalize(
            resolved.nut_standard
        ),
        "assembly": _canonical_assembly_payload(
            resolved
        ),
        "bolt_material": _canonicalize(
            resolved.bolt_material
        ),
        "nut_material": _canonicalize(
            resolved.nut_material
        ),
        "member_materials": _canonicalize(
            resolved.member_materials
        ),
        "bolt_property_class": _canonicalize(
            resolved.bolt_property_class
        ),
        "nut_property_class": _canonicalize(
            resolved.nut_property_class
        ),
    }


def canonical_resolution_json(
    resolved: ResolvedCase,
) -> str:
    """Serialize one resolved engineering state into stable canonical JSON."""

    return json.dumps(
        canonical_resolution_payload(resolved),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def resolution_sha256(
    resolved: ResolvedCase,
) -> str:
    """Return the SHA-256 fingerprint of exact resolved engineering state."""

    payload = canonical_resolution_json(resolved).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()

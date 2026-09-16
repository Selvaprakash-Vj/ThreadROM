"""Deterministic geometry identities for governed ThreadROM CAD.

The identity hierarchy deliberately separates:

* bolt component CAD;
* nut component CAD;
* combined fastener-component CAD;
* complete assembled-joint geometry;
* full resolved engineering identity, which remains ``resolution_hash``.

Only inputs that can affect generated geometry belong here. Materials,
property classes, evidence/provenance labels, preload, solver settings,
and other non-geometric physics are intentionally excluded.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json

from threadrom.case.resolved_case import ResolvedCase
from threadrom.factory.geometry_profile import (
    CERTIFIED_PHASE2_GEOMETRY_PROFILE,
    GeometryDefinitionProfile,
)
from threadrom.geometry.threaded_shank import (
    EXTERNAL_THREAD_CONSTRUCTION_REVISION,
)


BOLT_GEOMETRY_SCHEMA_VERSION = 2
NUT_GEOMETRY_SCHEMA_VERSION = 1
COMPONENT_GEOMETRY_SCHEMA_VERSION = 2
JOINT_GEOMETRY_SCHEMA_VERSION = 2


def _sha256(payload: dict[str, object]) -> str:
    """Return deterministic SHA-256 for one canonical geometry payload."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def bolt_geometry_payload(
    resolved: ResolvedCase,
    *,
    profile: GeometryDefinitionProfile = (
        CERTIFIED_PHASE2_GEOMETRY_PROFILE
    ),
) -> dict[str, object]:
    """Return inputs that can alter generated bolt component CAD."""

    assembly = resolved.assembly
    thread = resolved.thread_basic_dimensions
    fastener = resolved.source_case.fastener

    return {
        "schema_version": BOLT_GEOMETRY_SCHEMA_VERSION,
        "implementation": {
            "external_thread_construction": (
                EXTERNAL_THREAD_CONSTRUCTION_REVISION
            ),
        },
        "thread": {
            "nominal_diameter_mm": (
                resolved.thread_standard.nominal_diameter_mm
            ),
            "pitch_mm": resolved.thread_standard.pitch_mm,
            "basic_external_minor_diameter_mm": (
                thread.basic_external_minor_diameter_mm
            ),
            "handedness": fastener.handedness.value,
        },
        "bolt": {
            "underhead_length_mm": assembly.bolt_length_mm,
            "head_across_flats_mm": (
                resolved.bolt_standard.head_across_flats_mm
            ),
            "head_height_mm": (
                resolved.bolt_standard.head_height_mm
            ),
        },
        "cad_policy": {
            "external_thread_overshoot_pitches": (
                profile.external_thread_overshoot_pitches
            ),
            "external_thread_radial_clearance_mm": (
                profile.external_thread_radial_clearance_mm
            ),
            "external_thread_use_frenet_frame": (
                profile.external_thread_use_frenet_frame
            ),
            "mating_clearance_mm": (
                profile.mating_clearance_mm
            ),
            "quality_policy": asdict(profile.quality_policy),
        },
    }


def bolt_geometry_sha256(
    resolved: ResolvedCase,
    *,
    profile: GeometryDefinitionProfile = (
        CERTIFIED_PHASE2_GEOMETRY_PROFILE
    ),
) -> str:
    """Return content identity for generated bolt CAD."""

    return _sha256(
        bolt_geometry_payload(
            resolved,
            profile=profile,
        )
    )


def nut_geometry_payload(
    resolved: ResolvedCase,
    *,
    profile: GeometryDefinitionProfile = (
        CERTIFIED_PHASE2_GEOMETRY_PROFILE
    ),
) -> dict[str, object]:
    """Return inputs that can alter generated nut component CAD."""

    assembly = resolved.assembly
    thread = resolved.thread_basic_dimensions
    fastener = resolved.source_case.fastener

    return {
        "schema_version": NUT_GEOMETRY_SCHEMA_VERSION,
        "thread": {
            "nominal_diameter_mm": (
                resolved.thread_standard.nominal_diameter_mm
            ),
            "pitch_mm": resolved.thread_standard.pitch_mm,
            "basic_internal_minor_diameter_mm": (
                thread.basic_internal_minor_diameter_mm
            ),
            "handedness": fastener.handedness.value,
        },
        "nut": {
            "across_flats_mm": (
                resolved.nut_standard.across_flats_mm
            ),
            "thickness_mm": assembly.nut_thickness_mm,
            "thread_engagement_length_mm": (
                assembly.thread_engagement_length_mm
            ),
        },
        "cad_policy": {
            "internal_thread_use_frenet_frame": (
                profile.internal_thread_use_frenet_frame
            ),
            "nut_bore_basis": profile.nut_bore_basis,
            "nut_chamfer_included": (
                profile.nut_chamfer_included
            ),
            "quality_policy": asdict(profile.quality_policy),
        },
    }


def nut_geometry_sha256(
    resolved: ResolvedCase,
    *,
    profile: GeometryDefinitionProfile = (
        CERTIFIED_PHASE2_GEOMETRY_PROFILE
    ),
) -> str:
    """Return content identity for generated nut CAD."""

    return _sha256(
        nut_geometry_payload(
            resolved,
            profile=profile,
        )
    )


def component_geometry_payload(
    resolved: ResolvedCase,
    *,
    profile: GeometryDefinitionProfile = (
        CERTIFIED_PHASE2_GEOMETRY_PROFILE
    ),
) -> dict[str, object]:
    """Return combined bolt/nut component geometry identity."""

    return {
        "schema_version": COMPONENT_GEOMETRY_SCHEMA_VERSION,
        "bolt_geometry_sha256": bolt_geometry_sha256(
            resolved,
            profile=profile,
        ),
        "nut_geometry_sha256": nut_geometry_sha256(
            resolved,
            profile=profile,
        ),
    }


def component_geometry_sha256(
    resolved: ResolvedCase,
    *,
    profile: GeometryDefinitionProfile = (
        CERTIFIED_PHASE2_GEOMETRY_PROFILE
    ),
) -> str:
    """Return content identity for complete fastener component CAD."""

    return _sha256(
        component_geometry_payload(
            resolved,
            profile=profile,
        )
    )


def joint_geometry_payload(
    resolved: ResolvedCase,
    *,
    profile: GeometryDefinitionProfile = (
        CERTIFIED_PHASE2_GEOMETRY_PROFILE
    ),
) -> dict[str, object]:
    """Return inputs defining complete assembled-joint geometry."""

    assembly = resolved.assembly

    return {
        "schema_version": JOINT_GEOMETRY_SCHEMA_VERSION,
        "component_geometry_sha256": component_geometry_sha256(
            resolved,
            profile=profile,
        ),
        "assembly": {
            "bolt_length_mm": assembly.bolt_length_mm,
            "pitch_mm": assembly.pitch_mm,
            "upper_member_thickness_mm": (
                assembly.upper_member_thickness_mm
            ),
            "lower_member_thickness_mm": (
                assembly.lower_member_thickness_mm
            ),
            "total_grip_length_mm": (
                assembly.total_grip_length_mm
            ),
            "nut_thickness_mm": assembly.nut_thickness_mm,
            "thread_engagement_length_mm": (
                assembly.thread_engagement_length_mm
            ),
            "protrusion_length_mm": (
                assembly.protrusion_length_mm
            ),
            "clearance_hole_diameter_mm": (
                assembly.clearance_hole_diameter_mm
            ),
            "outer_diameter_mm": assembly.outer_diameter_mm,
        },
        "mating_phase_offset_deg": (
            profile.mating_phase_offset_deg
        ),
    }


def joint_geometry_sha256(
    resolved: ResolvedCase,
    *,
    profile: GeometryDefinitionProfile = (
        CERTIFIED_PHASE2_GEOMETRY_PROFILE
    ),
) -> str:
    """Return content identity for complete assembled-joint CAD."""

    return _sha256(
        joint_geometry_payload(
            resolved,
            profile=profile,
        )
    )

def joint_geometry_bundle_payload(
    resolved: ResolvedCase,
    geometry: object,
) -> dict[str, object]:
    """Return identity for the complete joint geometry actually built.

    The supplied geometry bundle is authoritative for component CAD and
    mating policy. This prevents a later consumer from reconstructing
    identity using a different/default geometry profile.
    """

    assembly = resolved.assembly

    bolt_blank = getattr(geometry, "bolt_blank")
    external_thread = getattr(geometry, "external_thread")
    nut_blank = getattr(geometry, "nut_blank")
    internal_thread = getattr(geometry, "internal_thread")
    quality_policy = getattr(geometry, "quality_policy")

    return {
        "schema_version": JOINT_GEOMETRY_SCHEMA_VERSION,
        "implementation": {
            "external_thread_construction": (
                EXTERNAL_THREAD_CONSTRUCTION_REVISION
            ),
        },
        "bolt_component": {
            "nominal_diameter_mm": bolt_blank.nominal_diameter_mm,
            "underhead_length_mm": bolt_blank.underhead_length_mm,
            "head_across_flats_mm": bolt_blank.head_across_flats_mm,
            "head_height_mm": bolt_blank.head_height_mm,
            "pitch_mm": external_thread.pitch_mm,
            "minor_diameter_mm": external_thread.minor_diameter_mm,
            "thread_length_mm": external_thread.thread_length_mm,
            "overshoot_pitches": external_thread.overshoot_pitches,
            "radial_clearance_mm": external_thread.radial_clearance_mm,
            "handedness": external_thread.handedness,
            "use_frenet_frame": external_thread.use_frenet_frame,
        },
        "nut_component": {
            "nominal_diameter_mm": nut_blank.nominal_diameter_mm,
            "pitch_mm": nut_blank.pitch_mm,
            "across_flats_mm": nut_blank.across_flats_mm,
            "thickness_mm": nut_blank.thickness_mm,
            "bore_diameter_mm": nut_blank.bore_diameter_mm,
            "bore_basis": nut_blank.bore_basis,
            "chamfer_included": nut_blank.chamfer_included,
            "minor_diameter_mm": internal_thread.minor_diameter_mm,
            "thread_length_mm": internal_thread.thread_length_mm,
            "handedness": internal_thread.handedness,
            "use_frenet_frame": internal_thread.use_frenet_frame,
        },
        "quality_policy": asdict(quality_policy),
        "assembly": {
            "bolt_length_mm": assembly.bolt_length_mm,
            "pitch_mm": assembly.pitch_mm,
            "upper_member_thickness_mm": (
                assembly.upper_member_thickness_mm
            ),
            "lower_member_thickness_mm": (
                assembly.lower_member_thickness_mm
            ),
            "total_grip_length_mm": (
                assembly.total_grip_length_mm
            ),
            "nut_thickness_mm": assembly.nut_thickness_mm,
            "thread_engagement_length_mm": (
                assembly.thread_engagement_length_mm
            ),
            "protrusion_length_mm": (
                assembly.protrusion_length_mm
            ),
            "clearance_hole_diameter_mm": (
                assembly.clearance_hole_diameter_mm
            ),
            "outer_diameter_mm": assembly.outer_diameter_mm,
        },
        "mating_clearance_mm": getattr(
            geometry,
            "mating_clearance_mm",
        ),
        "mating_phase_offset_deg": getattr(
            geometry,
            "mating_phase_offset_deg",
        ),
    }


def joint_geometry_bundle_sha256(
    resolved: ResolvedCase,
    geometry: object,
) -> str:
    """Return identity for the exact complete-joint CAD definition."""

    return _sha256(
        joint_geometry_bundle_payload(
            resolved,
            geometry,
        )
    )

"""Geometry-definition adapter for resolved ThreadROM cases."""

from __future__ import annotations

from dataclasses import dataclass

from threadrom.case.resolved_case import ResolvedCase
from threadrom.factory.geometry_profile import (
    CERTIFIED_PHASE2_GEOMETRY_PROFILE,
    GeometryDefinitionProfile,
)
from threadrom.geometry.bolt_blank import (
    BoltBlankDefinition,
)
from threadrom.geometry.geometry_quality import (
    GeometryQualityPolicy,
)
from threadrom.geometry.helical_thread_cutter import (
    HelicalThreadCutterDefinition,
)
from threadrom.geometry.internal_thread_cutter import (
    InternalThreadCutterDefinition,
)
from threadrom.geometry.nut_blank import (
    NutBlankDefinition,
)


@dataclass(frozen=True)
class GeometryDefinitionBundle:
    """Complete governed geometry inputs for one resolved case."""

    bolt_blank: BoltBlankDefinition
    external_thread: HelicalThreadCutterDefinition
    nut_blank: NutBlankDefinition
    internal_thread: InternalThreadCutterDefinition
    quality_policy: GeometryQualityPolicy
    mating_clearance_mm: float
    mating_phase_offset_deg: float


def build_geometry_definitions(
    resolved: ResolvedCase,
    *,
    profile: GeometryDefinitionProfile = (
        CERTIFIED_PHASE2_GEOMETRY_PROFILE
    ),
) -> GeometryDefinitionBundle:
    """Build geometry-kernel definitions from a resolved case."""

    case = resolved.source_case
    fastener = case.fastener
    assembly = resolved.assembly
    thread = resolved.thread_basic_dimensions

    if profile.nut_bore_basis != (
        "basic_internal_minor_diameter"
    ):
        raise ValueError(
            "The current geometry adapter supports only "
            "'basic_internal_minor_diameter' as the nut bore basis."
        )

    case_token = resolved.case_hash[:16]
    bolt_geometry_id = f"bolt-geometry-{case_token}"
    nut_geometry_id = f"nut-geometry-{case_token}"

    bolt_blank = BoltBlankDefinition(
        geometry_id=bolt_geometry_id,
        nominal_diameter_mm=(
            resolved.thread_standard.nominal_diameter_mm
        ),
        underhead_length_mm=assembly.bolt_length_mm,
        head_across_flats_mm=(
            resolved.bolt_standard.head_across_flats_mm
        ),
        head_height_mm=(
            resolved.bolt_standard.head_height_mm
        ),
    )

    external_thread = HelicalThreadCutterDefinition(
        geometry_id=bolt_geometry_id,
        nominal_diameter_mm=(
            resolved.thread_standard.nominal_diameter_mm
        ),
        pitch_mm=resolved.thread_standard.pitch_mm,
        minor_diameter_mm=(
            thread.basic_external_minor_diameter_mm
        ),
        thread_length_mm=assembly.bolt_length_mm,
        overshoot_pitches=(
            profile.external_thread_overshoot_pitches
        ),
        radial_clearance_mm=(
            profile.external_thread_radial_clearance_mm
        ),
        handedness=fastener.handedness.value,
        use_frenet_frame=(
            profile.external_thread_use_frenet_frame
        ),
    )

    nut_blank = NutBlankDefinition(
        geometry_id=nut_geometry_id,
        assembly_id=assembly.assembly_id,
        component_name="resolved_hex_nut",
        nominal_diameter_mm=(
            resolved.thread_standard.nominal_diameter_mm
        ),
        pitch_mm=resolved.thread_standard.pitch_mm,
        across_flats_mm=(
            resolved.nut_standard.across_flats_mm
        ),
        thickness_mm=assembly.nut_thickness_mm,
        bore_diameter_mm=(
            thread.basic_internal_minor_diameter_mm
        ),
        bore_basis=profile.nut_bore_basis,
        chamfer_included=profile.nut_chamfer_included,
    )

    internal_thread = InternalThreadCutterDefinition(
        geometry_id=nut_geometry_id,
        assembly_id=assembly.assembly_id,
        component_name="resolved_internal_thread",
        nominal_diameter_mm=(
            resolved.thread_standard.nominal_diameter_mm
        ),
        pitch_mm=resolved.thread_standard.pitch_mm,
        minor_diameter_mm=(
            thread.basic_internal_minor_diameter_mm
        ),
        thread_length_mm=(
            assembly.thread_engagement_length_mm
        ),
        handedness=fastener.handedness.value,
        use_frenet_frame=(
            profile.internal_thread_use_frenet_frame
        ),
    )

    return GeometryDefinitionBundle(
        bolt_blank=bolt_blank,
        external_thread=external_thread,
        nut_blank=nut_blank,
        internal_thread=internal_thread,
        quality_policy=profile.quality_policy,
        mating_clearance_mm=profile.mating_clearance_mm,
        mating_phase_offset_deg=(
            profile.mating_phase_offset_deg
        ),
    )

"""Analytical-definition adapter for resolved ThreadROM cases."""

from __future__ import annotations

from threadrom.case.resolved_case import ResolvedCase
from threadrom.engineering.analytical_inputs import (
    BoltAxialSegmentInput,
    BoltSegmentKind,
    LoadingInput,
    MemberLayerInput,
    MetricThreadInput,
)
from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
    AnalyticalMethodSelection,
    BoltInput,
    NutInput,
)
from threadrom.factory.analytical_profile import (
    AnalyticalDefinitionProfile,
    CERTIFIED_PHASE2_ANALYTICAL_PROFILE,
)
from threadrom.materials.fastener_classes import (
    FastenerComponentKind,
)
from threadrom.materials.resolver import (
    resolve_fastener_elastic_material,
    resolve_member_elastic_material,
)
from threadrom.materials.baseline_catalog import (
    BASELINE_MATERIAL_CATALOG,
)
from threadrom.materials.catalog import MaterialCatalog


def build_analytical_joint_input(
    resolved: ResolvedCase,
    *,
    profile: AnalyticalDefinitionProfile = (
        CERTIFIED_PHASE2_ANALYTICAL_PROFILE
    ),
    material_catalog: MaterialCatalog = BASELINE_MATERIAL_CATALOG,
) -> AnalyticalJointInput:
    """Build one analytical-engine definition from a resolved case."""

    case = resolved.source_case
    fastener = case.fastener
    assembly = resolved.assembly

    if case.loading.external_axial_load_n < 0.0:
        raise ValueError(
            "The current analytical backend supports only "
            "non-negative separating external axial load."
        )

    bolt_material = resolve_fastener_elastic_material(
        catalog=material_catalog,
        material_id=fastener.bolt_material_id,
        component_kind=FastenerComponentKind.BOLT,
        property_class=fastener.bolt_property_class,
    )

    nut_material = resolve_fastener_elastic_material(
        catalog=material_catalog,
        material_id=fastener.nut_material_id,
        component_kind=FastenerComponentKind.NUT,
        property_class=fastener.nut_property_class,
    )

    member_material_by_id = {}

    for layer in case.members.layers:
        member_material_by_id.setdefault(
            layer.material_id,
            resolve_member_elastic_material(
                catalog=material_catalog,
                material_id=layer.material_id,
            ),
        )

    member_materials = tuple(
        member_material_by_id[material_id]
        for material_id in member_material_by_id
    )

    thread = MetricThreadInput(
        nominal_diameter_mm=(
            resolved.thread_standard.nominal_diameter_mm
        ),
        pitch_mm=resolved.thread_standard.pitch_mm,
        handedness=fastener.handedness,
        starts=fastener.starts,
        included_angle_deg=profile.included_angle_deg,
        external_tolerance_class=(
            profile.external_tolerance_class
        ),
        internal_tolerance_class=(
            profile.internal_tolerance_class
        ),
    )

    bolt = BoltInput(
        bolt_id=f"bolt-{resolved.case_hash[:16]}",
        material_id=bolt_material.material_id,
        nominal_length_mm=assembly.bolt_length_mm,
        axial_segments=(
            BoltAxialSegmentInput(
                segment_id="grip_thread",
                kind=BoltSegmentKind.THREADED,
                length_mm=assembly.total_grip_length_mm,
            ),
        ),
        head_bearing_outer_diameter_mm=(
            resolved.bolt_standard.head_across_flats_mm
        ),
        head_bearing_inner_diameter_mm=(
            assembly.clearance_hole_diameter_mm
        ),
    )

    nut = NutInput(
        nut_id=f"nut-{resolved.case_hash[:16]}",
        material_id=nut_material.material_id,
        thickness_mm=assembly.nut_thickness_mm,
        thread_engagement_length_mm=(
            assembly.thread_engagement_length_mm
        ),
        bearing_outer_diameter_mm=(
            resolved.nut_standard.across_flats_mm
        ),
        bearing_inner_diameter_mm=(
            assembly.clearance_hole_diameter_mm
        ),
    )

    member_layers = tuple(
        MemberLayerInput(
            layer_id=layer.layer_id,
            thickness_mm=layer.thickness_mm,
            material_id=layer.material_id,
            clearance_hole_diameter_mm=(
                layer.clearance_hole_diameter_mm
            ),
            outer_diameter_mm=layer.outer_diameter_mm,
        )
        for layer in case.members.layers
    )

    loading = LoadingInput(
        preload_n=case.loading.target_preload_n,
        external_axial_load_n=(
            case.loading.external_axial_load_n
        ),
        preload_scatter_fraction=0.0,
    )

    methods = AnalyticalMethodSelection(
        bolt_compliance=profile.bolt_compliance,
        member_compression=profile.member_compression,
        external_load=profile.external_load,
        thread_load_distribution=(
            profile.thread_load_distribution
        ),
        head_participation_factor=(
            profile.head_participation_factor
        ),
        nut_participation_factor=(
            profile.nut_participation_factor
        ),
        load_introduction_factor=(
            profile.load_introduction_factor
        ),
        compression_cone_half_angle_deg=(
            profile.compression_cone_half_angle_deg
        ),
    )

    return AnalyticalJointInput(
        joint_id=f"analytical-{resolved.case_hash[:16]}",
        thread=thread,
        bolt=bolt,
        nut=nut,
        member_layers=member_layers,
        materials=(
            bolt_material,
            nut_material,
            *member_materials,
        ),
        loading=loading,
        methods=methods,
    )

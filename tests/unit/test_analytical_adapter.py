"""Tests for the resolved-case analytical definition adapter."""

from threadrom.case.contract import (
    FastenerSelection,
    InterfacesSelection,
    LoadingSelection,
    MemberLayerSelection,
    MembersSelection,
    ThreadROMCase,
)
from threadrom.case.resolver import resolve_case
from threadrom.engineering.analytical_inputs import (
    BoltSegmentKind,
    ThreadHandedness,
)
from threadrom.engineering.analytical_joint_input import (
    BoltComplianceMethod,
    ExternalLoadMethod,
    MemberCompressionMethod,
    ThreadLoadDistributionMethod,
)
from threadrom.factory.analytical_adapter import (
    build_analytical_joint_input,
)


def _baseline_case() -> ThreadROMCase:
    return ThreadROMCase(
        fastener=FastenerSelection(
            bolt_standard="ISO 4017:2022",
            thread_designation="M10x1.5",
            bolt_length_mm=30.0,
            bolt_material_id="fastener_steel",
            bolt_property_class="8.8",
            nut_standard="ISO 4032:2023",
            nut_material_id="fastener_steel",
            nut_property_class="8",
            handedness=ThreadHandedness.RIGHT,
            starts=1,
        ),
        members=MembersSelection(
            layers=(
                MemberLayerSelection(
                    layer_id="head_side_member",
                    thickness_mm=10.0,
                    material_id="steel_member",
                    outer_diameter_mm=30.0,
                    clearance_hole_diameter_mm=11.0,
                ),
                MemberLayerSelection(
                    layer_id="nut_side_member",
                    thickness_mm=10.0,
                    material_id="steel_member",
                    outer_diameter_mm=30.0,
                    clearance_hole_diameter_mm=11.0,
                ),
            )
        ),
        interfaces=InterfacesSelection(
            thread_friction_coefficient=0.15,
            head_bearing_friction_coefficient=0.15,
            nut_bearing_friction_coefficient=0.15,
            member_interface_friction_coefficient=0.15,
        ),
        loading=LoadingSelection(
            target_preload_n=20000.0,
            external_axial_load_n=0.0,
        ),
    )


def _analytical():
    return build_analytical_joint_input(
        resolve_case(_baseline_case())
    )


def test_thread_matches_certified_phase2_definition() -> None:
    analytical = _analytical()

    assert analytical.thread.nominal_diameter_mm == 10.0
    assert analytical.thread.pitch_mm == 1.5
    assert analytical.thread.handedness is ThreadHandedness.RIGHT
    assert analytical.thread.starts == 1
    assert analytical.thread.included_angle_deg == 60.0
    assert analytical.thread.external_tolerance_class == "6g"
    assert analytical.thread.internal_tolerance_class == "6H"


def test_bolt_matches_certified_phase2_definition() -> None:
    analytical = _analytical()

    assert analytical.bolt.nominal_length_mm == 30.0
    assert analytical.bolt.head_bearing_outer_diameter_mm == 16.0
    assert analytical.bolt.head_bearing_inner_diameter_mm == 11.0

    assert len(analytical.bolt.axial_segments) == 1

    segment = analytical.bolt.axial_segments[0]

    assert segment.segment_id == "grip_thread"
    assert segment.kind is BoltSegmentKind.THREADED
    assert segment.length_mm == 20.0
    assert segment.area_mm2 is None
    assert segment.diameter_mm is None


def test_nut_matches_certified_phase2_definition() -> None:
    analytical = _analytical()

    assert analytical.nut.thickness_mm == 8.0
    assert analytical.nut.thread_engagement_length_mm == 8.0
    assert analytical.nut.bearing_outer_diameter_mm == 16.0
    assert analytical.nut.bearing_inner_diameter_mm == 11.0


def test_member_stack_matches_certified_phase2_definition() -> None:
    analytical = _analytical()

    assert len(analytical.member_layers) == 2

    upper, lower = analytical.member_layers

    assert upper.layer_id == "head_side_member"
    assert upper.thickness_mm == 10.0
    assert upper.material_id == "steel_member"
    assert upper.clearance_hole_diameter_mm == 11.0
    assert upper.outer_diameter_mm == 30.0

    assert lower.layer_id == "nut_side_member"
    assert lower.thickness_mm == 10.0
    assert lower.material_id == "steel_member"
    assert lower.clearance_hole_diameter_mm == 11.0
    assert lower.outer_diameter_mm == 30.0


def test_materials_match_certified_phase2_properties() -> None:
    analytical = _analytical()

    assert len(analytical.materials) == 3

    bolt_material = analytical.material_by_id(
        "fastener_steel::bolt::8.8"
    )
    nut_material = analytical.material_by_id(
        "fastener_steel::nut::8"
    )
    member_material = analytical.material_by_id(
        "steel_member"
    )

    assert bolt_material.youngs_modulus_mpa == 210000.0
    assert bolt_material.poissons_ratio == 0.3
    assert bolt_material.proof_stress_mpa == 580.0
    assert bolt_material.yield_strength_mpa == 640.0
    assert bolt_material.ultimate_strength_mpa == 800.0

    assert nut_material.youngs_modulus_mpa == 210000.0
    assert nut_material.poissons_ratio == 0.3
    assert nut_material.proof_stress_mpa is None
    assert nut_material.yield_strength_mpa is None
    assert nut_material.ultimate_strength_mpa is None

    assert member_material.youngs_modulus_mpa == 210000.0
    assert member_material.poissons_ratio == 0.3


def test_component_material_references_are_resolved() -> None:
    analytical = _analytical()

    assert analytical.bolt.material_id == (
        "fastener_steel::bolt::8.8"
    )
    assert analytical.nut.material_id == (
        "fastener_steel::nut::8"
    )

    available = {
        material.material_id
        for material in analytical.materials
    }

    assert analytical.bolt.material_id in available
    assert analytical.nut.material_id in available

    for layer in analytical.member_layers:
        assert layer.material_id in available


def test_loading_matches_certified_phase2_definition() -> None:
    analytical = _analytical()

    assert analytical.loading.preload_n == 20000.0
    assert analytical.loading.external_axial_load_n == 0.0
    assert analytical.loading.preload_scatter_fraction == 0.0


def test_methods_match_certified_phase2_definition() -> None:
    analytical = _analytical()

    methods = analytical.methods

    assert methods.bolt_compliance is BoltComplianceMethod.SEGMENTED
    assert (
        methods.member_compression
        is MemberCompressionMethod.UNIFORM_ANNULAR_CYLINDER
    )
    assert (
        methods.external_load
        is ExternalLoadMethod.BASIC_SPRING_RATIO
    )
    assert (
        methods.thread_load_distribution
        is ThreadLoadDistributionMethod.DISCRETE_SPRING
    )

    assert methods.head_participation_factor == 0.5
    assert methods.nut_participation_factor == 0.5
    assert methods.load_introduction_factor == 1.0
    assert methods.compression_cone_half_angle_deg == 30.0


def test_factory_output_is_deterministic() -> None:
    first = _analytical()
    second = _analytical()

    assert first == second
    assert first.joint_id == second.joint_id
    assert first.bolt.bolt_id == second.bolt.bolt_id
    assert first.nut.nut_id == second.nut.nut_id

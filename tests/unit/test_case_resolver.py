"""Tests for deterministic ThreadROM case resolution."""

from dataclasses import replace

import pytest

from threadrom.case.contract import (
    FastenerSelection,
    InterfacesSelection,
    LoadingSelection,
    MemberLayerSelection,
    MembersSelection,
    ThreadROMCase,
)
from threadrom.case.resolver import resolve_case
from threadrom.case.serialization import case_sha256
from threadrom.engineering.analytical_inputs import ThreadHandedness


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


def test_certified_shaped_case_resolves() -> None:
    case = _baseline_case()

    resolved = resolve_case(case)

    assert resolved.source_case is case
    assert resolved.case_hash == case_sha256(case)

    assert resolved.thread_standard.designation == "M10x1.5"
    assert resolved.thread_standard.nominal_diameter_mm == 10.0
    assert resolved.thread_standard.pitch_mm == 1.5

    assert resolved.bolt_standard.product_standard == "ISO 4017:2022"
    assert resolved.bolt_standard.head_across_flats_mm == 16.0
    assert resolved.bolt_standard.head_height_mm == 6.4

    assert resolved.nut_standard.product_standard == "ISO 4032:2023"
    assert resolved.nut_standard.across_flats_mm == 16.0
    assert resolved.nut_standard.thickness_mm == 8.0


def test_metric_thread_basic_dimensions_are_derived() -> None:
    resolved = resolve_case(_baseline_case())

    dimensions = resolved.thread_basic_dimensions

    assert dimensions.nominal_diameter_mm == 10.0
    assert dimensions.pitch_mm == 1.5
    assert dimensions.basic_pitch_diameter_mm < 10.0
    assert dimensions.basic_internal_minor_diameter_mm < 10.0
    assert dimensions.basic_external_minor_diameter_mm < 10.0
    assert dimensions.tensile_stress_area_mm2 > 0.0


def test_baseline_assembly_is_derived() -> None:
    resolved = resolve_case(_baseline_case())

    assembly = resolved.assembly

    assert assembly.bolt_length_mm == 30.0
    assert assembly.upper_member_thickness_mm == 10.0
    assert assembly.lower_member_thickness_mm == 10.0
    assert assembly.total_grip_length_mm == 20.0
    assert assembly.nut_thickness_mm == 8.0
    assert assembly.thread_engagement_length_mm == 8.0
    assert assembly.protrusion_length_mm == 2.0
    assert assembly.clearance_hole_diameter_mm == 11.0
    assert assembly.outer_diameter_mm == 30.0
    assert assembly.engaged_thread_count == pytest.approx(8.0 / 1.5)


def test_baseline_materials_and_property_classes_resolve() -> None:
    resolved = resolve_case(_baseline_case())

    assert resolved.bolt_material.material_id == "fastener_steel"
    assert resolved.bolt_material.youngs_modulus_mpa == 210000.0
    assert resolved.bolt_material.density_kg_per_m3 == 7850.0
    assert resolved.bolt_material.thermal_expansion_per_c == 1.2e-5

    assert resolved.nut_material.material_id == "fastener_steel"

    assert tuple(
        material.material_id
        for material in resolved.member_materials
    ) == (
        "steel_member",
        "steel_member",
    )

    assert resolved.bolt_property_class.property_class == "8.8"
    assert resolved.bolt_property_class.proof_stress_mpa == 580.0
    assert resolved.bolt_property_class.yield_strength_mpa == 640.0
    assert resolved.bolt_property_class.ultimate_strength_mpa == 800.0

    assert resolved.nut_property_class.property_class == "8"
    assert resolved.nut_property_class.proof_stress_mpa is None


def test_resolution_is_deterministic() -> None:
    first = resolve_case(_baseline_case())
    second = resolve_case(_baseline_case())

    assert first == second
    assert first.case_hash == second.case_hash
    assert first.assembly.assembly_id == second.assembly.assembly_id


def test_insufficient_bolt_length_is_rejected() -> None:
    case = _baseline_case()

    short_fastener = replace(
        case.fastener,
        bolt_length_mm=27.0,
    )

    with pytest.raises(
        ValueError,
        match="Bolt length is insufficient",
    ):
        resolve_case(
            replace(
                case,
                fastener=short_fastener,
            )
        )


def test_current_geometry_path_requires_two_members() -> None:
    case = _baseline_case()

    one_member = MembersSelection(
        layers=(case.members.layers[0],)
    )

    with pytest.raises(
        ValueError,
        match="exactly two clamped-member layers",
    ):
        resolve_case(
            replace(
                case,
                members=one_member,
            )
        )


def test_current_geometry_path_requires_common_hole_diameter() -> None:
    case = _baseline_case()

    changed_lower = replace(
        case.members.layers[1],
        clearance_hole_diameter_mm=12.0,
    )

    members = MembersSelection(
        layers=(
            case.members.layers[0],
            changed_lower,
        )
    )

    with pytest.raises(
        ValueError,
        match="equal clearance-hole diameters",
    ):
        resolve_case(
            replace(
                case,
                members=members,
            )
        )


def test_current_geometry_path_requires_common_outer_diameter() -> None:
    case = _baseline_case()

    changed_lower = replace(
        case.members.layers[1],
        outer_diameter_mm=32.0,
    )

    members = MembersSelection(
        layers=(
            case.members.layers[0],
            changed_lower,
        )
    )

    with pytest.raises(
        ValueError,
        match="equal outer diameters",
    ):
        resolve_case(
            replace(
                case,
                members=members,
            )
        )


def test_unknown_material_is_rejected_during_resolution() -> None:
    case = _baseline_case()

    fastener = replace(
        case.fastener,
        bolt_material_id="unknown_material",
    )

    with pytest.raises(
        ValueError,
        match="Unknown ThreadROM material family",
    ):
        resolve_case(
            replace(
                case,
                fastener=fastener,
            )
        )
from dataclasses import replace

import pytest

from threadrom.case.reference_cases import phase2_certification_case
from threadrom.case.resolver import resolve_case


def test_metadata_known_but_dimensionally_unsupported_standard_fails_safe() -> None:
    """Known ISO metadata must not imply dimensional factory support."""

    case = phase2_certification_case()

    unsupported = replace(
        case,
        fastener=replace(
            case.fastener,
            bolt_standard="ISO 4014:2022",
        ),
    )

    with pytest.raises(
        ValueError,
        match="No governed bolt-standard record exists",
    ):
        resolve_case(unsupported)

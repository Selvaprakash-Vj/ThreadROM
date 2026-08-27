"""Parity tests for Phase-3 geometry-definition generation."""

from pathlib import Path

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
    ThreadHandedness,
)
from threadrom.factory.geometry_adapter import (
    build_geometry_definitions,
)
from threadrom.geometry.complete_nut import (
    load_complete_nut_definitions,
)
from threadrom.geometry.geometry_quality import (
    load_geometry_quality_policy,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def _new():
    return build_geometry_definitions(
        resolve_case(_baseline_case())
    )


def test_bolt_blank_matches_phase2_geometry() -> None:
    new = _new().bolt_blank
    old, _ = load_threaded_shank_definitions(PROJECT_ROOT)

    assert new.nominal_diameter_mm == old.nominal_diameter_mm
    assert new.underhead_length_mm == old.underhead_length_mm
    assert new.head_across_flats_mm == old.head_across_flats_mm
    assert new.head_height_mm == old.head_height_mm


def test_external_thread_matches_phase2_geometry() -> None:
    new = _new().external_thread
    _, old = load_threaded_shank_definitions(PROJECT_ROOT)

    assert new.nominal_diameter_mm == old.nominal_diameter_mm
    assert new.pitch_mm == old.pitch_mm
    assert new.minor_diameter_mm == old.minor_diameter_mm
    assert new.thread_length_mm == old.thread_length_mm
    assert new.overshoot_pitches == old.overshoot_pitches
    assert new.radial_clearance_mm == old.radial_clearance_mm
    assert new.handedness == old.handedness
    assert new.use_frenet_frame == old.use_frenet_frame


def test_nut_blank_matches_phase2_geometry() -> None:
    new = _new().nut_blank
    old, _ = load_complete_nut_definitions(PROJECT_ROOT)

    assert new.nominal_diameter_mm == old.nominal_diameter_mm
    assert new.pitch_mm == old.pitch_mm
    assert new.across_flats_mm == old.across_flats_mm
    assert new.thickness_mm == old.thickness_mm
    assert new.bore_diameter_mm == old.bore_diameter_mm
    assert new.bore_basis == old.bore_basis
    assert new.chamfer_included == old.chamfer_included


def test_internal_thread_matches_phase2_geometry() -> None:
    new = _new().internal_thread
    _, old = load_complete_nut_definitions(PROJECT_ROOT)

    assert new.nominal_diameter_mm == old.nominal_diameter_mm
    assert new.pitch_mm == old.pitch_mm
    assert new.minor_diameter_mm == old.minor_diameter_mm
    assert new.thread_length_mm == old.thread_length_mm
    assert new.handedness == old.handedness
    assert new.use_frenet_frame == old.use_frenet_frame


def test_geometry_quality_policy_matches_phase2() -> None:
    new = _new().quality_policy

    old = load_geometry_quality_policy(
        PROJECT_ROOT / "config" / "geometry_quality.toml"
    )

    assert new.boolean_tolerance_mm == old.boolean_tolerance_mm
    assert (
        new.thread_boolean_overlap_mm
        == old.thread_boolean_overlap_mm
    )
    assert (
        new.fusion_bridge_half_height_mm
        == old.fusion_bridge_half_height_mm
    )
    assert (
        new.fusion_bridge_radius_fraction
        == old.fusion_bridge_radius_fraction
    )
    assert (
        new.cad_envelope_tolerance_mm
        == old.cad_envelope_tolerance_mm
    )
    assert (
        new.step_bounds_tolerance_mm
        == old.step_bounds_tolerance_mm
    )
    assert (
        new.step_volume_relative_tolerance
        == old.step_volume_relative_tolerance
    )


def test_geometry_identity_relationships_are_preserved() -> None:
    bundle = _new()

    assert (
        bundle.bolt_blank.geometry_id
        == bundle.external_thread.geometry_id
    )

    assert (
        bundle.nut_blank.geometry_id
        == bundle.internal_thread.geometry_id
    )

    assert (
        bundle.nut_blank.assembly_id
        == bundle.internal_thread.assembly_id
    )


def test_geometry_factory_output_is_deterministic() -> None:
    first = _new()
    second = _new()

    assert first == second


def test_certified_mating_defaults_are_preserved() -> None:
    bundle = _new()

    assert bundle.mating_clearance_mm == 0.0
    assert bundle.mating_phase_offset_deg == 0.0

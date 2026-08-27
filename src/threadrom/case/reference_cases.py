"""Governed Phase-2 reference cases used by the Phase-3 factory."""

from __future__ import annotations

from threadrom.case.contract import (
    FastenerSelection,
    InterfacesSelection,
    LoadingSelection,
    MemberLayerSelection,
    MembersSelection,
    ThreadROMCase,
)
from threadrom.engineering.analytical_inputs import (
    ThreadHandedness,
)


PHASE2_CERTIFICATION_CASE_SOURCE = (
    "config/analytical_m10_20kn.toml; "
    "config/baseline_fastener.toml; "
    "config/baseline_assembly.toml"
)


def phase2_certification_case() -> ThreadROMCase:
    """Return the authoritative product case reproducing Phase-2."""

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
            target_preload_n=20_000.0,
            external_axial_load_n=0.0,
        ),
    )

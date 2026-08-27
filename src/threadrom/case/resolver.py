"""Deterministic resolution of product-level ThreadROM cases."""

from __future__ import annotations

from threadrom.case.contract import ThreadROMCase
from threadrom.case.resolved import ResolvedAssembly
from threadrom.case.resolved_case import ResolvedCase
from threadrom.case.serialization import case_sha256
from threadrom.case.standards import (
    resolve_bolt_standard,
    resolve_metric_thread_standard,
    resolve_nut_standard,
)
from threadrom.engineering.metric_thread import (
    calculate_metric_thread_basic_dimensions,
)
from threadrom.materials.baseline_catalog import (
    BASELINE_MATERIAL_CATALOG,
)
from threadrom.materials.catalog import MaterialCatalog
from threadrom.materials.fastener_classes import (
    FastenerComponentKind,
)


def resolve_case(
    case: ThreadROMCase,
    *,
    material_catalog: MaterialCatalog = BASELINE_MATERIAL_CATALOG,
) -> ResolvedCase:
    """Resolve one ThreadROM case into backend-neutral engineering data."""

    case_hash = case_sha256(case)
    fastener = case.fastener
    layers = case.members.layers

    thread_standard = resolve_metric_thread_standard(
        fastener.thread_designation
    )

    bolt_standard = resolve_bolt_standard(
        fastener.bolt_standard,
        fastener.thread_designation,
    )

    nut_standard = resolve_nut_standard(
        fastener.nut_standard,
        fastener.thread_designation,
    )

    thread_basic_dimensions = (
        calculate_metric_thread_basic_dimensions(
            thread_standard.nominal_diameter_mm,
            thread_standard.pitch_mm,
        )
    )

    if len(layers) != 2:
        raise ValueError(
            "The current complete-joint geometry adapter requires "
            "exactly two clamped-member layers."
        )

    upper_layer, lower_layer = layers

    if (
        upper_layer.clearance_hole_diameter_mm
        != lower_layer.clearance_hole_diameter_mm
    ):
        raise ValueError(
            "The current complete-joint geometry adapter requires "
            "equal clearance-hole diameters in both member layers."
        )

    if (
        upper_layer.outer_diameter_mm
        != lower_layer.outer_diameter_mm
    ):
        raise ValueError(
            "The current complete-joint geometry adapter requires "
            "equal outer diameters in both member layers."
        )

    grip_length_mm = case.members.total_grip_length_mm

    protrusion_length_mm = (
        fastener.bolt_length_mm
        - grip_length_mm
        - nut_standard.thickness_mm
    )

    if protrusion_length_mm < 0.0:
        raise ValueError(
            "Bolt length is insufficient for the resolved grip "
            "and nut thickness."
        )

    assembly = ResolvedAssembly(
        assembly_id=f"resolved-{case_hash[:16]}",
        bolt_length_mm=fastener.bolt_length_mm,
        pitch_mm=thread_standard.pitch_mm,
        upper_member_thickness_mm=upper_layer.thickness_mm,
        lower_member_thickness_mm=lower_layer.thickness_mm,
        total_grip_length_mm=grip_length_mm,
        nut_thickness_mm=nut_standard.thickness_mm,
        thread_engagement_length_mm=nut_standard.thickness_mm,
        protrusion_length_mm=protrusion_length_mm,
        clearance_hole_diameter_mm=(
            upper_layer.clearance_hole_diameter_mm
        ),
        outer_diameter_mm=upper_layer.outer_diameter_mm,
    )

    bolt_material = material_catalog.get_material(
        fastener.bolt_material_id
    )

    nut_material = material_catalog.get_material(
        fastener.nut_material_id
    )

    member_materials = tuple(
        material_catalog.get_material(layer.material_id)
        for layer in layers
    )

    bolt_property_class = (
        material_catalog.get_fastener_property_class(
            FastenerComponentKind.BOLT,
            fastener.bolt_property_class,
        )
    )

    nut_property_class = (
        material_catalog.get_fastener_property_class(
            FastenerComponentKind.NUT,
            fastener.nut_property_class,
        )
    )

    return ResolvedCase(
        source_case=case,
        case_hash=case_hash,
        thread_standard=thread_standard,
        thread_basic_dimensions=thread_basic_dimensions,
        bolt_standard=bolt_standard,
        nut_standard=nut_standard,
        assembly=assembly,
        bolt_material=bolt_material,
        nut_material=nut_material,
        member_materials=member_materials,
        bolt_property_class=bolt_property_class,
        nut_property_class=nut_property_class,
    )

"""Component CAD IDs must follow their own physical geometry identity."""

from dataclasses import replace

from threadrom.case.resolver import resolve_case
from threadrom.factory.geometry_adapter import (
    build_geometry_definitions,
)
from tests.unit.test_case_resolver import _baseline_case


def test_material_change_reuses_component_geometry_ids() -> None:
    resolved = resolve_case(_baseline_case())

    changed = replace(
        resolved,
        bolt_material=replace(
            resolved.bolt_material,
            youngs_modulus_mpa=205000.0,
        ),
    )

    original_geometry = build_geometry_definitions(resolved)
    changed_geometry = build_geometry_definitions(changed)

    assert (
        original_geometry.bolt_blank.geometry_id
        == changed_geometry.bolt_blank.geometry_id
    )
    assert (
        original_geometry.nut_blank.geometry_id
        == changed_geometry.nut_blank.geometry_id
    )


def test_bolt_shape_change_changes_only_bolt_geometry_id() -> None:
    resolved = resolve_case(_baseline_case())

    changed = replace(
        resolved,
        bolt_standard=replace(
            resolved.bolt_standard,
            head_height_mm=6.5,
        ),
    )

    original_geometry = build_geometry_definitions(resolved)
    changed_geometry = build_geometry_definitions(changed)

    assert (
        original_geometry.bolt_blank.geometry_id
        != changed_geometry.bolt_blank.geometry_id
    )
    assert (
        original_geometry.nut_blank.geometry_id
        == changed_geometry.nut_blank.geometry_id
    )


def test_nut_shape_change_changes_only_nut_geometry_id() -> None:
    resolved = resolve_case(_baseline_case())

    changed = replace(
        resolved,
        assembly=replace(
            resolved.assembly,
            nut_thickness_mm=8.2,
            thread_engagement_length_mm=8.2,
            protrusion_length_mm=1.8,
        ),
    )

    original_geometry = build_geometry_definitions(resolved)
    changed_geometry = build_geometry_definitions(changed)

    assert (
        original_geometry.bolt_blank.geometry_id
        == changed_geometry.bolt_blank.geometry_id
    )
    assert (
        original_geometry.nut_blank.geometry_id
        != changed_geometry.nut_blank.geometry_id
    )

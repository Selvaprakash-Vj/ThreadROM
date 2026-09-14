"""Bolt and nut CAD identities must change only with their own shape."""

from dataclasses import replace

from threadrom.case.resolver import resolve_case
from threadrom.factory.geometry_identity import (
    bolt_geometry_sha256,
    nut_geometry_sha256,
)
from tests.unit.test_case_resolver import _baseline_case


def test_bolt_only_shape_change_changes_only_bolt_identity() -> None:
    resolved = resolve_case(_baseline_case())

    changed = replace(
        resolved,
        bolt_standard=replace(
            resolved.bolt_standard,
            head_height_mm=6.5,
        ),
    )

    assert (
        bolt_geometry_sha256(changed)
        != bolt_geometry_sha256(resolved)
    )
    assert (
        nut_geometry_sha256(changed)
        == nut_geometry_sha256(resolved)
    )


def test_nut_only_shape_change_changes_only_nut_identity() -> None:
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

    assert (
        bolt_geometry_sha256(changed)
        == bolt_geometry_sha256(resolved)
    )
    assert (
        nut_geometry_sha256(changed)
        != nut_geometry_sha256(resolved)
    )


def test_material_change_changes_neither_component_identity() -> None:
    resolved = resolve_case(_baseline_case())

    changed = replace(
        resolved,
        bolt_material=replace(
            resolved.bolt_material,
            youngs_modulus_mpa=205000.0,
        ),
    )

    assert (
        bolt_geometry_sha256(changed)
        == bolt_geometry_sha256(resolved)
    )
    assert (
        nut_geometry_sha256(changed)
        == nut_geometry_sha256(resolved)
    )

"""Classification identity tracks semantic classification, not acceptance gates."""

from dataclasses import replace

from threadrom.case.resolver import resolve_case
from threadrom.factory.geometry_adapter import (
    build_geometry_definitions,
)
from threadrom.factory.mesh_identity import (
    classification_sha256,
)
from tests.unit.test_phase3_fem_case_mesh_preparation import (
    _p03,
    _templates,
)


def _identity(
    resolved,
    *,
    joint=None,
    bolt=None,
    nut=None,
):
    geometry = build_geometry_definitions(resolved)
    templates = _templates()

    return classification_sha256(
        resolved,
        geometry,
        joint_classification=(
            templates[1] if joint is None else joint
        ),
        bolt_classification=(
            templates[2] if bolt is None else bolt
        ),
        nut_classification=(
            templates[3] if nut is None else nut
        ),
    )


def test_material_change_does_not_change_classification_identity() -> None:
    resolved = resolve_case(_p03().case)

    changed = replace(
        resolved,
        bolt_material=replace(
            resolved.bolt_material,
            youngs_modulus_mpa=205000.0,
        ),
    )

    assert _identity(changed) == _identity(resolved)


def test_joint_geometry_change_changes_classification_identity() -> None:
    resolved = resolve_case(_p03().case)

    changed = replace(
        resolved,
        assembly=replace(
            resolved.assembly,
            outer_diameter_mm=(
                resolved.assembly.outer_diameter_mm + 1.0
            ),
        ),
    )

    assert _identity(changed) != _identity(resolved)


def test_classification_tolerance_change_changes_identity() -> None:
    resolved = resolve_case(_p03().case)
    templates = _templates()

    changed_joint = replace(
        templates[1],
        plane_tolerance_mm=(
            templates[1].plane_tolerance_mm * 2.0
        ),
    )

    assert (
        _identity(
            resolved,
            joint=changed_joint,
        )
        != _identity(resolved)
    )


def test_physical_group_name_change_changes_identity() -> None:
    resolved = resolve_case(_p03().case)
    templates = _templates()

    changed_bolt = replace(
        templates[2],
        thread_surfaces_name="THREAD_SURFACES_ALT",
    )

    assert (
        _identity(
            resolved,
            bolt=changed_bolt,
        )
        != _identity(resolved)
    )


def test_verification_only_threshold_change_does_not_change_identity() -> None:
    resolved = resolve_case(_p03().case)
    templates = _templates()

    changed_bolt = replace(
        templates[2],
        minimum_thread_surface_count=(
            templates[2].minimum_thread_surface_count + 1
        ),
    )

    assert (
        _identity(
            resolved,
            bolt=changed_bolt,
        )
        == _identity(resolved)
    )

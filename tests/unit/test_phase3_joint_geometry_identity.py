"""Complete-joint geometry IDs must follow assembled physical geometry."""

from dataclasses import replace

from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_case_mesh_preparation import (
    build_fem_case_mesh_definitions,
)
from threadrom.factory.geometry_adapter import (
    build_geometry_definitions,
)
from tests.unit.test_phase3_fem_case_mesh_preparation import (
    _p03,
    _templates,
)


def _definitions(resolved):
    geometry = build_geometry_definitions(resolved)
    templates = _templates()

    return build_fem_case_mesh_definitions(
        resolved,
        geometry,
        mesh_template=templates[0],
        joint_classification_template=templates[1],
        bolt_classification_template=templates[2],
        nut_classification_template=templates[3],
    )


def test_material_change_reuses_joint_geometry_id() -> None:
    resolved = resolve_case(_p03().case)

    changed = replace(
        resolved,
        bolt_material=replace(
            resolved.bolt_material,
            youngs_modulus_mpa=205000.0,
        ),
    )

    assert (
        _definitions(changed).joint_geometry_id
        == _definitions(resolved).joint_geometry_id
    )


def test_member_geometry_change_changes_joint_geometry_id() -> None:
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

    assert (
        _definitions(changed).joint_geometry_id
        != _definitions(resolved).joint_geometry_id
    )

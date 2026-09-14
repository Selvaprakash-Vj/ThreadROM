"""Mesh preparation must identify the geometry actually built."""

from dataclasses import replace

from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_case_mesh_preparation import (
    build_fem_case_mesh_definitions,
)
from threadrom.factory.geometry_adapter import (
    build_geometry_definitions,
)
from threadrom.factory.geometry_profile import (
    CERTIFIED_PHASE2_GEOMETRY_PROFILE,
)
from tests.unit.test_phase3_fem_case_mesh_preparation import (
    _p03,
    _templates,
)


def _mesh_definitions(resolved, geometry):
    templates = _templates()

    return build_fem_case_mesh_definitions(
        resolved,
        geometry,
        mesh_template=templates[0],
        joint_classification_template=templates[1],
        bolt_classification_template=templates[2],
        nut_classification_template=templates[3],
    )


def test_mating_profile_change_changes_prepared_joint_geometry_id() -> None:
    resolved = resolve_case(_p03().case)

    baseline_geometry = build_geometry_definitions(
        resolved
    )

    changed_profile = replace(
        CERTIFIED_PHASE2_GEOMETRY_PROFILE,
        mating_phase_offset_deg=1.0,
    )
    changed_geometry = build_geometry_definitions(
        resolved,
        profile=changed_profile,
    )

    assert (
        changed_geometry.mating_phase_offset_deg
        != baseline_geometry.mating_phase_offset_deg
    )

    baseline = _mesh_definitions(
        resolved,
        baseline_geometry,
    )
    changed = _mesh_definitions(
        resolved,
        changed_geometry,
    )

    assert (
        changed.joint_geometry_id
        != baseline.joint_geometry_id
    )

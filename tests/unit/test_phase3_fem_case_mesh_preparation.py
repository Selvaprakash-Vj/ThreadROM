"""Tests for generic Phase-3 grouped-mesh preparation."""

from __future__ import annotations

from pathlib import Path

from threadrom.case.resolver import resolve_case
from threadrom.factory.geometry_adapter import (
    build_geometry_definitions,
)
from threadrom.factory.pilot_doe import (
    PilotDoeCaseId,
    build_phase3_cp7_pilot_doe,
)
from threadrom.factory.fem_case_mesh_preparation import (
    build_fem_case_mesh_definitions,
)
from threadrom.meshing.complete_joint_mesh_definition import (
    load_complete_joint_mesh_definition,
)
from threadrom.meshing.complete_joint_surface_classification import (
    load_complete_joint_surface_definition,
)
from threadrom.meshing.nut_surface_classification import (
    load_nut_surface_classification_definition,
)
from threadrom.meshing.surface_classification import (
    load_surface_classification_definition,
)


def _templates():
    return (
        load_complete_joint_mesh_definition(
            Path("config/complete_joint_mesh.toml")
        ),
        load_complete_joint_surface_definition(
            Path(
                "config/"
                "complete_joint_surface_classification.toml"
            )
        ),
        load_surface_classification_definition(
            Path("config/surface_classification.toml")
        ),
        load_nut_surface_classification_definition(
            Path("config/nut_surface_classification.toml")
        ),
    )


def _p03():
    campaign = build_phase3_cp7_pilot_doe()

    return next(
        item
        for item in campaign.cases
        if item.case_id is PilotDoeCaseId.ASYMMETRIC_GRIP
    )


def test_generic_mesh_definitions_replace_all_phase2_identity_fields() -> None:
    resolved = resolve_case(
        _p03().case
    )

    geometry = build_geometry_definitions(
        resolved
    )

    (
        mesh_template,
        joint_template,
        bolt_template,
        nut_template,
    ) = _templates()

    definitions = build_fem_case_mesh_definitions(
        resolved,
        geometry,
        mesh_template=mesh_template,
        joint_classification_template=joint_template,
        bolt_classification_template=bolt_template,
        nut_classification_template=nut_template,
    )

    assert definitions.mesh.mesh_id != mesh_template.mesh_id

    assert (
        definitions.mesh.assembly_id
        == resolved.assembly.assembly_id
    )
    assert (
        definitions.joint_classification.assembly_id
        == resolved.assembly.assembly_id
    )

    assert (
        definitions.mesh.geometry_id
        == definitions.joint_geometry_id
    )
    assert (
        definitions.joint_classification.geometry_id
        == definitions.joint_geometry_id
    )

    assert (
        definitions.mesh.classification_id
        == definitions.classification_id
    )
    assert (
        definitions.joint_classification.classification_id
        == definitions.classification_id
    )

    assert (
        definitions.bolt_classification.geometry_id
        == geometry.bolt_blank.geometry_id
    )
    assert (
        definitions.nut_classification.geometry_id
        == geometry.nut_blank.geometry_id
    )

    assert (
        definitions.bolt_classification.mesh_id
        == definitions.mesh_id
    )
    assert (
        definitions.nut_classification.mesh_id
        == definitions.mesh_id
    )

    legacy_ids = {
        "TRM-MSH-000005",
        "TRM-MSH-000001",
        "TRM-MSH-000004",
        "TRM-ASM-000001",
        "TRM-GEO-000001",
        "TRM-JSC-000001",
    }

    generated_ids = {
        definitions.mesh.mesh_id,
        definitions.mesh.assembly_id,
        definitions.mesh.geometry_id,
        definitions.mesh.classification_id,
        definitions.joint_classification.classification_id,
        definitions.joint_classification.assembly_id,
        definitions.joint_classification.geometry_id,
        definitions.bolt_classification.mesh_id,
        definitions.bolt_classification.geometry_id,
        definitions.nut_classification.mesh_id,
        definitions.nut_classification.geometry_id,
    }

    assert legacy_ids.isdisjoint(
        generated_ids
    )


def test_mesh_identity_is_deterministic_for_same_case() -> None:
    resolved = resolve_case(
        _p03().case
    )

    geometry = build_geometry_definitions(
        resolved
    )

    templates = _templates()

    first = build_fem_case_mesh_definitions(
        resolved,
        geometry,
        mesh_template=templates[0],
        joint_classification_template=templates[1],
        bolt_classification_template=templates[2],
        nut_classification_template=templates[3],
    )

    second = build_fem_case_mesh_definitions(
        resolved,
        geometry,
        mesh_template=templates[0],
        joint_classification_template=templates[1],
        bolt_classification_template=templates[2],
        nut_classification_template=templates[3],
    )

    assert first == second

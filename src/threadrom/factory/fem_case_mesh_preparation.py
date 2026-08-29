"""Case-specific grouped-mesh definition preparation."""

from __future__ import annotations

from dataclasses import dataclass, replace

from threadrom.case.resolved_case import ResolvedCase
from threadrom.factory.geometry_adapter import (
    GeometryDefinitionBundle,
)
from threadrom.meshing.complete_joint_mesh_definition import (
    CompleteJointMeshDefinition,
)
from threadrom.meshing.complete_joint_surface_classification import (
    CompleteJointSurfaceClassificationDefinition,
)
from threadrom.meshing.nut_surface_classification import (
    NutSurfaceClassificationDefinition,
)
from threadrom.meshing.surface_classification import (
    SurfaceClassificationDefinition,
)


@dataclass(frozen=True, slots=True)
class FemCaseMeshDefinitions:
    """Identity-rebound mesh/classification definitions for one case."""

    mesh_id: str
    joint_geometry_id: str
    classification_id: str
    mesh: CompleteJointMeshDefinition
    joint_classification: (
        CompleteJointSurfaceClassificationDefinition
    )
    bolt_classification: SurfaceClassificationDefinition
    nut_classification: NutSurfaceClassificationDefinition


def build_fem_case_mesh_definitions(
    resolved: ResolvedCase,
    geometry: GeometryDefinitionBundle,
    *,
    mesh_template: CompleteJointMeshDefinition,
    joint_classification_template: (
        CompleteJointSurfaceClassificationDefinition
    ),
    bolt_classification_template: (
        SurfaceClassificationDefinition
    ),
    nut_classification_template: (
        NutSurfaceClassificationDefinition
    ),
) -> FemCaseMeshDefinitions:
    """Rebind legacy configuration identities to one resolved case.

    Numerical meshing/classification tolerances and semantic names are
    reused as backend policy. Phase-2 assembly, geometry, classification
    and mesh identities are never propagated into the generated case.
    """

    token = resolved.case_hash[:16]

    mesh_id = f"mesh-{token}"
    joint_geometry_id = f"joint-geometry-{token}"
    classification_id = f"joint-classification-{token}"

    mesh = replace(
        mesh_template,
        mesh_id=mesh_id,
        assembly_id=resolved.assembly.assembly_id,
        geometry_id=joint_geometry_id,
        classification_id=classification_id,
    )

    joint_classification = replace(
        joint_classification_template,
        classification_id=classification_id,
        assembly_id=resolved.assembly.assembly_id,
        geometry_id=joint_geometry_id,
    )

    bolt_classification = replace(
        bolt_classification_template,
        mesh_id=mesh_id,
        geometry_id=geometry.bolt_blank.geometry_id,
    )

    nut_classification = replace(
        nut_classification_template,
        mesh_id=mesh_id,
        geometry_id=geometry.nut_blank.geometry_id,
    )

    return FemCaseMeshDefinitions(
        mesh_id=mesh_id,
        joint_geometry_id=joint_geometry_id,
        classification_id=classification_id,
        mesh=mesh,
        joint_classification=joint_classification,
        bolt_classification=bolt_classification,
        nut_classification=nut_classification,
    )

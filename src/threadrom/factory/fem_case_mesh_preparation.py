"""Case-specific grouped-mesh definition preparation."""

from __future__ import annotations

from dataclasses import dataclass, replace

from threadrom.case.resolved_case import ResolvedCase
from threadrom.factory.geometry_adapter import (
    GeometryDefinitionBundle,
)
from threadrom.factory.geometry_identity import (
    joint_geometry_bundle_sha256,
)
from threadrom.factory.mesh_identity import (
    classification_sha256,
    mesh_generation_sha256,
)
from threadrom.meshing.complete_joint_local_refinement import (
    ResolvedCompleteJointLocalRefinement,
)
from threadrom.meshing.complete_joint_mesh_definition import (
    CompleteJointMeshDefinition,
    ResolvedCompleteJointMeshSizes,
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
    classification_sha256: str
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
    joint_geometry_token = joint_geometry_bundle_sha256(
        resolved,
        geometry,
    )[:16]
    classification_digest = classification_sha256(
        resolved,
        geometry,
        joint_classification=joint_classification_template,
        bolt_classification=bolt_classification_template,
        nut_classification=nut_classification_template,
    )
    classification_token = classification_digest[:16]

    mesh_id = f"mesh-{token}"
    joint_geometry_id = (
        f"joint-geometry-{joint_geometry_token}"
    )
    classification_id = (
        f"joint-classification-{classification_token}"
    )

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
        classification_sha256=classification_digest,
        mesh=mesh,
        joint_classification=joint_classification,
        bolt_classification=bolt_classification,
        nut_classification=nut_classification,
    )


def bind_fem_case_mesh_identity(
    definitions: FemCaseMeshDefinitions,
    sizes: ResolvedCompleteJointMeshSizes,
    local_refinement: (
        ResolvedCompleteJointLocalRefinement | None
    ),
) -> FemCaseMeshDefinitions:
    """Bind the final mesh identity after its recipe is fully resolved.

    Classification identity is computed once during preparation from the
    actual built geometry and then carried forward unchanged. Mesh identity
    is derived only here, once absolute mesh sizes and optional local
    refinement are known.
    """

    mesh_digest = mesh_generation_sha256(
        mesh_definition=definitions.mesh,
        sizes=sizes,
        classification_sha256=(
            definitions.classification_sha256
        ),
        local_refinement=local_refinement,
    )

    mesh_id = f"mesh-{mesh_digest[:16]}"

    return replace(
        definitions,
        mesh_id=mesh_id,
        mesh=replace(
            definitions.mesh,
            mesh_id=mesh_id,
        ),
        bolt_classification=replace(
            definitions.bolt_classification,
            mesh_id=mesh_id,
        ),
        nut_classification=replace(
            definitions.nut_classification,
            mesh_id=mesh_id,
        ),
    )

"""Executable grouped-mesh stage for one FEM case."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from threadrom.case.resolved_case import ResolvedCase
from threadrom.factory.fem_case_mesh_preparation import (
    FemCaseMeshDefinitions,
    build_fem_case_mesh_definitions,
)
from threadrom.factory.fem_case_preparation import (
    derive_fem_case_preparation,
)
from threadrom.factory.geometry_adapter import (
    GeometryDefinitionBundle,
)
from threadrom.meshing.complete_joint_mesh_definition import (
    CompleteJointMeshDefinition,
    ResolvedCompleteJointMeshSizes,
    resolve_complete_joint_mesh_sizes,
)
from threadrom.meshing.complete_joint_surface_classification import (
    CompleteJointSurfaceClassificationDefinition,
)
from threadrom.meshing.grouped_complete_joint_mesh import (
    GroupedCompleteJointMeshResult,
    generate_grouped_complete_joint_mesh,
)
from threadrom.meshing.mesh_levels import (
    MeshLevelPolicy,
    resolve_mesh_levels,
)
from threadrom.meshing.nut_surface_classification import (
    NutSurfaceClassificationDefinition,
)
from threadrom.meshing.surface_classification import (
    SurfaceClassificationDefinition,
)


@dataclass(frozen=True, slots=True)
class FemCaseMeshArtifact:
    """Verified grouped mesh produced for one resolved FEM case."""

    case_hash: str
    run_id: str
    definitions: FemCaseMeshDefinitions
    sizes: ResolvedCompleteJointMeshSizes
    step_path: Path
    msh_path: Path
    result: GroupedCompleteJointMeshResult


def generate_fem_case_grouped_mesh(
    resolved: ResolvedCase,
    geometry: GeometryDefinitionBundle,
    *,
    step_path: Path,
    artifact_root: Path,
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
    bolt_mesh_level_policy: MeshLevelPolicy,
    nut_mesh_level_policy: MeshLevelPolicy,
) -> FemCaseMeshArtifact:
    """Generate and validate one case-specific grouped tetrahedral mesh."""

    if not step_path.exists() or step_path.stat().st_size <= 0:
        raise FileNotFoundError(
            f"Valid FEM case STEP not found: {step_path}"
        )

    preparation = derive_fem_case_preparation(
        resolved
    )

    definitions = build_fem_case_mesh_definitions(
        resolved,
        geometry,
        mesh_template=mesh_template,
        joint_classification_template=(
            joint_classification_template
        ),
        bolt_classification_template=(
            bolt_classification_template
        ),
        nut_classification_template=(
            nut_classification_template
        ),
    )

    bolt_levels = resolve_mesh_levels(
        bolt_mesh_level_policy,
        geometry.external_thread,
    )

    nut_levels = resolve_mesh_levels(
        nut_mesh_level_policy,
        geometry.internal_thread,
    )

    sizes = resolve_complete_joint_mesh_sizes(
        definitions.mesh,
        bolt_levels,
        nut_levels,
    )

    msh_path = (
        artifact_root
        / preparation.identity.run_id
        / "mesh"
        / (
            "complete_joint_grouped_"
            f"{sizes.level_name}_first_order.msh"
        )
    )

    result = generate_grouped_complete_joint_mesh(
        step_path,
        msh_path,
        resolved.assembly,
        geometry.bolt_blank,
        geometry.nut_blank,
        definitions.mesh,
        sizes,
        definitions.joint_classification,
        definitions.bolt_classification,
        definitions.nut_classification,
    )

    return FemCaseMeshArtifact(
        case_hash=resolved.case_hash,
        run_id=preparation.identity.run_id,
        definitions=definitions,
        sizes=sizes,
        step_path=step_path,
        msh_path=msh_path,
        result=result,
    )

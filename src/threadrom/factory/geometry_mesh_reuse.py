"""Canonical geometry/mesh identity derivation and reuse planning.

This module performs no CAD generation, meshing, or FEM execution.

It derives the same identities used by ThreadROM's governed geometry and
mesh preparation machinery, then asks the Geometry/Mesh Atlas whether the
corresponding immutable artifacts already exist.
"""

from __future__ import annotations

from dataclasses import dataclass

from threadrom.case.resolved_case import ResolvedCase
from threadrom.factory.fem_case_mesh_preparation import (
    bind_fem_case_mesh_identity,
    build_fem_case_mesh_definitions,
)
from threadrom.factory.geometry_adapter import (
    build_geometry_definitions,
)
from threadrom.factory.geometry_identity import (
    joint_geometry_bundle_sha256,
)
from threadrom.factory.geometry_mesh_atlas import (
    resolve_geometry_asset,
    resolve_mesh_asset,
)
from threadrom.factory.mesh_identity import (
    mesh_generation_sha256,
)
from threadrom.meshing.complete_joint_local_refinement import (
    CompleteJointLocalRefinementPolicy,
    resolve_complete_joint_local_refinement,
)
from threadrom.meshing.complete_joint_mesh_definition import (
    CompleteJointMeshDefinition,
    resolve_complete_joint_mesh_sizes,
)
from threadrom.meshing.complete_joint_surface_classification import (
    CompleteJointSurfaceClassificationDefinition,
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


GEOMETRY_GENERATION_ID = (
    "threadrom_parametric_complete_joint_v1"
)

MESH_GENERATION_ID = (
    "threadrom_grouped_gmsh_complete_joint_v1"
)


@dataclass(frozen=True, slots=True)
class GeometryMeshReuseIdentity:
    """Exact reusable geometry/mesh identity for one resolved case."""

    geometry_id: str
    geometry_identity_sha256: str
    classification_id: str
    classification_sha256: str
    mesh_id: str
    mesh_identity_sha256: str


@dataclass(frozen=True, slots=True)
class GeometryMeshReuseResolution:
    """Atlas decision for one fully resolved geometry/mesh recipe."""

    identity: GeometryMeshReuseIdentity
    disposition: str
    geometry_record: dict | None
    mesh_record: dict | None

    @property
    def full_reuse_available(self) -> bool:
        return (
            self.disposition
            == "REUSE_GEOMETRY_AND_MESH"
        )


def derive_geometry_mesh_reuse_identity(
    resolved: ResolvedCase,
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
    bolt_mesh_level_policy: MeshLevelPolicy,
    nut_mesh_level_policy: MeshLevelPolicy,
    local_refinement_policy: (
        CompleteJointLocalRefinementPolicy | None
    ) = None,
) -> GeometryMeshReuseIdentity:
    """Derive canonical CAD/mesh identities without generating artifacts."""

    geometry = build_geometry_definitions(
        resolved
    )

    geometry_sha = (
        joint_geometry_bundle_sha256(
            resolved,
            geometry,
        )
    )

    geometry_id = (
        "joint-geometry-"
        + geometry_sha[:16]
    )

    definitions = (
        build_fem_case_mesh_definitions(
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
    )

    if (
        definitions.joint_geometry_id
        != geometry_id
    ):
        raise RuntimeError(
            "Derived joint-geometry identity drift."
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

    resolved_local_refinement = None

    if local_refinement_policy is not None:
        resolved_local_refinement = (
            resolve_complete_joint_local_refinement(
                policy=local_refinement_policy,
                base_mesh_level=sizes.level_name,
                global_max_size_mm=(
                    sizes.mesh_size_max_mm
                ),
            )
        )

    mesh_sha = mesh_generation_sha256(
        mesh_definition=definitions.mesh,
        sizes=sizes,
        classification_sha256=(
            definitions.classification_sha256
        ),
        local_refinement=(
            resolved_local_refinement
        ),
    )

    bound = bind_fem_case_mesh_identity(
        definitions,
        sizes,
        resolved_local_refinement,
    )

    expected_mesh_id = (
        "mesh-"
        + mesh_sha[:16]
    )

    if bound.mesh_id != expected_mesh_id:
        raise RuntimeError(
            "Derived final mesh identity drift."
        )

    return GeometryMeshReuseIdentity(
        geometry_id=geometry_id,
        geometry_identity_sha256=geometry_sha,
        classification_id=(
            bound.classification_id
        ),
        classification_sha256=(
            bound.classification_sha256
        ),
        mesh_id=bound.mesh_id,
        mesh_identity_sha256=mesh_sha,
    )


def resolve_geometry_mesh_reuse(
    atlas: dict,
    identity: GeometryMeshReuseIdentity,
) -> GeometryMeshReuseResolution:
    """Return the governed reuse/generation decision for one recipe."""

    geometry = resolve_geometry_asset(
        atlas,
        geometry_id=identity.geometry_id,
        identity_sha256=(
            identity.geometry_identity_sha256
        ),
    )

    if geometry is None:
        return GeometryMeshReuseResolution(
            identity=identity,
            disposition=(
                "GENERATE_GEOMETRY_AND_MESH"
            ),
            geometry_record=None,
            mesh_record=None,
        )

    mesh = resolve_mesh_asset(
        atlas,
        mesh_id=identity.mesh_id,
        geometry_id=identity.geometry_id,
        identity_sha256=(
            identity.mesh_identity_sha256
        ),
    )

    if mesh is None:
        return GeometryMeshReuseResolution(
            identity=identity,
            disposition=(
                "REUSE_GEOMETRY_GENERATE_MESH"
            ),
            geometry_record=geometry,
            mesh_record=None,
        )

    return GeometryMeshReuseResolution(
        identity=identity,
        disposition=(
            "REUSE_GEOMETRY_AND_MESH"
        ),
        geometry_record=geometry,
        mesh_record=mesh,
    )
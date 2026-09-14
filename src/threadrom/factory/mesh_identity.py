"""Deterministic identities for ThreadROM classification and meshing.

Classification identity represents the semantic interpretation of the
actual built geometry. Pure verification/acceptance thresholds are kept
outside this fingerprint because changing an acceptance gate does not
change how CAD surfaces are classified or named.

Mesh-generation identity is added separately once the resolved mesh
sizes and optional local-refinement state are available.
"""

from __future__ import annotations

import hashlib
import json

from threadrom.case.resolved_case import ResolvedCase
from threadrom.factory.geometry_adapter import (
    GeometryDefinitionBundle,
)
from threadrom.factory.geometry_identity import (
    joint_geometry_bundle_sha256,
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


CLASSIFICATION_SCHEMA_VERSION = 1


def _sha256(payload: dict[str, object]) -> str:
    """Return deterministic SHA-256 for one canonical payload."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()


def classification_payload(
    resolved: ResolvedCase,
    geometry: GeometryDefinitionBundle,
    *,
    joint_classification: (
        CompleteJointSurfaceClassificationDefinition
    ),
    bolt_classification: SurfaceClassificationDefinition,
    nut_classification: NutSurfaceClassificationDefinition,
) -> dict[str, object]:
    """Return inputs that determine semantic CAD classification.

    Deliberately excluded:
    * case/run/mesh/classification IDs;
    * assembly identity labels;
    * verification-only minimum surface/count gates;
    * materials and other non-geometric engineering physics.

    Included:
    * exact built-joint geometry identity;
    * geometric classification tolerances;
    * semantic physical-group names.
    """

    return {
        "schema_version": CLASSIFICATION_SCHEMA_VERSION,
        "joint_geometry_sha256": (
            joint_geometry_bundle_sha256(
                resolved,
                geometry,
            )
        ),
        "joint": {
            "plane_tolerance_mm": (
                joint_classification.plane_tolerance_mm
            ),
            "radial_tolerance_mm": (
                joint_classification.radial_tolerance_mm
            ),
            "volume_names": (
                joint_classification.volume_names
            ),
            "member_surface_names": (
                joint_classification.member_surface_names
            ),
        },
        "bolt": {
            "plane_tolerance_mm": (
                bolt_classification.plane_tolerance_mm
            ),
            "physical_names": {
                "head_top": (
                    bolt_classification.head_top_name
                ),
                "under_head_bearing": (
                    bolt_classification.under_head_bearing_name
                ),
                "head_sides": (
                    bolt_classification.head_sides_name
                ),
                "thread_surfaces": (
                    bolt_classification.thread_surfaces_name
                ),
                "bolt_tip": (
                    bolt_classification.bolt_tip_name
                ),
                "transition_surfaces": (
                    bolt_classification.transition_surfaces_name
                ),
            },
        },
        "nut": {
            "plane_tolerance_mm": (
                nut_classification.plane_tolerance_mm
            ),
            "radial_tolerance_mm": (
                nut_classification.radial_tolerance_mm
            ),
            "physical_names": {
                "lower_bearing": (
                    nut_classification.lower_bearing_name
                ),
                "upper_bearing": (
                    nut_classification.upper_bearing_name
                ),
                "outer_hex": (
                    nut_classification.outer_hex_name
                ),
                "internal_thread": (
                    nut_classification.internal_thread_name
                ),
                "transition_surfaces": (
                    nut_classification.transition_surfaces_name
                ),
            },
        },
    }


def classification_sha256(
    resolved: ResolvedCase,
    geometry: GeometryDefinitionBundle,
    *,
    joint_classification: (
        CompleteJointSurfaceClassificationDefinition
    ),
    bolt_classification: SurfaceClassificationDefinition,
    nut_classification: NutSurfaceClassificationDefinition,
) -> str:
    """Return identity for semantic classification of built CAD."""

    return _sha256(
        classification_payload(
            resolved,
            geometry,
            joint_classification=joint_classification,
            bolt_classification=bolt_classification,
            nut_classification=nut_classification,
        )
    )

MESH_GENERATION_SCHEMA_VERSION = 1


def mesh_generation_payload(
    *,
    mesh_definition: CompleteJointMeshDefinition,
    sizes: ResolvedCompleteJointMeshSizes,
    classification_sha256: str,
    local_refinement: (
        ResolvedCompleteJointLocalRefinement | None
    ),
) -> dict[str, object]:
    """Return the exact governed recipe used to generate one MSH artifact.

    Included:
    * semantic classification identity;
    * Gmsh generation/output settings;
    * resolved absolute mesh sizes;
    * resolved semantic local-refinement recipe.

    Deliberately excluded:
    * request/run/mesh identity labels;
    * assembly/geometry labels already represented upstream;
    * minimum node/tetrahedron/triangle acceptance thresholds;
    * other verification-only gates.

    Local-refinement policy names/IDs are provenance labels. The actual
    generated mesh is governed by its resolved sizes, sampling and
    semantic target regions, so those resolved values define identity.
    """

    if (
        len(classification_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in classification_sha256
        )
    ):
        raise ValueError(
            "classification_sha256 must be a lowercase 64-character "
            "hexadecimal SHA-256 digest."
        )

    refinement_payload: dict[str, object] | None

    if local_refinement is None:
        refinement_payload = None
    else:
        refinement_payload = {
            "base_mesh_level": (
                local_refinement.base_mesh_level
            ),
            "local_size_mm": (
                local_refinement.local_size_mm
            ),
            "transition_distance_mm": (
                local_refinement.transition_distance_mm
            ),
            "distance_sampling": (
                local_refinement.distance_sampling
            ),
            "bolt_regions": (
                local_refinement.bolt_regions
            ),
            "nut_regions": (
                local_refinement.nut_regions
            ),
            "member_regions": (
                local_refinement.member_regions
            ),
        }

    return {
        "schema_version": MESH_GENERATION_SCHEMA_VERSION,
        "classification_sha256": classification_sha256,
        "gmsh": {
            "element_order": mesh_definition.element_order,
            "algorithm_2d": mesh_definition.algorithm_2d,
            "algorithm_3d": mesh_definition.algorithm_3d,
            "msh_file_version": (
                mesh_definition.msh_file_version
            ),
            "binary_output": mesh_definition.binary_output,
            "save_all_elements": (
                mesh_definition.save_all_elements
            ),
        },
        "sizes": {
            "level_name": sizes.level_name,
            "mesh_size_min_mm": sizes.mesh_size_min_mm,
            "mesh_size_max_mm": sizes.mesh_size_max_mm,
            "bolt_thread_surface_size_mm": (
                sizes.bolt_thread_surface_size_mm
            ),
            "nut_thread_surface_size_mm": (
                sizes.nut_thread_surface_size_mm
            ),
        },
        "local_refinement": refinement_payload,
    }


def mesh_generation_sha256(
    *,
    mesh_definition: CompleteJointMeshDefinition,
    sizes: ResolvedCompleteJointMeshSizes,
    classification_sha256: str,
    local_refinement: (
        ResolvedCompleteJointLocalRefinement | None
    ),
) -> str:
    """Return identity for the exact governed Gmsh generation recipe."""

    return _sha256(
        mesh_generation_payload(
            mesh_definition=mesh_definition,
            sizes=sizes,
            classification_sha256=classification_sha256,
            local_refinement=local_refinement,
        )
    )

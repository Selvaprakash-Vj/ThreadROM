"""Mesh-generation identity tracks the actual Gmsh recipe."""

from dataclasses import replace

from threadrom.factory.mesh_identity import (
    mesh_generation_sha256,
)
from threadrom.meshing.complete_joint_local_refinement import (
    ResolvedCompleteJointLocalRefinement,
)
from threadrom.meshing.complete_joint_mesh_definition import (
    ResolvedCompleteJointMeshSizes,
)
from tests.unit.test_phase3_fem_case_mesh_preparation import (
    _templates,
)


CLASSIFICATION_HASH = "a" * 64


def _mesh_definition():
    return _templates()[0]


def _sizes() -> ResolvedCompleteJointMeshSizes:
    return ResolvedCompleteJointMeshSizes(
        level_name="medium",
        mesh_size_min_mm=0.267926609,
        mesh_size_max_mm=1.005,
        bolt_thread_surface_size_mm=0.267926609,
        nut_thread_surface_size_mm=0.267926609,
    )


def _refinement() -> ResolvedCompleteJointLocalRefinement:
    return ResolvedCompleteJointLocalRefinement(
        policy_id="TRM-LRP-000001",
        policy_name="medium_plus_v1",
        base_mesh_level="medium",
        local_size_mm=0.5025,
        transition_distance_mm=0.15075,
        distance_sampling=30,
        bolt_regions=("under_head_bearing",),
        nut_regions=("lower_bearing",),
        member_regions=(
            "head_member_interface",
            "nut_member_interface",
        ),
    )


def test_mesh_identity_is_deterministic() -> None:
    definition = _mesh_definition()
    sizes = _sizes()

    first = mesh_generation_sha256(
        mesh_definition=definition,
        sizes=sizes,
        classification_sha256=CLASSIFICATION_HASH,
        local_refinement=None,
    )
    second = mesh_generation_sha256(
        mesh_definition=definition,
        sizes=sizes,
        classification_sha256=CLASSIFICATION_HASH,
        local_refinement=None,
    )

    assert first == second


def test_resolved_mesh_size_change_changes_identity() -> None:
    definition = _mesh_definition()
    sizes = _sizes()

    changed_sizes = replace(
        sizes,
        mesh_size_max_mm=0.95,
    )

    assert (
        mesh_generation_sha256(
            mesh_definition=definition,
            sizes=changed_sizes,
            classification_sha256=CLASSIFICATION_HASH,
            local_refinement=None,
        )
        != mesh_generation_sha256(
            mesh_definition=definition,
            sizes=sizes,
            classification_sha256=CLASSIFICATION_HASH,
            local_refinement=None,
        )
    )


def test_local_refinement_changes_identity() -> None:
    definition = _mesh_definition()
    sizes = _sizes()

    assert (
        mesh_generation_sha256(
            mesh_definition=definition,
            sizes=sizes,
            classification_sha256=CLASSIFICATION_HASH,
            local_refinement=_refinement(),
        )
        != mesh_generation_sha256(
            mesh_definition=definition,
            sizes=sizes,
            classification_sha256=CLASSIFICATION_HASH,
            local_refinement=None,
        )
    )


def test_gmsh_algorithm_change_changes_identity() -> None:
    definition = _mesh_definition()
    sizes = _sizes()

    changed_definition = replace(
        definition,
        algorithm_3d=definition.algorithm_3d + 1,
    )

    assert (
        mesh_generation_sha256(
            mesh_definition=changed_definition,
            sizes=sizes,
            classification_sha256=CLASSIFICATION_HASH,
            local_refinement=None,
        )
        != mesh_generation_sha256(
            mesh_definition=definition,
            sizes=sizes,
            classification_sha256=CLASSIFICATION_HASH,
            local_refinement=None,
        )
    )


def test_verification_threshold_change_does_not_change_identity() -> None:
    definition = _mesh_definition()
    sizes = _sizes()

    changed_definition = replace(
        definition,
        minimum_node_count=definition.minimum_node_count + 1,
        minimum_tetrahedron_count=(
            definition.minimum_tetrahedron_count + 1
        ),
        minimum_boundary_triangle_count=(
            definition.minimum_boundary_triangle_count + 1
        ),
    )

    assert (
        mesh_generation_sha256(
            mesh_definition=changed_definition,
            sizes=sizes,
            classification_sha256=CLASSIFICATION_HASH,
            local_refinement=None,
        )
        == mesh_generation_sha256(
            mesh_definition=definition,
            sizes=sizes,
            classification_sha256=CLASSIFICATION_HASH,
            local_refinement=None,
        )
    )


def test_classification_change_changes_mesh_identity() -> None:
    definition = _mesh_definition()
    sizes = _sizes()

    assert (
        mesh_generation_sha256(
            mesh_definition=definition,
            sizes=sizes,
            classification_sha256="b" * 64,
            local_refinement=None,
        )
        != mesh_generation_sha256(
            mesh_definition=definition,
            sizes=sizes,
            classification_sha256=CLASSIFICATION_HASH,
            local_refinement=None,
        )
    )

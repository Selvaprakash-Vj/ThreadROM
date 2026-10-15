"""Geometry/Mesh Atlas reuse planning tests."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from threadrom.case.resolver import resolve_case
from threadrom.factory.geometry_mesh_atlas import (
    new_geometry_mesh_atlas,
    register_geometry_asset,
    register_mesh_asset,
)
from threadrom.factory.geometry_mesh_reuse import (
    GEOMETRY_GENERATION_ID,
    MESH_GENERATION_ID,
    GeometryMeshReuseIdentity,
    derive_geometry_mesh_reuse_identity,
    resolve_geometry_mesh_reuse,
)
from threadrom.meshing.complete_joint_mesh_definition import (
    load_complete_joint_mesh_definition,
)
from threadrom.meshing.complete_joint_surface_classification import (
    load_complete_joint_surface_definition,
)
from threadrom.meshing.mesh_levels import (
    load_mesh_level_policy,
)
from threadrom.meshing.nut_surface_classification import (
    load_nut_surface_classification_definition,
)
from threadrom.meshing.surface_classification import (
    load_surface_classification_definition,
)
from tests.unit.test_case_resolver import (
    _baseline_case,
)


def _derive(resolved):
    mesh = load_complete_joint_mesh_definition(
        Path(
            "config/complete_joint_mesh.toml"
        )
    )

    return derive_geometry_mesh_reuse_identity(
        resolved,
        mesh_template=mesh,
        joint_classification_template=(
            load_complete_joint_surface_definition(
                Path(
                    "config/"
                    "complete_joint_surface_classification.toml"
                )
            )
        ),
        bolt_classification_template=(
            load_surface_classification_definition(
                Path(
                    "config/surface_classification.toml"
                )
            )
        ),
        nut_classification_template=(
            load_nut_surface_classification_definition(
                Path(
                    "config/nut_surface_classification.toml"
                )
            )
        ),
        bolt_mesh_level_policy=(
            load_mesh_level_policy(
                Path("config")
                / mesh.bolt_mesh_level_policy
            )
        ),
        nut_mesh_level_policy=(
            load_mesh_level_policy(
                Path("config")
                / mesh.nut_mesh_level_policy
            )
        ),
    )


def test_identity_derivation_is_deterministic() -> None:
    resolved = resolve_case(
        _baseline_case()
    )

    assert (
        _derive(
            resolved
        )
        == _derive(
            resolved
        )
    )


def test_loading_change_does_not_change_geometry_or_mesh_recipe() -> None:
    resolved = resolve_case(
        _baseline_case()
    )

    changed_source = replace(
        resolved.source_case,
        loading=replace(
            resolved.source_case.loading,
            target_preload_n=(
                resolved.source_case.loading.target_preload_n
                * 0.75
            ),
        ),
    )

    changed = replace(
        resolved,
        source_case=changed_source,
    )

    assert (
        _derive(
            changed
        )
        == _derive(
            resolved
        )
    )


def test_material_property_change_does_not_change_geometry_or_mesh_recipe() -> None:
    resolved = resolve_case(
        _baseline_case()
    )

    changed = replace(
        resolved,
        bolt_material=replace(
            resolved.bolt_material,
            youngs_modulus_mpa=(
                resolved.bolt_material.youngs_modulus_mpa
                * 0.95
            ),
        ),
    )

    assert (
        _derive(
            changed
        )
        == _derive(
            resolved
        )
    )


def test_reuse_resolution_progresses_from_generate_to_full_reuse() -> None:
    geometry_sha = (
        "a" * 64
    )

    mesh_sha = (
        "b" * 64
    )

    identity = GeometryMeshReuseIdentity(
        geometry_id=(
            "joint-geometry-"
            + geometry_sha[:16]
        ),
        geometry_identity_sha256=(
            geometry_sha
        ),
        classification_id=(
            "joint-classification-"
            + ("c" * 16)
        ),
        classification_sha256=(
            "c" * 64
        ),
        mesh_id=(
            "mesh-"
            + mesh_sha[:16]
        ),
        mesh_identity_sha256=(
            mesh_sha
        ),
    )

    atlas = (
        new_geometry_mesh_atlas()
    )

    first = resolve_geometry_mesh_reuse(
        atlas,
        identity,
    )

    assert (
        first.disposition
        == "GENERATE_GEOMETRY_AND_MESH"
    )

    register_geometry_asset(
        atlas,
        geometry_id=identity.geometry_id,
        identity_sha256=(
            identity.geometry_identity_sha256
        ),
        generation_id=(
            GEOMETRY_GENERATION_ID
        ),
        artifact_path=(
            "simulations/example/joint.step"
        ),
        artifact_sha256=(
            "d" * 64
        ),
        source_case_id="CASE-A",
    )

    second = resolve_geometry_mesh_reuse(
        atlas,
        identity,
    )

    assert (
        second.disposition
        == "REUSE_GEOMETRY_GENERATE_MESH"
    )

    register_mesh_asset(
        atlas,
        mesh_id=identity.mesh_id,
        geometry_id=identity.geometry_id,
        identity_sha256=(
            identity.mesh_identity_sha256
        ),
        generation_id=(
            MESH_GENERATION_ID
        ),
        artifact_path=(
            "simulations/example/joint.msh"
        ),
        artifact_sha256=(
            "e" * 64
        ),
        source_case_id="CASE-A",
    )

    final = resolve_geometry_mesh_reuse(
        atlas,
        identity,
    )

    assert final.full_reuse_available
    assert (
        final.disposition
        == "REUSE_GEOMETRY_AND_MESH"
    )
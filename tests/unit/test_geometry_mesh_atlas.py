"""Tests for the governed geometry/mesh reuse atlas."""

from __future__ import annotations

import pytest

from threadrom.factory.geometry_mesh_atlas import (
    GeometryMeshAtlasError,
    load_geometry_mesh_atlas,
    new_geometry_mesh_atlas,
    persist_geometry_mesh_atlas,
    register_geometry_asset,
    register_mesh_asset,
    resolve_geometry_asset,
    resolve_mesh_asset,
)


GEO_SHA = "a" * 64
MESH_SHA = "b" * 64
STEP_SHA = "c" * 64
MSH_SHA = "d" * 64

GEO_ID = (
    "joint-geometry-"
    + GEO_SHA[:16]
)

MESH_ID = (
    "mesh-"
    + MESH_SHA[:16]
)


def _with_geometry():
    atlas = new_geometry_mesh_atlas()

    record, disposition = (
        register_geometry_asset(
            atlas,
            geometry_id=GEO_ID,
            identity_sha256=GEO_SHA,
            generation_id="geometry-generation-v1",
            artifact_path=(
                "simulations/staging/case-a/geometry/joint.step"
            ),
            artifact_sha256=STEP_SHA,
            source_case_id="CASE-A",
        )
    )

    assert disposition == "REGISTERED"

    return atlas, record


def test_same_geometry_identity_reuses_one_atlas_entry() -> None:
    atlas, first = _with_geometry()

    second, disposition = (
        register_geometry_asset(
            atlas,
            geometry_id=GEO_ID,
            identity_sha256=GEO_SHA,
            generation_id="geometry-generation-v1",
            artifact_path=(
                "simulations/staging/case-b/geometry/joint.step"
            ),
            artifact_sha256=STEP_SHA,
            source_case_id="CASE-B",
        )
    )

    assert disposition == "REUSED"
    assert first is second

    assert len(
        atlas["geometries"]
    ) == 1

    assert second[
        "source_case_ids"
    ] == [
        "CASE-A",
        "CASE-B",
    ]

    assert len(
        second[
            "artifact_paths"
        ]
    ) == 2


def test_geometry_identity_conflict_fails_closed() -> None:
    atlas, _ = _with_geometry()

    with pytest.raises(
        GeometryMeshAtlasError
    ):
        register_geometry_asset(
            atlas,
            geometry_id=GEO_ID,
            identity_sha256=GEO_SHA,
            generation_id="geometry-generation-v1",
            artifact_path=(
                "simulations/staging/case-c/geometry/joint.step"
            ),
            artifact_sha256="e" * 64,
            source_case_id="CASE-C",
        )


def test_same_mesh_identity_reuses_one_atlas_entry() -> None:
    atlas, _ = _with_geometry()

    first, disposition = (
        register_mesh_asset(
            atlas,
            mesh_id=MESH_ID,
            geometry_id=GEO_ID,
            identity_sha256=MESH_SHA,
            generation_id="mesh-generation-v1",
            artifact_path=(
                "simulations/staging/case-a/mesh/joint.msh"
            ),
            artifact_sha256=MSH_SHA,
            source_case_id="CASE-A",
            quality_evidence_path=(
                "simulations/staging/case-a/mesh/quality.json"
            ),
        )
    )

    assert disposition == "REGISTERED"

    second, disposition = (
        register_mesh_asset(
            atlas,
            mesh_id=MESH_ID,
            geometry_id=GEO_ID,
            identity_sha256=MESH_SHA,
            generation_id="mesh-generation-v1",
            artifact_path=(
                "simulations/staging/case-b/mesh/joint.msh"
            ),
            artifact_sha256=MSH_SHA,
            source_case_id="CASE-B",
            quality_evidence_path=(
                "simulations/staging/case-b/mesh/quality.json"
            ),
        )
    )

    assert disposition == "REUSED"
    assert first is second

    assert len(
        atlas["meshes"]
    ) == 1

    assert second[
        "source_case_ids"
    ] == [
        "CASE-A",
        "CASE-B",
    ]


def test_mesh_requires_registered_geometry() -> None:
    atlas = new_geometry_mesh_atlas()

    with pytest.raises(
        GeometryMeshAtlasError
    ):
        register_mesh_asset(
            atlas,
            mesh_id=MESH_ID,
            geometry_id=GEO_ID,
            identity_sha256=MESH_SHA,
            generation_id="mesh-generation-v1",
            artifact_path=(
                "simulations/staging/case-a/mesh/joint.msh"
            ),
            artifact_sha256=MSH_SHA,
            source_case_id="CASE-A",
        )


def test_lookup_returns_existing_reusable_assets() -> None:
    atlas, geometry = _with_geometry()

    mesh, _ = register_mesh_asset(
        atlas,
        mesh_id=MESH_ID,
        geometry_id=GEO_ID,
        identity_sha256=MESH_SHA,
        generation_id="mesh-generation-v1",
        artifact_path=(
            "simulations/staging/case-a/mesh/joint.msh"
        ),
        artifact_sha256=MSH_SHA,
        source_case_id="CASE-A",
    )

    assert (
        resolve_geometry_asset(
            atlas,
            geometry_id=GEO_ID,
            identity_sha256=GEO_SHA,
        )
        is geometry
    )

    assert (
        resolve_mesh_asset(
            atlas,
            mesh_id=MESH_ID,
            geometry_id=GEO_ID,
            identity_sha256=MESH_SHA,
        )
        is mesh
    )

    assert (
        resolve_geometry_asset(
            atlas,
            geometry_id="joint-geometry-ffffffffffffffff",
            identity_sha256="f" * 64,
        )
        is None
    )


def test_atlas_round_trip_is_deterministic(
    tmp_path,
) -> None:
    atlas, _ = _with_geometry()

    register_mesh_asset(
        atlas,
        mesh_id=MESH_ID,
        geometry_id=GEO_ID,
        identity_sha256=MESH_SHA,
        generation_id="mesh-generation-v1",
        artifact_path=(
            "simulations/staging/case-a/mesh/joint.msh"
        ),
        artifact_sha256=MSH_SHA,
        source_case_id="CASE-A",
    )

    path = (
        tmp_path
        / "geometry_mesh_atlas.json"
    )

    persist_geometry_mesh_atlas(
        path,
        atlas,
    )

    first_bytes = (
        path.read_bytes()
    )

    loaded = (
        load_geometry_mesh_atlas(
            path
        )
    )

    persist_geometry_mesh_atlas(
        path,
        loaded,
    )

    assert (
        path.read_bytes()
        == first_bytes
    )

    assert loaded == atlas
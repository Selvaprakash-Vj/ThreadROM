"""Governed reusable geometry/mesh asset registry.

This registry is intentionally separate from the accepted-FEM evidence atlas.

Geometry identity is owned by ``geometry_identity.py``.
Mesh identity is owned by ``mesh_identity.py``.

This module records immutable generated artifacts against those identities so
future FEM cases can resolve and reuse an existing CAD/mesh realization before
performing duplicate generation.
"""

from __future__ import annotations

import json
import re

from pathlib import Path
from typing import Any


ATLAS_SCHEMA = "threadrom.geometry_mesh_reuse_atlas.v1"
ATLAS_SCHEMA_VERSION = 1

_SHA256_PATTERN = re.compile(
    r"^[0-9a-f]{64}$"
)


class GeometryMeshAtlasError(RuntimeError):
    """Raised when reusable geometry/mesh evidence is inconsistent."""


def _require_text(
    value: object,
    name: str,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
    ):
        raise GeometryMeshAtlasError(
            f"{name} must be a non-blank trimmed string."
        )

    return value


def _require_sha256(
    value: object,
    name: str,
) -> str:
    text = _require_text(
        value,
        name,
    )

    if not _SHA256_PATTERN.fullmatch(text):
        raise GeometryMeshAtlasError(
            f"{name} must be exactly 64 lowercase hexadecimal characters."
        )

    return text


def _relative_path(
    value: object,
    name: str,
) -> str:
    text = _require_text(
        value,
        name,
    )

    path = Path(text)

    if path.is_absolute():
        raise GeometryMeshAtlasError(
            f"{name} must be repository-relative."
        )

    if ".." in path.parts:
        raise GeometryMeshAtlasError(
            f"{name} must not escape the repository."
        )

    normalized = path.as_posix()

    if normalized in {
        "",
        ".",
    }:
        raise GeometryMeshAtlasError(
            f"{name} is invalid."
        )

    return normalized


def _validate_identity_binding(
    *,
    identity: str,
    identity_sha256: str,
    prefix: str,
) -> None:
    expected_prefix = (
        prefix
        + identity_sha256[:16]
    )

    if (
        identity.startswith(prefix)
        and identity != expected_prefix
    ):
        raise GeometryMeshAtlasError(
            f"{identity!r} does not match its full identity SHA-256."
        )


def new_geometry_mesh_atlas() -> dict[str, Any]:
    """Return one empty deterministic V1 reuse atlas."""

    return {
        "schema": ATLAS_SCHEMA,
        "schema_version": ATLAS_SCHEMA_VERSION,
        "meaning": (
            "Reusable generated CAD and mesh artifact registry. "
            "This is not a FEM acceptance registry, ROM dataset, "
            "or dataset-admission certificate."
        ),
        "geometries": {},
        "meshes": {},
    }


def _validate_root(
    atlas: object,
) -> dict[str, Any]:
    if not isinstance(
        atlas,
        dict,
    ):
        raise GeometryMeshAtlasError(
            "Geometry/mesh atlas root must be an object."
        )

    if atlas.get("schema") != ATLAS_SCHEMA:
        raise GeometryMeshAtlasError(
            "Unexpected geometry/mesh atlas schema."
        )

    if (
        atlas.get("schema_version")
        != ATLAS_SCHEMA_VERSION
    ):
        raise GeometryMeshAtlasError(
            "Unexpected geometry/mesh atlas schema version."
        )

    geometries = atlas.get(
        "geometries"
    )

    meshes = atlas.get(
        "meshes"
    )

    if not isinstance(
        geometries,
        dict,
    ):
        raise GeometryMeshAtlasError(
            "Atlas geometries must be an object."
        )

    if not isinstance(
        meshes,
        dict,
    ):
        raise GeometryMeshAtlasError(
            "Atlas meshes must be an object."
        )

    return atlas


def load_geometry_mesh_atlas(
    path: Path,
) -> dict[str, Any]:
    """Load and validate one persisted reuse atlas."""

    payload = json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )

    return _validate_root(
        payload
    )


def persist_geometry_mesh_atlas(
    path: Path,
    atlas: dict[str, Any],
) -> None:
    """Atomically persist one deterministic reuse atlas."""

    _validate_root(
        atlas
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    encoded = (
        json.dumps(
            atlas,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )

    temporary = path.with_name(
        path.name + ".tmp"
    )

    temporary.write_text(
        encoded,
        encoding="utf-8",
        newline="\n",
    )

    temporary.replace(
        path
    )


def register_geometry_asset(
    atlas: dict[str, Any],
    *,
    geometry_id: str,
    identity_sha256: str,
    generation_id: str,
    artifact_path: str,
    artifact_sha256: str,
    source_case_id: str,
) -> tuple[dict[str, Any], str]:
    """Register or reuse one immutable generated geometry realization."""

    root = _validate_root(
        atlas
    )

    geometry_id = _require_text(
        geometry_id,
        "geometry_id",
    )

    identity_sha256 = _require_sha256(
        identity_sha256,
        "identity_sha256",
    )

    generation_id = _require_text(
        generation_id,
        "generation_id",
    )

    artifact_path = _relative_path(
        artifact_path,
        "artifact_path",
    )

    artifact_sha256 = _require_sha256(
        artifact_sha256,
        "artifact_sha256",
    )

    source_case_id = _require_text(
        source_case_id,
        "source_case_id",
    )

    _validate_identity_binding(
        identity=geometry_id,
        identity_sha256=identity_sha256,
        prefix="joint-geometry-",
    )

    geometries = root[
        "geometries"
    ]

    existing = geometries.get(
        geometry_id
    )

    if existing is None:
        record = {
            "geometry_id": geometry_id,
            "identity_sha256": identity_sha256,
            "generation_id": generation_id,
            "artifact_sha256": artifact_sha256,
            "canonical_artifact_path": artifact_path,
            "artifact_paths": [
                artifact_path,
            ],
            "source_case_ids": [
                source_case_id,
            ],
        }

        geometries[
            geometry_id
        ] = record

        return record, "REGISTERED"

    immutable = {
        "identity_sha256": identity_sha256,
        "generation_id": generation_id,
        "artifact_sha256": artifact_sha256,
    }

    for key, expected in immutable.items():
        if existing.get(key) != expected:
            raise GeometryMeshAtlasError(
                f"{geometry_id}: existing geometry asset conflicts "
                f"on {key}."
            )

    paths = sorted(
        {
            *existing.get(
                "artifact_paths",
                [],
            ),
            artifact_path,
        }
    )

    cases = sorted(
        {
            *existing.get(
                "source_case_ids",
                [],
            ),
            source_case_id,
        }
    )

    existing[
        "artifact_paths"
    ] = paths

    existing[
        "canonical_artifact_path"
    ] = paths[0]

    existing[
        "source_case_ids"
    ] = cases

    return existing, "REUSED"


def register_mesh_asset(
    atlas: dict[str, Any],
    *,
    mesh_id: str,
    geometry_id: str,
    identity_sha256: str,
    generation_id: str,
    artifact_path: str,
    artifact_sha256: str,
    source_case_id: str,
    quality_evidence_path: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Register or reuse one immutable generated mesh realization."""

    root = _validate_root(
        atlas
    )

    mesh_id = _require_text(
        mesh_id,
        "mesh_id",
    )

    geometry_id = _require_text(
        geometry_id,
        "geometry_id",
    )

    identity_sha256 = _require_sha256(
        identity_sha256,
        "identity_sha256",
    )

    generation_id = _require_text(
        generation_id,
        "generation_id",
    )

    artifact_path = _relative_path(
        artifact_path,
        "artifact_path",
    )

    artifact_sha256 = _require_sha256(
        artifact_sha256,
        "artifact_sha256",
    )

    source_case_id = _require_text(
        source_case_id,
        "source_case_id",
    )

    _validate_identity_binding(
        identity=mesh_id,
        identity_sha256=identity_sha256,
        prefix="mesh-",
    )

    if geometry_id not in root[
        "geometries"
    ]:
        raise GeometryMeshAtlasError(
            f"{mesh_id}: geometry {geometry_id!r} "
            "must be registered before its mesh."
        )

    quality_paths: list[str] = []

    if quality_evidence_path is not None:
        quality_paths.append(
            _relative_path(
                quality_evidence_path,
                "quality_evidence_path",
            )
        )

    meshes = root[
        "meshes"
    ]

    existing = meshes.get(
        mesh_id
    )

    if existing is None:
        record = {
            "mesh_id": mesh_id,
            "geometry_id": geometry_id,
            "identity_sha256": identity_sha256,
            "generation_id": generation_id,
            "artifact_sha256": artifact_sha256,
            "canonical_artifact_path": artifact_path,
            "artifact_paths": [
                artifact_path,
            ],
            "quality_evidence_paths": (
                quality_paths
            ),
            "source_case_ids": [
                source_case_id,
            ],
        }

        meshes[
            mesh_id
        ] = record

        return record, "REGISTERED"

    immutable = {
        "geometry_id": geometry_id,
        "identity_sha256": identity_sha256,
        "generation_id": generation_id,
        "artifact_sha256": artifact_sha256,
    }

    for key, expected in immutable.items():
        if existing.get(key) != expected:
            raise GeometryMeshAtlasError(
                f"{mesh_id}: existing mesh asset conflicts "
                f"on {key}."
            )

    paths = sorted(
        {
            *existing.get(
                "artifact_paths",
                [],
            ),
            artifact_path,
        }
    )

    cases = sorted(
        {
            *existing.get(
                "source_case_ids",
                [],
            ),
            source_case_id,
        }
    )

    evidence = sorted(
        {
            *existing.get(
                "quality_evidence_paths",
                [],
            ),
            *quality_paths,
        }
    )

    existing[
        "artifact_paths"
    ] = paths

    existing[
        "canonical_artifact_path"
    ] = paths[0]

    existing[
        "source_case_ids"
    ] = cases

    existing[
        "quality_evidence_paths"
    ] = evidence

    return existing, "REUSED"


def resolve_geometry_asset(
    atlas: dict[str, Any],
    *,
    geometry_id: str,
    identity_sha256: str,
) -> dict[str, Any] | None:
    """Resolve an existing geometry asset or prove it is absent."""

    root = _validate_root(
        atlas
    )

    identity_sha256 = _require_sha256(
        identity_sha256,
        "identity_sha256",
    )

    record = root[
        "geometries"
    ].get(
        geometry_id
    )

    if record is None:
        return None

    if (
        record.get(
            "identity_sha256"
        )
        != identity_sha256
    ):
        raise GeometryMeshAtlasError(
            f"{geometry_id}: geometry identity collision."
        )

    return record


def resolve_mesh_asset(
    atlas: dict[str, Any],
    *,
    mesh_id: str,
    geometry_id: str,
    identity_sha256: str,
) -> dict[str, Any] | None:
    """Resolve an existing mesh asset or prove it is absent."""

    root = _validate_root(
        atlas
    )

    identity_sha256 = _require_sha256(
        identity_sha256,
        "identity_sha256",
    )

    record = root[
        "meshes"
    ].get(
        mesh_id
    )

    if record is None:
        return None

    if (
        record.get(
            "identity_sha256"
        )
        != identity_sha256
        or record.get(
            "geometry_id"
        )
        != geometry_id
    ):
        raise GeometryMeshAtlasError(
            f"{mesh_id}: mesh identity collision."
        )

    return record
"""Admit one CLOSED governed Phase-3 wave into the Geometry/Mesh Atlas V1.

This adapter is intentionally independent of solver execution.

Admission contract:
- immutable governed-wave closure must be pinned by SHA-256;
- Trial-1 preparation index must be pinned by SHA-256;
- exact prepared-case identities must match the closed wave;
- each preparation record must be FINAL and SHA-verified;
- STEP/MSH artifacts must exist and match their recorded SHA-256;
- canonical geometry/mesh identities come from governed preparation evidence;
- existing Atlas identities are reused only through the canonical Atlas API;
- conflicting existing identities fail closed;
- case bindings are idempotent and immutable;
- no solver, calibration decision, holdout access, FEM acceptance promotion,
  or ROM dataset admission occurs here.

Default mode is DRY RUN. Use --apply only after reviewing a successful plan.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from threadrom.factory.geometry_mesh_atlas import (
    GeometryMeshAtlasError,
    load_geometry_mesh_atlas,
    persist_geometry_mesh_atlas,
    register_geometry_asset,
    register_mesh_asset,
)


ROOT = Path(r"D:\ThreadROM").resolve()

ATLAS_PATH = (
    ROOT
    / "docs"
    / "phase3_geometry_mesh_atlas"
    / "atlas.json"
)

EXPECTED_ATLAS_SCHEMA = (
    "threadrom.geometry_mesh_reuse_atlas.v1"
)

EXPECTED_PREPARATION_SCHEMA = (
    "threadrom.phase3_diversified_doe_trial1_preparation.v1"
)

EXPECTED_CLOSURE_SCHEMA = (
    "threadrom.governed_wave_closure.v1"
)

EXPECTED_CLOSURE_DISPOSITION = (
    "GOVERNED_WAVE_FULL_PHYSICS_CLOSED"
)

SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(
    path: Path,
) -> str:
    require(
        path.is_file(),
        f"Required file is missing: {path}",
    )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(
                8 * 1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def load_json(
    path: Path,
) -> dict[str, Any]:
    require(
        path.is_file(),
        f"Required JSON is missing: {path}",
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )

    require(
        isinstance(payload, dict),
        f"{path}: expected JSON object.",
    )

    return payload


def relative(
    path: Path,
) -> str:
    resolved = path.resolve()

    require(
        resolved.is_relative_to(ROOT),
        f"Path escapes repository root: {resolved}",
    )

    return resolved.relative_to(
        ROOT
    ).as_posix()


def repo_path(
    value: str,
    *,
    label: str,
) -> Path:
    require(
        isinstance(value, str)
        and value.strip(),
        f"{label}: expected non-empty relative path.",
    )

    raw = Path(value)

    require(
        not raw.is_absolute(),
        f"{label}: absolute paths are forbidden.",
    )

    resolved = (
        ROOT
        / raw
    ).resolve()

    require(
        resolved.is_relative_to(ROOT),
        f"{label}: path escapes repository root.",
    )

    return resolved


def require_sha(
    value: str,
    *,
    label: str,
) -> str:
    require(
        isinstance(value, str)
        and SHA_RE.fullmatch(
            value.lower()
        )
        is not None,
        f"{label}: invalid SHA-256.",
    )

    return value.lower()


def closure_case_identity(
    payload: dict[str, Any],
) -> dict[str, str]:
    cases = payload.get(
        "cases"
    )

    require(
        isinstance(cases, list)
        and cases,
        "Wave closure has no case list.",
    )

    result: dict[str, str] = {}

    for index, item in enumerate(
        cases,
        start=1,
    ):
        require(
            isinstance(item, dict),
            f"Closure case #{index}: expected object.",
        )

        case_id = item.get(
            "case_id"
        )
        case_hash = item.get(
            "case_hash"
        )

        require(
            isinstance(case_id, str)
            and case_id,
            f"Closure case #{index}: missing case_id.",
        )

        require_sha(
            case_hash,
            label=(
                f"{case_id} closure case_hash"
            ),
        )

        require(
            case_id not in result,
            f"Duplicate closure case ID: {case_id}",
        )

        result[
            case_id
        ] = case_hash.lower()

    return result


def preparation_case_identity(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    trials = payload.get(
        "prepared_trials"
    )

    require(
        isinstance(trials, list)
        and trials,
        "Preparation index has no prepared_trials.",
    )

    result: dict[
        str,
        dict[str, Any],
    ] = {}

    for index, item in enumerate(
        trials,
        start=1,
    ):
        require(
            isinstance(item, dict),
            f"Prepared trial #{index}: expected object.",
        )

        case_id = item.get(
            "case_id"
        )

        require(
            isinstance(case_id, str)
            and case_id,
            f"Prepared trial #{index}: missing case_id.",
        )

        require(
            case_id not in result,
            f"Duplicate prepared case ID: {case_id}",
        )

        require_sha(
            item.get(
                "case_hash"
            ),
            label=(
                f"{case_id} preparation-index case_hash"
            ),
        )

        require_sha(
            item.get(
                "preparation_record_sha256"
            ),
            label=(
                f"{case_id} preparation-record SHA"
            ),
        )

        result[
            case_id
        ] = item

    return result


def verify_artifact(
    *,
    case_id: str,
    section: dict[str, Any],
    label: str,
) -> tuple[str, str]:
    relative_path = section.get(
        "relative_path"
    )

    artifact_sha = require_sha(
        section.get(
            "sha256"
        ),
        label=(
            f"{case_id} {label} artifact SHA"
        ),
    )

    artifact = repo_path(
        relative_path,
        label=(
            f"{case_id} {label} artifact"
        ),
    )

    actual = sha256(
        artifact
    )

    require(
        actual == artifact_sha,
        (
            f"{case_id}: {label} artifact SHA drift. "
            f"recorded={artifact_sha} actual={actual}"
        ),
    )

    return (
        relative(
            artifact
        ),
        actual,
    )


def build_case_binding(
    *,
    wave_id: str,
    case_id: str,
    case_hash: str,
    preparation_record_path: str,
    preparation: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    require(
        preparation.get(
            "schema"
        )
        == EXPECTED_PREPARATION_SCHEMA,
        (
            f"{case_id}: unsupported Trial-1 preparation schema "
            f"{preparation.get('schema')!r}."
        ),
    )

    require(
        preparation.get(
            "record_status"
        )
        == "FINAL",
        f"{case_id}: Trial-1 preparation is not FINAL.",
    )

    require(
        preparation.get(
            "wave_id"
        )
        == wave_id,
        f"{case_id}: preparation wave identity drift.",
    )

    case = preparation.get(
        "case"
    )
    geometry = preparation.get(
        "geometry"
    )
    mesh = preparation.get(
        "mesh"
    )

    require(
        isinstance(case, dict),
        f"{case_id}: missing preparation case object.",
    )

    require(
        isinstance(geometry, dict),
        f"{case_id}: missing geometry evidence.",
    )

    require(
        isinstance(mesh, dict),
        f"{case_id}: missing mesh evidence.",
    )

    require(
        case.get(
            "case_id"
        )
        == case_id,
        f"{case_id}: preparation case_id drift.",
    )

    require(
        case.get(
            "case_hash"
        )
        == case_hash,
        f"{case_id}: preparation case_hash drift.",
    )

    geometry_id = geometry.get(
        "canonical_geometry_id"
    )
    geometry_identity_sha = require_sha(
        geometry.get(
            "identity_sha256"
        ),
        label=(
            f"{case_id} geometry identity SHA"
        ),
    )

    mesh_id = mesh.get(
        "canonical_mesh_id"
    )
    mesh_identity_sha = require_sha(
        mesh.get(
            "identity_sha256"
        ),
        label=(
            f"{case_id} mesh identity SHA"
        ),
    )

    classification_id = mesh.get(
        "canonical_classification_id"
    )
    classification_sha = require_sha(
        mesh.get(
            "classification_sha256"
        ),
        label=(
            f"{case_id} classification SHA"
        ),
    )

    require(
        isinstance(geometry_id, str)
        and geometry_id.startswith(
            "joint-geometry-"
        ),
        f"{case_id}: invalid canonical geometry ID.",
    )

    require(
        isinstance(mesh_id, str)
        and mesh_id.startswith(
            "mesh-"
        ),
        f"{case_id}: invalid canonical mesh ID.",
    )

    require(
        isinstance(classification_id, str)
        and classification_id,
        f"{case_id}: invalid classification ID.",
    )

    geometry_path, geometry_sha = (
        verify_artifact(
            case_id=case_id,
            section=geometry,
            label="geometry",
        )
    )

    mesh_path, mesh_sha = (
        verify_artifact(
            case_id=case_id,
            section=mesh,
            label="mesh",
        )
    )

    geometry_mode = geometry.get(
        "mode"
    )
    mesh_mode = mesh.get(
        "mode"
    )

    require(
        isinstance(geometry_mode, str)
        and geometry_mode,
        f"{case_id}: missing geometry mode.",
    )

    require(
        isinstance(mesh_mode, str)
        and mesh_mode,
        f"{case_id}: missing mesh mode.",
    )

    geometry_registration = {
        "geometry_id": geometry_id,
        "identity_sha256": (
            geometry_identity_sha
        ),
        "generation_id": (
            "threadrom_parametric_complete_joint_v1"
        ),
        "artifact_path": geometry_path,
        "artifact_sha256": geometry_sha,
        "source_case_id": case_id,
    }

    mesh_registration = {
        "mesh_id": mesh_id,
        "geometry_id": geometry_id,
        "identity_sha256": (
            mesh_identity_sha
        ),
        "generation_id": (
            "threadrom_grouped_gmsh_complete_joint_v1"
        ),
        "artifact_path": mesh_path,
        "artifact_sha256": mesh_sha,
        "source_case_id": case_id,
        "quality_evidence_path": None,
    }

    binding = {
        "wave_id": wave_id,
        "case_hash": case_hash,
        "classification_id": (
            classification_id
        ),
        "classification_sha256": (
            classification_sha
        ),
        "geometry_artifact_sha256": (
            geometry_sha
        ),
        "geometry_canonical_artifact": (
            geometry_path
        ),
        "geometry_id": geometry_id,
        "geometry_identity_sha256": (
            geometry_identity_sha
        ),
        "geometry_mode": geometry_mode,
        "mesh_artifact_sha256": mesh_sha,
        "mesh_canonical_artifact": mesh_path,
        "mesh_id": mesh_id,
        "mesh_identity_sha256": (
            mesh_identity_sha
        ),
        "mesh_mode": mesh_mode,
        "preparation_record": (
            preparation_record_path
        ),
    }

    return (
        geometry_registration,
        mesh_registration,
        binding,
    )



def _step_kernel_signature(
    artifact_path: Path,
) -> tuple[
    tuple[
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        float,
        int,
        int,
        int,
    ],
    ...,
]:
    """
    Return a deterministic CAD-kernel signature for a STEP realization.

    Raw STEP SHA-256 remains evidence for the individual preparation
    realization. This signature is used only when two preparations carry
    the same canonical geometry identity but Open CASCADE serialization
    bytes differ.
    """
    try:
        import cadquery as cq
    except ImportError as exc:
        raise RuntimeError(
            "CadQuery is required to certify equivalent STEP "
            "serialization before canonical geometry reuse."
        ) from exc

    model = cq.importers.importStep(
        str(artifact_path)
    )

    solids = model.solids().vals()

    require(
        bool(solids),
        (
            "STEP equivalence certification found no solids: "
            f"{artifact_path}"
        ),
    )

    rows = []

    for solid in solids:
        box = solid.BoundingBox()

        rows.append(
            (
                float(solid.Volume()),
                float(solid.Area()),
                float(box.xmin),
                float(box.ymin),
                float(box.zmin),
                float(box.xmax),
                float(box.ymax),
                float(box.zmax),
                len(solid.Edges()),
                len(solid.Faces()),
                len(solid.Vertices()),
            )
        )

    rows.sort(
        key=lambda row: (
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            row[6],
            row[7],
            row[8],
            row[9],
            row[10],
        )
    )

    return tuple(rows)


def _require_kernel_equivalent_step(
    *,
    canonical_path: str,
    candidate_path: str,
    geometry_id: str,
) -> None:
    canonical = repo_path(
        canonical_path,
        label=(
            f"{geometry_id} canonical geometry artifact"
        ),
    )

    candidate = repo_path(
        candidate_path,
        label=(
            f"{geometry_id} candidate geometry artifact"
        ),
    )

    canonical_signature = (
        _step_kernel_signature(
            canonical
        )
    )

    candidate_signature = (
        _step_kernel_signature(
            candidate
        )
    )

    require(
        len(canonical_signature)
        == len(candidate_signature),
        (
            f"{geometry_id}: STEP solid-count mismatch "
            "under one canonical geometry identity."
        ),
    )

    scalar_count = 8

    for solid_index, (
        canonical_solid,
        candidate_solid,
    ) in enumerate(
        zip(
            canonical_signature,
            candidate_signature,
            strict=True,
        ),
        start=1,
    ):
        for scalar_index in range(
            scalar_count
        ):
            left = canonical_solid[
                scalar_index
            ]

            right = candidate_solid[
                scalar_index
            ]

            scale = max(
                1.0,
                abs(left),
                abs(right),
            )

            require(
                abs(left - right)
                <= 1.0e-10 * scale,
                (
                    f"{geometry_id}: STEP kernel geometry "
                    f"differs at solid {solid_index}, "
                    f"scalar {scalar_index}."
                ),
            )

        require(
            canonical_solid[
                scalar_count:
            ]
            == candidate_solid[
                scalar_count:
            ],
            (
                f"{geometry_id}: STEP kernel topology differs "
                f"at solid {solid_index}."
            ),
        )


def register_geometry_realization(
    atlas: dict[str, Any],
    *,
    registration: dict[str, Any],
) -> tuple[
    dict[str, Any],
    str,
]:
    """
    Register one governed geometry realization.

    Canonical geometry identity is semantic. Raw STEP bytes are a
    realization-level property and may differ because of exporter
    serialization metadata.

    A differing STEP SHA is reusable only when:
      - the full canonical geometry identity SHA matches;
      - the generation implementation ID matches;
      - CAD-kernel geometry and topology are equivalent.

    The first registered realization remains the canonical Atlas
    artifact. The later preparation record remains immutable provenance
    for its original STEP path and SHA.
    """
    try:
        return register_geometry_asset(
            atlas,
            **registration,
        )

    except GeometryMeshAtlasError as exc:
        expected_message = (
            f"{registration['geometry_id']}: "
            "existing geometry asset conflicts "
            "on artifact_sha256."
        )

        if str(exc) != expected_message:
            raise

        geometry_id = registration[
            "geometry_id"
        ]

        existing = atlas[
            "geometries"
        ].get(
            geometry_id
        )

        require(
            isinstance(existing, dict),
            (
                f"{geometry_id}: conflicting geometry "
                "record disappeared."
            ),
        )

        require(
            existing.get(
                "identity_sha256"
            )
            == registration[
                "identity_sha256"
            ],
            (
                f"{geometry_id}: identity SHA mismatch "
                "cannot be treated as serialization reuse."
            ),
        )

        require(
            existing.get(
                "generation_id"
            )
            == registration[
                "generation_id"
            ],
            (
                f"{geometry_id}: generation implementation "
                "mismatch cannot be treated as serialization reuse."
            ),
        )

        _require_kernel_equivalent_step(
            canonical_path=existing[
                "canonical_artifact_path"
            ],
            candidate_path=registration[
                "artifact_path"
            ],
            geometry_id=geometry_id,
        )

        source_case_ids = sorted(
            {
                *existing.get(
                    "source_case_ids",
                    [],
                ),
                registration[
                    "source_case_id"
                ],
            }
        )

        existing[
            "source_case_ids"
        ] = source_case_ids

        return (
            existing,
            "REUSED_EQUIVALENT_SERIALIZATION",
        )

def plan(
    *,
    wave_id: str,
    preparation_index_path: Path,
    closure_path: Path,
    expected_preparation_sha: str,
    expected_closure_sha: str,
    expected_case_count: int | None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
]:
    expected_preparation_sha = require_sha(
        expected_preparation_sha,
        label="Expected preparation-index SHA",
    )

    expected_closure_sha = require_sha(
        expected_closure_sha,
        label="Expected closure SHA",
    )

    actual_preparation_sha = sha256(
        preparation_index_path
    )
    actual_closure_sha = sha256(
        closure_path
    )

    require(
        actual_preparation_sha
        == expected_preparation_sha,
        (
            "Preparation-index SHA mismatch. "
            f"expected={expected_preparation_sha} "
            f"actual={actual_preparation_sha}"
        ),
    )

    require(
        actual_closure_sha
        == expected_closure_sha,
        (
            "Wave-closure SHA mismatch. "
            f"expected={expected_closure_sha} "
            f"actual={actual_closure_sha}"
        ),
    )

    closure = load_json(
        closure_path
    )
    preparation_index = load_json(
        preparation_index_path
    )

    require(
        closure.get(
            "schema"
        )
        == EXPECTED_CLOSURE_SCHEMA,
        (
            "Unsupported governed-wave closure schema: "
            f"{closure.get('schema')!r}"
        ),
    )

    closure_status = closure.get(
        "record_status",
        closure.get(
            "status"
        ),
    )

    require(
        closure_status == "FINAL",
        (
            "Wave closure is not FINAL: "
            f"{closure_status!r}"
        ),
    )

    require(
        closure.get(
            "disposition"
        )
        == EXPECTED_CLOSURE_DISPOSITION,
        (
            "Wave closure does not prove full-physics closure: "
            f"{closure.get('disposition')!r}"
        ),
    )

    require(
        closure.get(
            "wave_id"
        )
        == wave_id,
        "Wave-closure identity drift.",
    )

    require(
        preparation_index.get(
            "wave_id"
        )
        == wave_id,
        "Preparation-index wave identity drift.",
    )

    require(
        preparation_index.get(
            "record_status"
        )
        == "FINAL",
        "Preparation index is not FINAL.",
    )

    require(
        preparation_index.get(
            "holdouts_accessed"
        )
        is False,
        "Preparation index reports holdout access.",
    )

    closure_cases = (
        closure_case_identity(
            closure
        )
    )

    prepared_cases = (
        preparation_case_identity(
            preparation_index
        )
    )

    require(
        set(
            closure_cases
        )
        == set(
            prepared_cases
        ),
        (
            "Closed-wave cohort differs from prepared cohort. "
            f"closure_only={sorted(set(closure_cases) - set(prepared_cases))} "
            f"preparation_only={sorted(set(prepared_cases) - set(closure_cases))}"
        ),
    )

    if expected_case_count is not None:
        require(
            len(
                closure_cases
            )
            == expected_case_count,
            (
                "Unexpected governed case count. "
                f"expected={expected_case_count} "
                f"actual={len(closure_cases)}"
            ),
        )

    for case_id in sorted(
        closure_cases
    ):
        prepared_hash = (
            prepared_cases[
                case_id
            ][
                "case_hash"
            ].lower()
        )

        require(
            prepared_hash
            == closure_cases[
                case_id
            ],
            f"{case_id}: closure/preparation case_hash drift.",
        )

    atlas = load_geometry_mesh_atlas(
        ATLAS_PATH
    )

    require(
        atlas.get(
            "schema"
        )
        == EXPECTED_ATLAS_SCHEMA,
        (
            "Unexpected Geometry/Mesh Atlas schema: "
            f"{atlas.get('schema')!r}"
        ),
    )

    planned = copy.deepcopy(
        atlas
    )

    before = {
        "case_bindings": len(
            planned[
                "case_bindings"
            ]
        ),
        "geometries": len(
            planned[
                "geometries"
            ]
        ),
        "meshes": len(
            planned[
                "meshes"
            ]
        ),
    }

    geometry_statuses: dict[
        str,
        str,
    ] = {}

    mesh_statuses: dict[
        str,
        str,
    ] = {}

    binding_statuses: dict[
        str,
        str,
    ] = {}

    for case_id in sorted(
        prepared_cases
    ):
        index_item = (
            prepared_cases[
                case_id
            ]
        )

        preparation_record_path = (
            repo_path(
                index_item[
                    "preparation_record"
                ],
                label=(
                    f"{case_id} preparation record"
                ),
            )
        )

        preparation_sha = sha256(
            preparation_record_path
        )

        require(
            preparation_sha
            == index_item[
                "preparation_record_sha256"
            ].lower(),
            (
                f"{case_id}: preparation-record SHA drift. "
                f"recorded={index_item['preparation_record_sha256']} "
                f"actual={preparation_sha}"
            ),
        )

        preparation = load_json(
            preparation_record_path
        )

        (
            geometry_registration,
            mesh_registration,
            binding,
        ) = build_case_binding(
            wave_id=wave_id,
            case_id=case_id,
            case_hash=(
                closure_cases[
                    case_id
                ]
            ),
            preparation_record_path=relative(
                preparation_record_path
            ),
            preparation=preparation,
        )

        (
            geometry_record,
            geometry_status,
        ) = register_geometry_realization(
            planned,
            registration=geometry_registration,
        )

        # Case bindings reference the canonical Atlas realization.
        # The immutable preparation record still preserves the
        # case-specific generated STEP path and raw SHA-256.
        binding[
            "geometry_artifact_sha256"
        ] = geometry_record[
            "artifact_sha256"
        ]

        binding[
            "geometry_canonical_artifact"
        ] = geometry_record[
            "canonical_artifact_path"
        ]

        _, mesh_status = (
            register_mesh_asset(
                planned,
                **mesh_registration,
            )
        )

        existing_binding = (
            planned[
                "case_bindings"
            ].get(
                case_id
            )
        )

        if existing_binding is None:
            planned[
                "case_bindings"
            ][
                case_id
            ] = binding

            binding_status = (
                "REGISTERED"
            )

        else:
            require(
                existing_binding
                == binding,
                (
                    f"{case_id}: conflicting Atlas "
                    "case binding already exists."
                ),
            )

            binding_status = (
                "REUSED"
            )

        geometry_statuses[
            case_id
        ] = geometry_status

        mesh_statuses[
            case_id
        ] = mesh_status

        binding_statuses[
            case_id
        ] = binding_status

    source_evidence = planned.setdefault(
        "source_evidence",
        {},
    )

    require(
        isinstance(
            source_evidence,
            dict,
        ),
        "Atlas source_evidence is not an object.",
    )

    wave_evidence = {
        "preparation_index_path": relative(
            preparation_index_path
        ),
        "preparation_index_sha256": (
            actual_preparation_sha
        ),
        "wave_closure_path": relative(
            closure_path
        ),
        "wave_closure_sha256": (
            actual_closure_sha
        ),
    }

    existing_wave_evidence = (
        source_evidence.get(
            wave_id
        )
    )

    if existing_wave_evidence is None:
        source_evidence[
            wave_id
        ] = wave_evidence

        source_evidence_status = (
            "REGISTERED"
        )

    else:
        require(
            existing_wave_evidence
            == wave_evidence,
            (
                f"{wave_id}: conflicting Atlas "
                "source-evidence binding exists."
            ),
        )

        source_evidence_status = (
            "REUSED"
        )

    after = {
        "case_bindings": len(
            planned[
                "case_bindings"
            ]
        ),
        "geometries": len(
            planned[
                "geometries"
            ]
        ),
        "meshes": len(
            planned[
                "meshes"
            ]
        ),
    }

    report = {
        "wave_id": wave_id,
        "preparation_index_sha256": (
            actual_preparation_sha
        ),
        "wave_closure_sha256": (
            actual_closure_sha
        ),
        "case_count": len(
            prepared_cases
        ),
        "before": before,
        "after": after,
        "geometry_statuses": (
            geometry_statuses
        ),
        "mesh_statuses": (
            mesh_statuses
        ),
        "binding_statuses": (
            binding_statuses
        ),
        "source_evidence_status": (
            source_evidence_status
        ),
    }

    return (
        planned,
        report,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--wave-id",
        required=True,
    )

    parser.add_argument(
        "--preparation-index",
        required=True,
    )

    parser.add_argument(
        "--wave-closure",
        required=True,
    )

    parser.add_argument(
        "--expected-preparation-sha",
        required=True,
    )

    parser.add_argument(
        "--expected-closure-sha",
        required=True,
    )

    parser.add_argument(
        "--expected-case-count",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Persist the planned Atlas. "
            "Without this flag the command is read-only."
        ),
    )

    args = parser.parse_args()

    preparation_index_path = (
        repo_path(
            args.preparation_index,
            label="Preparation index",
        )
    )

    closure_path = repo_path(
        args.wave_closure,
        label="Wave closure",
    )

    atlas_before_sha = sha256(
        ATLAS_PATH
    )

    planned, report = plan(
        wave_id=args.wave_id,
        preparation_index_path=(
            preparation_index_path
        ),
        closure_path=closure_path,
        expected_preparation_sha=(
            args.expected_preparation_sha
        ),
        expected_closure_sha=(
            args.expected_closure_sha
        ),
        expected_case_count=(
            args.expected_case_count
        ),
    )

    print()
    print("=" * 108)
    print(
        "THREADROM - GOVERNED WAVE "
        "GEOMETRY/MESH ATLAS ADMISSION V1"
    )
    print("=" * 108)

    print(
        "Mode                  :",
        (
            "APPLY"
            if args.apply
            else "DRY_RUN"
        ),
    )
    print(
        "Wave                  :",
        report["wave_id"],
    )
    print(
        "Preparation SHA       :",
        report[
            "preparation_index_sha256"
        ],
    )
    print(
        "Closure SHA           :",
        report[
            "wave_closure_sha256"
        ],
    )
    print(
        "Atlas before SHA      :",
        atlas_before_sha,
    )
    print(
        "Governed cases        :",
        report["case_count"],
    )

    print()
    print(
        "Before                :",
        report["before"],
    )
    print(
        "Planned after         :",
        report["after"],
    )

    print()
    print("Per-case admission:")

    for case_id in sorted(
        report[
            "binding_statuses"
        ]
    ):
        print(
            f"  {case_id}"
        )
        print(
            "    geometry :",
            report[
                "geometry_statuses"
            ][
                case_id
            ],
        )
        print(
            "    mesh     :",
            report[
                "mesh_statuses"
            ][
                case_id
            ],
        )
        print(
            "    binding  :",
            report[
                "binding_statuses"
            ][
                case_id
            ],
        )

    print()
    print(
        "Wave source evidence  :",
        report[
            "source_evidence_status"
        ],
    )

    if not args.apply:
        atlas_after_sha = sha256(
            ATLAS_PATH
        )

        require(
            atlas_after_sha
            == atlas_before_sha,
            "DRY RUN mutated the Atlas.",
        )

        print(
            "Atlas after SHA       :",
            atlas_after_sha,
        )
        print(
            "Atlas persisted       : NO",
        )
        print(
            "Disposition           : "
            "VALIDATED_ADMISSION_PLAN_ONLY"
        )

        print("=" * 108)
        return

    persist_geometry_mesh_atlas(
        ATLAS_PATH,
        planned,
    )

    recovered = (
        load_geometry_mesh_atlas(
            ATLAS_PATH
        )
    )

    require(
        recovered == planned,
        "Persisted Atlas replay differs from planned Atlas.",
    )

    atlas_after_sha = sha256(
        ATLAS_PATH
    )

    print(
        "Atlas after SHA       :",
        atlas_after_sha,
    )
    print(
        "Atlas persisted       : YES",
    )
    print(
        "Disposition           : "
        "GOVERNED_WAVE_GEOMETRY_MESH_ADMITTED"
    )
    print("=" * 108)


if __name__ == "__main__":
    main()
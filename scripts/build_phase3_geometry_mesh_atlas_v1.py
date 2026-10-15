"""Build/audit ThreadROM Phase-3 Geometry/Mesh Atlas V1.

The builder reconstructs canonical identities from governed case definitions
and generation recipes. Existing STEP/MSH files are verified by SHA-256 and
registered; no geometry, mesh, solver deck, or FEM job is generated here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tomllib

from pathlib import Path

from threadrom.case.resolver import resolve_case
from threadrom.factory.diversified_doe_design import (
    _build_case,
)
from threadrom.factory.geometry_mesh_atlas import (
    load_geometry_mesh_atlas,
    new_geometry_mesh_atlas,
    persist_geometry_mesh_atlas,
    register_geometry_asset,
    register_mesh_asset,
)
from threadrom.factory.geometry_mesh_reuse import (
    GEOMETRY_GENERATION_ID,
    MESH_GENERATION_ID,
    derive_geometry_mesh_reuse_identity,
)
from threadrom.materials.diversified_candidate_catalog import (
    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
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


ROOT = Path(r"D:\ThreadROM").resolve()

CONFIG = ROOT / "config"

DOE_ROOT = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
)

CAMPAIGN_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / "TRM-DDOE-001"
)

OUTPUT_ROOT = (
    ROOT
    / "docs"
    / "phase3_geometry_mesh_atlas"
)

ATLAS_PATH = (
    OUTPUT_ROOT
    / "atlas.json"
)

CLOSURE_PATH = (
    OUTPUT_ROOT
    / "slice1_closure.json"
)

ACCEPTED_FEM_ATLAS = (
    ROOT
    / "docs"
    / "phase3_fem_atlas"
    / "atlas.json"
)

EXPECTED_ACCEPTED_FEM_ATLAS_SHA256 = (
    "eed5e52f4e9baaad5e2eb89634de48bb"
    "df53c14c584921d8afb0df00631ffc60"
)

POLICY_PATH = (
    CONFIG
    / "phase3_diversified_doe.toml"
)

PROPOSAL_PATH = (
    DOE_ROOT
    / "design_proposal.json"
)

WAVES = (
    {
        "wave_id": "TRM-DDOE-001-W01",
        "preparation_index": (
            CAMPAIGN_ROOT
            / "W01"
            / "w01_trial1_preparation.json"
        ),
        "nut_policy": (
            CAMPAIGN_ROOT
            / "W01"
            / "w01_targeted_nut_mesh_levels.toml"
        ),
    },
    {
        "wave_id": "TRM-DDOE-001-W02",
        "preparation_index": (
            CAMPAIGN_ROOT
            / "W02"
            / "w02_trial1_preparation.json"
        ),
        "nut_policy": (
            CAMPAIGN_ROOT
            / "W02"
            / "w02_targeted_nut_mesh_levels.toml"
        ),
    },
)


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(
            message
        )


def sha256(
    path: Path,
) -> str:
    require(
        path.is_file(),
        f"Required file missing: {path}",
    )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def relative(
    path: Path,
) -> str:
    return (
        path.resolve()
        .relative_to(ROOT)
        .as_posix()
    )


def load_json(
    path: Path,
):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def write_json(
    path: Path,
    payload: dict,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    encoded = (
        json.dumps(
            payload,
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


def artifact_binding(
    section: dict,
    *,
    label: str,
) -> tuple[Path, str]:
    require(
        isinstance(
            section,
            dict,
        ),
        f"{label}: missing artifact section.",
    )

    path_text = section.get(
        "relative_path"
    )

    expected_sha = section.get(
        "sha256"
    )

    require(
        isinstance(
            path_text,
            str,
        )
        and path_text,
        f"{label}: missing relative_path.",
    )

    require(
        isinstance(
            expected_sha,
            str,
        )
        and len(expected_sha) == 64,
        f"{label}: malformed SHA-256.",
    )

    path = (
        ROOT
        / path_text
    )

    require(
        path.is_file()
        and path.stat().st_size > 0,
        f"{label}: artifact missing or empty.",
    )

    actual_sha = sha256(
        path
    )

    require(
        actual_sha
        == expected_sha.lower(),
        f"{label}: artifact SHA-256 drift.",
    )

    return (
        path,
        actual_sha,
    )


def source_evidence() -> dict:
    result = {
        "design_policy": {
            "path": relative(
                POLICY_PATH
            ),
            "sha256": sha256(
                POLICY_PATH
            ),
        },
        "design_proposal": {
            "path": relative(
                PROPOSAL_PATH
            ),
            "sha256": sha256(
                PROPOSAL_PATH
            ),
        },
        "accepted_fem_atlas_guard": {
            "path": relative(
                ACCEPTED_FEM_ATLAS
            ),
            "sha256": sha256(
                ACCEPTED_FEM_ATLAS
            ),
        },
    }

    for wave in WAVES:
        key = wave[
            "wave_id"
        ]

        result[key] = {
            "preparation_index_path": (
                relative(
                    wave[
                        "preparation_index"
                    ]
                )
            ),
            "preparation_index_sha256": (
                sha256(
                    wave[
                        "preparation_index"
                    ]
                )
            ),
            "nut_mesh_policy_path": (
                relative(
                    wave[
                        "nut_policy"
                    ]
                )
            ),
            "nut_mesh_policy_sha256": (
                sha256(
                    wave[
                        "nut_policy"
                    ]
                )
            ),
        }

    return result


def build_expected_atlas() -> dict:
    accepted_sha = sha256(
        ACCEPTED_FEM_ATLAS
    )

    require(
        accepted_sha
        == EXPECTED_ACCEPTED_FEM_ATLAS_SHA256,
        "Frozen accepted-FEM atlas SHA drift.",
    )

    policy = tomllib.loads(
        POLICY_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    proposal = load_json(
        PROPOSAL_PATH
    )

    proposal_by_id = {
        row["proposal_id"]: row
        for row in proposal[
            "cases"
        ]
    }

    mesh_template = (
        load_complete_joint_mesh_definition(
            CONFIG
            / "complete_joint_mesh.toml"
        )
    )

    joint_classification = (
        load_complete_joint_surface_definition(
            CONFIG
            / (
                "complete_joint_"
                "surface_classification.toml"
            )
        )
    )

    bolt_classification = (
        load_surface_classification_definition(
            CONFIG
            / "surface_classification.toml"
        )
    )

    nut_classification = (
        load_nut_surface_classification_definition(
            CONFIG
            / "nut_surface_classification.toml"
        )
    )

    bolt_policy = (
        load_mesh_level_policy(
            CONFIG
            / mesh_template.bolt_mesh_level_policy
        )
    )

    atlas = (
        new_geometry_mesh_atlas()
    )

    atlas[
        "scope"
    ] = (
        "ThreadROM Phase-3 governed geometry/mesh "
        "reuse foundation for prospective W03+ execution."
    )

    atlas[
        "identity_contract"
    ] = {
        "geometry_generation_id": (
            GEOMETRY_GENERATION_ID
        ),
        "mesh_generation_id": (
            MESH_GENERATION_ID
        ),
        "geometry_identity_basis": (
            "joint_geometry_bundle_sha256"
        ),
        "mesh_identity_basis": (
            "mesh_generation_sha256"
        ),
        "material_and_load_excluded_from_geometry_identity": True,
        "run_and_case_labels_excluded_from_mesh_identity": True,
    }

    atlas[
        "source_evidence"
    ] = source_evidence()

    atlas[
        "case_bindings"
    ] = {}

    for wave in WAVES:
        wave_id = wave[
            "wave_id"
        ]

        preparation = load_json(
            wave[
                "preparation_index"
            ]
        )

        require(
            preparation[
                "wave_id"
            ]
            == wave_id,
            f"{wave_id}: preparation-index identity drift.",
        )

        prepared_rows = preparation[
            "prepared_trials"
        ]

        require(
            len(
                prepared_rows
            )
            == 4,
            f"{wave_id}: expected exactly four prepared cases.",
        )

        nut_policy = (
            load_mesh_level_policy(
                wave[
                    "nut_policy"
                ]
            )
        )

        for prepared in prepared_rows:
            case_id = prepared[
                "case_id"
            ]

            proposal_row = (
                proposal_by_id.get(
                    case_id
                )
            )

            require(
                proposal_row
                is not None,
                f"{case_id}: proposal row missing.",
            )

            require(
                prepared[
                    "case_hash"
                ]
                == proposal_row[
                    "case_hash"
                ],
                f"{case_id}: case-hash drift.",
            )

            size = next(
                row
                for row in policy[
                    "size_candidates"
                ]
                if row[
                    "designation"
                ]
                == proposal_row[
                    "thread_designation"
                ]
            )

            case, _ = _build_case(
                policy,
                size,
                proposal_row[
                    "member_material_id"
                ],
                tuple(
                    proposal_row[
                        "normalized_coordinates"
                    ]
                ),
            )

            resolved = resolve_case(
                case,
                material_catalog=(
                    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG
                ),
            )

            require(
                resolved.case_hash
                == proposal_row[
                    "case_hash"
                ],
                f"{case_id}: deterministic case reconstruction drift.",
            )

            identity = (
                derive_geometry_mesh_reuse_identity(
                    resolved,
                    mesh_template=(
                        mesh_template
                    ),
                    joint_classification_template=(
                        joint_classification
                    ),
                    bolt_classification_template=(
                        bolt_classification
                    ),
                    nut_classification_template=(
                        nut_classification
                    ),
                    bolt_mesh_level_policy=(
                        bolt_policy
                    ),
                    nut_mesh_level_policy=(
                        nut_policy
                    ),
                    local_refinement_policy=None,
                )
            )

            prep_record_path = (
                ROOT
                / prepared[
                    "preparation_record"
                ]
            )

            require(
                sha256(
                    prep_record_path
                )
                == prepared[
                    "preparation_record_sha256"
                ],
                f"{case_id}: immutable preparation-record SHA drift.",
            )

            prep_record = load_json(
                prep_record_path
            )

            prep_case = prep_record[
                "case"
            ]

            require(
                prep_case[
                    "case_id"
                ]
                == case_id
                and prep_case[
                    "case_hash"
                ]
                == resolved.case_hash,
                f"{case_id}: preparation-record case identity drift.",
            )

            geometry_section = (
                prep_record[
                    "geometry"
                ]
            )

            mesh_section = (
                prep_record[
                    "mesh"
                ]
            )

            (
                step_path,
                step_sha,
            ) = artifact_binding(
                geometry_section,
                label=(
                    f"{case_id} STEP"
                ),
            )

            (
                msh_path,
                msh_sha,
            ) = artifact_binding(
                mesh_section,
                label=(
                    f"{case_id} MSH"
                ),
            )

            geometry_record, _ = (
                register_geometry_asset(
                    atlas,
                    geometry_id=(
                        identity.geometry_id
                    ),
                    identity_sha256=(
                        identity.geometry_identity_sha256
                    ),
                    generation_id=(
                        GEOMETRY_GENERATION_ID
                    ),
                    artifact_path=(
                        relative(
                            step_path
                        )
                    ),
                    artifact_sha256=(
                        step_sha
                    ),
                    source_case_id=(
                        case_id
                    ),
                )
            )

            geometry_source = (
                geometry_section.get(
                    "source_case_id"
                )
            )

            if (
                isinstance(
                    geometry_source,
                    str,
                )
                and geometry_source
            ):
                register_geometry_asset(
                    atlas,
                    geometry_id=(
                        identity.geometry_id
                    ),
                    identity_sha256=(
                        identity.geometry_identity_sha256
                    ),
                    generation_id=(
                        GEOMETRY_GENERATION_ID
                    ),
                    artifact_path=(
                        relative(
                            step_path
                        )
                    ),
                    artifact_sha256=(
                        step_sha
                    ),
                    source_case_id=(
                        geometry_source
                    ),
                )

            mesh_record, _ = (
                register_mesh_asset(
                    atlas,
                    mesh_id=(
                        identity.mesh_id
                    ),
                    geometry_id=(
                        identity.geometry_id
                    ),
                    identity_sha256=(
                        identity.mesh_identity_sha256
                    ),
                    generation_id=(
                        MESH_GENERATION_ID
                    ),
                    artifact_path=(
                        relative(
                            msh_path
                        )
                    ),
                    artifact_sha256=(
                        msh_sha
                    ),
                    source_case_id=(
                        case_id
                    ),
                )
            )

            mesh_source = (
                mesh_section.get(
                    "source_case_id"
                )
            )

            if (
                isinstance(
                    mesh_source,
                    str,
                )
                and mesh_source
            ):
                register_mesh_asset(
                    atlas,
                    mesh_id=(
                        identity.mesh_id
                    ),
                    geometry_id=(
                        identity.geometry_id
                    ),
                    identity_sha256=(
                        identity.mesh_identity_sha256
                    ),
                    generation_id=(
                        MESH_GENERATION_ID
                    ),
                    artifact_path=(
                        relative(
                            msh_path
                        )
                    ),
                    artifact_sha256=(
                        msh_sha
                    ),
                    source_case_id=(
                        mesh_source
                    ),
                )

            atlas[
                "case_bindings"
            ][
                case_id
            ] = {
                "wave_id": wave_id,
                "case_hash": (
                    resolved.case_hash
                ),
                "geometry_id": (
                    identity.geometry_id
                ),
                "geometry_identity_sha256": (
                    identity.geometry_identity_sha256
                ),
                "classification_id": (
                    identity.classification_id
                ),
                "classification_sha256": (
                    identity.classification_sha256
                ),
                "mesh_id": (
                    identity.mesh_id
                ),
                "mesh_identity_sha256": (
                    identity.mesh_identity_sha256
                ),
                "geometry_artifact_sha256": (
                    step_sha
                ),
                "mesh_artifact_sha256": (
                    msh_sha
                ),
                "geometry_mode": (
                    geometry_section[
                        "mode"
                    ]
                ),
                "mesh_mode": (
                    mesh_section[
                        "mode"
                    ]
                ),
                "geometry_canonical_artifact": (
                    geometry_record[
                        "canonical_artifact_path"
                    ]
                ),
                "mesh_canonical_artifact": (
                    mesh_record[
                        "canonical_artifact_path"
                    ]
                ),
                "preparation_record": (
                    relative(
                        prep_record_path
                    )
                ),
            }

    require(
        len(
            atlas[
                "case_bindings"
            ]
        )
        == 8,
        "Expected exactly eight W01/W02 case bindings.",
    )

    return atlas


def closure_payload(
    atlas_sha: str,
    atlas: dict,
) -> dict:
    return {
        "schema": (
            "threadrom.pre_w03_"
            "geometry_mesh_atlas_slice1_closure.v1"
        ),
        "record_status": "FINAL",
        "scope": (
            "PRE_W03_HARDENING_SLICE_1"
        ),
        "overall_disposition": (
            "SLICE_1_GEOMETRY_MESH_ATLAS_V1_CLOSED"
        ),
        "atlas": {
            "path": relative(
                ATLAS_PATH
            ),
            "sha256": atlas_sha,
            "case_binding_count": len(
                atlas[
                    "case_bindings"
                ]
            ),
            "distinct_geometry_count": len(
                atlas[
                    "geometries"
                ]
            ),
            "distinct_mesh_count": len(
                atlas[
                    "meshes"
                ]
            ),
        },
        "source_evidence": (
            source_evidence()
        ),
        "governance": {
            "canonical_identity_reconstruction": True,
            "existing_artifact_sha_verification": True,
            "future_reuse_lookup_api_available": True,
            "new_geometry_generated": False,
            "new_mesh_generated": False,
            "fem_executed": False,
            "holdouts_accessed": False,
            "rom_dataset_admission_authorized": False,
            "w03_execution_authorized": False,
        },
        "scope_boundary": (
            "Slice 1 establishes deterministic geometry/mesh "
            "identity, persistent reusable-artifact lookup, and "
            "W01/W02 governed backfill. It does not launch W03, "
            "admit ROM data, access holdouts, or authorize FEM."
        ),
    }


def validate_persisted_artifacts(
    atlas: dict,
) -> None:
    for record in atlas[
        "geometries"
    ].values():
        artifact = (
            ROOT
            / record[
                "canonical_artifact_path"
            ]
        )

        require(
            sha256(
                artifact
            )
            == record[
                "artifact_sha256"
            ],
            (
                f"{record['geometry_id']}: "
                "canonical STEP artifact drift."
            ),
        )

    for record in atlas[
        "meshes"
    ].values():
        artifact = (
            ROOT
            / record[
                "canonical_artifact_path"
            ]
        )

        require(
            sha256(
                artifact
            )
            == record[
                "artifact_sha256"
            ],
            (
                f"{record['mesh_id']}: "
                "canonical MSH artifact drift."
            ),
        )


def write_mode() -> None:
    atlas = build_expected_atlas()

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    persist_geometry_mesh_atlas(
        ATLAS_PATH,
        atlas,
    )

    atlas_sha = sha256(
        ATLAS_PATH
    )

    closure = closure_payload(
        atlas_sha,
        atlas,
    )

    write_json(
        CLOSURE_PATH,
        closure,
    )

    validate_persisted_artifacts(
        atlas
    )

    print()
    print("=" * 110)
    print("THREADROM — GEOMETRY / MESH ATLAS V1 WRITTEN")
    print("=" * 110)
    print(
        "Case bindings       :",
        len(
            atlas[
                "case_bindings"
            ]
        ),
    )
    print(
        "Distinct geometries :",
        len(
            atlas[
                "geometries"
            ]
        ),
    )
    print(
        "Distinct meshes     :",
        len(
            atlas[
                "meshes"
            ]
        ),
    )
    print(
        "Atlas SHA-256       :",
        atlas_sha,
    )
    print(
        "Closure SHA-256     :",
        sha256(
            CLOSURE_PATH
        ),
    )
    print("CAD generated       : NO")
    print("Mesh generated      : NO")
    print("FEM launched        : NO")
    print("=" * 110)


def audit_mode() -> None:
    require(
        ATLAS_PATH.is_file(),
        "Persistent geometry/mesh atlas missing.",
    )

    require(
        CLOSURE_PATH.is_file(),
        "Slice-1 closure certificate missing.",
    )

    persisted = (
        load_geometry_mesh_atlas(
            ATLAS_PATH
        )
    )

    expected = (
        build_expected_atlas()
    )

    require(
        persisted == expected,
        (
            "Persisted Geometry/Mesh Atlas differs "
            "from deterministic reconstruction."
        ),
    )

    validate_persisted_artifacts(
        persisted
    )

    atlas_sha = sha256(
        ATLAS_PATH
    )

    closure = load_json(
        CLOSURE_PATH
    )

    expected_closure = (
        closure_payload(
            atlas_sha,
            persisted,
        )
    )

    require(
        closure
        == expected_closure,
        "Slice-1 closure certificate drift.",
    )

    require(
        sha256(
            ACCEPTED_FEM_ATLAS
        )
        == EXPECTED_ACCEPTED_FEM_ATLAS_SHA256,
        "Accepted-FEM atlas changed during Slice 1.",
    )

    print()
    print("=" * 110)
    print("THREADROM — SLICE 1 AUDIT PASS")
    print("=" * 110)
    print(
        "Case bindings       :",
        len(
            persisted[
                "case_bindings"
            ]
        ),
    )
    print(
        "Distinct geometries :",
        len(
            persisted[
                "geometries"
            ]
        ),
    )
    print(
        "Distinct meshes     :",
        len(
            persisted[
                "meshes"
            ]
        ),
    )
    print(
        "Atlas SHA-256       :",
        atlas_sha,
    )
    print(
        "Closure SHA-256     :",
        sha256(
            CLOSURE_PATH
        ),
    )
    print("Canonical rebuild   : PASS")
    print("Artifact SHA replay : PASS")
    print("Accepted atlas guard: PASS")
    print("Holdouts accessed   : NO")
    print("CAD generated       : NO")
    print("Mesh generated      : NO")
    print("FEM launched        : NO")
    print("=" * 110)


def main() -> None:
    parser = argparse.ArgumentParser()

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--write",
        action="store_true",
    )

    mode.add_argument(
        "--audit",
        action="store_true",
    )

    args = parser.parse_args()

    if args.write:
        write_mode()
    else:
        audit_mode()


if __name__ == "__main__":
    main()
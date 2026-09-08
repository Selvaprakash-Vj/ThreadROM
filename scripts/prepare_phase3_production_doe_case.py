from __future__ import annotations

import argparse
import hashlib
import json

from pathlib import Path

from threadrom.case.resolver import resolve_case

from threadrom.factory.fem_case_geometry import (
    build_fem_case_geometry,
)
from threadrom.factory.fem_case_mesh import (
    generate_fem_case_grouped_mesh,
)
from threadrom.factory.fem_case_preparation import (
    derive_fem_case_preparation,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)

from threadrom.geometry.complete_joint_assembly import (
    load_assembly_geometry_validation_policy,
)

from threadrom.meshing.complete_joint_local_refinement import (
    load_complete_joint_local_refinement_policy,
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


ROOT = Path(r"D:\ThreadROM")

CONFIG = ROOT / "config"

CAMPAIGN_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp8_production_doe"
    / "TRM-PDOE-C01"
)

ARTIFACT_ROOT = (
    CAMPAIGN_ROOT
    / "prepared_cases"
)

DOE_POLICY_PATH = (
    CONFIG
    / "phase3_production_doe.toml"
)

CAMPAIGN_MANIFEST_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_campaign_manifest.json"
)

ANCHOR_BINDING_PATH = (
    CAMPAIGN_ROOT
    / "existing_anchor_binding_record.json"
)


EXPECTED_DOE_POLICY_SHA256 = (
    "43032557cb2abead0118362bcfc6a9b2e"
    "5246a7d363ca83eef5fcf35054befc1"
)

EXPECTED_CAMPAIGN_SHA256 = (
    "84516519bbb188664268936e2d116e133"
    "431d90d037bed407ffb2d1fe92d2a67"
)

EXPECTED_ANCHOR_BINDING_SHA256 = (
    "ab861ff62af6bbc4589b3a469e8dc159"
    "c92dd61116fd8275c02e8f1adcf813b2"
)


def sha256(path: Path) -> str:
    if (
        not path.is_file()
        or path.stat().st_size <= 0
    ):
        raise FileNotFoundError(path)

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


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:
    actual = sha256(path)

    if actual != expected:
        raise RuntimeError(
            f"{label} drift detected.\n"
            f"Expected: {expected}\n"
            f"Actual  : {actual}\n"
            f"Path    : {path}"
        )

    return actual


def relative(path: Path) -> str:
    return path.relative_to(
        ROOT
    ).as_posix()


def write_immutable_json(
    path: Path,
    payload: dict[str, object],
) -> tuple[str, str]:

    serialized = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    if path.exists():
        existing = path.read_text(
            encoding="utf-8"
        )

        if existing != serialized:
            raise RuntimeError(
                "Preparation evidence already exists "
                "with different content. Refusing "
                f"immutable overwrite: {path}"
            )

        action = "UNCHANGED / IDENTICAL"

    else:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = path.with_suffix(
            ".json.tmp"
        )

        temporary.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )

        temporary.replace(path)

        action = "CREATED"

    record_hash = sha256(path)

    sidecar = path.with_suffix(
        ".sha256"
    )

    sidecar_text = (
        f"{record_hash}  {path.name}\n"
    )

    if sidecar.exists():
        existing = sidecar.read_text(
            encoding="ascii"
        )

        if existing != sidecar_text:
            raise RuntimeError(
                "Preparation SHA sidecar drift "
                f"detected: {sidecar}"
            )

    else:
        sidecar.write_text(
            sidecar_text,
            encoding="ascii",
            newline="\n",
        )

    return action, record_hash


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare one frozen Phase-3 Production DOE "
            "design case through validated geometry and "
            "governed grouped mesh generation. "
            "This script never launches CalculiX."
        )
    )

    parser.add_argument(
        "--case-id",
        required=True,
        help=(
            "Frozen design case ID, for example "
            "D-BND-001."
        ),
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    # --------------------------------------------------
    # GOVERNANCE INTEGRITY
    # --------------------------------------------------

    doe_policy_hash = require_sha256(
        DOE_POLICY_PATH,
        EXPECTED_DOE_POLICY_SHA256,
        "Production DOE policy",
    )

    campaign_hash = require_sha256(
        CAMPAIGN_MANIFEST_PATH,
        EXPECTED_CAMPAIGN_SHA256,
        "Production DOE campaign manifest",
    )

    anchor_binding_hash = require_sha256(
        ANCHOR_BINDING_PATH,
        EXPECTED_ANCHOR_BINDING_SHA256,
        "Existing-anchor binding record",
    )

    policy = load_phase3_production_doe_policy(
        DOE_POLICY_PATH
    )

    campaign = build_phase3_production_doe(
        policy
    )

    # IMPORTANT:
    # Search design_cases only. Holdouts remain sealed.
    try:
        doe_case = next(
            item
            for item in campaign.design_cases
            if item.case_id == arguments.case_id
        )
    except StopIteration as exc:
        raise RuntimeError(
            "Requested case is not an authorized "
            "Production DOE design case. Holdout cases "
            "are intentionally inaccessible here: "
            f"{arguments.case_id}"
        ) from exc

    if doe_case.source_case_id is not None:
        raise RuntimeError(
            "Existing anchor cases must not be rebuilt. "
            "They are already bound to certified FEM "
            f"evidence: {doe_case.case_id}"
        )

    frozen_manifest = json.loads(
        CAMPAIGN_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    try:
        frozen_row = next(
            row
            for row in frozen_manifest["design_cases"]
            if row["case_id"] == doe_case.case_id
        )
    except StopIteration as exc:
        raise RuntimeError(
            "Generated DOE design case is absent from "
            "the frozen campaign manifest."
        ) from exc

    if frozen_row["case_hash"] != doe_case.case_hash:
        raise RuntimeError(
            "Generated DOE case hash does not match "
            "the frozen campaign manifest."
        )

    if (
        frozen_row["mesh_policy_name"]
        != doe_case.mesh_policy_name
    ):
        raise RuntimeError(
            "Generated DOE mesh policy does not match "
            "the frozen campaign manifest."
        )

    if frozen_row[
        "existing_evidence_reuse_planned"
    ]:
        raise RuntimeError(
            "New-case preparation cannot operate on "
            "an existing-evidence anchor."
        )

    resolved = resolve_case(
        doe_case.case
    )

    if resolved.case_hash != doe_case.case_hash:
        raise RuntimeError(
            "Resolved case hash does not match "
            "the frozen Production DOE case hash."
        )

    preparation = derive_fem_case_preparation(
        resolved
    )

    # --------------------------------------------------
    # GOVERNED TEMPLATE/POLICY LOADS
    # --------------------------------------------------

    geometry_validation_path = (
        CONFIG
        / "assembly_geometry_validation.toml"
    )

    mesh_template_path = (
        CONFIG
        / "complete_joint_mesh.toml"
    )

    joint_classification_path = (
        CONFIG
        / "complete_joint_surface_classification.toml"
    )

    bolt_classification_path = (
        CONFIG
        / "surface_classification.toml"
    )

    nut_classification_path = (
        CONFIG
        / "nut_surface_classification.toml"
    )

    local_refinement_path = (
        CONFIG
        / "complete_joint_local_refinement.toml"
    )

    validation_policy = (
        load_assembly_geometry_validation_policy(
            geometry_validation_path
        )
    )

    mesh_template = (
        load_complete_joint_mesh_definition(
            mesh_template_path
        )
    )

    joint_classification_template = (
        load_complete_joint_surface_definition(
            joint_classification_path
        )
    )

    bolt_classification_template = (
        load_surface_classification_definition(
            bolt_classification_path
        )
    )

    nut_classification_template = (
        load_nut_surface_classification_definition(
            nut_classification_path
        )
    )

    bolt_mesh_level_path = (
        CONFIG
        / mesh_template.bolt_mesh_level_policy
    )

    nut_mesh_level_path = (
        CONFIG
        / mesh_template.nut_mesh_level_policy
    )

    bolt_mesh_level_policy = (
        load_mesh_level_policy(
            bolt_mesh_level_path
        )
    )

    nut_mesh_level_policy = (
        load_mesh_level_policy(
            nut_mesh_level_path
        )
    )

    if doe_case.mesh_policy_name == "medium":
        local_refinement_policy = None

    elif (
        doe_case.mesh_policy_name
        == "medium_plus_v1"
    ):
        local_refinement_policy = (
            load_complete_joint_local_refinement_policy(
                local_refinement_path
            )
        )

        if (
            local_refinement_policy.policy_name
            != doe_case.mesh_policy_name
        ):
            raise RuntimeError(
                "Frozen Medium+ mesh policy name does "
                "not match governed refinement policy."
            )

    else:
        raise RuntimeError(
            "Unsupported frozen mesh policy: "
            f"{doe_case.mesh_policy_name}"
        )

    # --------------------------------------------------
    # CASE GEOMETRY
    # --------------------------------------------------

    geometry_artifact = (
        build_fem_case_geometry(
            resolved,
            artifact_root=ARTIFACT_ROOT,
            validation_policy=(
                validation_policy
            ),
        )
    )

    if (
        geometry_artifact.case_hash
        != doe_case.case_hash
    ):
        raise RuntimeError(
            "Geometry artifact case hash mismatch."
        )

    if (
        geometry_artifact.run_id
        != preparation.identity.run_id
    ):
        raise RuntimeError(
            "Geometry artifact run ID mismatch."
        )

    step_path = geometry_artifact.step_path

    if (
        not step_path.is_file()
        or step_path.stat().st_size <= 0
    ):
        raise RuntimeError(
            "Validated STEP artifact was not produced."
        )

    # --------------------------------------------------
    # GOVERNED GROUPED MESH
    # --------------------------------------------------

    mesh_artifact = (
        generate_fem_case_grouped_mesh(
            resolved,
            geometry_artifact.geometry,
            step_path=step_path,
            artifact_root=ARTIFACT_ROOT,
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
            bolt_mesh_level_policy=(
                bolt_mesh_level_policy
            ),
            nut_mesh_level_policy=(
                nut_mesh_level_policy
            ),
            local_refinement_policy=(
                local_refinement_policy
            ),
        )
    )

    if (
        mesh_artifact.case_hash
        != doe_case.case_hash
    ):
        raise RuntimeError(
            "Mesh artifact case hash mismatch."
        )

    if (
        mesh_artifact.run_id
        != preparation.identity.run_id
    ):
        raise RuntimeError(
            "Mesh artifact run ID mismatch."
        )

    msh_path = mesh_artifact.msh_path

    if (
        not msh_path.is_file()
        or msh_path.stat().st_size <= 0
    ):
        raise RuntimeError(
            "Governed grouped mesh was not produced."
        )

    actual_mesh_variant = (
        mesh_artifact.sizes.level_name
        if mesh_artifact.local_refinement is None
        else mesh_artifact.local_refinement.policy_name
    )

    if (
        actual_mesh_variant
        != doe_case.mesh_policy_name
    ):
        raise RuntimeError(
            "Produced mesh variant does not match "
            "the frozen DOE mesh policy.\n"
            f"Frozen  : {doe_case.mesh_policy_name}\n"
            f"Produced: {actual_mesh_variant}"
        )

    # --------------------------------------------------
    # IMMUTABLE PREPARATION PROVENANCE
    # --------------------------------------------------

    case_root = (
        ARTIFACT_ROOT
        / preparation.identity.run_id
    )

    record_path = (
        case_root
        / "production_doe_preparation_record.json"
    )

    config_paths = [
        geometry_validation_path,
        mesh_template_path,
        joint_classification_path,
        bolt_classification_path,
        nut_classification_path,
        bolt_mesh_level_path,
        nut_mesh_level_path,
    ]

    if local_refinement_policy is not None:
        config_paths.append(
            local_refinement_path
        )

    record = {
        "schema_version": 1,

        "record_id": (
            "TRM-P3-CP8-PDOE-C01-PREP-"
            f"{doe_case.case_id}"
        ),

        "record_status": "FINAL",

        "campaign": {
            "campaign_id": "TRM-PDOE-C01",
            "policy_id": policy.policy_id,
            "policy_sha256": (
                doe_policy_hash
            ),
            "campaign_manifest_sha256": (
                campaign_hash
            ),
            "anchor_binding_sha256": (
                anchor_binding_hash
            ),
        },

        "case": {
            "case_id": doe_case.case_id,
            "role": doe_case.role,
            "case_hash": doe_case.case_hash,
            "run_id": (
                preparation.identity.run_id
            ),
            "normalized_coordinates": list(
                doe_case.normalized_coordinates
            ),
            "mesh_policy_name": (
                doe_case.mesh_policy_name
            ),
            "source_case_id": (
                doe_case.source_case_id
            ),
        },

        "geometry": {
            "assembly_id": (
                geometry_artifact.assembly_id
            ),
            "step_relative_path": (
                relative(step_path)
            ),
            "step_size_bytes": (
                step_path.stat().st_size
            ),
            "step_sha256": (
                sha256(step_path)
            ),
        },

        "mesh": {
            "mesh_id": (
                mesh_artifact.definitions.mesh_id
            ),
            "classification_id": (
                mesh_artifact.definitions.classification_id
            ),
            "joint_geometry_id": (
                mesh_artifact.definitions.joint_geometry_id
            ),
            "base_mesh_level": (
                mesh_artifact.sizes.level_name
            ),
            "actual_mesh_variant": (
                actual_mesh_variant
            ),
            "msh_relative_path": (
                relative(msh_path)
            ),
            "msh_size_bytes": (
                msh_path.stat().st_size
            ),
            "msh_sha256": (
                sha256(msh_path)
            ),
            "local_refinement": (
                None
                if mesh_artifact.local_refinement is None
                else {
                    "policy_id": (
                        mesh_artifact
                        .local_refinement
                        .policy_id
                    ),
                    "policy_name": (
                        mesh_artifact
                        .local_refinement
                        .policy_name
                    ),
                    "local_size_mm": (
                        mesh_artifact
                        .local_refinement
                        .local_size_mm
                    ),
                    "transition_distance_mm": (
                        mesh_artifact
                        .local_refinement
                        .transition_distance_mm
                    ),
                }
            ),
        },

        "governed_configuration": [
            {
                "relative_path": (
                    relative(path)
                ),
                "sha256": sha256(path),
            }
            for path in config_paths
        ],

        "gates": {
            "frozen_campaign_membership": (
                "PASS"
            ),
            "case_hash_parity": "PASS",
            "mesh_policy_parity": "PASS",
            "geometry_validation": "PASS",
            "step_round_trip_validation": (
                "PASS"
            ),
            "grouped_mesh_generation": (
                "PASS"
            ),
            "mesh_variant_validation": (
                "PASS"
            ),
            "holdout_accessed": False,
        },

        "solve_authorization": {
            "calculix_invoked": False,
            "solver_launch_authorized": (
                False
            ),
            "preload_calibration_performed": (
                False
            ),
        },

        "overall_disposition": (
            "PRODUCTION_DOE_CASE_PREPARED"
        ),
    }

    action, record_hash = (
        write_immutable_json(
            record_path,
            record,
        )
    )

    print("=" * 122)
    print(
        "THREADROM — PRODUCTION DOE CASE PREPARATION"
    )
    print("=" * 122)
    print(
        "Case ID            :",
        doe_case.case_id,
    )
    print(
        "Case hash          :",
        doe_case.case_hash,
    )
    print(
        "Run ID             :",
        preparation.identity.run_id,
    )
    print(
        "Normalized coords  :",
        doe_case.normalized_coordinates,
    )
    print(
        "Frozen mesh policy :",
        doe_case.mesh_policy_name,
    )
    print(
        "Produced variant   :",
        actual_mesh_variant,
    )
    print()
    print(
        "STEP                :",
        step_path,
    )
    print(
        "STEP size           :",
        step_path.stat().st_size,
    )
    print(
        "STEP SHA256         :",
        sha256(step_path),
    )
    print()
    print(
        "MSH                 :",
        msh_path,
    )
    print(
        "MSH size            :",
        msh_path.stat().st_size,
    )
    print(
        "MSH SHA256          :",
        sha256(msh_path),
    )
    print()
    print(
        "Preparation record  :",
        record_path,
    )
    print(
        "Record action       :",
        action,
    )
    print(
        "Record SHA256       :",
        record_hash,
    )
    print()
    print(
        "Disposition         :",
        "PRODUCTION_DOE_CASE_PREPARED",
    )
    print(
        "CalculiX invoked    : NO"
    )
    print(
        "Holdouts accessed   : NO"
    )
    print("=" * 122)


if __name__ == "__main__":
    main()

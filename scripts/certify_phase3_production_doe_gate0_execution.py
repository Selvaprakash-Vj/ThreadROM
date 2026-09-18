from __future__ import annotations

import argparse
import hashlib
import json
import subprocess

from pathlib import Path


ROOT = Path(r"D:\ThreadROM")

CAMPAIGN_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp8_production_doe"
    / "TRM-PDOE-C01"
)

SOLVER_ROOT = (
    CAMPAIGN_ROOT
    / "solver_preparation"
)

DOE_POLICY_PATH = (
    ROOT
    / "config"
    / "phase3_production_doe.toml"
)

CAMPAIGN_MANIFEST_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_campaign_manifest.json"
)

GATE1_CERT_PATH = (
    ROOT
    / "docs"
    / "verification"
    / "TRM-PDOE-000001_FINAL_DIVERSIFIED_PRODUCTION_DOE_MATRIX_CERTIFICATION.md"
)

OUTPUT_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_gate0_execution_certification.json"
)


EXPECTED_DOE_POLICY_SHA256 = (
    "43032557cb2abead0118362bcfc6a9b2"
    "e5246a7d363ca83eef5fcf35054befc1"
)

EXPECTED_CAMPAIGN_MANIFEST_SHA256 = (
    "84516519bbb188664268936e2d116e133"
    "431d90d037bed407ffb2d1fe92d2a67"
)

EXPECTED_GATE1_CERT_SHA256 = (
    "743ea4bfa99994bcec5783e7d63aa5f"
    "03d5cef72256e795c533bef578c033ee3"
)

GATE1_SOURCE_COMMIT = (
    "ed3b357af87132ee1070c5abbc21cf5b991be152"
)

GATE1_REPO_RELATIVE_PATH = (
    "docs/verification/"
    "TRM-PDOE-000001_FINAL_DIVERSIFIED_PRODUCTION_DOE_MATRIX_CERTIFICATION.md"
)

EXPECTED_REACTION_SETS = frozenset(
    {
        "BOLT_HEAD_GUIDANCE_REFERENCE",
        "BOLT_HEAD_ROTATION_X_REFERENCE",
        "BOLT_HEAD_ROTATION_Y_REFERENCE",
        "HEAD_MEMBER_SUPPORT_BAND",
        "NUT_MEMBER_GUIDANCE_REFERENCE",
        "NUT_ROTATION_GUIDANCE_REFERENCE",
        "NUT_ROTATION_X_REFERENCE",
        "NUT_ROTATION_Y_REFERENCE",
        "NUT_TRANSLATION_GUIDANCE_REFERENCE",
    }
)

EXPECTED_CASES = (
    {
        "case_id": "D-INT-012",
        "canonical_case_run_id": "trm_fem_d667bb1aca27",
        "trial_run_id": (
            "trm_fem_d667bb1aca27_cal_01_wsv21_rfobs1"
        ),
        "preparation_sha256": (
            "b5a88ff926b49c774d1f209162e07740993eacd392ee8b72ede8c57a44f366be"
        ),
        "deck_sha256": (
            "c270aa1a08186538b9f64829f07373de531949988466b7b2cff3c3fbad2c7e8d"
        ),
    },
    {
        "case_id": "D-INT-013",
        "canonical_case_run_id": "trm_fem_039053767417",
        "trial_run_id": (
            "trm_fem_039053767417_cal_01_wsv21_rfobs1"
        ),
        "preparation_sha256": (
            "f3d8b8b1f1efe21d77879276f959cb37edc3d089cdcd8d8f9738ef1d78257e37"
        ),
        "deck_sha256": (
            "ea768a358a970bff7d760e1e7ad0c79afa0ac96226999de0fe5755bb9f59b5e4"
        ),
    },
    {
        "case_id": "D-INT-014",
        "canonical_case_run_id": "trm_fem_941ce23d715c",
        "trial_run_id": (
            "trm_fem_941ce23d715c_cal_01_wsv21_rfobs1"
        ),
        "preparation_sha256": (
            "8eb8e0a49fdcf6d73c9f2888a32bb4f18113b2c66f2006adb3b027b603f8a235"
        ),
        "deck_sha256": (
            "863b41c5cc1c8b57d6805ff533a24014a392879be8f346d5d24025666906616a"
        ),
    },
    {
        "case_id": "D-INT-015",
        "canonical_case_run_id": "trm_fem_34fffb87e0f7",
        "trial_run_id": (
            "trm_fem_34fffb87e0f7_cal_01_wsv21_rfobs1"
        ),
        "preparation_sha256": (
            "f787276289df03f021db5ce596f864fac2fa438a819b55f5b27c3829d1168c72"
        ),
        "deck_sha256": (
            "0e88df8e20631862d4d6aca374e65d5c7b0812d523548b0d420daeefec660ae5"
        ),
    },
    {
        "case_id": "D-INT-016",
        "canonical_case_run_id": "trm_fem_c74956ffff17",
        "trial_run_id": (
            "trm_fem_c74956ffff17_cal_01_wsv21_rfobs1"
        ),
        "preparation_sha256": (
            "59d0c0dd734c023df87a95b8f48a4d9e4610d5f33b332e3e171d7e1af41a3209"
        ),
        "deck_sha256": (
            "e405d68998148b7feb9fb6fb2cd1d98c87522adb9623730d5c18b8e3dee19842"
        ),
    },
)


PREPARATION_NAME = (
    "production_doe_reaction_observable_revision_record.json"
)

PREPARATION_SIDECAR_NAME = (
    "production_doe_reaction_observable_revision_record.sha256"
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Independently certify the five remaining "
            "Production DOE rfobs1 Trial-1 siblings for "
            "Gate-0 FEM execution."
        )
    )

    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Publish the immutable Gate-0 execution "
            "certification. Default is zero-write dry-run."
        ),
    )

    return parser.parse_args()


def sha256(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)

    if path.stat().st_size <= 0:
        raise RuntimeError(
            f"Required artifact is empty: {path}"
        )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:
    actual = sha256(path)

    if actual != expected:
        raise RuntimeError(
            f"{label} SHA drift.\n"
            f"Expected: {expected}\n"
            f"Actual  : {actual}\n"
            f"Path    : {path}"
        )

    return actual


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def relative(path: Path) -> str:
    return (
        path.resolve()
        .relative_to(ROOT.resolve())
        .as_posix()
    )


def write_immutable_json(
    path: Path,
    payload: dict,
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
                "Immutable Gate-0 certification already "
                "exists with different content. "
                f"Refusing overwrite: {path}"
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

    return action, sha256(path)


def serialized_sha256(payload: dict) -> str:
    serialized = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    return sha256_bytes(
        serialized.encode("utf-8")
    )


def require_bool(
    mapping: dict,
    field: str,
    expected: bool,
    label: str,
) -> None:
    actual = mapping.get(field)

    if actual is not expected:
        raise RuntimeError(
            f"{label}: expected {field}={expected!r}; "
            f"found {actual!r}."
        )


def main() -> int:
    args = parse_arguments()

    print(
        "=" * 132
    )
    print(
        "THREADROM - PRODUCTION DOE GATE-0 "
        "EXECUTION CERTIFICATION"
    )
    print(
        "=" * 132
    )

    # ========================================================
    # 1. FROZEN GOVERNANCE + GATE-1 EVIDENCE
    # ========================================================

    policy_sha = require_sha256(
        DOE_POLICY_PATH,
        EXPECTED_DOE_POLICY_SHA256,
        "Production DOE policy",
    )

    campaign_sha = require_sha256(
        CAMPAIGN_MANIFEST_PATH,
        EXPECTED_CAMPAIGN_MANIFEST_SHA256,
        "Production DOE campaign manifest",
    )

    gate1_sha = require_sha256(
        GATE1_CERT_PATH,
        EXPECTED_GATE1_CERT_SHA256,
        "Gate-1 final matrix certification",
    )

    committed_gate1 = subprocess.check_output(
        [
            "git",
            "show",
            (
                f"{GATE1_SOURCE_COMMIT}:"
                f"{GATE1_REPO_RELATIVE_PATH}"
            ),
        ],
        cwd=ROOT,
    )

    committed_gate1_sha = sha256_bytes(
        committed_gate1
    )

    if (
        committed_gate1_sha
        != EXPECTED_GATE1_CERT_SHA256
    ):
        raise RuntimeError(
            "Gate-1 source-commit certificate SHA drift.\n"
            f"Expected: {EXPECTED_GATE1_CERT_SHA256}\n"
            f"Actual  : {committed_gate1_sha}"
        )

    campaign_manifest = load_json(
        CAMPAIGN_MANIFEST_PATH
    )

    if (
        campaign_manifest.get("record_status")
        != "FROZEN"
    ):
        raise RuntimeError(
            "Production DOE campaign manifest "
            "is not FROZEN."
        )

    frozen_authorization = (
        campaign_manifest.get(
            "solve_authorization",
            {},
        )
    )

    for field in (
        "geometry_generation_authorized",
        "input_deck_generation_authorized",
        "mesh_generation_authorized",
        "new_fem_solve_performed_by_this_record",
        "solver_launch_authorized",
    ):
        require_bool(
            frozen_authorization,
            field,
            False,
            "Frozen campaign provenance",
        )

    # ========================================================
    # 2. INDEPENDENT RFOBS1 CASE CERTIFICATION
    # ========================================================

    certified_rows: list[dict] = []

    for expected in EXPECTED_CASES:
        case_id = expected["case_id"]

        if case_id.startswith("H"):
            raise RuntimeError(
                "Blind holdout entered Gate-0 "
                f"authorization scope: {case_id}"
            )

        canonical_case_run_id = (
            expected["canonical_case_run_id"]
        )

        trial_run_id = (
            expected["trial_run_id"]
        )

        run_dir = (
            SOLVER_ROOT
            / canonical_case_run_id
            / trial_run_id
        )

        prep_path = (
            run_dir
            / PREPARATION_NAME
        )

        prep_sha = require_sha256(
            prep_path,
            expected["preparation_sha256"],
            f"{case_id} rfobs1 preparation",
        )

        prep_sidecar_path = (
            run_dir
            / PREPARATION_SIDECAR_NAME
        )

        if not prep_sidecar_path.is_file():
            raise FileNotFoundError(
                f"{case_id}: rfobs1 preparation "
                "SHA sidecar missing: "
                f"{prep_sidecar_path}"
            )

        prep_sidecar_text = (
            prep_sidecar_path.read_text(
                encoding="utf-8-sig"
            )
            .strip()
        )

        expected_sidecar_text = (
            f"{prep_sha}  {PREPARATION_NAME}"
        )

        if (
            prep_sidecar_text
            != expected_sidecar_text
        ):
            raise RuntimeError(
                f"{case_id}: rfobs1 preparation "
                "SHA sidecar binding drift.\n"
                f"Expected: {expected_sidecar_text}\n"
                f"Actual  : {prep_sidecar_text}"
            )

        prep_sidecar_sha = sha256(
            prep_sidecar_path
        )

        prep = load_json(
            prep_path
        )

        if (
            prep.get("schema_version") != 1
            or prep.get("record_status") != "FINAL"
            or prep.get("overall_disposition")
            != (
                "PRODUCTION_DOE_REACTION_OBSERVABLE_"
                "REVISION_PREPARATION_PASS"
            )
        ):
            raise RuntimeError(
                f"{case_id}: rfobs1 preparation "
                "is not FINAL / PASS."
            )

        case = prep["case"]

        if (
            case.get("case_id") != case_id
            or case.get(
                "canonical_case_run_id"
            )
            != canonical_case_run_id
            or case.get(
                "reaction_observable_trial_run_id"
            )
            != trial_run_id
            or int(
                case.get(
                    "trial_index",
                    -1,
                )
            )
            != 1
        ):
            raise RuntimeError(
                f"{case_id}: rfobs1 case/run "
                "identity drift."
            )

        case_hash = case["case_hash"]

        expected_case_prefix = (
            canonical_case_run_id.removeprefix(
                "trm_fem_"
            )
        )

        if not case_hash.startswith(
            expected_case_prefix
        ):
            raise RuntimeError(
                f"{case_id}: canonical case-hash "
                "prefix drift."
            )

        current_resolution_hash = (
            case["current_resolution_hash"]
        )

        current_resolution_run_id = (
            case["current_resolution_run_id"]
        )

        if (
            current_resolution_run_id
            != (
                "trm_fem_"
                + current_resolution_hash[:12]
            )
        ):
            raise RuntimeError(
                f"{case_id}: current resolution "
                "identity drift."
            )

        expected_source_run_id = (
            f"{canonical_case_run_id}"
            "_cal_01_wsv21"
        )

        if (
            case[
                "source_v2_1_trial_run_id"
            ]
            != expected_source_run_id
        ):
            raise RuntimeError(
                f"{case_id}: source V2.1 "
                "run identity drift."
            )

        target_preload_n = float(
            case["target_preload_n"]
        )

        if not (
            15000.0
            <= target_preload_n
            <= 20000.0
        ):
            raise RuntimeError(
                f"{case_id}: target preload "
                "left governed 15-20 kN domain."
            )

        preflight = prep[
            "fem_preflight"
        ]

        if (
            preflight.get("status")
            != "PASS"
            or int(
                preflight.get(
                    "blocking_error_count",
                    -1,
                )
            )
            != 0
            or preflight.get("target")
            != "fem"
        ):
            raise RuntimeError(
                f"{case_id}: FEM preflight "
                "is not clean."
            )

        trial = prep["trial"]

        if (
            int(
                trial.get(
                    "trial_index",
                    -1,
                )
            )
            != 1
            or trial.get("run_id")
            != trial_run_id
            or trial.get("source")
            != "fem_warm_start"
        ):
            raise RuntimeError(
                f"{case_id}: Trial-1 semantics drift."
            )

        deck = prep["deck"]

        input_path = (
            ROOT
            / deck["relative_path"]
        )

        expected_input_path = (
            run_dir
            / f"{trial_run_id}.inp"
        )

        if (
            input_path.resolve()
            != expected_input_path.resolve()
        ):
            raise RuntimeError(
                f"{case_id}: rfobs1 deck "
                "path/run identity drift."
            )

        deck_sha = require_sha256(
            input_path,
            expected["deck_sha256"],
            f"{case_id} rfobs1 deck",
        )

        if (
            deck.get("sha256")
            != deck_sha
            or int(
                deck.get(
                    "size_bytes",
                    -1,
                )
            )
            != input_path.stat().st_size
        ):
            raise RuntimeError(
                f"{case_id}: recorded deck "
                "hash/size drift."
            )

        trial_dt = float(
            trial[
                "delta_temperature_c"
            ]
        )

        deck_dt = float(
            deck[
                "delta_temperature_c"
            ]
        )

        if trial_dt != deck_dt:
            raise RuntimeError(
                f"{case_id}: trial/deck "
                "delta-T mismatch."
            )

        source = prep[
            "source_v2_1_preparation"
        ]

        source_prep_path = (
            ROOT
            / source[
                "relative_path"
            ]
        )

        source_deck_path = (
            ROOT
            / source[
                "deck_relative_path"
            ]
        )

        source_prep_sha = require_sha256(
            source_prep_path,
            source["sha256"],
            f"{case_id} source V2.1 preparation",
        )

        source_deck_sha = require_sha256(
            source_deck_path,
            source["deck_sha256"],
            f"{case_id} source V2.1 deck",
        )

        source_dt = float(
            source[
                "delta_temperature_c"
            ]
        )

        if (
            source_dt != trial_dt
            or source.get(
                "overall_disposition"
            )
            != (
                "V2_1_ROLLOUT_CASE_PREPARATION_"
                "PASS_AWAITING_BATCH_CERTIFICATION"
            )
        ):
            raise RuntimeError(
                f"{case_id}: source V2.1 "
                "prediction/semantics drift."
            )

        reaction = prep[
            "reaction_observability"
        ]

        constrained = frozenset(
            reaction[
                "constrained_reaction_sets"
            ]
        )

        observable = frozenset(
            reaction[
                "observable_reaction_sets"
            ]
        )

        missing = tuple(
            reaction[
                "missing_reaction_sets"
            ]
        )

        if (
            constrained
            != EXPECTED_REACTION_SETS
            or observable
            != EXPECTED_REACTION_SETS
            or missing
            or reaction.get(
                "fully_observable"
            )
            is not True
            or reaction.get(
                "full_system_equilibrium_pass_claimed"
            )
            is not False
            or reaction.get(
                "equilibrium_tolerance_changed"
            )
            is not False
        ):
            raise RuntimeError(
                f"{case_id}: reaction-output "
                "contract certification failed."
            )

        execution = prep[
            "execution_authorization"
        ]

        require_bool(
            execution,
            "calculix_invoked_by_this_record",
            False,
            f"{case_id} execution provenance",
        )

        require_bool(
            execution,
            "execution_authorized_by_this_record",
            False,
            f"{case_id} execution provenance",
        )

        require_bool(
            execution,
            "blind_holdout_execution_authorized",
            False,
            f"{case_id} execution provenance",
        )

        require_bool(
            execution,
            "requires_gate0_authorization_before_execution",
            True,
            f"{case_id} execution provenance",
        )

        semantics = prep[
            "revision_semantics"
        ]

        expected_true_semantics = (
            "current_resolution_hash_preserved",
            "frozen_lineage_identity_bridge_applied",
            "source_delta_temperature_preserved",
            "source_v2_1_prediction_preserved",
            "trial_one_semantics_preserved",
        )

        expected_false_semantics = (
            "equilibrium_pass_claimed",
            "equilibrium_tolerance_changed",
            "fem_solution_reused",
            "holdout_accessed",
            "mesh_regenerated",
            "new_calibration_attempt",
            "solver_result_read",
        )

        for field in expected_true_semantics:
            require_bool(
                semantics,
                field,
                True,
                f"{case_id} revision semantics",
            )

        for field in expected_false_semantics:
            require_bool(
                semantics,
                field,
                False,
                f"{case_id} revision semantics",
            )

        if (
            semantics.get("purpose")
            != "REACTION_OUTPUT_CONTRACT_ONLY"
            or semantics.get(
                "revision_tag"
            )
            != "rfobs1"
            or semantics.get(
                "frozen_lineage_identity_bridge_scope"
            )
            != "EXECUTION_IDENTITY_ONLY"
        ):
            raise RuntimeError(
                f"{case_id}: rfobs1 revision "
                "semantics drift."
            )

        artifacts = prep[
            "certified_prepared_artifacts"
        ]

        mesh_path = (
            ROOT
            / artifacts[
                "mesh_relative_path"
            ]
        )

        step_path = (
            ROOT
            / artifacts[
                "step_relative_path"
            ]
        )

        mesh_sha = require_sha256(
            mesh_path,
            artifacts["mesh_sha256"],
            f"{case_id} certified mesh",
        )

        step_sha = require_sha256(
            step_path,
            artifacts["step_sha256"],
            f"{case_id} certified STEP",
        )

        allowed_files = {
            input_path.name,
            prep_path.name,
            prep_sidecar_path.name,
        }

        actual_files = {
            item.name
            for item in run_dir.iterdir()
            if item.is_file()
        }

        unexpected_files = sorted(
            actual_files
            - allowed_files
        )

        if unexpected_files:
            raise RuntimeError(
                f"{case_id}: unexpected file(s) "
                "in rfobs1 run directory:\n"
                + "\n".join(
                    unexpected_files
                )
            )

        if (
            not input_path.is_file()
            or not prep_path.is_file()
        ):
            raise RuntimeError(
                f"{case_id}: required rfobs1 "
                "artifacts missing."
            )

        manifest_path = (
            run_dir
            / "fem_run_manifest.json"
        )

        if manifest_path.exists():
            raise RuntimeError(
                f"{case_id}: FEM run manifest "
                "already exists. Gate-0 "
                "authorization refused."
            )

        accepted_evidence_path = (
            SOLVER_ROOT
            / canonical_case_run_id
            / "production_doe_accepted_fem_evidence.json"
        )

        if accepted_evidence_path.exists():
            raise RuntimeError(
                f"{case_id}: governed accepted "
                "FEM evidence already exists. "
                "Duplicate execution authorization refused."
            )

        certified_rows.append(
            {
                "case_id": case_id,
                "case_hash": case_hash,
                "canonical_case_run_id": (
                    canonical_case_run_id
                ),
                "current_resolution_hash": (
                    current_resolution_hash
                ),
                "current_resolution_run_id": (
                    current_resolution_run_id
                ),
                "authorized_trial_index": 1,
                "authorized_run_id": (
                    trial_run_id
                ),
                "target_preload_n": (
                    target_preload_n
                ),
                "frozen_delta_temperature_c": (
                    trial_dt
                ),
                "rfobs1_preparation_relative_path": (
                    relative(
                        prep_path
                    )
                ),
                "rfobs1_preparation_sha256": (
                    prep_sha
                ),
                "rfobs1_preparation_sidecar_relative_path": (
                    relative(
                        prep_sidecar_path
                    )
                ),
                "rfobs1_preparation_sidecar_sha256": (
                    prep_sidecar_sha
                ),
                "rfobs1_deck_relative_path": (
                    relative(
                        input_path
                    )
                ),
                "rfobs1_deck_sha256": (
                    deck_sha
                ),
                "source_v2_1_preparation_sha256": (
                    source_prep_sha
                ),
                "source_v2_1_deck_sha256": (
                    source_deck_sha
                ),
                "mesh_sha256": (
                    mesh_sha
                ),
                "step_sha256": (
                    step_sha
                ),
                "reaction_carrier_count": (
                    len(
                        EXPECTED_REACTION_SETS
                    )
                ),
                "full_system_equilibrium_pass_claimed": (
                    False
                ),
                "equilibrium_tolerance_changed": (
                    False
                ),
            }
        )

    # ========================================================
    # 3. FINAL GATE-0 EXECUTION AUTHORIZATION
    # ========================================================

    authorized_case_ids = [
        row["case_id"]
        for row in certified_rows
    ]

    authorized_run_ids = [
        row["authorized_run_id"]
        for row in certified_rows
    ]

    if (
        len(certified_rows) != 5
        or len(
            set(
                authorized_case_ids
            )
        )
        != 5
        or len(
            set(
                authorized_run_ids
            )
        )
        != 5
    ):
        raise RuntimeError(
            "Gate-0 scope is not exactly "
            "five unique cases/runs."
        )

    record = {
        "schema_version": 1,
        "record_id": (
            "TRM-P3-CP8-PDOE-C01-"
            "GATE0-EXEC-CERT-P01"
        ),
        "record_status": "FINAL",
        "campaign_id": "TRM-PDOE-C01",
        "certification_date": "2026-09-18",

        "source_evidence": {
            "production_doe_policy": {
                "relative_path": (
                    relative(
                        DOE_POLICY_PATH
                    )
                ),
                "sha256": policy_sha,
            },
            "frozen_campaign_manifest": {
                "relative_path": (
                    relative(
                        CAMPAIGN_MANIFEST_PATH
                    )
                ),
                "sha256": campaign_sha,
            },
            "gate1_final_matrix_certification": {
                "relative_path": (
                    relative(
                        GATE1_CERT_PATH
                    )
                ),
                "sha256": gate1_sha,
                "source_commit": (
                    GATE1_SOURCE_COMMIT
                ),
                "source_commit_blob_sha256": (
                    committed_gate1_sha
                ),
            },
        },

        "certified_gate0_cases": (
            certified_rows
        ),

        "zero_solve_verification": {
            "prepared_case_count": 5,
            "all_rfobs1_preparations_verified": True,
            "all_rfobs1_preparation_sidecars_verified": True,
            "all_rfobs1_deck_hashes_verified": True,
            "all_source_v2_1_artifacts_verified": True,
            "all_mesh_hashes_verified": True,
            "all_step_hashes_verified": True,
            "all_fem_preflights_passed": True,
            "all_nine_reaction_carriers_observable": True,
            "solver_outputs_detected": False,
            "fem_run_manifests_present": False,
            "accepted_case_evidence_already_present": False,
            "solver_results_read": False,
            "calculix_invoked": False,
            "mesh_regenerated": False,
            "deck_regenerated": False,
            "v2_1_refit_performed": False,
            "blind_holdout_accessed": False,
        },

        "execution_authorization": {
            "authorized": True,
            "authorization_basis": (
                "GATE1_PASS_PLUS_INDEPENDENT_"
                "RFOBS1_ZERO_SOLVE_CERTIFICATION"
            ),
            "scope": (
                "FIVE_REMAINING_PRODUCTION_DESIGN_"
                "RFOBS1_TRIAL1_SIBLINGS_ONLY"
            ),
            "authorized_case_ids": (
                authorized_case_ids
            ),
            "authorized_run_ids": (
                authorized_run_ids
            ),
            "authorized_trial": (
                "RFOBS1_V2_1_TRIAL_1_"
                "FIRST_SHOT_ONLY"
            ),
            "reaction_observable_revision_tag": (
                "rfobs1"
            ),
            "maximum_concurrent_calculix_runs": 4,
            "fresh_full_solve_required": True,
            "historical_checkpoint_resume_authorized": False,
            "additional_calibration_trial_authorized": False,
            "trial_2_requires_separate_governed_post_reject_preparation_and_authorization": True,
            "v2_1_prediction_must_remain_frozen": True,
            "reaction_output_contract_must_remain_frozen": True,
            "equilibrium_tolerance_change_authorized": False,
            "full_system_equilibrium_pass_preclaimed": False,
            "authorization_requires_exact_deck_and_preparation_hash_match": True,
            "blind_holdout_execution_authorized": False,
            "blind_holdouts_remain_sealed": True,
        },

        "evidence_semantics": {
            "gate1_certification_verified": True,
            "rfobs1_preparations_independently_verified": True,
            "solver_execution_performed_by_certifier": False,
            "production_fem_execution_now_authorized": True,
            "authorization_limited_to_five_certified_rfobs1_runs": True,
            "runs_remain_original_trial_1_physics": True,
            "rfobs1_is_not_new_calibration_attempt": True,
            "reaction_observability_is_not_equilibrium_acceptance": True,
            "equilibrium_tolerance_unchanged": True,
            "holdout_execution_authorized": False,
        },

        "overall_disposition": (
            "PRODUCTION_DOE_GATE0_EXECUTION_"
            "CERTIFIED_READY_FOR_FEM"
        ),
    }

    candidate_sha = serialized_sha256(
        record
    )

    print()
    print(
        "Gate-1 certificate SHA256     :",
        gate1_sha,
    )
    print(
        "Gate-1 source commit          :",
        GATE1_SOURCE_COMMIT,
    )
    print(
        "Production DOE policy SHA256  :",
        policy_sha,
    )
    print(
        "Campaign manifest SHA256      :",
        campaign_sha,
    )

    print()
    print(
        "Cases independently certified :",
        len(
            certified_rows
        ),
    )

    for row in certified_rows:
        print(
            f"{row['case_id']:12s} | "
            f"{row['authorized_run_id']} | "
            f"dT={row['frozen_delta_temperature_c']:.9f} C | "
            f"deck={row['rfobs1_deck_sha256'][:16]}..."
        )

    print()
    print(
        "Reaction carriers / case      : 9 / 9"
    )
    print(
        "Full equilibrium pre-claimed  : NO"
    )
    print(
        "Equilibrium tolerance changed : NO"
    )
    print(
        "CalculiX invoked              : NO"
    )
    print(
        "Solver outputs detected       : NO"
    )
    print(
        "Holdouts accessed             : NO"
    )
    print(
        "Holdout execution             : NOT AUTHORIZED"
    )
    print(
        "Trial 2                       : NOT AUTHORIZED BY THIS RECORD"
    )
    print(
        "Maximum concurrency ceiling   : 4"
    )

    print()
    print(
        "Candidate certification SHA   :",
        candidate_sha,
    )

    if args.write:
        action, record_sha = (
            write_immutable_json(
                OUTPUT_PATH,
                record,
            )
        )

        if record_sha != candidate_sha:
            raise RuntimeError(
                "Published Gate-0 certification "
                "hash differs from deterministic candidate."
            )

        print(
            "Certification record         :",
            OUTPUT_PATH,
        )
        print(
            "Certification SHA256         :",
            record_sha,
        )
        print(
            "Record action                :",
            action,
        )

    else:
        print(
            "Certification record         : DRY-RUN / NOT WRITTEN"
        )
        print(
            "Record action                : NONE"
        )

    print()
    print(
        "OVERALL DISPOSITION           : "
        "PRODUCTION_DOE_GATE0_EXECUTION_"
        "CERTIFIED_READY_FOR_FEM"
    )

    if not args.write:
        print(
            "EXECUTION AUTHORIZATION       : "
            "CANDIDATE ONLY — NOT YET PUBLISHED"
        )
    else:
        print(
            "EXECUTION AUTHORIZATION       : "
            "PUBLISHED"
        )

    print(
        "=" * 132
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

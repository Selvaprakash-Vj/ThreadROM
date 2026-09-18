from __future__ import annotations

import argparse
import hashlib
import json

from pathlib import Path

import threadrom.factory.fem_case_definition_bundle as bundle_mod

from threadrom.factory.fem_solver_orchestrator import (
    orchestrate_calculix_run,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)
from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
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

SOLVER_ROOT = (
    CAMPAIGN_ROOT
    / "solver_preparation"
)

DOE_POLICY_PATH = (
    CONFIG
    / "phase3_production_doe.toml"
)

CERTIFICATION_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_gate0_execution_certification.json"
)

EXPECTED_CERTIFICATION_SHA256 = (
    "1de14304d291c8b5c4dfd763bafec414"
    "92128b2cba8eb9471b13c1390b6ecad6"
)

EXPECTED_DOE_POLICY_SHA256 = (
    "43032557cb2abead0118362bcfc6a9b2"
    "e5246a7d363ca83eef5fcf35054befc1"
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

SOLVER_OUTPUT_SUFFIXES = {
    ".dat",
    ".frd",
    ".sta",
    ".cvg",
    ".12d",
    ".eig",
    ".equ",
    ".rout",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute exactly one Gate-0-certified "
            "Production DOE rfobs1 Trial-1 FEM case."
        )
    )

    parser.add_argument(
        "--case-id",
        required=True,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Verify the exact Gate-0 authorization, "
            "preparation and deck, then stop before "
            "CalculiX execution."
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


def solver_outputs_present(
    run_dir: Path,
) -> tuple[str, ...]:
    if not run_dir.is_dir():
        return ()

    outputs = []

    for path in run_dir.iterdir():
        if (
            path.is_file()
            and path.suffix.lower()
            in SOLVER_OUTPUT_SUFFIXES
        ):
            outputs.append(
                path.name
            )

    return tuple(
        sorted(outputs)
    )


def main() -> int:
    args = parse_arguments()

    # ========================================================
    # 1. BIND TO EXACT IMMUTABLE GATE-0 CERTIFICATION
    # ========================================================

    certification_sha = require_sha256(
        CERTIFICATION_PATH,
        EXPECTED_CERTIFICATION_SHA256,
        "Gate-0 execution certification",
    )

    certification = load_json(
        CERTIFICATION_PATH
    )

    if (
        certification.get("schema_version") != 1
        or certification.get("record_status") != "FINAL"
        or certification.get("campaign_id")
        != "TRM-PDOE-C01"
        or certification.get(
            "overall_disposition"
        )
        != (
            "PRODUCTION_DOE_GATE0_EXECUTION_"
            "CERTIFIED_READY_FOR_FEM"
        )
    ):
        raise RuntimeError(
            "Gate-0 certification is not "
            "FINAL / READY_FOR_FEM."
        )

    semantics = certification[
        "evidence_semantics"
    ]

    if (
        semantics.get(
            "gate1_certification_verified"
        )
        is not True
        or semantics.get(
            "rfobs1_preparations_independently_verified"
        )
        is not True
        or semantics.get(
            "solver_execution_performed_by_certifier"
        )
        is not False
        or semantics.get(
            "production_fem_execution_now_authorized"
        )
        is not True
        or semantics.get(
            "authorization_limited_to_five_certified_rfobs1_runs"
        )
        is not True
        or semantics.get(
            "runs_remain_original_trial_1_physics"
        )
        is not True
        or semantics.get(
            "rfobs1_is_not_new_calibration_attempt"
        )
        is not True
        or semantics.get(
            "reaction_observability_is_not_equilibrium_acceptance"
        )
        is not True
        or semantics.get(
            "equilibrium_tolerance_unchanged"
        )
        is not True
        or semantics.get(
            "holdout_execution_authorized"
        )
        is not False
    ):
        raise RuntimeError(
            "Gate-0 evidence semantics drift."
        )

    authorization = certification[
        "execution_authorization"
    ]

    if (
        authorization.get("authorized")
        is not True
        or authorization.get("scope")
        != (
            "FIVE_REMAINING_PRODUCTION_DESIGN_"
            "RFOBS1_TRIAL1_SIBLINGS_ONLY"
        )
        or authorization.get(
            "authorized_trial"
        )
        != (
            "RFOBS1_V2_1_TRIAL_1_"
            "FIRST_SHOT_ONLY"
        )
        or authorization.get(
            "reaction_observable_revision_tag"
        )
        != "rfobs1"
        or int(
            authorization.get(
                "maximum_concurrent_calculix_runs",
                -1,
            )
        )
        != 4
        or authorization.get(
            "fresh_full_solve_required"
        )
        is not True
        or authorization.get(
            "historical_checkpoint_resume_authorized"
        )
        is not False
        or authorization.get(
            "additional_calibration_trial_authorized"
        )
        is not False
        or authorization.get(
            "trial_2_requires_separate_governed_post_reject_preparation_and_authorization"
        )
        is not True
        or authorization.get(
            "v2_1_prediction_must_remain_frozen"
        )
        is not True
        or authorization.get(
            "reaction_output_contract_must_remain_frozen"
        )
        is not True
        or authorization.get(
            "equilibrium_tolerance_change_authorized"
        )
        is not False
        or authorization.get(
            "full_system_equilibrium_pass_preclaimed"
        )
        is not False
        or authorization.get(
            "authorization_requires_exact_deck_and_preparation_hash_match"
        )
        is not True
        or authorization.get(
            "blind_holdout_execution_authorized"
        )
        is not False
        or authorization.get(
            "blind_holdouts_remain_sealed"
        )
        is not True
    ):
        raise RuntimeError(
            "Gate-0 execution authorization drift."
        )

    authorized_case_ids = tuple(
        authorization[
            "authorized_case_ids"
        ]
    )

    authorized_run_ids = tuple(
        authorization[
            "authorized_run_ids"
        ]
    )

    if (
        len(authorized_case_ids) != 5
        or len(set(authorized_case_ids)) != 5
        or len(authorized_run_ids) != 5
        or len(set(authorized_run_ids)) != 5
    ):
        raise RuntimeError(
            "Gate-0 authorization scope is not "
            "exactly five unique cases/runs."
        )

    if args.case_id.startswith("H"):
        raise RuntimeError(
            "Blind holdout execution is forbidden."
        )

    if args.case_id not in authorized_case_ids:
        raise RuntimeError(
            f"{args.case_id}: case is not inside "
            "the Gate-0-certified rfobs1 scope."
        )

    # ========================================================
    # 2. RECONSTRUCT THE FROZEN PRODUCTION DOE CASE
    # ========================================================

    require_sha256(
        DOE_POLICY_PATH,
        EXPECTED_DOE_POLICY_SHA256,
        "Production DOE policy",
    )

    policy = (
        load_phase3_production_doe_policy(
            DOE_POLICY_PATH
        )
    )

    campaign = (
        build_phase3_production_doe(
            policy
        )
    )

    matches = tuple(
        item
        for item in campaign.design_cases
        if item.case_id == args.case_id
    )

    if len(matches) != 1:
        raise RuntimeError(
            f"{args.case_id}: expected exactly "
            f"one Production DOE design case; "
            f"found {len(matches)}."
        )

    doe_case = matches[0]

    if doe_case.source_case_id is not None:
        raise RuntimeError(
            "Certified FEM anchor rerun forbidden."
        )

    # ========================================================
    # 3. BIND TO EXACT GATE-0 CERTIFIED ROW
    # ========================================================

    certified_rows = [
        row
        for row in certification[
            "certified_gate0_cases"
        ]
        if row["case_id"] == args.case_id
    ]

    if len(certified_rows) != 1:
        raise RuntimeError(
            f"{args.case_id}: expected exactly "
            "one Gate-0 certified row."
        )

    certified = certified_rows[0]

    if (
        certified["case_hash"]
        != doe_case.case_hash
    ):
        raise RuntimeError(
            "Gate-0 certified case-hash drift."
        )

    if (
        int(
            certified[
                "authorized_trial_index"
            ]
        )
        != 1
    ):
        raise RuntimeError(
            "Only Trial-1 execution is authorized."
        )

    trial_run_id = certified[
        "authorized_run_id"
    ]

    if (
        trial_run_id
        not in authorized_run_ids
    ):
        raise RuntimeError(
            "Certified run ID is not present in "
            "Gate-0 execution authorization."
        )

    canonical_case_run_id = (
        certified[
            "canonical_case_run_id"
        ]
    )

    expected_case_run_id = (
        f"trm_fem_{doe_case.case_hash[:12]}"
    )

    if (
        canonical_case_run_id
        != expected_case_run_id
    ):
        raise RuntimeError(
            "Canonical frozen-lineage case-run "
            "identity drift."
        )

    expected_trial_run_id = (
        f"{canonical_case_run_id}"
        "_cal_01_wsv21_rfobs1"
    )

    if (
        trial_run_id
        != expected_trial_run_id
    ):
        raise RuntimeError(
            "rfobs1 Trial-1 run-ID semantics drift."
        )

    run_dir = (
        SOLVER_ROOT
        / canonical_case_run_id
        / trial_run_id
    )

    # ========================================================
    # 4. VERIFY EXACT IMMUTABLE RFOBS1 PREPARATION
    # ========================================================

    prep_path = (
        ROOT
        / certified[
            "rfobs1_preparation_relative_path"
        ]
    )

    if prep_path.parent != run_dir:
        raise RuntimeError(
            "rfobs1 preparation directory/run "
            "identity drift."
        )

    prep_sha = require_sha256(
        prep_path,
        certified[
            "rfobs1_preparation_sha256"
        ],
        "rfobs1 preparation",
    )

    prep = load_json(
        prep_path
    )

    if (
        prep.get("record_status") != "FINAL"
        or prep.get(
            "overall_disposition"
        )
        != (
            "PRODUCTION_DOE_REACTION_OBSERVABLE_"
            "REVISION_PREPARATION_PASS"
        )
    ):
        raise RuntimeError(
            "rfobs1 preparation is not "
            "FINAL / PASS."
        )

    case = prep["case"]

    if (
        case["case_id"] != doe_case.case_id
        or case["case_hash"]
        != doe_case.case_hash
        or case[
            "canonical_case_run_id"
        ]
        != canonical_case_run_id
        or case[
            "reaction_observable_trial_run_id"
        ]
        != trial_run_id
        or int(
            case["trial_index"]
        )
        != 1
    ):
        raise RuntimeError(
            "rfobs1 preparation case/run "
            "identity drift."
        )

    execution = prep[
        "execution_authorization"
    ]

    if (
        execution.get(
            "calculix_invoked_by_this_record"
        )
        is not False
        or execution.get(
            "execution_authorized_by_this_record"
        )
        is not False
        or execution.get(
            "blind_holdout_execution_authorized"
        )
        is not False
        or execution.get(
            "requires_gate0_authorization_before_execution"
        )
        is not True
    ):
        raise RuntimeError(
            "rfobs1 preparation execution "
            "provenance drift."
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
    ):
        raise RuntimeError(
            "rfobs1 FEM preflight is not clean."
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

    if (
        constrained
        != EXPECTED_REACTION_SETS
        or observable
        != EXPECTED_REACTION_SETS
        or tuple(
            reaction[
                "missing_reaction_sets"
            ]
        )
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
            "rfobs1 reaction-output contract drift."
        )

    # ========================================================
    # 5. VERIFY EXACT CERTIFIED RFOBS1 DECK
    # ========================================================

    input_path = (
        ROOT
        / certified[
            "rfobs1_deck_relative_path"
        ]
    )

    if input_path.parent != run_dir:
        raise RuntimeError(
            "rfobs1 deck directory/run "
            "identity drift."
        )

    if (
        input_path.name
        != f"{trial_run_id}.inp"
    ):
        raise RuntimeError(
            "rfobs1 deck filename/run "
            "identity drift."
        )

    deck_sha = require_sha256(
        input_path,
        certified[
            "rfobs1_deck_sha256"
        ],
        "rfobs1 deck",
    )

    if (
        deck_sha
        != prep["deck"]["sha256"]
        or input_path.stat().st_size
        != int(
            prep["deck"][
                "size_bytes"
            ]
        )
    ):
        raise RuntimeError(
            "rfobs1 deck hash/size drift."
        )

    trial = prep["trial"]

    if (
        int(
            trial["trial_index"]
        )
        != 1
        or trial["run_id"]
        != trial_run_id
        or trial["source"]
        != "fem_warm_start"
        or float(
            trial[
                "delta_temperature_c"
            ]
        )
        != float(
            certified[
                "frozen_delta_temperature_c"
            ]
        )
        or float(
            prep["deck"][
                "delta_temperature_c"
            ]
        )
        != float(
            certified[
                "frozen_delta_temperature_c"
            ]
        )
    ):
        raise RuntimeError(
            "Frozen Trial-1 delta-T semantics drift."
        )

    # ========================================================
    # 6. STRONG DUPLICATE / PARTIAL-SOLVE GUARD
    # ========================================================

    manifest_path = (
        run_dir
        / "fem_run_manifest.json"
    )

    existing_outputs = (
        solver_outputs_present(
            run_dir
        )
    )

    if existing_outputs:
        raise RuntimeError(
            "Existing solver output detected. "
            "Refusing duplicate or ambiguous FEM execution:\n"
            + "\n".join(
                existing_outputs
            )
        )

    if manifest_path.exists():
        raise RuntimeError(
            "FEM run manifest already exists. "
            "Duplicate solve refused."
        )

    accepted_evidence_path = (
        SOLVER_ROOT
        / canonical_case_run_id
        / "production_doe_accepted_fem_evidence.json"
    )

    if accepted_evidence_path.exists():
        raise RuntimeError(
            "Governed accepted FEM evidence "
            "already exists. Duplicate execution refused."
        )

    # ========================================================
    # 7. CERTIFIED SOLVER BACKEND
    # ========================================================

    transfer = (
        load_complete_joint_calculix_transfer_definition(
            CONFIG
            / "complete_joint_calculix_transfer.toml"
        )
    )

    backend = (
        bundle_mod
        .PHASE2_CERTIFIED_FEM_PROFILE
        .backend
    )

    definition = CalculixJobDefinition(
        executable_relative_path=(
            transfer.executable_relative_path
        ),
        job_name=trial_run_id,
        timeout_seconds=None,
    )

    # ========================================================
    # 8. DRY-RUN OR LIVE EXECUTION
    # ========================================================

    print(
        "=" * 132,
        flush=True,
    )
    print(
        "THREADROM - GATE-0 CERTIFIED "
        "RFOBS1 PRODUCTION DOE TRIAL-1",
        flush=True,
    )
    print(
        "=" * 132,
        flush=True,
    )
    print(
        "Case ID                    :",
        doe_case.case_id,
        flush=True,
    )
    print(
        "Case hash                  :",
        doe_case.case_hash,
        flush=True,
    )
    print(
        "Run ID                     :",
        trial_run_id,
        flush=True,
    )
    print(
        "Target preload N           :",
        certified[
            "target_preload_n"
        ],
        flush=True,
    )
    print(
        "Frozen V2.1 delta T C      :",
        certified[
            "frozen_delta_temperature_c"
        ],
        flush=True,
    )
    print(
        "Reaction carriers          : 9 / 9",
        flush=True,
    )
    print(
        "Equilibrium pre-claimed    : NO",
        flush=True,
    )
    print(
        "Equilibrium tolerance      : UNCHANGED",
        flush=True,
    )
    print(
        "Deck SHA256                :",
        deck_sha,
        flush=True,
    )
    print(
        "Preparation SHA256         :",
        prep_sha,
        flush=True,
    )
    print(
        "Gate-0 certification SHA   :",
        certification_sha,
        flush=True,
    )
    print(
        "Timeout                    : NONE",
        flush=True,
    )
    print(
        "Trial 2                    : NOT AUTHORIZED",
        flush=True,
    )
    print(
        "Holdout execution          : NOT AUTHORIZED",
        flush=True,
    )
    print(
        "Manifest                   :",
        manifest_path,
        flush=True,
    )
    print(
        "=" * 132,
        flush=True,
    )

    if args.dry_run:
        print()
        print(
            "GATE-0 RFOBS1 EXECUTION DRY RUN PASS",
            flush=True,
        )
        print(
            "Exact authorization        : VERIFIED",
            flush=True,
        )
        print(
            "Exact rfobs1 preparation   : VERIFIED",
            flush=True,
        )
        print(
            "Exact rfobs1 deck          : VERIFIED",
            flush=True,
        )
        print(
            "Duplicate/partial outputs  : NONE",
            flush=True,
        )
        print(
            "CalculiX invoked           : NO",
            flush=True,
        )
        print(
            "FEM launched               : NO",
            flush=True,
        )
        print(
            "=" * 132,
            flush=True,
        )
        return 0

    result = orchestrate_calculix_run(
        project_root=ROOT,
        input_path=input_path,
        definition=definition,
        run_id=trial_run_id,
        case_hash=doe_case.case_hash,
        backend_policy_id=backend.policy_id,
        solver_name=backend.solver_name,
        solver_version=backend.solver_version,
        manifest_path=manifest_path,
    )

    print()
    print(
        "=" * 132,
        flush=True,
    )
    print(
        "THREADROM - GATE-0 CERTIFIED "
        "RFOBS1 FEM FINISHED",
        flush=True,
    )
    print(
        "=" * 132,
        flush=True,
    )
    print(
        "Case ID                    :",
        doe_case.case_id,
        flush=True,
    )
    print(
        "Run ID                     :",
        trial_run_id,
        flush=True,
    )
    print(
        "Disposition                :",
        result.manifest.disposition,
        flush=True,
    )
    print(
        "Return code                :",
        result.manifest.return_code,
        flush=True,
    )
    print(
        "Job finished               :",
        result.manifest.job_finished,
        flush=True,
    )
    print(
        "Accepted increments        :",
        result.manifest.accepted_increment_count,
        flush=True,
    )
    print(
        "Manifest                   :",
        result.manifest_path,
        flush=True,
    )
    print(
        "=" * 132,
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

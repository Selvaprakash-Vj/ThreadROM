from __future__ import annotations

import argparse
import hashlib
import json
import math

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
    / "warm_start_delta_t_v2_1_rollout_preparation_certification.json"
)

EXPECTED_CERTIFICATION_SHA256 = (
    "a11662817427d9131b92f798e953d116"
    "269ad672c49434365a75f68dac4709a7"
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Execute exactly one independently certified "
            "Warm-Start V2.1 Production DOE first-shot FEM case."
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
            "Verify the exact certified V2.1 rollout "
            "case and stop before CalculiX execution."
        ),
    )

    return parser.parse_args()


def sha256(
    path: Path,
    *,
    allow_empty: bool = False,
) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)

    if (
        not allow_empty
        and path.stat().st_size <= 0
    ):
        raise RuntimeError(
            f"Required artifact is empty: {path}"
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


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def require_close(
    label: str,
    actual: float,
    expected: float,
    *,
    tolerance: float = 1.0e-10,
) -> None:
    if not math.isclose(
        actual,
        expected,
        rel_tol=0.0,
        abs_tol=tolerance,
    ):
        raise RuntimeError(
            f"{label} drift.\n"
            f"Expected: {expected}\n"
            f"Actual  : {actual}"
        )


def solver_outputs_present(
    run_dir: Path,
) -> tuple[str, ...]:
    if not run_dir.exists():
        return ()

    forbidden_names = {
        "fem_run_manifest.json",
    }

    forbidden_suffixes = {
        ".dat",
        ".frd",
        ".sta",
        ".cvg",
        ".12d",
        ".eig",
        ".equ",
        ".rout",
        ".log",
    }

    found = []

    for path in run_dir.rglob("*"):
        if not path.is_file():
            continue

        if (
            path.name in forbidden_names
            or path.suffix.lower()
            in forbidden_suffixes
        ):
            found.append(
                path.relative_to(ROOT).as_posix()
            )

    return tuple(
        sorted(found)
    )


def main() -> int:
    args = parse_arguments()

    # ========================================================
    # 1. BIND EXECUTION TO THE INDEPENDENT CERTIFICATION
    # ========================================================

    certification_sha = sha256(
        CERTIFICATION_PATH
    )

    if (
        certification_sha
        != EXPECTED_CERTIFICATION_SHA256
    ):
        raise RuntimeError(
            "V2.1 rollout-preparation certification SHA drift.\n"
            f"Expected: {EXPECTED_CERTIFICATION_SHA256}\n"
            f"Actual  : {certification_sha}"
        )

    certification = load_json(
        CERTIFICATION_PATH
    )

    if (
        certification.get("record_status")
        != "FINAL"
        or certification.get(
            "overall_disposition"
        )
        != (
            "V2_1_ROLLOUT_PREPARATION_"
            "CERTIFIED_READY_FOR_FEM"
        )
    ):
        raise RuntimeError(
            "V2.1 rollout preparation is not "
            "FINAL / READY_FOR_FEM."
        )

    semantics = certification[
        "evidence_semantics"
    ]

    if (
        semantics.get(
            "production_fem_execution_now_authorized"
        )
        is not True
        or semantics.get(
            "authorization_limited_to_certified_case_ids"
        )
        is not True
        or semantics.get(
            "holdout_execution_authorized"
        )
        is not False
    ):
        raise RuntimeError(
            "Rollout execution evidence semantics drift."
        )

    authorization = certification[
        "rollout_execution_authorization"
    ]

    if (
        authorization.get("authorized")
        is not True
        or authorization.get("predictor")
        != "warm_start_delta_t_v2_1"
        or authorization.get(
            "authorized_trial"
        )
        != "V2_1_FIRST_SHOT_ONLY"
    ):
        raise RuntimeError(
            "V2.1 first-shot execution "
            "is not properly authorized."
        )

    if (
        authorization.get(
            "maximum_concurrent_calculix_runs"
        )
        != 4
    ):
        raise RuntimeError(
            "Certified concurrency ceiling drift."
        )

    if (
        authorization.get(
            "v2_1_model_must_remain_frozen"
        )
        is not True
        or authorization.get(
            "trial_2_only_after_governed_first_shot_reject"
        )
        is not True
    ):
        raise RuntimeError(
            "Frozen-model / Trial-2 governance drift."
        )

    if (
        authorization.get(
            "blind_holdout_execution_authorized"
        )
        is not False
        or authorization.get(
            "blind_holdouts_remain_sealed"
        )
        is not True
    ):
        raise RuntimeError(
            "Blind-holdout execution seal drift."
        )

    authorized_case_ids = tuple(
        authorization[
            "authorized_case_ids"
        ]
    )

    if (
        len(authorized_case_ids) != 14
        or len(set(authorized_case_ids)) != 14
    ):
        raise RuntimeError(
            "Certified rollout case set "
            "does not contain exactly 14 unique cases."
        )

    if args.case_id not in authorized_case_ids:
        raise RuntimeError(
            "Requested case is not in the independently "
            "certified V2.1 rollout set. "
            "Execution refused: "
            f"{args.case_id}"
        )

    if args.case_id.startswith("H"):
        raise RuntimeError(
            "Blind holdout execution is forbidden."
        )


    # ========================================================
    # 2. RESOLVE THE FROZEN PRODUCTION DOE CASE
    # ========================================================

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
    # 3. BIND TO THE EXACT CERTIFIED CASE ROW
    # ========================================================

    certified_rows = [
        row
        for row in certification[
            "certified_rollout_cases"
        ]
        if row["case_id"] == args.case_id
    ]

    if len(certified_rows) != 1:
        raise RuntimeError(
            f"{args.case_id}: expected one certified "
            f"rollout row; found {len(certified_rows)}."
        )

    certified = certified_rows[0]

    if (
        certified["case_hash"]
        != doe_case.case_hash
    ):
        raise RuntimeError(
            "Certified rollout case-hash drift."
        )

    case_run_id = (
        f"trm_fem_{doe_case.case_hash[:12]}"
    )

    expected_trial_run_id = (
        f"{case_run_id}_cal_01_wsv21"
    )

    if (
        certified["run_id"]
        != expected_trial_run_id
    ):
        raise RuntimeError(
            "Certified V2.1 sibling run-ID drift."
        )

    trial_run_id = expected_trial_run_id

    run_dir = (
        SOLVER_ROOT
        / case_run_id
        / trial_run_id
    )


    # ========================================================
    # 4. VERIFY THE EXACT FROZEN PER-CASE PREPARATION
    # ========================================================

    prep_path = (
        ROOT
        / certified[
            "preparation_relative_path"
        ]
    )

    prep_sha = sha256(
        prep_path
    )

    if (
        prep_sha
        != certified[
            "preparation_sha256"
        ]
    ):
        raise RuntimeError(
            "Certified V2.1 per-case preparation SHA drift."
        )

    prep = load_json(
        prep_path
    )

    if (
        prep.get("record_status")
        != "FINAL"
        or prep.get(
            "overall_disposition"
        )
        != (
            "V2_1_ROLLOUT_CASE_PREPARATION_PASS_"
            "AWAITING_BATCH_CERTIFICATION"
        )
    ):
        raise RuntimeError(
            "V2.1 per-case preparation "
            "is not the frozen FINAL PASS."
        )

    if (
        prep["case"]["case_id"]
        != doe_case.case_id
        or prep["case"]["case_hash"]
        != doe_case.case_hash
        or prep["case"][
            "v2_1_trial1_run_id"
        ]
        != trial_run_id
    ):
        raise RuntimeError(
            "V2.1 preparation case/run identity drift."
        )

    if (
        prep["fem_preflight"]["status"]
        != "PASS"
        or prep["fem_preflight"][
            "blocking_error_count"
        ]
        != 0
    ):
        raise RuntimeError(
            "Certified V2.1 FEM preflight "
            "is not PASS."
        )

    zero = prep[
        "zero_solve_assertion"
    ]

    for field in (
        "solver_outputs_detected",
        "solver_results_read",
        "calculix_invoked",
        "solver_authorized_by_this_script",
        "blind_holdout_accessed",
        "v2_1_refit_performed",
    ):
        if zero.get(field) is not False:
            raise RuntimeError(
                "Frozen V2.1 zero-solve provenance "
                f"drift for {field}."
            )

    prediction = prep[
        "frozen_v2_1_prediction"
    ]

    if (
        prediction.get(
            "model_refit_performed"
        )
        is not False
    ):
        raise RuntimeError(
            "V2.1 model-refit provenance drift."
        )

    require_close(
        "Certified predicted delta T",
        float(
            prediction[
                "predicted_delta_temperature_c"
            ]
        ),
        float(
            certified[
                "predicted_delta_temperature_c"
            ]
        ),
    )

    trial = prep[
        "trial_1"
    ]

    if (
        int(trial["trial_index"]) != 1
        or trial["run_id"] != trial_run_id
    ):
        raise RuntimeError(
            "Frozen V2.1 Trial-1 identity drift."
        )

    require_close(
        "Trial/prediction delta T",
        float(
            trial["delta_temperature_c"]
        ),
        float(
            certified[
                "predicted_delta_temperature_c"
            ]
        ),
    )


    # ========================================================
    # 5. VERIFY EXACT CERTIFIED SIBLING DECK
    # ========================================================

    input_path = (
        ROOT
        / certified[
            "deck_relative_path"
        ]
    )

    if input_path.parent != run_dir:
        raise RuntimeError(
            "Certified deck directory/run identity drift."
        )

    if (
        input_path.name
        != f"{trial_run_id}.inp"
    ):
        raise RuntimeError(
            "Certified deck filename/run identity drift."
        )

    deck_sha = sha256(
        input_path
    )

    if (
        deck_sha
        != certified[
            "deck_sha256"
        ]
        or deck_sha
        != prep[
            "deck"
        ][
            "sha256"
        ]
    ):
        raise RuntimeError(
            "Certified V2.1 sibling deck SHA drift."
        )

    actual_size = (
        input_path.stat().st_size
    )

    if (
        actual_size
        != int(
            certified[
                "deck_size_bytes"
            ]
        )
        or actual_size
        != int(
            prep[
                "deck"
            ][
                "size_bytes"
            ]
        )
    ):
        raise RuntimeError(
            "Certified V2.1 sibling deck size drift."
        )

    require_close(
        "Deck/certified delta T",
        float(
            prep[
                "deck"
            ][
                "delta_temperature_c"
            ]
        ),
        float(
            certified[
                "predicted_delta_temperature_c"
            ]
        ),
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


    # ========================================================
    # 7. CERTIFIED PHASE-2 SOLVER BACKEND
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
    # 8. LIVE EXECUTION
    # ========================================================

    print("=" * 128, flush=True)
    print(
        "THREADROM - WARM-START V2.1 "
        "PRODUCTION DOE FIRST-SHOT FEM START",
        flush=True,
    )
    print("=" * 128, flush=True)

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
            "predicted_delta_temperature_c"
        ],
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
        "Rollout certification SHA  :",
        certification_sha,
        flush=True,
    )

    print(
        "Timeout                    : NONE",
        flush=True,
    )

    print(
        "V2.1 refit                 : FORBIDDEN",
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

    print("=" * 128, flush=True)

    if args.dry_run:
        print()
        print("=" * 128, flush=True)
        print(
            "V2.1 ROLLOUT EXECUTION DRY RUN PASS",
            flush=True,
        )
        print(
            "Certified case            : VERIFIED",
            flush=True,
        )
        print(
            "Certified sibling deck    : VERIFIED",
            flush=True,
        )
        print(
            "Duplicate/partial outputs : NONE",
            flush=True,
        )
        print(
            "CalculiX invoked          : NO",
            flush=True,
        )
        print(
            "FEM launched              : NO",
            flush=True,
        )
        print("=" * 128, flush=True)
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
    print("=" * 128, flush=True)
    print(
        "THREADROM - WARM-START V2.1 "
        "PRODUCTION DOE FIRST-SHOT FEM FINISHED",
        flush=True,
    )
    print("=" * 128, flush=True)

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

    print("=" * 128, flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
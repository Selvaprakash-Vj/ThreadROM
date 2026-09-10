from __future__ import annotations

import argparse
import hashlib
import json

from pathlib import Path

import threadrom.factory.fem_case_definition_bundle as bundle_mod

from threadrom.factory.fem_solver_orchestrator import (
    orchestrate_calculix_run,
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

CERTIFICATION_PATH = (
    CAMPAIGN_ROOT
    / "cp8_restart_v2_wave_02_execution_certification.json"
)

EXPECTED_CERTIFICATION_SHA256 = (
    "76889796cdcb1c07c00778b40d01531f"
    "76cfd72fa4c72ddea168a1ebc44aaaa0"
)

AUTHORIZED_CASE_IDS = (
    "D-INT-006",
    "D-INT-007",
    "D-INT-009",
    "D-INT-011",
)

SOLVER_SUFFIXES = {
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
            "Execute exactly one independently certified "
            "CP8 restart-v2 Warm-Start V2.1 Trial-1 sibling."
        )
    )

    parser.add_argument(
        "--case-id",
        required=True,
        choices=AUTHORIZED_CASE_IDS,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Verify the exact certified restart-v2 "
            "case and stop before CalculiX execution."
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


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def find_unique(
    rows: list[dict],
    case_id: str,
) -> dict:
    matches = [
        row
        for row in rows
        if row["case_id"] == case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected exactly one "
            "certified restart-v2 row; "
            f"found {len(matches)}."
        )

    return matches[0]


def solver_outputs_present(
    run_dir: Path,
) -> tuple[str, ...]:
    if not run_dir.exists():
        return ()

    found = []

    for path in run_dir.iterdir():
        if not path.is_file():
            continue

        if (
            path.name == "fem_run_manifest.json"
            or path.suffix.lower()
            in SOLVER_SUFFIXES
        ):
            found.append(path.name)

    return tuple(sorted(found))


def main() -> int:
    args = parse_arguments()

    # ========================================================
    # 1. LOCK INDEPENDENT EXECUTION CERTIFICATION
    # ========================================================

    certification_sha = sha256(
        CERTIFICATION_PATH
    )

    if (
        certification_sha
        != EXPECTED_CERTIFICATION_SHA256
    ):
        raise RuntimeError(
            "Restart-v2 execution certification SHA drift.\n"
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
            "CP8_RESTART_V2_WAVE_EXECUTION_"
            "CERTIFIED_READY_FOR_FEM"
        )
    ):
        raise RuntimeError(
            "Restart-v2 execution certification "
            "is not FINAL / READY_FOR_FEM."
        )

    authorization = certification[
        "execution_authorization"
    ]

    if (
        authorization.get("authorized")
        is not True
        or authorization.get("predictor")
        != "warm_start_delta_t_v2_1"
        or authorization.get(
            "authorized_trial"
        )
        != (
            "V2_1_TRIAL_1_REPLACEMENT_"
            "EXECUTION_ONLY"
        )
        or authorization.get(
            "replacement_execution_is_new_calibration_attempt"
        )
        is not False
        or authorization.get(
            "fresh_full_solve_required"
        )
        is not True
        or authorization.get(
            "historical_checkpoint_resume_authorized"
        )
        is not False
        or int(
            authorization[
                "maximum_concurrent_calculix_runs"
            ]
        )
        != 4
        or authorization.get(
            "v2_1_model_must_remain_frozen"
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
            "Restart-v2 execution authorization drift."
        )

    if args.case_id not in set(
        authorization[
            "authorized_case_ids"
        ]
    ):
        raise RuntimeError(
            f"{args.case_id}: case is not inside "
            "certified restart-v2 execution scope."
        )

    # ========================================================
    # 2. RESOLVE EXACT CERTIFIED RUN
    # ========================================================

    certified = find_unique(
        certification[
            "certified_restart_v2_cases"
        ],
        args.case_id,
    )

    if int(
        certified["trial_index"]
    ) != 1:
        raise RuntimeError(
            "Only governed Trial 1 replacement "
            "execution is authorized."
        )

    trial_run_id = certified[
        "authorized_restart_v2_run_id"
    ]

    if trial_run_id not in set(
        authorization[
            "authorized_run_ids"
        ]
    ):
        raise RuntimeError(
            f"{args.case_id}: run ID is not "
            "explicitly execution-authorized."
        )

    expected_suffix = (
        "_cal_01_wsv21_rv2"
    )

    if not trial_run_id.endswith(
        expected_suffix
    ):
        raise RuntimeError(
            f"{args.case_id}: restart-v2 "
            "Trial-1 run-ID semantics drift."
        )

    case_hash = certified[
        "case_hash"
    ]

    canonical_case_run_id = (
        f"trm_fem_{case_hash[:12]}"
    )

    expected_run_id = (
        f"{canonical_case_run_id}"
        f"{expected_suffix}"
    )

    if trial_run_id != expected_run_id:
        raise RuntimeError(
            f"{args.case_id}: certified run-ID "
            "does not match case hash."
        )

    run_dir = (
        SOLVER_ROOT
        / canonical_case_run_id
        / trial_run_id
    )

    input_path = (
        ROOT
        / certified[
            "deck_relative_path"
        ]
    )

    prep_path = (
        ROOT
        / certified[
            "preparation_relative_path"
        ]
    )

    if (
        input_path.parent.resolve()
        != run_dir.resolve()
        or prep_path.parent.resolve()
        != run_dir.resolve()
    ):
        raise RuntimeError(
            f"{args.case_id}: certified artifact "
            "location drift."
        )

    if input_path.name != (
        f"{trial_run_id}.inp"
    ):
        raise RuntimeError(
            f"{args.case_id}: certified deck "
            "filename drift."
        )

    deck_sha = sha256(
        input_path
    )

    prep_sha = sha256(
        prep_path
    )

    if (
        deck_sha
        != certified[
            "deck_sha256"
        ]
    ):
        raise RuntimeError(
            f"{args.case_id}: certified deck SHA drift."
        )

    if (
        prep_sha
        != certified[
            "preparation_sha256"
        ]
    ):
        raise RuntimeError(
            f"{args.case_id}: certified preparation SHA drift."
        )

    # ========================================================
    # 3. REVERIFY PER-CASE GOVERNANCE
    # ========================================================

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
            "CP8_RESTART_V2_SIBLING_PREPARATION_PASS_"
            "AWAITING_INDEPENDENT_EXECUTION_CERTIFICATION"
        )
    ):
        raise RuntimeError(
            f"{args.case_id}: per-case restart-v2 "
            "preparation evidence drift."
        )

    case_record = prep[
        "case"
    ]

    if (
        case_record["case_id"]
        != args.case_id
        or case_record["case_hash"]
        != case_hash
        or int(
            case_record["trial_index"]
        )
        != 1
        or case_record[
            "restart_v2_trial_run_id"
        ]
        != trial_run_id
    ):
        raise RuntimeError(
            f"{args.case_id}: per-case identity drift."
        )

    semantics = prep[
        "replacement_semantics"
    ]

    if (
        semantics[
            "calibration_trial_identity"
        ]
        != "TRIAL_1"
        or semantics[
            "new_calibration_attempt"
        ]
        is not False
        or semantics[
            "physics_prediction_changed"
        ]
        is not False
        or semantics[
            "resume_from_historical_checkpoint"
        ]
        is not False
        or semantics[
            "fresh_full_solve_required"
        ]
        is not True
    ):
        raise RuntimeError(
            f"{args.case_id}: replacement "
            "semantics drift."
        )

    frozen_dt = float(
        certified[
            "frozen_delta_temperature_c"
        ]
    )

    if float(
        semantics[
            "frozen_v2_1_delta_temperature_c"
        ]
    ) != frozen_dt:
        raise RuntimeError(
            f"{args.case_id}: frozen V2.1 "
            "delta-T drift."
        )

    resilience = prep[
        "execution_resilience"
    ]

    if (
        resilience["checkpoint_count"]
        != 20
        or resilience[
            "restart_write_enabled"
        ]
        is not True
        or resilience[
            "restart_write_frequency_steps"
        ]
        != 1
        or resilience[
            "overlay_latest"
        ]
        is not False
        or resilience[
            "preserve_total_pseudo_time"
        ]
        is not True
    ):
        raise RuntimeError(
            f"{args.case_id}: restart-v2 "
            "resilience drift."
        )

    text = input_path.read_text(
        encoding="utf-8-sig"
    )

    lines = text.splitlines()

    step_count = sum(
        1
        for line in lines
        if line.strip().upper().startswith(
            "*STEP"
        )
    )

    restart_lines = tuple(
        line.strip()
        for line in lines
        if line.strip().upper().startswith(
            "*RESTART"
        )
    )

    if (
        step_count != 20
        or restart_lines
        != (
            "*RESTART,WRITE,FREQUENCY=1",
        )
    ):
        raise RuntimeError(
            f"{args.case_id}: certified "
            "restart-v2 deck structure drift."
        )

    if any(
        ",OVERLAY"
        in line.strip().upper()
        for line in lines
        if line.strip().upper().startswith(
            "*RESTART"
        )
    ):
        raise RuntimeError(
            f"{args.case_id}: Windows-unsafe "
            "restart OVERLAY detected."
        )

    # ========================================================
    # 4. REFUSE DUPLICATE / AMBIGUOUS EXECUTION
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
            "Existing restart-v2 solver output detected. "
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
    # 5. CERTIFIED PHASE-2 SOLVER BACKEND
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
    # 6. EXECUTION GATE / DRY RUN
    # ========================================================

    print("=" * 132, flush=True)
    print(
        "THREADROM - CP8 RESTART-V2 "
        "TRIAL-1 FEM EXECUTION GATE",
        flush=True,
    )
    print("=" * 132, flush=True)

    print(
        "Case ID                    :",
        args.case_id,
        flush=True,
    )
    print(
        "Case hash                  :",
        case_hash,
        flush=True,
    )
    print(
        "Run ID                     :",
        trial_run_id,
        flush=True,
    )
    print(
        "Trial index                : 1",
        flush=True,
    )
    print(
        "Frozen V2.1 delta T C      :",
        frozen_dt,
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
        "Execution certification SHA:",
        certification_sha,
        flush=True,
    )
    print(
        "Restart checkpoints        : 20",
        flush=True,
    )
    print(
        "Restart OVERLAY            : NO",
        flush=True,
    )
    print(
        "Historical checkpoint use  : NO",
        flush=True,
    )
    print(
        "Fresh full solve           : YES",
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
    print("=" * 132, flush=True)

    if args.dry_run:
        print()
        print("=" * 132, flush=True)
        print(
            "CP8 RESTART-V2 EXECUTION DRY RUN PASS",
            flush=True,
        )
        print(
            "Certified case             : VERIFIED",
            flush=True,
        )
        print(
            "Certified restart-v2 deck  : VERIFIED",
            flush=True,
        )
        print(
            "Trial-1 semantics          : VERIFIED",
            flush=True,
        )
        print(
            "Frozen V2.1 delta T        : VERIFIED",
            flush=True,
        )
        print(
            "20 checkpoints             : VERIFIED",
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
        print("=" * 132, flush=True)

        return 0

    # ========================================================
    # 7. LIVE EXECUTION
    # ========================================================

    result = orchestrate_calculix_run(
        project_root=ROOT,
        input_path=input_path,
        definition=definition,
        run_id=trial_run_id,
        case_hash=case_hash,
        backend_policy_id=backend.policy_id,
        solver_name=backend.solver_name,
        solver_version=backend.solver_version,
        manifest_path=manifest_path,
    )

    print()
    print("=" * 132, flush=True)
    print(
        "THREADROM - CP8 RESTART-V2 "
        "TRIAL-1 FEM FINISHED",
        flush=True,
    )
    print("=" * 132, flush=True)

    print(
        "Case ID                    :",
        args.case_id,
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

    print("=" * 132, flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys

from pathlib import Path

from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)


ROOT = Path(r"D:\ThreadROM")

CAMPAIGN_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp8_production_doe"
    / "TRM-PDOE-C01"
)

SOLVER_ROOT = CAMPAIGN_ROOT / "solver_preparation"

EXECUTOR = (
    ROOT
    / "scripts"
    / "run_phase3_production_doe_calibration_trial_case.py"
)

POLICY_PATH = (
    ROOT
    / "config"
    / "phase3_production_doe.toml"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a governed bounded-concurrency wave of "
            "Production DOE Trial-1 FEM cases."
        )
    )

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--dry-run",
        action="store_true",
    )

    mode.add_argument(
        "--execute",
        action="store_true",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=4,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=4,
    )

    args = parser.parse_args()

    if not 1 <= args.workers <= 4:
        parser.error(
            "--workers must be between 1 and 4."
        )

    if args.limit < 1:
        parser.error(
            "--limit must be >= 1."
        )

    return args


def read_existing_manifest(
    manifest_path: Path,
) -> tuple[str, str]:
    if not manifest_path.exists():
        return "UNSOLVED", "-"

    try:
        data = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        return (
            "BLOCKED_INVALID_MANIFEST",
            str(exc),
        )

    disposition = str(
        data.get(
            "disposition",
            "UNKNOWN",
        )
    )

    job_finished = data.get(
        "job_finished"
    )

    return (
        "EXISTING",
        (
            f"disposition={disposition}, "
            f"job_finished={job_finished}"
        ),
    )


def run_case(
    case_id: str,
    case_run_id: str,
) -> tuple[str, int, Path]:
    log_root = (
        CAMPAIGN_ROOT
        / "batch_logs"
        / "trial1_wave"
    )

    log_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_path = (
        log_root
        / f"{case_run_id}_cal_01.log"
    )

    command = [
        sys.executable,
        str(EXECUTOR),
        "--case-id",
        case_id,
        "--trial-index",
        "1",
    ]

    with log_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as log:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )

    return (
        case_id,
        completed.returncode,
        log_path,
    )


def main() -> int:
    args = parse_args()

    if not EXECUTOR.is_file():
        raise FileNotFoundError(
            EXECUTOR
        )

    policy = (
        load_phase3_production_doe_policy(
            POLICY_PATH
        )
    )

    campaign = (
        build_phase3_production_doe(
            policy
        )
    )

    candidates = []

    print("=" * 118)
    print(
        "THREADROM — PRODUCTION DOE TRIAL-1 "
        "CONCURRENCY COORDINATOR"
    )
    print("=" * 118)

    for doe_case in campaign.design_cases:

        # Existing certified anchors are not solver candidates.
        if doe_case.source_case_id is not None:
            continue

        case_run_id = (
            f"trm_fem_{doe_case.case_hash[:12]}"
        )

        trial_run_id = (
            f"{case_run_id}_cal_01"
        )

        run_dir = (
            SOLVER_ROOT
            / case_run_id
            / trial_run_id
        )

        prep_record = (
            run_dir
            / "production_doe_solver_preparation_record.json"
        )

        manifest_path = (
            run_dir
            / "fem_run_manifest.json"
        )

        status, detail = read_existing_manifest(
            manifest_path
        )

        if status == "BLOCKED_INVALID_MANIFEST":
            raise RuntimeError(
                f"{doe_case.case_id}: "
                f"{status}: {detail}"
            )

        if status == "EXISTING":
            print(
                f"SKIP  {doe_case.case_id:<12} "
                f"{trial_run_id} | {detail}"
            )
            continue

        if not prep_record.is_file():
            raise FileNotFoundError(
                "Frozen Trial-1 solver-preparation "
                "record missing:\n"
                f"{prep_record}"
            )

        candidates.append(
            (
                doe_case.case_id,
                case_run_id,
                trial_run_id,
                prep_record,
            )
        )

    selected = candidates[
        : args.limit
    ]

    print()
    print(
        f"Remaining unsolved Trial-1 cases : "
        f"{len(candidates)}"
    )

    print(
        f"Selected for this wave           : "
        f"{len(selected)}"
    )

    print(
        f"Worker ceiling                   : "
        f"{args.workers}"
    )

    print()

    for index, (
        case_id,
        case_run_id,
        trial_run_id,
        prep_record,
    ) in enumerate(
        selected,
        start=1,
    ):
        print(
            f"{index:02d}. "
            f"{case_id:<12} "
            f"{trial_run_id}"
        )
        print(
            f"    Prep: {prep_record}"
        )

    if args.dry_run:
        print()
        print("=" * 118)
        print(
            "DRY RUN PASS"
        )
        print(
            "CalculiX invoked : NO"
        )
        print(
            "Files solved     : 0"
        )
        print("=" * 118)

        return 0

    if not selected:
        print(
            "No unsolved Trial-1 cases remain."
        )
        return 0

    print()
    print("=" * 118)
    print(
        "LIVE WAVE START"
    )
    print(
        f"Concurrent workers : {args.workers}"
    )
    print("=" * 118)

    results = []

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.workers
    ) as pool:

        futures = {
            pool.submit(
                run_case,
                case_id,
                case_run_id,
            ): case_id
            for (
                case_id,
                case_run_id,
                _,
                _,
            ) in selected
        }

        for future in (
            concurrent.futures.as_completed(
                futures
            )
        ):
            result = future.result()
            results.append(result)

            case_id, return_code, log_path = result

            print(
                f"FINISHED {case_id}: "
                f"return_code={return_code}"
            )
            print(
                f"         log={log_path}"
            )

    failures = [
        result
        for result in results
        if result[1] != 0
    ]

    print()
    print("=" * 118)
    print(
        "LIVE WAVE COMPLETE"
    )
    print(
        f"Cases completed : {len(results)}"
    )
    print(
        f"Failures        : {len(failures)}"
    )
    print("=" * 118)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

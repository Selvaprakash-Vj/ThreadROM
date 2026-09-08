from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import sys

from pathlib import Path


ROOT = Path(r"D:\ThreadROM")

CAMPAIGN_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp8_production_doe"
    / "TRM-PDOE-C01"
)

CERTIFICATION_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_rollout_preparation_certification.json"
)

EXECUTOR = (
    ROOT
    / "scripts"
    / "run_phase3_warm_start_v2_1_rollout_case.py"
)

LOG_ROOT = (
    CAMPAIGN_ROOT
    / "batch_logs"
    / "v2_1_rollout"
)

EXPECTED_CERTIFICATION_SHA256 = (
    "a11662817427d9131b92f798e953d116"
    "269ad672c49434365a75f68dac4709a7"
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a bounded-concurrency wave of independently "
            "certified Warm-Start V2.1 Production DOE first shots."
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

    if not 1 <= args.limit <= 4:
        parser.error(
            "--limit must be between 1 and 4."
        )

    return args


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


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def manifest_state(
    manifest_path: Path,
) -> tuple[str, str]:
    if not manifest_path.exists():
        return "UNSOLVED", "-"

    try:
        manifest = load_json(
            manifest_path
        )
    except Exception as exc:
        return (
            "BLOCKED_INVALID_MANIFEST",
            str(exc),
        )

    return (
        "EXISTING",
        (
            f"disposition={manifest.get('disposition')}, "
            f"return_code={manifest.get('return_code')}, "
            f"job_finished={manifest.get('job_finished')}, "
            f"accepted_increments="
            f"{manifest.get('accepted_increment_count')}"
        ),
    )


def run_case(
    case_id: str,
    run_id: str,
) -> tuple[str, int, Path]:
    LOG_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_path = (
        LOG_ROOT
        / f"{run_id}.log"
    )

    command = [
        sys.executable,
        str(EXECUTOR),
        "--case-id",
        case_id,
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
    args = parse_arguments()

    if not EXECUTOR.is_file():
        raise FileNotFoundError(
            EXECUTOR
        )

    certification_sha = sha256(
        CERTIFICATION_PATH
    )

    if (
        certification_sha
        != EXPECTED_CERTIFICATION_SHA256
    ):
        raise RuntimeError(
            "Rollout certification SHA drift.\n"
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
            "Rollout preparation is not "
            "FINAL / READY_FOR_FEM."
        )

    authorization = certification[
        "rollout_execution_authorization"
    ]

    if (
        authorization.get("authorized")
        is not True
        or authorization.get(
            "authorized_trial"
        )
        != "V2_1_FIRST_SHOT_ONLY"
        or authorization.get(
            "maximum_concurrent_calculix_runs"
        )
        != 4
    ):
        raise RuntimeError(
            "Certified rollout execution "
            "authorization drift."
        )

    if (
        authorization.get(
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
            "Frozen-model / holdout governance drift."
        )

    authorized_ids = tuple(
        authorization[
            "authorized_case_ids"
        ]
    )

    if (
        len(authorized_ids) != 14
        or len(set(authorized_ids)) != 14
    ):
        raise RuntimeError(
            "Certified rollout set must contain "
            "exactly 14 unique cases."
        )

    rows = certification[
        "certified_rollout_cases"
    ]

    row_by_id = {
        row["case_id"]: row
        for row in rows
    }

    if set(row_by_id) != set(
        authorized_ids
    ):
        raise RuntimeError(
            "Certified case rows do not match "
            "authorized case IDs."
        )

    candidates = []

    print("=" * 128)
    print(
        "THREADROM - WARM-START V2.1 "
        "PRODUCTION DOE ROLLOUT WAVE COORDINATOR"
    )
    print("=" * 128)

    print()
    print(
        "Certification SHA256         :",
        certification_sha,
    )
    print(
        "Authorized case count        :",
        len(authorized_ids),
    )
    print(
        "Maximum concurrency          :",
        authorization[
            "maximum_concurrent_calculix_runs"
        ],
    )
    print(
        "V2.1 model frozen            : YES"
    )
    print(
        "Blind holdout execution      : NOT AUTHORIZED"
    )

    print()

    for case_id in authorized_ids:
        if case_id.startswith("H"):
            raise RuntimeError(
                f"Holdout leaked into rollout "
                f"authorization: {case_id}"
            )

        row = row_by_id[
            case_id
        ]

        run_id = row[
            "run_id"
        ]

        deck_path = (
            ROOT
            / row[
                "deck_relative_path"
            ]
        )

        if sha256(
            deck_path
        ) != row[
            "deck_sha256"
        ]:
            raise RuntimeError(
                f"{case_id}: certified deck SHA drift."
            )

        run_dir = deck_path.parent

        manifest_path = (
            run_dir
            / "fem_run_manifest.json"
        )

        status, detail = manifest_state(
            manifest_path
        )

        if (
            status
            == "BLOCKED_INVALID_MANIFEST"
        ):
            raise RuntimeError(
                f"{case_id}: invalid existing "
                f"manifest: {detail}"
            )

        if status == "EXISTING":
            print(
                f"SKIP  {case_id:<12} "
                f"{run_id} | {detail}"
            )
            continue

        candidates.append(
            (
                case_id,
                run_id,
                manifest_path,
            )
        )

    selected = candidates[
        : args.limit
    ]

    print()
    print(
        "Remaining unsolved certified :",
        len(candidates),
    )
    print(
        "Selected for this wave       :",
        len(selected),
    )
    print(
        "Worker ceiling               :",
        args.workers,
    )

    print()

    for index, (
        case_id,
        run_id,
        manifest_path,
    ) in enumerate(
        selected,
        start=1,
    ):
        print(
            f"{index:02d}. "
            f"{case_id:<12} "
            f"{run_id}"
        )
        print(
            "    Manifest:",
            manifest_path,
        )

    if args.dry_run:
        print()
        print("=" * 128)
        print(
            "V2.1 ROLLOUT WAVE DRY RUN PASS"
        )
        print(
            "Selected cases              :",
            len(selected),
        )
        print(
            "CalculiX invoked            : NO"
        )
        print(
            "FEM launches                : 0"
        )
        print(
            "Blind holdouts accessed     : NO"
        )
        print("=" * 128)

        return 0

    if not selected:
        print()
        print(
            "No unsolved certified V2.1 "
            "first-shot cases remain."
        )
        return 0

    print()
    print("=" * 128)
    print(
        "V2.1 LIVE ROLLOUT WAVE START"
    )
    print(
        "Concurrent workers          :",
        args.workers,
    )
    print(
        "Cases in wave               :",
        len(selected),
    )
    print("=" * 128)

    results = []

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.workers
    ) as pool:
        futures = {
            pool.submit(
                run_case,
                case_id,
                run_id,
            ): case_id
            for (
                case_id,
                run_id,
                _,
            ) in selected
        }

        for future in (
            concurrent.futures.as_completed(
                futures
            )
        ):
            result = future.result()

            results.append(
                result
            )

            (
                case_id,
                return_code,
                log_path,
            ) = result

            print(
                f"FINISHED {case_id}: "
                f"return_code={return_code}"
            )
            print(
                f"         log={log_path}"
            )

    failures = [
        row
        for row in results
        if row[1] != 0
    ]

    print()
    print("=" * 128)
    print(
        "V2.1 LIVE ROLLOUT WAVE COMPLETE"
    )
    print(
        "Cases completed             :",
        len(results),
    )
    print(
        "Executor failures           :",
        len(failures),
    )
    print("=" * 128)

    return (
        1
        if failures
        else 0
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
"""Persistent governed Production-DOE FEM worker coordinator."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import threading
import time

from pathlib import Path

from threadrom.factory.fem_factory_registry import (
    FemFactoryClaim,
    FemFactoryJobState,
    FemFactoryPriority,
    FemFactoryRegistry,
)
from threadrom.factory.windows_process_adjudication import (
    FemProcessStatus,
    adjudicate_live_fem_processes,
)
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

FACTORY_DATABASE = (
    CAMPAIGN_ROOT
    / "factory"
    / "phase3_production_doe.sqlite3"
)

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

LEASE_SECONDS = 300
HEARTBEAT_SECONDS = 30


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the persistent governed Phase-3 Production DOE "
            "Trial-1 FEM factory."
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


def project_relative(path: Path) -> str:
    return path.resolve().relative_to(
        ROOT.resolve()
    ).as_posix()


def inspect_manifest(
    manifest_path: Path,
) -> tuple[str, dict[str, object] | None, str]:
    if not manifest_path.is_file():
        return "MISSING", None, "-"

    try:
        payload = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        return (
            "INVALID",
            None,
            str(exc),
        )

    disposition = str(
        payload.get(
            "disposition",
            "UNKNOWN",
        )
    ).lower()

    if disposition == "succeeded":
        return "SUCCEEDED", payload, "-"

    if disposition == "failed":
        return "FAILED", payload, "-"

    return (
        "INVALID",
        payload,
        f"Unsupported disposition: {disposition}",
    )


def transition_existing_manifest(
    registry: FemFactoryRegistry,
    claim: FemFactoryClaim,
    manifest_path: Path,
) -> tuple[str, int]:
    status, payload, detail = inspect_manifest(
        manifest_path
    )

    relative_manifest = project_relative(
        manifest_path
    )

    if status == "SUCCEEDED":
        registry.transition_claimed_job(
            claim,
            new_state=FemFactoryJobState.SOLVED,
            manifest_path=relative_manifest,
        )
        return "RECONCILED_EXISTING_SUCCESS", 0

    if status == "FAILED":
        assert payload is not None

        category = str(
            payload.get(
                "failure_category",
                "solver_failure",
            )
        )

        message = str(
            payload.get(
                "failure_message",
                "Existing FEM run manifest reports failure.",
            )
        )

        registry.transition_claimed_job(
            claim,
            new_state=FemFactoryJobState.FAILED,
            manifest_path=relative_manifest,
            failure_category=category,
            failure_message=message,
        )

        return "RECONCILED_EXISTING_FAILURE", 1

    registry.transition_claimed_job(
        claim,
        new_state=FemFactoryJobState.QUARANTINED,
        failure_message=(
            "Existing FEM run manifest is invalid: "
            f"{detail}"
        ),
    )

    return "QUARANTINED_INVALID_MANIFEST", 2


def terminate_stale_worker_process(
    process: subprocess.Popen[str],
) -> None:
    if process.poll() is not None:
        return

    process.terminate()

    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def run_claimed_case(
    registry: FemFactoryRegistry,
    claim: FemFactoryClaim,
) -> tuple[str, int, Path, str]:
    case_run_id = claim.run_id.rsplit(
        "_cal_",
        maxsplit=1,
    )[0]

    run_dir = (
        SOLVER_ROOT
        / case_run_id
        / claim.run_id
    )

    manifest_path = (
        run_dir
        / "fem_run_manifest.json"
    )

    log_root = (
        CAMPAIGN_ROOT
        / "batch_logs"
        / "persistent_trial1_wave"
    )

    log_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    log_path = (
        log_root
        / f"{claim.run_id}.log"
    )

    existing_status, _, _ = inspect_manifest(
        manifest_path
    )

    if existing_status != "MISSING":
        status, return_code = transition_existing_manifest(
            registry,
            claim,
            manifest_path,
        )

        return (
            claim.case_hash,
            return_code,
            log_path,
            status,
        )

    command = [
        sys.executable,
        str(EXECUTOR),
        "--case-id",
        claim.case_hash
        if False
        else "",
    ]

    # The governed executor addresses Production-DOE cases by case ID.
    command = [
        sys.executable,
        str(EXECUTOR),
        "--case-id",
        registry.get_job(
            case_hash=claim.case_hash,
            trial_index=claim.trial_index,
        ).case_id,
        "--trial-index",
        str(claim.trial_index),
    ]

    active_claim = claim

    try:
        with log_path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as log:

            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
            )

            next_heartbeat = (
                time.monotonic()
                + HEARTBEAT_SECONDS
            )

            while True:
                return_code = process.poll()

                if return_code is not None:
                    break

                now = time.monotonic()

                if now >= next_heartbeat:
                    try:
                        active_claim = (
                            registry.heartbeat_claim(
                                active_claim,
                                lease_seconds=LEASE_SECONDS,
                            )
                        )
                    except Exception:
                        terminate_stale_worker_process(
                            process
                        )
                        raise

                    next_heartbeat = (
                        now
                        + HEARTBEAT_SECONDS
                    )

                time.sleep(1.0)

    except Exception as exc:
        try:
            registry.transition_claimed_job(
                active_claim,
                new_state=FemFactoryJobState.FAILED,
                failure_category="orchestration_error",
                failure_message=str(exc),
            )
        except Exception:
            pass

        return (
            claim.case_hash,
            99,
            log_path,
            "ORCHESTRATION_ERROR",
        )

    manifest_status, payload, detail = inspect_manifest(
        manifest_path
    )

    if manifest_status == "SUCCEEDED":
        registry.transition_claimed_job(
            active_claim,
            new_state=FemFactoryJobState.SOLVED,
            manifest_path=project_relative(
                manifest_path
            ),
        )

        return (
            claim.case_hash,
            return_code,
            log_path,
            "SOLVED",
        )

    if manifest_status == "FAILED":
        assert payload is not None

        registry.transition_claimed_job(
            active_claim,
            new_state=FemFactoryJobState.FAILED,
            manifest_path=project_relative(
                manifest_path
            ),
            failure_category=str(
                payload.get(
                    "failure_category",
                    "solver_failure",
                )
            ),
            failure_message=str(
                payload.get(
                    "failure_message",
                    "FEM run manifest reports failure.",
                )
            ),
        )

        return (
            claim.case_hash,
            1,
            log_path,
            "FAILED_MANIFEST",
        )

    if manifest_status == "INVALID":
        registry.transition_claimed_job(
            active_claim,
            new_state=FemFactoryJobState.QUARANTINED,
            failure_message=(
                "Generated FEM run manifest is invalid: "
                f"{detail}"
            ),
        )

        return (
            claim.case_hash,
            2,
            log_path,
            "QUARANTINED_INVALID_MANIFEST",
        )

    registry.transition_claimed_job(
        active_claim,
        new_state=FemFactoryJobState.FAILED,
        failure_category=(
            "missing_required_output"
            if return_code == 0
            else "nonzero_exit"
        ),
        failure_message=(
            "Executor finished without an immutable FEM run manifest. "
            f"return_code={return_code}"
        ),
    )

    return (
        claim.case_hash,
        return_code if return_code != 0 else 3,
        log_path,
        "FAILED_NO_MANIFEST",
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
        "THREADROM ? PERSISTENT GOVERNED PRODUCTION DOE "
        "TRIAL-1 FEM FACTORY"
    )
    print("=" * 118)

    for doe_case in campaign.design_cases:

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

        manifest_status, _, detail = inspect_manifest(
            manifest_path
        )

        if manifest_status == "INVALID":
            raise RuntimeError(
                f"{doe_case.case_id}: invalid existing manifest: "
                f"{detail}"
            )

        if manifest_status in {
            "SUCCEEDED",
            "FAILED",
        }:
            print(
                f"EXISTING {doe_case.case_id:<12} "
                f"{trial_run_id} | {manifest_status}"
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
                doe_case.case_hash,
                trial_run_id,
                prep_record,
            )
        )

    print()
    print(
        f"Unsolved prepared candidates : {len(candidates)}"
    )
    print(
        f"Worker ceiling              : {args.workers}"
    )
    print(
        f"Execution claim limit       : {args.limit}"
    )

    if args.dry_run:
        print()
        print(
            "Persistent registry mutation : NO"
        )
        print(
            "CalculiX invoked             : NO"
        )
        print()

        for index, (
            case_id,
            _,
            run_id,
            prep_record,
        ) in enumerate(
            candidates[: args.limit],
            start=1,
        ):
            print(
                f"{index:02d}. {case_id:<12} {run_id}"
            )
            print(
                f"    Prep: {prep_record}"
            )

        print()
        print("DRY RUN PASS")
        return 0

    registry = FemFactoryRegistry(
        FACTORY_DATABASE
    )
    registry.initialize()

    for (
        case_id,
        case_hash,
        run_id,
        prep_record,
    ) in candidates:

        record = registry.register_job(
            case_id=case_id,
            case_hash=case_hash,
            trial_index=1,
            run_id=run_id,
            priority=(
                FemFactoryPriority.HIGH_INFORMATION_DOE
            ),
        )

        if record.state is FemFactoryJobState.PLANNED:
            registry.transition_job(
                case_hash=case_hash,
                trial_index=1,
                new_state=FemFactoryJobState.PREPARED,
                preparation_record=project_relative(
                    prep_record
                ),
            )

    # --------------------------------------------------------------
    # STALE RUN ADJUDICATION
    #
    # Recovery priority is highest, but no expired lease may be
    # stolen until the OS confirms that neither the governed executor
    # nor the exact CalculiX run remains live.
    # --------------------------------------------------------------

    recoverable = []

    expired = registry.list_expired_running_jobs()

    if expired:
        print()
        print("STALE RUN ADJUDICATION")

    for stale in expired:
        case_run_id = stale.run_id.rsplit(
            "_cal_",
            maxsplit=1,
        )[0]

        run_dir = (
            SOLVER_ROOT
            / case_run_id
            / stale.run_id
        )

        manifest_path = (
            run_dir
            / "fem_run_manifest.json"
        )

        manifest_status, _, detail = inspect_manifest(
            manifest_path
        )

        if manifest_status in {
            "SUCCEEDED",
            "FAILED",
        }:
            recoverable.append(
                (
                    stale,
                    "MANIFEST_RECONCILIATION",
                )
            )

            print(
                f"RECOVER {stale.case_id:<12} | "
                f"immutable manifest={manifest_status}"
            )
            continue

        if manifest_status == "INVALID":
            print(
                f"HOLD    {stale.case_id:<12} | "
                f"invalid manifest: {detail}"
            )
            continue

        process_state = adjudicate_live_fem_processes(
            run_id=stale.run_id,
            case_id=stale.case_id,
        )

        if (
            process_state.status
            is FemProcessStatus.LIVE_MATCH
        ):
            print(
                f"HOLD    {stale.case_id:<12} | "
                f"live process(es)="
                f"{process_state.matching_process_ids}"
            )
            continue

        if (
            process_state.status
            is FemProcessStatus.UNKNOWN
        ):
            print(
                f"HOLD    {stale.case_id:<12} | "
                f"{process_state.reason}"
            )
            continue

        recoverable.append(
            (
                stale,
                "NO_LIVE_PROCESS",
            )
        )

        print(
            f"RECOVER {stale.case_id:<12} | "
            "expired lease + no manifest + "
            "no matching live process"
        )

    claim_lock = threading.Lock()
    claims_started = 0
    recovery_index = 0

    def worker_loop(
        worker_index: int,
    ) -> list[tuple[str, int, Path, str]]:
        nonlocal claims_started
        nonlocal recovery_index

        worker_results = []

        worker_id = (
            f"persistent-trial1-"
            f"{os.getpid()}-"
            f"{worker_index:02d}"
        )

        while True:
            with claim_lock:
                if claims_started >= args.limit:
                    break

                if recovery_index < len(recoverable):
                    stale, recovery_reason = (
                        recoverable[recovery_index]
                    )
                    recovery_index += 1

                    claim = registry.recover_expired_job(
                        case_hash=stale.case_hash,
                        trial_index=stale.trial_index,
                        expected_generation=(
                            stale.lease_generation
                        ),
                        worker_id=worker_id,
                        lease_seconds=LEASE_SECONDS,
                    )

                    if (
                        recovery_reason
                        == "MANIFEST_RECONCILIATION"
                    ):
                        case_run_id = claim.run_id.rsplit(
                            "_cal_",
                            maxsplit=1,
                        )[0]

                        manifest_path = (
                            SOLVER_ROOT
                            / case_run_id
                            / claim.run_id
                            / "fem_run_manifest.json"
                        )

                        status, return_code = (
                            transition_existing_manifest(
                                registry,
                                claim,
                                manifest_path,
                            )
                        )

                        worker_results.append(
                            (
                                claim.case_hash,
                                return_code,
                                manifest_path,
                                status,
                            )
                        )

                        claims_started += 1
                        continue

                else:
                    claim = registry.claim_next_job(
                        worker_id=worker_id,
                        lease_seconds=LEASE_SECONDS,
                        recover_expired=False,
                    )

                if claim is None:
                    break

                claims_started += 1

            result = run_claimed_case(
                registry,
                claim,
            )

            worker_results.append(
                result
            )

        return worker_results

    print()
    print("=" * 118)
    print(
        "PERSISTENT FACTORY LIVE WAVE START"
    )
    print(
        "Automatic stale-job recovery : GOVERNED"
    )
    print(
        "Recovery requires: expired lease + no authoritative "
        "manifest requiring reconciliation + confirmed absence "
        "of matching executor/CalculiX process."
    )
    print("=" * 118)

    results = []

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=args.workers
    ) as pool:

        futures = [
            pool.submit(
                worker_loop,
                worker_index,
            )
            for worker_index in range(
                1,
                args.workers + 1,
            )
        ]

        for future in (
            concurrent.futures.as_completed(
                futures
            )
        ):
            worker_results = future.result()

            for result in worker_results:
                results.append(result)

                (
                    case_hash,
                    return_code,
                    log_path,
                    status,
                ) = result

                print(
                    f"FINISHED {case_hash[:12]} | "
                    f"return_code={return_code} | "
                    f"status={status}"
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
        "PERSISTENT FACTORY LIVE WAVE COMPLETE"
    )
    print(
        f"Claims executed : {len(results)}"
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

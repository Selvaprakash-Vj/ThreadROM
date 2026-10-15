from __future__ import annotations

import concurrent.futures
import hashlib
import json
import sys
import threading
from pathlib import Path

from threadrom.factory.fem_factory_registry import (
    FemFactoryJobState,
    FemFactoryPriority,
    FemFactoryRegistry,
)

from threadrom.factory.fem_solver_orchestrator import (
    orchestrate_calculix_run,
)

from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
)

from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
)

import threadrom.factory.fem_case_definition_bundle as bundle_mod


ROOT = Path(r"D:\ThreadROM").resolve()

CAMPAIGN_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / "TRM-DDOE-001"
    / "W01"
)

PREPARATION_INDEX = (
    CAMPAIGN_ROOT
    / "w01_trial1_preparation.json"
)

EXPECTED_PREPARATION_SHA = (
    "7e6114c2f78957f01f7ad568a0f90fa6372ef03e88545ad759b0407b83791b75"
)

FACTORY_ROOT = (
    CAMPAIGN_ROOT
    / "factory"
)

FACTORY_DB = (
    FACTORY_ROOT
    / "w01_trial1_factory.sqlite3"
)

EXPECTED_RUNS = {
    "trm_fem_c58fd67718cd_cal_01":
        "6a6566995f71a0c75b7a677c604b94b23a6027c5b3e7833119ce7e14fd8a8009",

    "trm_fem_5b22a5376136_cal_01":
        "46d07690abd4ef43afb626422f65069fc3b648a538ef7f6b9df643bd2df92e94",

    "trm_fem_b8f3cce4a230_cal_01":
        "0db5c5da0b61be95ab6d946ab71182edf1035d73c0c5cd2b56de03a7f1ad0a18",

    "trm_fem_a756711642a5_cal_01":
        "7833dc80e8b8163490208763ab58a96cbcbfcadb48a9e3c13f8b9e04253c27b6",
}

WORKERS = 4

# One hour lease, refreshed every five minutes.
LEASE_SECONDS = 3600
HEARTBEAT_SECONDS = 300


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    require(
        path.is_file()
        and path.stat().st_size > 0,
        f"Required file missing/empty: {path}",
    )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def project_relative(path: Path) -> str:
    return (
        path.resolve()
        .relative_to(ROOT)
        .as_posix()
    )


# ============================================================
# EXACT PREPARATION BINDING
# ============================================================

require(
    sha256(PREPARATION_INDEX)
    == EXPECTED_PREPARATION_SHA,
    "W01 preparation index SHA drift.",
)

wave = json.loads(
    PREPARATION_INDEX.read_text(
        encoding="utf-8-sig"
    )
)

require(
    wave["record_status"] == "FINAL",
    "W01 preparation is not FINAL.",
)

require(
    wave["factory_ready"] is True,
    "W01 is not factory-ready.",
)

require(
    wave["solver_launched"] is False,
    "Preparation index unexpectedly claims a prior solver launch.",
)

require(
    wave[
        "adaptive_continuation_authorized"
    ] is False,
    "CAL_02+ must remain unauthorized.",
)

require(
    wave["holdouts_accessed"] is False,
    "Holdout boundary violated.",
)

rows = wave["prepared_trials"]

require(
    len(rows) == 4,
    "Expected exactly four W01 prepared jobs.",
)

by_run = {
    row["trial_run_id"]: row
    for row in rows
}

require(
    set(by_run) == set(EXPECTED_RUNS),
    "Prepared W01 run cohort drift.",
)


# ============================================================
# VERIFY EVERY PREPARATION RECORD + DECK
# ============================================================

for run_id, expected_deck_sha in EXPECTED_RUNS.items():

    row = by_run[run_id]

    prep_path = (
        ROOT
        / row["preparation_record"]
    )

    require(
        sha256(prep_path)
        == row[
            "preparation_record_sha256"
        ],
        f"{run_id}: preparation-record SHA drift.",
    )

    prep = json.loads(
        prep_path.read_text(
            encoding="utf-8-sig"
        )
    )

    require(
        prep["record_status"]
        == "FINAL",
        f"{run_id}: preparation record is not FINAL.",
    )

    require(
        prep["overall_disposition"]
        == "DIVERSIFIED_DOE_W01_TRIAL1_PREPARATION_PASS",
        f"{run_id}: preparation disposition drift.",
    )

    require(
        prep["trial_1"]["run_id"]
        == run_id,
        f"{run_id}: trial identity mismatch.",
    )

    require(
        int(
            prep["trial_1"]["trial_index"]
        ) == 1,
        f"{run_id}: non-Trial-1 job encountered.",
    )

    require(
        prep["fem_preflight"]["status"]
        == "PASS",
        f"{run_id}: FEM preflight not PASS.",
    )

    require(
        prep[
            "solve_authorization"
        ][
            "trial1_execution_authority_exists"
        ]
        is True,
        f"{run_id}: Trial-1 execution authority absent.",
    )

    require(
        prep[
            "solve_authorization"
        ][
            "adaptive_continuation_authorized"
        ]
        is False,
        f"{run_id}: unexpected continuation authority.",
    )

    require(
        prep[
            "solve_authorization"
        ][
            "holdout_accessed"
        ]
        is False,
        f"{run_id}: holdout access detected.",
    )

    deck_path = (
        ROOT
        / prep["deck"]["relative_path"]
    )

    require(
        sha256(deck_path)
        == expected_deck_sha
        == prep["deck"]["sha256"],
        f"{run_id}: frozen CAL_01 deck SHA drift.",
    )

    run_dir = deck_path.parent

    duplicate_artifacts = [
        run_dir / "fem_run_manifest.json",
        run_dir / f"{run_id}.run_manifest.json",
        run_dir / f"{run_id}.dat",
        run_dir / f"{run_id}.frd",
        run_dir / f"{run_id}.sta",
    ]

    require(
        not any(
            item.exists()
            for item in duplicate_artifacts
        ),
        f"{run_id}: existing solver evidence blocks duplicate launch.",
    )


# ============================================================
# REGISTER EXACT W01 COHORT
# ============================================================

FACTORY_ROOT.mkdir(
    parents=True,
    exist_ok=True,
)

registry = FemFactoryRegistry(
    FACTORY_DB
)

registry.initialize()

print()
print("=" * 112)
print("THREADROM — TRM-DDOE-001-W01 GOVERNED FACTORY LAUNCH")
print("=" * 112)
print("Prepared jobs       : 4")
print("Authorized workers  : 4")
print("Trial               : CAL_01 ONLY")
print("Adaptive CAL_02+    : BLOCKED")
print("Holdouts            : SEALED")
print("Dataset admission   : BLOCKED")
print()


for row in sorted(
    rows,
    key=lambda item: item["wave_order"],
):
    record = registry.register_job(
        case_id=row["case_id"],
        case_hash=row["case_hash"],
        trial_index=1,
        run_id=row["trial_run_id"],
        priority=(
            FemFactoryPriority.HIGH_INFORMATION_DOE
        ),
    )

    if record.state is FemFactoryJobState.PLANNED:

        record = registry.transition_job(
            case_hash=row["case_hash"],
            trial_index=1,
            new_state=(
                FemFactoryJobState.PREPARED
            ),
            preparation_record=(
                row["preparation_record"]
            ),
        )

    require(
        record.state
        is FemFactoryJobState.PREPARED,
        (
            f"{row['trial_run_id']}: expected PREPARED "
            f"factory state, found {record.state}."
        ),
    )

    print(
        "REGISTERED/PREPARED :",
        row["trial_run_id"],
        flush=True,
    )


# ============================================================
# SHORT ATOMIC ADMISSION / DURABLE RESERVATION
# ============================================================

claims = []

for worker_index in range(
    1,
    WORKERS + 1,
):

    worker_id = (
        f"TRM-DDOE-W01-worker-{worker_index:02d}"
    )

    claim = registry.claim_next_job(
        worker_id=worker_id,
        lease_seconds=LEASE_SECONDS,
        recover_expired=False,
    )

    require(
        claim is not None,
        (
            "Factory could not reserve all four "
            "authorized W01 solver slots."
        ),
    )

    claims.append(
        claim
    )

claimed_runs = {
    claim.run_id
    for claim in claims
}

require(
    claimed_runs
    == set(EXPECTED_RUNS),
    "Factory claimed an unexpected job cohort.",
)

print()
print("=== DURABLE FACTORY RESERVATIONS ===")

for claim in claims:
    print(
        claim.worker_id,
        "->",
        claim.run_id,
        "| lease generation",
        claim.lease_generation,
        flush=True,
    )


# ============================================================
# SOLVER BACKEND
# ============================================================

transfer = (
    load_complete_joint_calculix_transfer_definition(
        ROOT
        / "config"
        / "complete_joint_calculix_transfer.toml"
    )
)

backend = (
    bundle_mod
    .PHASE2_CERTIFIED_FEM_PROFILE
    .backend
)


def heartbeat_loop(
    claim,
    stop_event,
    failures,
):
    while not stop_event.wait(
        HEARTBEAT_SECONDS
    ):
        try:
            registry.heartbeat_claim(
                claim,
                lease_seconds=LEASE_SECONDS,
            )

        except Exception as exc:
            failures.append(
                f"{type(exc).__name__}: {exc}"
            )
            return


def execute_claim(claim):

    row = by_run[
        claim.run_id
    ]

    prep_path = (
        ROOT
        / row["preparation_record"]
    )

    prep = json.loads(
        prep_path.read_text(
            encoding="utf-8-sig"
        )
    )

    input_path = (
        ROOT
        / prep["deck"]["relative_path"]
    )

    manifest_path = (
        input_path.parent
        / "fem_run_manifest.json"
    )

    definition = CalculixJobDefinition(
        executable_relative_path=(
            transfer.executable_relative_path
        ),
        job_name=claim.run_id,
        timeout_seconds=None,
    )

    stop_heartbeat = threading.Event()
    heartbeat_failures = []

    heartbeat = threading.Thread(
        target=heartbeat_loop,
        args=(
            claim,
            stop_heartbeat,
            heartbeat_failures,
        ),
        name=(
            f"heartbeat-{claim.run_id}"
        ),
        daemon=True,
    )

    heartbeat.start()

    print()
    print(
        "SOLVER START :",
        claim.run_id,
        "| worker:",
        claim.worker_id,
        flush=True,
    )

    try:

        orchestrate_calculix_run(
            project_root=ROOT,
            input_path=input_path,
            definition=definition,
            run_id=claim.run_id,
            case_hash=claim.case_hash,
            backend_policy_id=(
                backend.policy_id
            ),
            solver_name=(
                backend.solver_name
            ),
            solver_version=(
                backend.solver_version
            ),
            manifest_path=manifest_path,
        )

        stop_heartbeat.set()
        heartbeat.join(
            timeout=10
        )

        require(
            not heartbeat_failures,
            (
                f"{claim.run_id}: lease heartbeat failed: "
                + "; ".join(
                    heartbeat_failures
                )
            ),
        )

        require(
            manifest_path.is_file(),
            (
                f"{claim.run_id}: governed solver "
                "manifest missing."
            ),
        )

        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8-sig"
            )
        )

        disposition = str(
            manifest.get(
                "disposition",
                "",
            )
        ).lower()

        if disposition == "succeeded":

            registry.transition_claimed_job(
                claim,
                new_state=(
                    FemFactoryJobState.SOLVED
                ),
                manifest_path=(
                    project_relative(
                        manifest_path
                    )
                ),
            )

            print(
                "SOLVER DONE  :",
                claim.run_id,
                "| SUCCEEDED",
                flush=True,
            )

            return (
                claim.run_id,
                "SUCCEEDED",
            )

        failure_category = str(
            manifest.get(
                "failure_category",
                "SOLVER_FAILURE",
            )
            or "SOLVER_FAILURE"
        )

        failure_message = str(
            manifest.get(
                "failure_message",
                "Governed CalculiX run failed.",
            )
            or "Governed CalculiX run failed."
        )

        registry.transition_claimed_job(
            claim,
            new_state=(
                FemFactoryJobState.FAILED
            ),
            manifest_path=(
                project_relative(
                    manifest_path
                )
            ),
            failure_category=(
                failure_category
            ),
            failure_message=(
                failure_message
            ),
        )

        print(
            "SOLVER DONE  :",
            claim.run_id,
            "| FAILED |",
            failure_category,
            flush=True,
        )

        return (
            claim.run_id,
            "FAILED",
        )

    except Exception as exc:

        stop_heartbeat.set()
        heartbeat.join(
            timeout=10
        )

        try:
            registry.transition_claimed_job(
                claim,
                new_state=(
                    FemFactoryJobState.FAILED
                ),
                failure_category=(
                    "FACTORY_EXECUTION_EXCEPTION"
                ),
                failure_message=(
                    f"{type(exc).__name__}: {exc}"
                ),
            )
        except Exception:
            pass

        print(
            "SOLVER EXCEPTION :",
            claim.run_id,
            "|",
            type(exc).__name__,
            "|",
            exc,
            flush=True,
        )

        return (
            claim.run_id,
            "FAILED",
        )


# ============================================================
# FIRE THE FOUR AUTHORIZED CAL_01 JOBS
# ============================================================

print()
print("=" * 112)
print("W01 FOUR-WAY CALCULIX LAUNCH")
print("=" * 112)

results = []

with concurrent.futures.ThreadPoolExecutor(
    max_workers=WORKERS
) as pool:

    future_map = {
        pool.submit(
            execute_claim,
            claim,
        ): claim
        for claim in claims
    }

    for future in concurrent.futures.as_completed(
        future_map
    ):
        results.append(
            future.result()
        )


# ============================================================
# WAVE EXECUTION SUMMARY
# ============================================================

results.sort()

failed = [
    item
    for item in results
    if item[1] != "SUCCEEDED"
]

print()
print("=" * 112)
print("TRM-DDOE-001-W01 — CAL_01 FACTORY EXECUTION COMPLETE")
print("=" * 112)

for run_id, status in results:
    print(
        run_id,
        "=>",
        status,
    )

print()
print(
    "Succeeded :",
    len(results) - len(failed),
)

print(
    "Failed    :",
    len(failed),
)

print()
print("CAL_02+            : NOT LAUNCHED")
print("Dataset admission  : NO")
print("Holdouts accessed  : NO")
print("Factory database   :", project_relative(FACTORY_DB))

if failed:
    print()
    print(
        "W01 CAL_01 FACTORY RESULT: ATTENTION REQUIRED"
    )
    raise SystemExit(1)

print()
print(
    "W01 CAL_01 FACTORY RESULT: ALL FOUR SOLVES SUCCEEDED"
)
print(
    "Next stage: governed result extraction + "
    "adaptive calibration decisions."
)

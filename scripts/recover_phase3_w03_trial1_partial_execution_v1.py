from __future__ import annotations

import hashlib
import json

from pathlib import Path


from threadrom.factory import (
    fem_case_definition_bundle as bundle_mod,
)

from threadrom.factory.diversified_calculix_worker_adapter import (
    GovernedCalculixExecutionSpec,
    make_claimed_calculix_executor,
)

from threadrom.factory.diversified_factory_worker import (
    execute_claimed_factory_job,
)

from threadrom.factory.diversified_parallel_admission import (
    claim_parallel_factory_slot,
)

from threadrom.factory.fem_factory_registry import (
    FemFactoryJobState,
    FemFactoryPriority,
    FemFactoryRegistry,
)

from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
)

from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
)


ROOT = Path(r"D:\ThreadROM").resolve()
CONFIG = ROOT / "config"

CAMPAIGN_ID = "TRM-DDOE-001"
WAVE_ID = "TRM-DDOE-001-W03"
WAVE_TOKEN = "W03"

EXPECTED_WAVE_SHA = (
    "3714441cb14386e2fcc3adf7b90300a1"
    "dcec6ebd2d4404212f2a1adbacb3b225"
)

EXPECTED_PREPARATION_SHA = (
    "813b602392dd66cf0b30e2089b3695c8"
    "e8ae0859946da775bfc1736efd404393"
)

EXPECTED_EXECUTION_AUTH_SHA = (
    "60afcb826a2c8228ac405d4d0c772e7c"
    "fb2a6a625a18685b32d8c661c56b59fc"
)

EXPECTED_PREFLIGHT_SHA = (
    "67d29a5307c44b478b8d7caab3d9d43f"
    "e97c357c2d8cdf716c360eed6574605c"
)

EXPECTED_PRELAUNCH_REGISTRY_SHA = (
    "51c6d63a0b99fbce88d9a2f2563857dc"
    "31ae44c47f47185c4fefe45200a10c7f"
)

REMAINING_CASE_ID = (
    "TRM-DDOE-D-M12x1_75__steel_member-03"
)

REMAINING_RUN_ID = (
    "trm_fem_323293011028_cal_01"
)

EXPECTED_REMAINING_DECK_SHA = (
    "72fc829943d310807a07855ae1d6f60e"
    "01f6c93655b8152a5bc7a466886b9653"
)

LEASE_SECONDS = 900
HEARTBEAT_SECONDS = 60


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    require(
        path.is_file(),
        f"Required file missing: {path}",
    )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def load_json(path: Path):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def canonical_json_bytes(payload: dict) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def write_immutable_json(
    path: Path,
    payload: dict,
) -> str:

    encoded = canonical_json_bytes(payload)

    digest = hashlib.sha256(
        encoded
    ).hexdigest()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if path.exists():
        require(
            path.read_bytes() == encoded,
            f"Immutable JSON conflict: {path}",
        )
        return digest

    path.write_bytes(encoded)

    return digest


def repository_path(value: str) -> Path:
    candidate = Path(value)

    if not candidate.is_absolute():
        candidate = ROOT / candidate

    candidate = candidate.resolve()

    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError(
            f"Path escapes repository: {value}"
        ) from exc

    return candidate


def relative(path: Path) -> str:
    return (
        path.resolve()
        .relative_to(ROOT)
        .as_posix()
    )


# ==============================================================================
# Paths
# ==============================================================================

wave_root = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "waves"
    / WAVE_ID
)

wave_path = wave_root / "wave_plan.json"

authorization_path = (
    wave_root
    / "trial1_execution_owner_authorization.json"
)

preflight_path = (
    wave_root
    / "trial1_execution_preflight.json"
)

adaptive_auth_path = (
    wave_root
    / "adaptive_campaign_owner_authorization.json"
)

campaign_root = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / CAMPAIGN_ID
    / WAVE_TOKEN
)

preparation_path = (
    campaign_root
    / "w03_trial1_preparation.json"
)

factory_root = (
    campaign_root
    / "factory"
)

registry_path = (
    factory_root
    / "w03_trial1_factory.sqlite3"
)

admission_lock = (
    factory_root
    / "w03_trial1_parallel_admission.lock"
)

execution_summary_path = (
    factory_root
    / "w03_trial1_execution_summary.json"
)


# ==============================================================================
# Immutable launch authority still valid
# ==============================================================================

print()
print("=== GOVERNED RECOVERY PINS ===")

for label, path, expected in (
    (
        "Wave plan",
        wave_path,
        EXPECTED_WAVE_SHA,
    ),
    (
        "Trial-1 preparation",
        preparation_path,
        EXPECTED_PREPARATION_SHA,
    ),
    (
        "CAL_01 execution authorization",
        authorization_path,
        EXPECTED_EXECUTION_AUTH_SHA,
    ),
    (
        "CAL_01 preflight",
        preflight_path,
        EXPECTED_PREFLIGHT_SHA,
    ),
):

    actual = sha256(path)

    require(
        actual == expected,
        (
            f"{label} SHA drift.\n"
            f"expected={expected}\n"
            f"actual={actual}"
        ),
    )

    print(
        "PASS:",
        label,
        actual,
    )


require(
    not adaptive_auth_path.exists(),
    "Adaptive CAL_02+ authorization unexpectedly exists.",
)

require(
    not execution_summary_path.exists(),
    (
        "Final CAL_01 execution summary already exists. "
        "Refusing recovery launch."
    ),
)


preparation = load_json(
    preparation_path
)

authorization = load_json(
    authorization_path
)


require(
    authorization[
        "authorization_type"
    ]
    == "OWNER_WAVE_CAL_01_ONLY_EXECUTION_AUTHORIZATION",
    "Wrong execution authorization.",
)

require(
    authorization[
        "execution_contract"
    ][
        "authorized_trial_index"
    ]
    == 1,
    "Authorization is not CAL_01-only.",
)

require(
    authorization[
        "execution_contract"
    ][
        "adaptive_cal_02_plus_authorized"
    ]
    is False,
    "Adaptive CAL_02+ unexpectedly authorized.",
)


# ==============================================================================
# Recover exact durable registry state
# ==============================================================================

registry = FemFactoryRegistry(
    registry_path
)

jobs = registry.list_jobs()


require(
    len(jobs) == 4,
    f"Expected four registry jobs; found {len(jobs)}.",
)


solved = tuple(
    job
    for job in jobs
    if job.state
    is FemFactoryJobState.SOLVED
)

prepared = tuple(
    job
    for job in jobs
    if job.state
    is FemFactoryJobState.PREPARED
)

running = tuple(
    job
    for job in jobs
    if job.state
    is FemFactoryJobState.RUNNING
)

failed_or_quarantined = tuple(
    job
    for job in jobs
    if job.state
    in {
        FemFactoryJobState.FAILED,
        FemFactoryJobState.QUARANTINED,
    }
)


require(
    len(solved) == 3,
    (
        "Recovery requires exactly three SOLVED jobs; "
        f"found {len(solved)}."
    ),
)

require(
    len(prepared) == 1,
    (
        "Recovery requires exactly one PREPARED job; "
        f"found {len(prepared)}."
    ),
)

require(
    not running,
    "RUNNING registry jobs still exist. Refusing recovery.",
)

require(
    not failed_or_quarantined,
    (
        "FAILED/QUARANTINED jobs exist. "
        "Different recovery path required."
    ),
)


remaining = prepared[0]


require(
    remaining.case_id
    == REMAINING_CASE_ID,
    (
        "Unexpected remaining case: "
        f"{remaining.case_id}"
    ),
)

require(
    remaining.run_id
    == REMAINING_RUN_ID,
    (
        "Unexpected remaining run: "
        f"{remaining.run_id}"
    ),
)

require(
    remaining.trial_index == 1,
    "Remaining job is not CAL_01.",
)

require(
    remaining.priority
    is FemFactoryPriority.HIGH_INFORMATION_DOE,
    "Remaining job priority drift.",
)

require(
    remaining.lease_generation == 0,
    "Remaining job has already been claimed.",
)

require(
    remaining.lease_owner is None,
    "Remaining job already has a lease owner.",
)

require(
    remaining.manifest_path is None,
    "Remaining job already has a manifest.",
)


print()
print("=== DURABLE PARTIAL STATE ===")

for job in jobs:
    print(
        f"{job.run_id:<34} "
        f"{job.state.value.upper():<10} "
        f"lease={job.lease_generation}"
    )


# ==============================================================================
# Three completed jobs must be immutable successful evidence
# ==============================================================================

for job in solved:

    require(
        job.manifest_path is not None,
        f"{job.run_id}: SOLVED job lacks manifest.",
    )

    manifest_path = repository_path(
        job.manifest_path
    )

    require(
        manifest_path.is_file(),
        f"{job.run_id}: manifest missing.",
    )

    manifest = load_json(
        manifest_path
    )

    require(
        str(
            manifest.get(
                "disposition"
            )
        ).lower()
        == "succeeded",
        (
            f"{job.run_id}: existing manifest does "
            "not report succeeded."
        ),
    )

    require(
        manifest.get(
            "run_id"
        )
        == job.run_id,
        f"{job.run_id}: manifest run identity drift.",
    )

    require(
        manifest.get(
            "case_hash"
        )
        == job.case_hash,
        f"{job.run_id}: manifest case SHA drift.",
    )


print(
    "PASS: existing 3/3 SOLVED jobs and manifests verified."
)


# ==============================================================================
# Locate remaining frozen preparation/deck
# ==============================================================================

prep_rows = {
    row[
        "case_hash"
    ]: row
    for row in preparation[
        "prepared_trials"
    ]
}

row = prep_rows[
    remaining.case_hash
]


require(
    row[
        "case_id"
    ]
    == REMAINING_CASE_ID,
    "Remaining preparation identity drift.",
)

require(
    row[
        "trial_run_id"
    ]
    == REMAINING_RUN_ID,
    "Remaining preparation run identity drift.",
)

require(
    row[
        "deck_sha256"
    ]
    == EXPECTED_REMAINING_DECK_SHA,
    "Remaining deck SHA binding drift.",
)


prep_record_path = repository_path(
    row[
        "preparation_record"
    ]
)

require(
    sha256(
        prep_record_path
    )
    == row[
        "preparation_record_sha256"
    ],
    "Remaining preparation-record SHA drift.",
)


prep_record = load_json(
    prep_record_path
)

deck_path = repository_path(
    prep_record[
        "deck"
    ][
        "relative_path"
    ]
)

manifest_path = (
    deck_path.parent
    / "fem_run_manifest.json"
)


require(
    sha256(deck_path)
    == EXPECTED_REMAINING_DECK_SHA,
    "Remaining CAL_01 deck SHA drift.",
)

require(
    deck_path.name
    == f"{REMAINING_RUN_ID}.inp",
    "Remaining deck/run identity drift.",
)


authorized_by_hash = {
    item[
        "case_hash"
    ]: item
    for item in authorization[
        "authorized_trials"
    ]
}


authorized = authorized_by_hash[
    remaining.case_hash
]


require(
    authorized[
        "trial_run_id"
    ]
    == REMAINING_RUN_ID,
    "Remaining job absent from owner authorization.",
)

require(
    authorized[
        "deck_sha256"
    ]
    == EXPECTED_REMAINING_DECK_SHA,
    "Remaining authorization deck SHA drift.",
)

require(
    relative(deck_path)
    == authorized[
        "deck_path"
    ],
    "Remaining authorization deck path drift.",
)

require(
    relative(manifest_path)
    == authorized[
        "manifest_path"
    ],
    "Remaining authorization manifest path drift.",
)


# Absolute duplicate-execution guard.
require(
    not manifest_path.exists(),
    "Remaining CAL_01 manifest already exists.",
)

for suffix in (
    ".dat",
    ".frd",
    ".sta",
    ".cvg",
    ".rout",
):
    require(
        not (
            deck_path.parent
            / f"{REMAINING_RUN_ID}{suffix}"
        ).exists(),
        (
            f"Remaining run already has {suffix} evidence. "
            "Refusing duplicate execution."
        ),
    )


print()
print(
    "PASS: remaining M12-steel CAL_01 is pristine and authorized."
)


# ==============================================================================
# Certified execution spec
# ==============================================================================

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
    job_name=REMAINING_RUN_ID,
    timeout_seconds=None,
)


spec = GovernedCalculixExecutionSpec(
    project_root=ROOT,
    input_path=deck_path,
    definition=definition,
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


# ==============================================================================
# Claim exactly one remaining PREPARED job
# ==============================================================================

worker_id = (
    "TRM-DDOE-W03-trial1-recovery-worker-01"
)


print()
print("=" * 108)
print(
    "EXPLICIT RECOVERY LAUNCH - ONE REMAINING CAL_01"
)
print("=" * 108)

print(
    "Case           :",
    REMAINING_CASE_ID,
)

print(
    "Run            :",
    REMAINING_RUN_ID,
)

print(
    "Deck SHA       :",
    EXPECTED_REMAINING_DECK_SHA,
)

print(
    "Concurrent ccx : 1"
)

print(
    "Timeout        : NONE"
)

print(
    "CAL_02+        : BLOCKED"
)


admission = claim_parallel_factory_slot(
    registry=registry,
    lock_path=admission_lock,
    worker_id=worker_id,
    lease_seconds=LEASE_SECONDS,
    maximum_authorized_ccx=1,
)


require(
    admission.claim is not None,
    (
        "Recovery worker could not claim remaining job. "
        f"reason={admission.reason}, "
        f"occupied={admission.occupied_slots}, "
        f"capacity={admission.capacity}"
    ),
)


claim = admission.claim


require(
    claim.run_id
    == REMAINING_RUN_ID,
    (
        "Recovery claimed the wrong job: "
        f"{claim.run_id}"
    ),
)

require(
    claim.case_hash
    == remaining.case_hash,
    "Recovery claim case identity drift.",
)

require(
    claim.trial_index == 1,
    "Recovery claimed non-CAL_01 work.",
)


print()
print(
    "CLAIMED      :",
    claim.run_id,
    "|",
    worker_id,
    "| lease generation",
    claim.lease_generation,
    flush=True,
)

print(
    "SOLVER START :",
    claim.run_id,
    "|",
    worker_id,
    flush=True,
)


record = execute_claimed_factory_job(
    registry=registry,
    claim=claim,
    lease_seconds=LEASE_SECONDS,
    heartbeat_interval_seconds=(
        HEARTBEAT_SECONDS
    ),
    execute=(
        make_claimed_calculix_executor(
            spec
        )
    ),
)


print(
    "SOLVER END   :",
    claim.run_id,
    "|",
    record.state.value.upper(),
    flush=True,
)


require(
    record.state
    is FemFactoryJobState.SOLVED,
    (
        "Remaining CAL_01 did not finish SOLVED; "
        f"state={record.state.value}"
    ),
)

require(
    manifest_path.is_file(),
    "Remaining governed manifest missing.",
)


# ==============================================================================
# Final 4/4 durable state
# ==============================================================================

final_jobs = registry.list_jobs()


require(
    len(final_jobs) == 4,
    "Registry job count changed.",
)

require(
    all(
        job.state
        is FemFactoryJobState.SOLVED
        for job in final_jobs
    ),
    "Final W03 CAL_01 registry is not 4/4 SOLVED.",
)

require(
    all(
        job.trial_index == 1
        for job in final_jobs
    ),
    "CAL_02+ registry work appeared unexpectedly.",
)

require(
    not adaptive_auth_path.exists(),
    "Adaptive authorization appeared unexpectedly.",
)


# ==============================================================================
# Create the final execution summary that original Step 2F did not reach
# ==============================================================================

summary_jobs = []


for job in sorted(
    final_jobs,
    key=lambda item: item.job_id,
):

    require(
        job.manifest_path is not None,
        f"{job.run_id}: missing manifest binding.",
    )

    job_manifest = repository_path(
        job.manifest_path
    )

    require(
        job_manifest.is_file(),
        f"{job.run_id}: manifest missing.",
    )

    manifest = load_json(
        job_manifest
    )

    require(
        str(
            manifest.get(
                "disposition"
            )
        ).lower()
        == "succeeded",
        f"{job.run_id}: manifest not succeeded.",
    )


    summary_jobs.append(
        {
            "job_id":
                job.job_id,

            "case_id":
                job.case_id,

            "case_hash":
                job.case_hash,

            "trial_index":
                job.trial_index,

            "run_id":
                job.run_id,

            "priority":
                job.priority.value,

            "state":
                job.state.value,

            "lease_generation":
                job.lease_generation,

            "manifest_path":
                relative(
                    job_manifest
                ),

            "manifest_sha256":
                sha256(
                    job_manifest
                ),
        }
    )


summary = {
    "schema":
        "threadrom.phase3_governed_wave_trial1_execution_summary.v1",

    "record_status":
        "FINAL",

    "campaign_id":
        CAMPAIGN_ID,

    "wave_id":
        WAVE_ID,

    "bound_artifacts": {
        "wave_plan_sha256":
            EXPECTED_WAVE_SHA,

        "trial1_preparation_sha256":
            EXPECTED_PREPARATION_SHA,

        "trial1_execution_owner_authorization_sha256":
            EXPECTED_EXECUTION_AUTH_SHA,

        "trial1_execution_preflight_sha256":
            EXPECTED_PREFLIGHT_SHA,

        "prelaunch_registry_sha256":
            EXPECTED_PRELAUNCH_REGISTRY_SHA,
    },

    "execution": {
        "authorized_case_count":
            4,

        "executed_case_count":
            4,

        "trial_index":
            1,

        "maximum_concurrent_calculix":
            4,

        "lease_seconds":
            LEASE_SECONDS,

        "heartbeat_seconds":
            HEARTBEAT_SECONDS,

        "solver_timeout_seconds":
            None,

        "all_jobs_solved":
            True,
    },

    "jobs":
        summary_jobs,

    "safety": {
        "duplicate_cal01_execution":
            False,

        "cal02_plus_launched":
            False,

        "adaptive_continuation":
            False,

        "full_physics_certification":
            False,

        "holdouts_accessed":
            False,

        "dataset_admission":
            False,
    },

    "overall_disposition":
        "W03_ALL_FOUR_CAL_01_SOLVES_SUCCEEDED",
}


summary_sha = write_immutable_json(
    execution_summary_path,
    summary,
)

post_registry_sha = sha256(
    registry_path
)


print()
print("=" * 108)
print(
    "TRM-DDOE-001-W03 - CAL_01 FACTORY EXECUTION COMPLETE"
)
print("=" * 108)


for row in summary_jobs:
    print(
        row[
            "run_id"
        ],
        "=>",
        row[
            "state"
        ].upper(),
    )


print()
print(
    "Succeeded              : 4"
)
print(
    "Failed                 : 0"
)
print(
    "Duplicate CAL_01       : 0"
)
print(
    "CAL_02+                : NOT LAUNCHED"
)
print(
    "Adaptive continuation  : NO"
)
print(
    "Full physics cert.     : NO"
)
print(
    "Dataset admission      : NO"
)
print(
    "Holdouts accessed      : NO"
)
print(
    "Execution summary SHA  :",
    summary_sha,
)
print(
    "Post-run registry SHA  :",
    post_registry_sha,
)

print("=" * 108)
print(
    "W03 STEP 2F RECOVERY COMPLETE - ALL FOUR CAL_01 SOLVED"
)
print("=" * 108)
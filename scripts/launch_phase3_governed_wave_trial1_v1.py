from __future__ import annotations

import concurrent.futures
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


ROOT = Path(
    r"D:\ThreadROM"
).resolve()

CONFIG = (
    ROOT
    / "config"
)

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

EXPECTED_PRELAUNCH_REGISTRY_SHA = (
    "51c6d63a0b99fbce88d9a2f2563857dc"
    "31ae44c47f47185c4fefe45200a10c7f"
)

EXPECTED_EXECUTION_AUTH_SHA = (
    "60afcb826a2c8228ac405d4d0c772e7c"
    "fb2a6a625a18685b32d8c661c56b59fc"
)

EXPECTED_PREFLIGHT_SHA = (
    "67d29a5307c44b478b8d7caab3d9d43f"
    "e97c357c2d8cdf716c360eed6574605c"
)

AUTHORIZED_CASE_COUNT = 4
AUTHORIZED_TRIAL_INDEX = 1
MAXIMUM_CONCURRENT_CCX = 4

# Proven historical factory envelope.
LEASE_SECONDS = 900
HEARTBEAT_SECONDS = 60


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(
    path: Path,
) -> str:

    require(
        path.is_file(),
        f"Required file missing: {path}",
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


def load_json(
    path: Path,
):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def canonical_json_bytes(
    payload: dict,
) -> bytes:

    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def write_immutable_json(
    path: Path,
    payload: dict,
) -> str:

    encoded = canonical_json_bytes(
        payload
    )

    digest = hashlib.sha256(
        encoded
    ).hexdigest()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if path.exists():
        require(
            path.read_bytes()
            == encoded,
            f"Immutable JSON conflict: {path}",
        )

        return digest

    path.write_bytes(
        encoded
    )

    return digest


def repository_path(
    value: str,
) -> Path:

    path = (
        ROOT
        / value
    ).resolve()

    try:
        path.relative_to(
            ROOT
        )
    except ValueError as exc:
        raise RuntimeError(
            f"Path escapes repository: {value}"
        ) from exc

    return path


def relative(
    path: Path,
) -> str:

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

wave_path = (
    wave_root
    / "wave_plan.json"
)

execution_auth_path = (
    wave_root
    / "trial1_execution_owner_authorization.json"
)

execution_preflight_path = (
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

# CAL_01-specific short admission lock.
# This is deliberately separate from the future adaptive lock.
admission_lock = (
    factory_root
    / "w03_trial1_parallel_admission.lock"
)

execution_summary_path = (
    factory_root
    / "w03_trial1_execution_summary.json"
)


# ==============================================================================
# Exact governed launch pins
# ==============================================================================

print()
print("=== GOVERNED CAL_01 LAUNCH PINS ===")


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
        execution_auth_path,
        EXPECTED_EXECUTION_AUTH_SHA,
    ),
    (
        "CAL_01 launch preflight",
        execution_preflight_path,
        EXPECTED_PREFLIGHT_SHA,
    ),
    (
        "Pre-launch factory registry",
        registry_path,
        EXPECTED_PRELAUNCH_REGISTRY_SHA,
    ),
):

    actual = sha256(
        path
    )

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


# Adaptive continuation is NOT part of this launch.
require(
    not adaptive_auth_path.exists(),
    (
        "Adaptive campaign authorization exists before "
        "CAL_01 completion."
    ),
)


# A successful prior execution summary means this launch
# must never be repeated.
require(
    not execution_summary_path.exists(),
    (
        "W03 CAL_01 execution summary already exists. "
        "Refusing duplicate launch."
    ),
)


# ==============================================================================
# Authorization + preflight contract
# ==============================================================================

authorization = load_json(
    execution_auth_path
)

preflight = load_json(
    execution_preflight_path
)

preparation = load_json(
    preparation_path
)


require(
    authorization[
        "authorization_type"
    ]
    == "OWNER_WAVE_CAL_01_ONLY_EXECUTION_AUTHORIZATION",
    "Wrong execution authorization type.",
)

require(
    authorization[
        "approval_status"
    ]
    == "OWNER_APPROVED",
    "CAL_01 execution is not owner-approved.",
)

require(
    authorization[
        "campaign_id"
    ]
    == CAMPAIGN_ID
    and authorization[
        "wave_id"
    ]
    == WAVE_ID,
    "CAL_01 authorization identity drift.",
)


contract = authorization[
    "execution_contract"
]


require(
    contract[
        "authorized_trial_index"
    ]
    == 1,
    "Authorization is not CAL_01-only.",
)

require(
    contract[
        "authorized_case_count"
    ]
    == 4,
    "Authorized case-count drift.",
)

require(
    contract[
        "maximum_concurrent_calculix"
    ]
    == MAXIMUM_CONCURRENT_CCX,
    "Authorized concurrency drift.",
)

require(
    contract[
        "duplicate_solver_execution_forbidden"
    ]
    is True,
    "Duplicate execution guard absent.",
)

require(
    contract[
        "registry_claim_required"
    ]
    is True,
    "Registry claim requirement absent.",
)

require(
    contract[
        "durable_lease_required"
    ]
    is True,
    "Durable lease requirement absent.",
)

require(
    contract[
        "certified_solver_backend_required"
    ]
    is True,
    "Certified backend requirement absent.",
)

require(
    contract[
        "adaptive_cal_02_plus_authorized"
    ]
    is False,
    "CAL_02+ unexpectedly authorized.",
)

require(
    contract[
        "additional_trials_authorized"
    ]
    is False,
    "Additional trials unexpectedly authorized.",
)

require(
    contract[
        "full_physics_certification_authorized"
    ]
    is False,
    "Full-physics certification unexpectedly authorized.",
)


scope = authorization[
    "scope"
]


require(
    all(
        scope[key]
        is False
        for key in (
            "additional_doe_cases_authorized",
            "additional_waves_authorized",
            "dataset_admission_authorized",
            "holdout_access_authorized",
            "surrogate_training_authorized",
            "artifact_retirement_authorized",
        )
    ),
    "CAL_01 owner scope broadened.",
)


require(
    preflight[
        "overall_disposition"
    ]
    == (
        "W03_CAL_01_EXECUTION_PREFLIGHT_PASS_"
        "LAUNCH_NOT_PERFORMED"
    ),
    "CAL_01 preflight disposition drift.",
)

require(
    preflight[
        "safety"
    ][
        "jobs_claimed"
    ]
    is False,
    "Preflight claims jobs were already claimed.",
)

require(
    preflight[
        "safety"
    ][
        "calculix_launched"
    ]
    is False,
    "Preflight claims prior CalculiX launch.",
)

require(
    preflight[
        "execution_scope"
    ][
        "adaptive_cal_02_plus_authorized"
    ]
    is False,
    "Preflight unexpectedly authorizes CAL_02+.",
)


# ==============================================================================
# Registry must still be pristine immediately before claims
# ==============================================================================

registry = FemFactoryRegistry(
    registry_path
)

jobs = registry.list_jobs()


require(
    len(
        jobs
    )
    == AUTHORIZED_CASE_COUNT,
    f"Expected four registry jobs; found {len(jobs)}.",
)


prepared_by_hash = {
    row[
        "case_hash"
    ]: row
    for row in preparation[
        "prepared_trials"
    ]
}


for job in jobs:

    require(
        job.case_hash
        in prepared_by_hash,
        "Registry contains unauthorized case.",
    )

    row = prepared_by_hash[
        job.case_hash
    ]

    require(
        job.case_id
        == row[
            "case_id"
        ],
        f"{job.case_hash}: registry case identity drift.",
    )

    require(
        job.trial_index
        == AUTHORIZED_TRIAL_INDEX,
        f"{job.case_id}: non-CAL_01 registry trial.",
    )

    require(
        job.run_id
        == row[
            "trial_run_id"
        ],
        f"{job.case_id}: run identity drift.",
    )

    require(
        job.priority
        is FemFactoryPriority.HIGH_INFORMATION_DOE,
        f"{job.case_id}: priority drift.",
    )

    require(
        job.state
        is FemFactoryJobState.PREPARED,
        (
            f"{job.case_id}: launch requires PREPARED; "
            f"found {job.state.value}."
        ),
    )

    require(
        job.lease_owner
        is None,
        f"{job.case_id}: already has lease owner.",
    )

    require(
        job.lease_generation
        == 0,
        f"{job.case_id}: lease generation is non-zero.",
    )

    require(
        job.manifest_path
        is None,
        f"{job.case_id}: manifest already registered.",
    )


print()
print(
    "PASS: 4/4 registry jobs pristine PREPARED CAL_01."
)


# ==============================================================================
# Certified backend + pinned execution specs
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


solver_executable = (
    ROOT
    / transfer.executable_relative_path
).resolve()


require(
    solver_executable.is_file(),
    (
        "Certified CalculiX executable missing: "
        f"{solver_executable}"
    ),
)


authorization_trials = {
    row[
        "case_hash"
    ]: row
    for row in authorization[
        "authorized_trials"
    ]
}


require(
    len(
        authorization_trials
    )
    == 4,
    "Authorization trial inventory drift.",
)


specs = {}


for row in preparation[
    "prepared_trials"
]:

    case_id = row[
        "case_id"
    ]

    case_hash = row[
        "case_hash"
    ]

    run_id = row[
        "trial_run_id"
    ]


    authorized = authorization_trials.get(
        case_hash
    )

    require(
        authorized is not None,
        f"{case_id}: absent from execution authorization.",
    )

    require(
        authorized[
            "trial_run_id"
        ]
        == run_id,
        f"{case_id}: authorization run identity drift.",
    )

    require(
        authorized[
            "deck_sha256"
        ]
        == row[
            "deck_sha256"
        ],
        f"{case_id}: authorization deck SHA drift.",
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
        f"{case_id}: preparation-record SHA drift.",
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
        sha256(
            deck_path
        )
        == row[
            "deck_sha256"
        ],
        f"{case_id}: launch deck SHA drift.",
    )

    require(
        relative(
            deck_path
        )
        == authorized[
            "deck_path"
        ],
        f"{case_id}: authorization deck path drift.",
    )

    require(
        relative(
            manifest_path
        )
        == authorized[
            "manifest_path"
        ],
        f"{case_id}: authorization manifest path drift.",
    )


    # Final duplicate-solve guard immediately before workers exist.
    require(
        not manifest_path.exists(),
        f"{case_id}: manifest already exists.",
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
                / f"{run_id}{suffix}"
            ).exists(),
            (
                f"{case_id}: solver evidence {suffix} "
                "already exists; duplicate launch refused."
            ),
        )


    definition = CalculixJobDefinition(
        executable_relative_path=(
            transfer.executable_relative_path
        ),
        job_name=run_id,
        timeout_seconds=None,
    )


    specs[
        run_id
    ] = GovernedCalculixExecutionSpec(
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
        manifest_path=(
            manifest_path
        ),
    )


require(
    len(
        specs
    )
    == 4,
    "Expected exactly four CAL_01 execution specs.",
)


print()
print("=== CERTIFIED EXECUTION SPECS ===")
print(
    "Backend policy :",
    backend.policy_id,
)
print(
    "Solver         :",
    backend.solver_name,
)
print(
    "Version        :",
    backend.solver_version,
)
print(
    "Timeout        : NONE"
)
print(
    "Specs          :",
    len(
        specs
    ),
)


for run_id in sorted(
    specs
):
    print(
        " ",
        run_id,
        sha256(
            specs[
                run_id
            ].input_path
        ),
    )


# ==============================================================================
# Worker function
# ==============================================================================

def run_worker(
    worker_number: int,
):
    worker_id = (
        "TRM-DDOE-W03-trial1-"
        f"worker-{worker_number:02d}"
    )

    admission = (
        claim_parallel_factory_slot(
            registry=registry,
            lock_path=admission_lock,
            worker_id=worker_id,
            lease_seconds=LEASE_SECONDS,
            maximum_authorized_ccx=(
                MAXIMUM_CONCURRENT_CCX
            ),
        )
    )


    require(
        admission.claim is not None,
        (
            f"{worker_id}: failed to claim CAL_01 work; "
            f"reason={admission.reason}, "
            f"occupied={admission.occupied_slots}, "
            f"capacity={admission.capacity}"
        ),
    )


    claim = admission.claim


    require(
        claim.trial_index
        == 1,
        (
            f"{worker_id}: claimed non-CAL_01 job "
            f"{claim.run_id}."
        ),
    )

    require(
        claim.run_id
        in specs,
        (
            f"{worker_id}: claimed job outside "
            f"authorized W03 CAL_01 set: {claim.run_id}"
        ),
    )


    spec = specs[
        claim.run_id
    ]


    # Recheck deck + duplicate evidence after durable claim,
    # immediately before entering the generic worker.
    expected_row = prepared_by_hash[
        claim.case_hash
    ]

    require(
        sha256(
            spec.input_path
        )
        == expected_row[
            "deck_sha256"
        ],
        (
            f"{claim.run_id}: deck changed after "
            "factory claim."
        ),
    )

    require(
        not spec.manifest_path.exists(),
        (
            f"{claim.run_id}: manifest appeared after "
            "factory claim."
        ),
    )


    print(
        f"CLAIMED      : {claim.run_id} | "
        f"{worker_id} | "
        f"lease generation {claim.lease_generation}",
        flush=True,
    )

    print(
        f"SOLVER START : {claim.run_id} | "
        f"{worker_id}",
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
        f"SOLVER END   : {claim.run_id} | "
        f"{record.state.value.upper()}",
        flush=True,
    )


    require(
        record.state
        is FemFactoryJobState.SOLVED,
        (
            f"{claim.run_id}: worker returned "
            f"{record.state.value}, expected SOLVED."
        ),
    )


    require(
        record.manifest_path
        is not None,
        (
            f"{claim.run_id}: SOLVED registry record "
            "has no manifest."
        ),
    )


    require(
        spec.manifest_path.is_file(),
        (
            f"{claim.run_id}: governed solver manifest "
            "missing after successful execution."
        ),
    )


    return {
        "worker_id":
            worker_id,

        "case_hash":
            claim.case_hash,

        "run_id":
            claim.run_id,

        "lease_generation":
            claim.lease_generation,

        "state":
            record.state.value,

        "manifest_path":
            relative(
                spec.manifest_path
            ),

        "manifest_sha256":
            sha256(
                spec.manifest_path
            ),
    }


# ==============================================================================
# EXPLICIT SOLVER-LAUNCH BOUNDARY
# ==============================================================================

print()
print("=" * 108)
print(
    "THREADROM - TRM-DDOE-001-W03 GOVERNED CAL_01 FACTORY LAUNCH"
)
print("=" * 108)

print(
    "Prepared jobs       : 4"
)
print(
    "Authorized workers  : 4"
)
print(
    "Trial               : CAL_01 ONLY"
)
print(
    "Adaptive CAL_02+    : BLOCKED"
)
print(
    "Full physics cert.  : BLOCKED"
)
print(
    "Holdouts            : SEALED"
)
print(
    "Dataset admission   : BLOCKED"
)
print(
    "Duplicate CAL_01    : FORBIDDEN"
)
print(
    "Solver timeout      : NONE"
)

print("=" * 108)
print(
    "EXPLICIT OWNER-AUTHORIZED CALCULIX LAUNCH"
)
print("=" * 108)


results = []
errors = []


with concurrent.futures.ThreadPoolExecutor(
    max_workers=MAXIMUM_CONCURRENT_CCX,
    thread_name_prefix=(
        "threadrom-w03-cal01"
    ),
) as pool:

    future_map = {
        pool.submit(
            run_worker,
            worker_number,
        ): worker_number

        for worker_number in range(
            1,
            AUTHORIZED_CASE_COUNT + 1,
        )
    }


    for future in concurrent.futures.as_completed(
        future_map
    ):

        worker_number = future_map[
            future
        ]

        try:
            results.append(
                future.result()
            )

        except BaseException as exc:

            errors.append(
                (
                    worker_number,
                    exc,
                )
            )

            print(
                f"WORKER ERROR : {worker_number:02d} | "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )


# ==============================================================================
# Post-run registry gate
# ==============================================================================

final_jobs = registry.list_jobs()


print()
print("=" * 108)
print(
    "W03 CAL_01 FACTORY POST-RUN STATE"
)
print("=" * 108)


for job in final_jobs:

    print(
        f"{job.case_id}"
    )

    print(
        "  run       :",
        job.run_id,
    )

    print(
        "  state     :",
        job.state.value,
    )

    print(
        "  lease gen :",
        job.lease_generation,
    )

    print(
        "  manifest  :",
        job.manifest_path,
    )

    if job.failure_category is not None:
        print(
            "  failure   :",
            job.failure_category,
            "|",
            job.failure_message,
        )


require(
    len(
        final_jobs
    )
    == 4,
    "Registry job count changed during CAL_01 execution.",
)


if errors:

    details = "\n".join(
        (
            f"worker-{number:02d}: "
            f"{type(exc).__name__}: {exc}"
        )
        for number, exc in errors
    )

    raise RuntimeError(
        "One or more governed CAL_01 workers failed.\n"
        + details
    )


require(
    len(
        results
    )
    == 4,
    (
        "Expected four completed workers; "
        f"received {len(results)}."
    ),
)


for job in final_jobs:

    require(
        job.trial_index
        == 1,
        f"{job.case_id}: unexpected trial index.",
    )

    require(
        job.state
        is FemFactoryJobState.SOLVED,
        (
            f"{job.case_id}: expected SOLVED after "
            f"CAL_01 factory execution, found "
            f"{job.state.value}."
        ),
    )

    require(
        job.manifest_path
        is not None,
        f"{job.case_id}: SOLVED job lacks manifest.",
    )


# No adaptive work may have appeared.
require(
    not adaptive_auth_path.exists(),
    "Adaptive authorization appeared during CAL_01 execution.",
)


cal02_registry_jobs = tuple(
    job
    for job in final_jobs
    if job.trial_index >= 2
)


require(
    not cal02_registry_jobs,
    "CAL_02+ registry work appeared during CAL_01-only launch.",
)


# ==============================================================================
# Immutable execution summary
# ==============================================================================

results_by_run = {
    row[
        "run_id"
    ]: row
    for row in results
}


summary_jobs = []


for job in sorted(
    final_jobs,
    key=lambda item: item.job_id,
):

    result = results_by_run[
        job.run_id
    ]

    manifest_path = repository_path(
        job.manifest_path
    )


    require(
        manifest_path.is_file(),
        f"{job.run_id}: manifest missing.",
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
                    manifest_path
                ),

            "manifest_sha256":
                sha256(
                    manifest_path
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
    "W03 CAL_01 FACTORY RESULT: ALL FOUR SOLVES SUCCEEDED"
)
print(
    "Next stage: governed result extraction + "
    "calibration decisions."
)
print("=" * 108)
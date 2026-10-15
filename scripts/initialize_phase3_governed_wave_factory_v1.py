from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3

from pathlib import Path


from threadrom.factory.fem_factory_registry import (
    FemFactoryJobState,
    FemFactoryPriority,
    FemFactoryRegistry,
)


ROOT = Path(
    r"D:\ThreadROM"
).resolve()


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(
            message
        )


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


def relative(
    path: Path,
) -> str:
    return (
        path.resolve()
        .relative_to(ROOT)
        .as_posix()
    )


def repository_path(
    text: str,
) -> Path:

    result = (
        ROOT
        / text
    ).resolve()

    try:
        result.relative_to(
            ROOT
        )
    except ValueError as exc:
        raise RuntimeError(
            f"Path escapes repository: {text}"
        ) from exc

    return result


def parse_args():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--wave-id",
        required=True,
    )

    parser.add_argument(
        "--expected-wave-sha",
        required=True,
    )

    parser.add_argument(
        "--expected-preparation-sha",
        required=True,
    )

    return parser.parse_args()


args = parse_args()


wave_id = args.wave_id

require(
    wave_id.startswith(
        "TRM-DDOE-001-W"
    ),
    f"Malformed wave identity: {wave_id}",
)

wave_token = wave_id.rsplit(
    "-",
    1,
)[-1]

wave_token_lower = (
    wave_token.lower()
)


# ==============================================================================
# Paths
# ==============================================================================

wave_path = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "waves"
    / wave_id
    / "wave_plan.json"
)

campaign_root = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / "TRM-DDOE-001"
    / wave_token
)

preparation_path = (
    campaign_root
    / f"{wave_token_lower}_trial1_preparation.json"
)

factory_root = (
    campaign_root
    / "factory"
)

database_path = (
    factory_root
    / f"{wave_token_lower}_trial1_factory.sqlite3"
)

admission_lock = (
    factory_root
    / f"{wave_token_lower}_adaptive_parallel_admission.lock"
)

authorization_path = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "waves"
    / wave_id
    / "adaptive_campaign_owner_authorization.json"
)


# ==============================================================================
# Frozen governed inputs
# ==============================================================================

require(
    sha256(
        wave_path
    )
    == args.expected_wave_sha,
    "Wave-plan SHA drift.",
)

require(
    sha256(
        preparation_path
    )
    == args.expected_preparation_sha,
    "Preparation-index SHA drift.",
)


wave = load_json(
    wave_path
)

preparation = load_json(
    preparation_path
)


require(
    wave.get(
        "wave_id"
    )
    == wave_id,
    "Wave-plan identity drift.",
)

require(
    preparation.get(
        "wave_id"
    )
    == wave_id,
    "Preparation identity drift.",
)

require(
    preparation.get(
        "wave_plan_sha256"
    )
    == args.expected_wave_sha,
    "Preparation / wave-plan binding drift.",
)

require(
    preparation.get(
        "factory_ready"
    )
    is True,
    "Preparation is not factory-ready.",
)

require(
    preparation.get(
        "solver_launched"
    )
    is False,
    "Preparation claims solver execution.",
)

require(
    preparation.get(
        "adaptive_continuation_authorized"
    )
    is False,
    "Preparation already grants adaptive authority.",
)

require(
    preparation.get(
        "holdouts_accessed"
    )
    is False,
    "Preparation claims holdout access.",
)

require(
    preparation.get(
        "prepared_trial_count"
    )
    == 4,
    "Expected exactly four prepared Trial-1 jobs.",
)


for key in (
    "fem_execution_authorized",
    "adaptive_continuation_authorized",
    "full_physics_certification_authorized",
    "dataset_admission_authorized",
    "holdout_access_authorized",
    "artifact_retirement_authorized",
):
    require(
        wave.get(
            key
        )
        is False,
        (
            "Frozen wave plan unexpectedly grants "
            f"authority: {key}"
        ),
    )


# Execution authority MUST NOT exist yet.
require(
    not authorization_path.exists(),
    (
        "Adaptive execution authorization already exists. "
        "Step 2D.2 must occur before execution authorization."
    ),
)


# Admission lock must not exist.
require(
    not admission_lock.exists(),
    (
        "Parallel-admission lock already exists before "
        "execution authorization."
    ),
)


# ==============================================================================
# Validate four immutable preparation rows before touching SQLite
# ==============================================================================

rows = sorted(
    preparation[
        "prepared_trials"
    ],
    key=lambda row: row[
        "wave_order"
    ],
)


require(
    len(
        rows
    )
    == 4,
    "Prepared-row count drift.",
)


seen_case_ids = set()
seen_case_hashes = set()
seen_run_ids = set()


for row in rows:

    case_id = row[
        "case_id"
    ]

    case_hash = row[
        "case_hash"
    ]

    run_id = row[
        "trial_run_id"
    ]

    require(
        case_id not in seen_case_ids,
        f"Duplicate case identity: {case_id}",
    )

    require(
        case_hash not in seen_case_hashes,
        f"Duplicate case hash: {case_hash}",
    )

    require(
        run_id not in seen_run_ids,
        f"Duplicate Trial-1 run identity: {run_id}",
    )

    seen_case_ids.add(
        case_id
    )

    seen_case_hashes.add(
        case_hash
    )

    seen_run_ids.add(
        run_id
    )


    require(
        run_id
        == (
            row[
                "case_run_id"
            ]
            + "_cal_01"
        ),
        f"{case_id}: Trial-1 run identity drift.",
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

    require(
        prep_record[
            "case"
        ][
            "case_id"
        ]
        == case_id,
        f"{case_id}: preparation-record case identity drift.",
    )

    require(
        prep_record[
            "case"
        ][
            "case_hash"
        ]
        == case_hash,
        f"{case_id}: preparation-record case SHA drift.",
    )

    require(
        prep_record[
            "solve_authorization"
        ][
            "calculix_invoked"
        ]
        is False,
        f"{case_id}: preparation claims CalculiX invocation.",
    )

    require(
        prep_record[
            "solve_authorization"
        ][
            "trial1_execution_authority_exists"
        ]
        is False,
        f"{case_id}: preparation claims execution authority.",
    )


    deck_path = repository_path(
        prep_record[
            "deck"
        ][
            "relative_path"
        ]
    )

    require(
        sha256(
            deck_path
        )
        == row[
            "deck_sha256"
        ]
        == prep_record[
            "deck"
        ][
            "sha256"
        ],
        f"{case_id}: CAL_01 deck SHA drift.",
    )


    # No solver result/manifest evidence is permitted yet.
    run_dir = deck_path.parent

    for suffix in (
        ".dat",
        ".frd",
        ".sta",
        ".cvg",
        ".rout",
    ):
        require(
            not (
                run_dir
                / f"{run_id}{suffix}"
            ).exists(),
            (
                f"{case_id}: solver result exists before "
                "execution authorization."
            ),
        )

    require(
        not (
            run_dir
            / "fem_run_manifest.json"
        ).exists(),
        (
            f"{case_id}: solver manifest exists before "
            "execution authorization."
        ),
    )


# ==============================================================================
# Registry creation / verification
#
# If the DB already exists, this path performs semantic verification only.
# We NEVER delete/rebuild an existing governed registry.
# ==============================================================================

database_preexisting = (
    database_path.exists()
)


if not database_preexisting:

    print()
    print(
        "=== INITIALIZE GOVERNED WAVE FACTORY REGISTRY ==="
    )

    registry = FemFactoryRegistry(
        database_path
    )

    registry.initialize()


    for row in rows:

        print()
        print(
            f"REGISTER: {row['case_id']}"
        )

        registered = (
            registry.register_job(
                case_id=row[
                    "case_id"
                ],
                case_hash=row[
                    "case_hash"
                ],
                trial_index=1,
                run_id=row[
                    "trial_run_id"
                ],
                priority=(
                    FemFactoryPriority
                    .HIGH_INFORMATION_DOE
                ),
            )
        )


        require(
            registered.state
            is FemFactoryJobState.PLANNED,
            (
                f"{row['case_id']}: new registry job "
                "did not begin PLANNED."
            ),
        )


        prepared = (
            registry.transition_job(
                case_hash=row[
                    "case_hash"
                ],
                trial_index=1,
                new_state=(
                    FemFactoryJobState.PREPARED
                ),
                preparation_record=row[
                    "preparation_record"
                ],
            )
        )


        require(
            prepared.state
            is FemFactoryJobState.PREPARED,
            (
                f"{row['case_id']}: registry transition "
                "to PREPARED failed."
            ),
        )

        require(
            prepared.preparation_record
            == row[
                "preparation_record"
            ],
            (
                f"{row['case_id']}: persisted preparation "
                "record binding drift."
            ),
        )


        print(
            "  job id      :",
            prepared.job_id,
        )

        print(
            "  run id      :",
            prepared.run_id,
        )

        print(
            "  priority    :",
            prepared.priority.value,
        )

        print(
            "  state       :",
            prepared.state.value,
        )

        print(
            "  preparation :",
            prepared.preparation_record,
        )


else:

    print()
    print(
        "INFO: registry already exists; "
        "entering verification-only mode."
    )

    registry = FemFactoryRegistry(
        database_path
    )

    registry.initialize()


# ==============================================================================
# Full semantic registry verification
# ==============================================================================

jobs = registry.list_jobs()


require(
    len(
        jobs
    )
    == 4,
    (
        "Governed wave registry must contain exactly four jobs; "
        f"found {len(jobs)}."
    ),
)


rows_by_hash = {
    row[
        "case_hash"
    ]: row
    for row in rows
}


for job in jobs:

    require(
        job.case_hash
        in rows_by_hash,
        (
            "Registry contains an unauthorized case hash: "
            f"{job.case_hash}"
        ),
    )

    expected = rows_by_hash[
        job.case_hash
    ]


    require(
        job.case_id
        == expected[
            "case_id"
        ],
        f"{job.case_hash}: registry case identity drift.",
    )

    require(
        job.trial_index
        == 1,
        f"{job.case_id}: registry trial index is not 1.",
    )

    require(
        job.run_id
        == expected[
            "trial_run_id"
        ],
        f"{job.case_id}: registry run identity drift.",
    )

    require(
        job.priority
        is FemFactoryPriority.HIGH_INFORMATION_DOE,
        f"{job.case_id}: registry priority drift.",
    )

    require(
        job.state
        is FemFactoryJobState.PREPARED,
        (
            f"{job.case_id}: registry job is not PREPARED; "
            f"found {job.state.value}."
        ),
    )

    require(
        job.preparation_record
        == expected[
            "preparation_record"
        ],
        f"{job.case_id}: registry preparation binding drift.",
    )


    require(
        job.manifest_path
        is None,
        f"{job.case_id}: registry already has a manifest.",
    )

    require(
        job.acceptance_record
        is None,
        f"{job.case_id}: registry already has acceptance evidence.",
    )

    require(
        job.failure_category
        is None,
        f"{job.case_id}: registry already has failure state.",
    )

    require(
        job.failure_message
        is None,
        f"{job.case_id}: registry already has failure message.",
    )

    require(
        job.lease_owner
        is None,
        f"{job.case_id}: PREPARED job already has a lease owner.",
    )

    require(
        job.lease_expires_at_utc
        is None,
        f"{job.case_id}: PREPARED job already has a lease expiry.",
    )

    require(
        job.lease_generation
        == 0,
        (
            f"{job.case_id}: PREPARED job already has "
            "non-zero lease generation."
        ),
    )


# ==============================================================================
# Raw SQLite schema + metadata verification
# ==============================================================================

connection = sqlite3.connect(
    database_path
)

connection.row_factory = sqlite3.Row


try:

    integrity = connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()

    require(
        integrity is not None
        and integrity[0] == "ok",
        (
            "SQLite integrity check failed: "
            f"{None if integrity is None else integrity[0]}"
        ),
    )


    metadata = {
        row[
            "key"
        ]: row[
            "value"
        ]
        for row in connection.execute(
            """
            SELECT key, value
            FROM registry_metadata
            ORDER BY key
            """
        ).fetchall()
    }


    raw_jobs = connection.execute(
        """
        SELECT
            case_id,
            case_hash,
            trial_index,
            run_id,
            priority_class,
            priority_rank,
            state,
            preparation_record,
            manifest_path,
            acceptance_record,
            failure_category,
            failure_message,
            lease_owner,
            lease_expires_at_utc,
            lease_generation
        FROM fem_jobs
        ORDER BY priority_rank, job_id
        """
    ).fetchall()


finally:

    connection.close()


require(
    len(
        raw_jobs
    )
    == 4,
    "Raw SQLite job count drift.",
)


print()
print(
    "=== REGISTRY METADATA ==="
)

for key, value in sorted(
    metadata.items()
):
    print(
        f"  {key}: {value}"
    )


print()
print(
    "=== FINAL GOVERNED WAVE FACTORY JOBS ==="
)

for job in jobs:

    print()
    print(
        job.case_id
    )

    print(
        "  run        :",
        job.run_id,
    )

    print(
        "  trial      :",
        job.trial_index,
    )

    print(
        "  priority   :",
        job.priority.value,
    )

    print(
        "  state      :",
        job.state.value,
    )

    print(
        "  lease gen  :",
        job.lease_generation,
    )

    print(
        "  prep       :",
        job.preparation_record,
    )


# ==============================================================================
# Filesystem safety checks
# ==============================================================================

require(
    database_path.is_file(),
    "Factory database missing after initialization.",
)

require(
    not admission_lock.exists(),
    "Parallel admission lock exists unexpectedly.",
)

require(
    not authorization_path.exists(),
    "Execution authorization unexpectedly exists.",
)


factory_files = tuple(
    path
    for path in factory_root.rglob("*")
    if path.is_file()
)


allowed_factory_names = {
    database_path.name,
}


unexpected_factory_files = tuple(
    path
    for path in factory_files
    if path.name
    not in allowed_factory_names
)


require(
    not unexpected_factory_files,
    (
        "Unexpected governed-wave factory files exist:\n"
        + "\n".join(
            str(path)
            for path in unexpected_factory_files
        )
    ),
)


database_sha = sha256(
    database_path
)


print()
print("=" * 108)
print(
    "GOVERNED WAVE FACTORY REGISTRY READY"
)
print("=" * 108)

print(
    "Database :",
    relative(
        database_path
    ),
)

print(
    "SHA256   :",
    database_sha,
)

print(
    "Jobs     :",
    len(
        jobs
    ),
)

print(
    "PREPARED :",
    len(
        registry.list_jobs(
            state=(
                FemFactoryJobState.PREPARED
            )
        )
    ),
)

print(
    "RUNNING  :",
    len(
        registry.list_jobs(
            state=(
                FemFactoryJobState.RUNNING
            )
        )
    ),
)

print(
    "SOLVED   :",
    len(
        registry.list_jobs(
            state=(
                FemFactoryJobState.SOLVED
            )
        )
    ),
)

print(
    "ACCEPTED :",
    len(
        registry.list_jobs(
            state=(
                FemFactoryJobState.ACCEPTED
            )
        )
    ),
)

print(
    "Execution authorization : NO"
)

print(
    "CalculiX launch          : NO"
)

print("=" * 108)


if database_preexisting:

    print(
        "Mode                     : VERIFY EXISTING"
    )

else:

    print(
        "Mode                     : INITIALIZE + REGISTER"
    )
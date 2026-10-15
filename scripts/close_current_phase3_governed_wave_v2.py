from __future__ import annotations

import hashlib
import json
import sqlite3

from pathlib import Path

from threadrom.factory.governed_wave_contract import (
    build_governed_wave_execution_contract,
)

from threadrom.factory.governed_wave_runner import (
    build_governed_wave_runner,
)

from threadrom.factory.governed_wave_closure import (
    GovernedWaveExpectedCase,
    build_governed_wave_closure_record,
    persist_governed_wave_closure,
    recover_governed_wave_acceptance_evidence,
    recover_governed_wave_closure,
)

from threadrom.factory.production_doe_launch_fence import (
    count_running_ccx,
)


ROOT = Path(r"D:\ThreadROM").resolve()

CAMPAIGN_ID = "TRM-DDOE-001"
WAVE_TOKEN = "W06"
WAVE_ID = f"{CAMPAIGN_ID}-{WAVE_TOKEN}"

AUTHORIZED_CASE_COUNT = 4
MAXIMUM_CONCURRENT_CCX = 4
MAXIMUM_TRIAL_INDEX = 6

OWNER_AUTH_SHA = (
    "4b0ade420647ea5db88757fefa731d91a"
    "46c35ac1483ff2788a1738413019958"
)

PREPARATION_SHA = (
    "1e0f7ef463aab532bd9fbeb3225e14ed"
    "525c32e78493a70d8a634784c4bb1385"
)

OWNER_AUTH = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "waves"
    / WAVE_ID
    / "adaptive_campaign_owner_authorization.json"
)

PREPARATION = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / CAMPAIGN_ID
    / WAVE_TOKEN
    / "w06_trial1_preparation.json"
)

CLOSURE_PATH = (
    ROOT
    / "docs"
    / "phase3_governed_wave_closure"
    / f"{WAVE_ID}.wave_closure.json"
)

CLOSURE_SIDECAR = Path(
    str(CLOSURE_PATH) + ".sha256"
)

CLOSURE_MODULE = (
    ROOT
    / "src"
    / "threadrom"
    / "factory"
    / "governed_wave_closure.py"
)

RUNNER_MODULE = (
    ROOT
    / "src"
    / "threadrom"
    / "factory"
    / "governed_wave_runner.py"
)

EXPECTED_CLOSURE_MODULE_SHA = (
    "316ee4ce766615535296c92cc0efea3edcecbaa65c48f24bfa2439e96283e951"
)

EXPECTED_RUNNER_SHA = (
    "b944340afe9c94d1b2f0e503913745c11d79d285883147520bed99479bf13128"
)


def sha256(path: Path) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def relative(path: Path) -> str:

    return str(
        path.resolve().relative_to(ROOT)
    ).replace("\\", "/")


print("=" * 120)
print("THREADROM - GENERIC CURRENT GOVERNED-WAVE CLOSURE")
print("=" * 120)
print("Wave :", WAVE_ID)


# --------------------------------------------------------------------------------------------------------------
# Immutable authorities
# --------------------------------------------------------------------------------------------------------------

for path, expected in (
    (
        OWNER_AUTH,
        OWNER_AUTH_SHA,
    ),
    (
        PREPARATION,
        PREPARATION_SHA,
    ),
    (
        CLOSURE_MODULE,
        EXPECTED_CLOSURE_MODULE_SHA,
    ),
    (
        RUNNER_MODULE,
        EXPECTED_RUNNER_SHA,
    ),
):

    if not path.is_file():

        raise RuntimeError(
            f"Required authority missing: {path}"
        )

    actual = sha256(
        path
    )

    if actual != expected:

        raise RuntimeError(
            f"SHA drift: {path}\n"
            f"Expected: {expected}\n"
            f"Actual  : {actual}"
        )


print("PASS: immutable W06 authorities pinned.")


# --------------------------------------------------------------------------------------------------------------
# No concurrent solver work
# --------------------------------------------------------------------------------------------------------------

running_ccx = count_running_ccx()

if running_ccx != 0:

    raise RuntimeError(
        f"W06 closure requires global ccx quiescence; "
        f"found {running_ccx}."
    )


print("PASS: CalculiX process count = 0.")


# --------------------------------------------------------------------------------------------------------------
# Rebuild the exact generic execution contract
# --------------------------------------------------------------------------------------------------------------

contract = build_governed_wave_execution_contract(
    campaign_id=CAMPAIGN_ID,
    wave_token=WAVE_TOKEN,
    expected_owner_authorization_sha256=(
        OWNER_AUTH_SHA
    ),
    expected_preparation_index_sha256=(
        PREPARATION_SHA
    ),
    authorized_case_count=(
        AUTHORIZED_CASE_COUNT
    ),
    maximum_concurrent_solver_slots=(
        MAXIMUM_CONCURRENT_CCX
    ),
    maximum_trial_index=(
        MAXIMUM_TRIAL_INDEX
    ),
)


contract_sha = (
    contract.contract_sha256
)


print(
    "Execution contract SHA :",
    contract_sha,
)


# --------------------------------------------------------------------------------------------------------------
# Generic runner reconstructs the exact frozen authorized cohort
# --------------------------------------------------------------------------------------------------------------

runner = build_governed_wave_runner(
    repository_root=ROOT,
    contract=contract,
)


runner.call(
    "verify_owner_authorization"
)


contexts = (
    runner.build_case_contexts()
)


if len(contexts) != AUTHORIZED_CASE_COUNT:

    raise RuntimeError(
        "Authorized W06 context count drift."
    )


expected_cases = tuple(
    GovernedWaveExpectedCase(
        case_id=context[
            "case_id"
        ],
        case_hash=context[
            "case_hash"
        ],
        case_run_id=context[
            "case_run_id"
        ],
    )
    for context in contexts
)


print(
    "PASS: exact authorized cohort reconstructed:",
    len(expected_cases),
)


# --------------------------------------------------------------------------------------------------------------
# Registry must have no presently executable work / leases.
#
# Historical solved predecessor trials are VALID and intentionally preserved.
# --------------------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------------------------------
# Materialize the contract's platform-neutral PurePosixPath only at the
# filesystem I/O boundary.
# --------------------------------------------------------------------------------------------------------------

database_locator = (
    contract.factory_database_path
)


if database_locator.is_absolute():

    raise RuntimeError(
        "Governed factory database locator "
        "must remain repository-relative."
    )


database_path = (
    ROOT.joinpath(
        *database_locator.parts
    ).resolve()
)


try:

    database_path.relative_to(
        ROOT
    )

except ValueError as exc:

    raise RuntimeError(
        "Governed factory database escaped "
        "repository root."
    ) from exc


if not database_path.is_file():

    raise RuntimeError(
        "W06 factory database missing."
    )


uri = (
    "file:"
    + database_path.as_posix()
    + "?mode=ro"
)


connection = sqlite3.connect(
    uri,
    uri=True,
)

connection.row_factory = sqlite3.Row


try:

    jobs = list(
        connection.execute(
            """
            SELECT
                case_id,
                trial_index,
                run_id,
                state,
                acceptance_record,
                failure_category,
                lease_owner
            FROM fem_jobs
            ORDER BY
                case_id,
                trial_index
            """
        )
    )

finally:

    connection.close()


live = [
    row
    for row in jobs
    if (
        str(
            row[
                "state"
            ]
        ).lower()
        in {
            "prepared",
            "running",
        }
        or bool(
            row[
                "lease_owner"
            ]
        )
    )
]


if live:

    raise RuntimeError(
        "W06 still contains executable/leased work: "
        + repr(
            [
                (
                    row[
                        "case_id"
                    ],
                    row[
                        "trial_index"
                    ],
                    row[
                        "state"
                    ],
                )
                for row in live
            ]
        )
    )


print(
    "PASS: no prepared/running/leased W06 work."
)


# --------------------------------------------------------------------------------------------------------------
# This canonical recovery operates at CASE level.
#
# It selects the governed physics-accepted run for each expected case,
# while preserving older solved trials in the registry.
# --------------------------------------------------------------------------------------------------------------

evidence = (
    recover_governed_wave_acceptance_evidence(
        repo_root=ROOT,
        wave_id=WAVE_ID,
        factory_database_path=(
            database_path
        ),
        expected_cases=(
            expected_cases
        ),
    )
)


if (
    evidence.authorized_case_count
    != AUTHORIZED_CASE_COUNT
    or len(
        evidence.cases
    )
    != AUTHORIZED_CASE_COUNT
):

    raise RuntimeError(
        "W06 accepted-evidence count drift."
    )


print()
print("=" * 120)
print("W06 ACCEPTED CASE EVIDENCE")
print("=" * 120)


for case in evidence.cases:

    print(
        f"{case.case_id} | "
        f"{case.run_id} | "
        f"trial {case.trial_index} | "
        f"gates {case.hard_gate_count} | "
        f"increments {case.accepted_increment_count}"
    )


# --------------------------------------------------------------------------------------------------------------
# Build canonical closure
# --------------------------------------------------------------------------------------------------------------

record = build_governed_wave_closure_record(
    evidence=evidence,
    execution_contract_sha256=(
        contract_sha
    ),
    owner_authorization_sha256=(
        OWNER_AUTH_SHA
    ),
    preparation_index_sha256=(
        PREPARATION_SHA
    ),
)


if CLOSURE_PATH.exists():

    recovered = (
        recover_governed_wave_closure(
            path=CLOSURE_PATH,
            expected_wave_id=WAVE_ID,
            expected_evidence=evidence,
        )
    )

    if recovered is None:

        raise RuntimeError(
            "Existing W06 closure could not be recovered."
        )


    if recovered != record:

        raise RuntimeError(
            "Existing W06 closure differs from "
            "the canonical reconstructed record."
        )


    closure_sha = (
        sha256(
            CLOSURE_PATH
        )
    )

else:

    CLOSURE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    closure_sha = (
        persist_governed_wave_closure(
            path=CLOSURE_PATH,
            record=record,
        )
    )


# Re-read using the canonical verifier.
verified = (
    recover_governed_wave_closure(
        path=CLOSURE_PATH,
        expected_wave_id=WAVE_ID,
        expected_evidence=evidence,
    )
)


if verified is None:

    raise RuntimeError(
        "Persisted W06 closure failed canonical recovery."
    )


actual_closure_sha = sha256(
    CLOSURE_PATH
)


if (
    closure_sha
    != actual_closure_sha
):

    raise RuntimeError(
        "Persisted closure SHA disagreement."
    )


sidecar_text = (
    actual_closure_sha
    + "  "
    + CLOSURE_PATH.name
    + "\n"
)


if CLOSURE_SIDECAR.exists():

    if (
        CLOSURE_SIDECAR.read_text(
            encoding="ascii"
        )
        != sidecar_text
    ):

        raise RuntimeError(
            "W06 closure SHA sidecar drift."
        )

else:

    CLOSURE_SIDECAR.write_text(
        sidecar_text,
        encoding="ascii",
    )


print()
print("=" * 120)
print("TRM-DDOE-001-W06 - GOVERNED WAVE CLOSURE COMPLETE")
print("=" * 120)

print(
    "Authorized cases       :",
    record[
        "authorized_case_count"
    ],
)

print(
    "Accepted cases         :",
    record[
        "accepted_case_count"
    ],
)

print(
    "Disposition            :",
    record[
        "disposition"
    ],
)

print(
    "Closure                :",
    relative(
        CLOSURE_PATH
    ),
)

print(
    "Closure SHA256         :",
    actual_closure_sha,
)

print()
print("New FEM launched        : NO")
print("Registry mutated        : NO")
print("Solved misses preserved : YES")
print("Holdouts                : SEALED")
print("Dataset                 : UNTOUCHED")

print()
print(
    "NEXT : DA08 SOLVER-LAUNCH AUTHORIZATION"
)

print("=" * 120)

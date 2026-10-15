from __future__ import annotations

import hashlib

from pathlib import Path


from threadrom.factory.governed_wave_contract import (
    build_governed_wave_execution_contract,
)

from threadrom.factory.governed_wave_runtime import (
    run_governed_wave_entrypoint,
)

from threadrom.factory.fem_factory_registry import (
    FemFactoryJobState,
    FemFactoryRegistry,
)


ROOT = Path(r"D:\ThreadROM").resolve()

CAMPAIGN_ID = "TRM-DDOE-001"
WAVE_TOKEN = "W03"
WAVE_ID = "TRM-DDOE-001-W03"

EXPECTED_WAVE_SHA = (
    "3714441cb14386e2fcc3adf7b90300a1"
    "dcec6ebd2d4404212f2a1adbacb3b225"
)

EXPECTED_PREPARATION_SHA = (
    "813b602392dd66cf0b30e2089b3695c8"
    "e8ae0859946da775bfc1736efd404393"
)

EXPECTED_RUNNER_SHA = (
    "b944340afe9c94d1b2f0e503913745c1"
    "1d79d285883147520bed99479bf13128"
)

EXPECTED_AUTHORIZATION_SHA = (
    "ce533a356144d0d67d6c0e1ae6e9d524"
    "d998004146113e0682eb5a9de38369d6"
)

EXPECTED_PREFLIGHT_SHA = (
    "e6f55eac645ad95b1bc0453ee591013f"
    "0c809baea9b60fce2196b9c7127d7550"
)

EXPECTED_PRELAUNCH_REGISTRY_SHA = (
    "9280fed3afa13f26bc766dc6ee1d2724"
    "c4f07332d0e71c2af4b6bd6b1143ee1e"
)

AUTHORIZED_CASE_COUNT = 4
MAXIMUM_CONCURRENT_CCX = 4
MAXIMUM_TRIAL_INDEX = 6


WAVE_ROOT = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "waves"
    / WAVE_ID
)

WAVE_PATH = (
    WAVE_ROOT
    / "wave_plan.json"
)

AUTH_PATH = (
    WAVE_ROOT
    / "adaptive_campaign_owner_authorization.json"
)

PREFLIGHT_PATH = (
    WAVE_ROOT
    / "adaptive_campaign_preflight.json"
)

PREPARATION_PATH = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / CAMPAIGN_ID
    / WAVE_TOKEN
    / "w03_trial1_preparation.json"
)

REGISTRY_PATH = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / CAMPAIGN_ID
    / WAVE_TOKEN
    / "factory"
    / "w03_trial1_factory.sqlite3"
)

RUNNER_PATH = (
    ROOT
    / "src"
    / "threadrom"
    / "factory"
    / "governed_wave_runner.py"
)


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
        f"Required artifact missing: {path}",
    )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def pin(
    label: str,
    path: Path,
    expected: str,
) -> None:

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
        f"PASS: {label} {actual}",
        flush=True,
    )


print()
print("=" * 108)
print("W03 GENERIC ADAPTIVE FACTORY - FINAL EXECUTION PINS")
print("=" * 108)

pin(
    "Wave plan",
    WAVE_PATH,
    EXPECTED_WAVE_SHA,
)

pin(
    "Trial-1 preparation",
    PREPARATION_PATH,
    EXPECTED_PREPARATION_SHA,
)

pin(
    "Repaired generic runner",
    RUNNER_PATH,
    EXPECTED_RUNNER_SHA,
)

pin(
    "Adaptive owner authorization",
    AUTH_PATH,
    EXPECTED_AUTHORIZATION_SHA,
)

pin(
    "Successful adaptive preflight",
    PREFLIGHT_PATH,
    EXPECTED_PREFLIGHT_SHA,
)

pin(
    "Pre-launch mixed-state registry",
    REGISTRY_PATH,
    EXPECTED_PRELAUNCH_REGISTRY_SHA,
)


# -------------------------------------------------------------------------
# Reconfirm exact durable starting state.
# -------------------------------------------------------------------------

registry = FemFactoryRegistry(
    REGISTRY_PATH
)

jobs = registry.list_jobs()

require(
    len(jobs) == 4,
    f"Expected exactly four W03 factory jobs; found {len(jobs)}.",
)

solved = [
    job
    for job in jobs
    if job.state
    is FemFactoryJobState.SOLVED
]

prepared = [
    job
    for job in jobs
    if job.state
    is FemFactoryJobState.PREPARED
]

running = [
    job
    for job in jobs
    if job.state
    is FemFactoryJobState.RUNNING
]


require(
    len(solved) == 3,
    f"Expected 3 SOLVED CAL_01 jobs; found {len(solved)}.",
)

require(
    len(prepared) == 1,
    f"Expected 1 PREPARED CAL_01 job; found {len(prepared)}.",
)

require(
    not running,
    "RUNNING job exists before explicit adaptive launch.",
)


remaining = prepared[0]

require(
    remaining.run_id
    == "trm_fem_323293011028_cal_01",
    (
        "Unexpected remaining PREPARED job: "
        f"{remaining.run_id}"
    ),
)

require(
    remaining.trial_index == 1,
    "Remaining PREPARED job is not CAL_01.",
)

require(
    remaining.lease_generation == 0,
    "Remaining CAL_01 has already been claimed.",
)

require(
    remaining.manifest_path is None,
    "Remaining CAL_01 already has governed execution evidence.",
)


print()
print("PASS: durable W03 mixed state is exactly:")
print("  3 x CAL_01 SOLVED")
print("  1 x CAL_01 PREPARED")
print("  0 x RUNNING")
print()


# -------------------------------------------------------------------------
# Build the already-preflighted bounded execution contract.
# -------------------------------------------------------------------------

contract = (
    build_governed_wave_execution_contract(
        campaign_id=CAMPAIGN_ID,
        wave_token=WAVE_TOKEN,
        expected_owner_authorization_sha256=(
            EXPECTED_AUTHORIZATION_SHA
        ),
        expected_preparation_index_sha256=(
            EXPECTED_PREPARATION_SHA
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
)


print("=" * 108)
print("EXPLICIT GENERIC ADAPTIVE FACTORY START")
print("=" * 108)

print("Wave                    :", WAVE_ID)
print("Authorized cases        :", AUTHORIZED_CASE_COUNT)
print("Maximum CAL index       :", MAXIMUM_TRIAL_INDEX)
print("Maximum concurrent ccx  :", MAXIMUM_CONCURRENT_CCX)
print("Duplicate execution     : FORBIDDEN")
print("Automatic continuation  : ENABLED")
print("Full physics acceptance : ENABLED")
print("Holdouts                : SEALED")
print("Dataset admission       : BLOCKED")
print()
print("First recovered cycle:")
print("  2 -> FULL PHYSICS CERTIFICATION")
print("  1 -> ADAPTIVE CAL_02")
print("  1 -> EXISTING PREPARED CAL_01")
print()
print("Crossing solver execution boundary now.")
print("=" * 108)
print()


status = run_governed_wave_entrypoint(
    repository_root=ROOT,
    contract=contract,
    execute=True,
)


require(
    status == 0,
    (
        "Generic adaptive factory returned "
        f"non-zero status {status}."
    ),
)


# -------------------------------------------------------------------------
# Successful generic completion must leave all four governed cases accepted.
# -------------------------------------------------------------------------

final_jobs = registry.list_jobs()

require(
    len(final_jobs) >= 4,
    "Factory registry unexpectedly lost jobs.",
)


accepted_cases = {
    job.case_hash
    for job in final_jobs
    if job.state
    is FemFactoryJobState.ACCEPTED
}


initial_case_hashes = {
    job.case_hash
    for job in jobs
}


require(
    accepted_cases
    == initial_case_hashes,
    (
        "Generic runner returned success but the four W03 "
        "cases are not all factory ACCEPTED."
    ),
)


require(
    not any(
        job.state
        is FemFactoryJobState.RUNNING
        for job in final_jobs
    ),
    "RUNNING work remains after successful factory completion.",
)


post_registry_sha = sha256(
    REGISTRY_PATH
)


print()
print("=" * 108)
print("W03 GENERIC AUTONOMOUS ADAPTIVE FACTORY COMPLETE")
print("=" * 108)

for case_hash in sorted(
    initial_case_hashes
):

    case_jobs = [
        job
        for job in final_jobs
        if job.case_hash
        == case_hash
    ]

    case_jobs.sort(
        key=lambda job: job.trial_index
    )

    print()
    print(case_jobs[0].case_id)

    for job in case_jobs:
        print(
            f"  CAL_{job.trial_index:02d}"
            f" | {job.run_id}"
            f" | {job.state.value.upper()}"
        )


print()
print("W03 governed cases      : 4/4 ACCEPTED")
print("Automatic CAL_n         : COMPLETE")
print("Full physics acceptance : COMPLETE")
print("Duplicate solves        : NONE")
print("Holdouts accessed       : NO")
print("Dataset admission       : NO")
print("Final registry SHA      :", post_registry_sha)

print("=" * 108)
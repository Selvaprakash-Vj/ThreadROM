"""Generic governed-wave production execution entry point.

This is the thin explicit execute=True boundary over the certified
ThreadROM governed-wave runtime.

It contains no wave-specific identities. All mutable campaign identity
comes from --wave-id and all immutable launch evidence is SHA-pinned by
the caller.

The command fails closed unless --execute is explicitly supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from threadrom.factory.fem_factory_registry import (
    FemFactoryJobState,
    FemFactoryPriority,
    FemFactoryRegistry,
)
from threadrom.factory.governed_wave_contract import (
    build_governed_wave_execution_contract,
)
from threadrom.factory.governed_wave_runtime import (
    run_governed_wave_entrypoint,
)


ROOT = Path(r"D:\ThreadROM").resolve()

AUTHORIZED_CASE_COUNT = 4
MAXIMUM_CONCURRENT_CCX = 4
MAXIMUM_TRIAL_INDEX = 6

CERTIFIED_RUNNER_SHA256 = (
    "b944340afe9c94d1b2f0e503913745c1"
    "1d79d285883147520bed99479bf13128"
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
        f"Required file missing: {path}",
    )

    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def pin(
    label: str,
    path: Path,
    expected_sha256: str,
) -> None:
    actual = sha256(path)

    require(
        actual == expected_sha256,
        (
            f"{label} SHA drift.\n"
            f"expected={expected_sha256}\n"
            f"actual={actual}"
        ),
    )

    print(
        f"PASS: {label} {actual}",
        flush=True,
    )


def load_json(
    path: Path,
) -> dict:
    require(
        path.is_file(),
        f"Required JSON missing: {path}",
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )

    require(
        isinstance(payload, dict),
        f"Expected JSON object: {path}",
    )

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Start one fully authorized generic governed "
            "ThreadROM diversified-DOE wave."
        )
    )

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

    parser.add_argument(
        "--expected-authorization-sha",
        required=True,
    )

    parser.add_argument(
        "--expected-preflight-sha",
        required=True,
    )

    parser.add_argument(
        "--expected-registry-sha",
        required=True,
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        required=True,
        help=(
            "Explicitly cross the solver execution boundary."
        ),
    )

    args = parser.parse_args()

    wave_id = args.wave_id.strip()

    match = re.fullmatch(
        r"(?P<campaign>TRM-DDOE-\d+)-(?P<wave>W\d+)",
        wave_id,
    )

    require(
        match is not None,
        (
            "Wave ID must match "
            "TRM-DDOE-<campaign>-W<wave>."
        ),
    )

    campaign_id = match.group(
        "campaign"
    )

    wave_token = match.group(
        "wave"
    )

    wave_token_lower = (
        wave_token.lower()
    )

    wave_root = (
        ROOT
        / "docs"
        / "phase3_diversified_doe"
        / "waves"
        / wave_id
    )

    wave_path = (
        wave_root
        / "wave_plan.json"
    )

    authorization_path = (
        wave_root
        / "adaptive_campaign_owner_authorization.json"
    )

    preflight_path = (
        wave_root
        / "governed_execution_preflight.json"
    )

    campaign_root = (
        ROOT
        / "simulations"
        / "staging"
        / "phase3_diversified_doe"
        / campaign_id
        / wave_token
    )

    preparation_path = (
        campaign_root
        / f"{wave_token_lower}_trial1_preparation.json"
    )

    registry_path = (
        campaign_root
        / "factory"
        / f"{wave_token_lower}_trial1_factory.sqlite3"
    )

    runner_path = (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "governed_wave_runner.py"
    )

    print()
    print("=" * 116)
    print(
        f"THREADROM — {wave_token} GENERIC GOVERNED-WAVE EXECUTION BOUNDARY"
    )
    print("=" * 116)

    pin(
        "Wave plan",
        wave_path,
        args.expected_wave_sha,
    )

    pin(
        "Trial-1 preparation",
        preparation_path,
        args.expected_preparation_sha,
    )

    pin(
        "Certified generic runner",
        runner_path,
        CERTIFIED_RUNNER_SHA256,
    )

    pin(
        "Adaptive campaign owner authorization",
        authorization_path,
        args.expected_authorization_sha,
    )

    pin(
        "Governed execution preflight",
        preflight_path,
        args.expected_preflight_sha,
    )

    pin(
        "Pre-launch factory registry",
        registry_path,
        args.expected_registry_sha,
    )

    preflight = load_json(
        preflight_path
    )

    require(
        preflight.get("schema")
        == "threadrom.phase3_governed_wave_execution_preflight.v1",
        "Governed execution preflight schema drift.",
    )

    require(
        preflight.get("record_status")
        == "FINAL",
        "Governed execution preflight is not FINAL.",
    )

    require(
        preflight.get("campaign_id")
        == campaign_id,
        "Preflight campaign identity drift.",
    )

    require(
        preflight.get("wave_id")
        == wave_id,
        "Preflight wave identity drift.",
    )

    require(
        preflight.get("wave_token")
        == wave_token,
        "Preflight wave-token drift.",
    )

    execution_contract = (
        preflight.get(
            "execution_contract"
        )
    )

    require(
        isinstance(
            execution_contract,
            dict,
        ),
        "Preflight execution contract missing.",
    )

    require(
        execution_contract.get(
            "expected_owner_authorization_sha256"
        )
        == args.expected_authorization_sha,
        "Preflight authorization binding drift.",
    )

    require(
        execution_contract.get(
            "expected_preparation_index_sha256"
        )
        == args.expected_preparation_sha,
        "Preflight preparation binding drift.",
    )

    require(
        execution_contract.get(
            "authorized_case_count"
        )
        == AUTHORIZED_CASE_COUNT,
        "Authorized case-count drift.",
    )

    require(
        execution_contract.get(
            "maximum_concurrent_solver_slots"
        )
        == MAXIMUM_CONCURRENT_CCX,
        "Authorized concurrency drift.",
    )

    require(
        execution_contract.get(
            "maximum_trial_index"
        )
        == MAXIMUM_TRIAL_INDEX,
        "Authorized trial ceiling drift.",
    )

    bound = preflight.get(
        "bound_artifacts"
    )

    require(
        isinstance(
            bound,
            dict,
        ),
        "Preflight bound-artifact block missing.",
    )

    require(
        bound.get(
            "wave_plan_sha256"
        )
        == args.expected_wave_sha,
        "Preflight wave-plan binding drift.",
    )

    require(
        bound.get(
            "trial1_preparation_sha256"
        )
        == args.expected_preparation_sha,
        "Preflight Trial-1 preparation binding drift.",
    )

    require(
        bound.get(
            "factory_registry_sha256"
        )
        == args.expected_registry_sha,
        "Preflight registry binding drift.",
    )

    require(
        bound.get(
            "adaptive_campaign_owner_authorization_sha256"
        )
        == args.expected_authorization_sha,
        "Preflight adaptive authorization binding drift.",
    )

    runtime = preflight.get(
        "runtime"
    )

    require(
        isinstance(
            runtime,
            dict,
        ),
        "Preflight runtime block missing.",
    )

    require(
        runtime.get(
            "entrypoint"
        )
        == "run_governed_wave_entrypoint",
        "Preflight runtime entrypoint drift.",
    )

    require(
        runtime.get(
            "execute"
        )
        is False,
        "Preflight was not execute=False.",
    )

    require(
        runtime.get(
            "status"
        )
        == 0,
        "Preflight generic runtime did not pass.",
    )

    require(
        runtime.get(
            "registry_mutated"
        )
        is False,
        "Preflight reports registry mutation.",
    )

    require(
        runtime.get(
            "admission_lock_created"
        )
        is False,
        "Preflight reports admission-lock creation.",
    )

    require(
        runtime.get(
            "solver_evidence_created"
        )
        is False,
        "Preflight reports solver evidence.",
    )

    safety = preflight.get(
        "safety"
    )

    require(
        isinstance(
            safety,
            dict,
        ),
        "Preflight safety block missing.",
    )

    require(
        safety.get(
            "calculix_launched"
        )
        is False,
        "Preflight reports prior CalculiX launch.",
    )

    require(
        safety.get(
            "holdouts_accessed"
        )
        is False,
        "Preflight reports holdout access.",
    )

    require(
        safety.get(
            "dataset_admission_authorized"
        )
        is False,
        "Preflight unexpectedly authorizes dataset admission.",
    )

    require(
        safety.get(
            "surrogate_training_authorized"
        )
        is False,
        "Preflight unexpectedly authorizes surrogate training.",
    )

    registry = FemFactoryRegistry(
        registry_path
    )

    jobs = registry.list_jobs()

    require(
        len(jobs)
        == AUTHORIZED_CASE_COUNT,
        (
            "Expected exactly four pristine Trial-1 jobs; "
            f"found {len(jobs)}."
        ),
    )

    initial_case_hashes: set[str] = set()

    for job in jobs:
        require(
            job.trial_index == 1,
            (
                f"{job.case_id}: pre-launch registry "
                "contains non-CAL_01 work."
            ),
        )

        require(
            job.priority
            is FemFactoryPriority.HIGH_INFORMATION_DOE,
            (
                f"{job.case_id}: factory priority drift."
            ),
        )

        require(
            job.state
            is FemFactoryJobState.PREPARED,
            (
                f"{job.case_id}: expected PREPARED, "
                f"found {job.state.value}."
            ),
        )

        require(
            job.lease_generation == 0,
            (
                f"{job.case_id}: lease generation "
                "is not pristine."
            ),
        )

        require(
            job.lease_owner is None,
            (
                f"{job.case_id}: existing lease owner."
            ),
        )

        require(
            job.manifest_path is None,
            (
                f"{job.case_id}: existing solver manifest."
            ),
        )

        require(
            job.acceptance_record is None,
            (
                f"{job.case_id}: existing acceptance record."
            ),
        )

        require(
            job.failure_category is None
            and job.failure_message is None,
            (
                f"{job.case_id}: pre-launch failure state exists."
            ),
        )

        initial_case_hashes.add(
            job.case_hash
        )

    require(
        len(initial_case_hashes)
        == AUTHORIZED_CASE_COUNT,
        "Initial case hashes are not unique.",
    )

    contract = (
        build_governed_wave_execution_contract(
            campaign_id=campaign_id,
            wave_token=wave_token,
            expected_owner_authorization_sha256=(
                args.expected_authorization_sha
            ),
            expected_preparation_index_sha256=(
                args.expected_preparation_sha
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

    print()
    print("=" * 116)
    print("EXPLICIT GENERIC GOVERNED-WAVE START")
    print("=" * 116)
    print(
        "Wave                    :",
        wave_id,
    )
    print(
        "Authorized cases        :",
        AUTHORIZED_CASE_COUNT,
    )
    print(
        "Maximum CAL index       :",
        MAXIMUM_TRIAL_INDEX,
    )
    print(
        "Maximum concurrent ccx  :",
        MAXIMUM_CONCURRENT_CCX,
    )
    print(
        "Duplicate execution     : FORBIDDEN"
    )
    print(
        "Automatic continuation  : ENABLED"
    )
    print(
        "Full physics acceptance : ENABLED"
    )
    print(
        "Holdouts                : SEALED"
    )
    print(
        "Dataset admission       : BLOCKED"
    )
    print("=" * 116)
    print()

    status = run_governed_wave_entrypoint(
        repository_root=ROOT,
        contract=contract,
        execute=True,
    )

    require(
        status == 0,
        (
            "Generic governed-wave runtime returned "
            f"non-zero status {status}."
        ),
    )

    final_jobs = registry.list_jobs()

    accepted_cases = {
        job.case_hash
        for job in final_jobs
        if job.state
        is FemFactoryJobState.ACCEPTED
    }

    missing_acceptance = (
        initial_case_hashes
        - accepted_cases
    )

    require(
        not missing_acceptance,
        (
            "Generic runtime returned success but "
            "initial governed cases are not all ACCEPTED: "
            f"{sorted(missing_acceptance)}"
        ),
    )

    running_jobs = [
        job
        for job in final_jobs
        if job.state
        is FemFactoryJobState.RUNNING
    ]

    require(
        not running_jobs,
        (
            "RUNNING work remains after successful "
            "generic-wave completion."
        ),
    )

    post_registry_sha = sha256(
        registry_path
    )

    print()
    print("=" * 116)
    print(
        f"{wave_token} GENERIC AUTONOMOUS ADAPTIVE FACTORY COMPLETE"
    )
    print("=" * 116)
    print(
        "Governed cases accepted :",
        len(
            initial_case_hashes
        ),
        "/",
        AUTHORIZED_CASE_COUNT,
    )
    print(
        "Full physics acceptance : COMPLETE"
    )
    print(
        "Duplicate solves        : NONE"
    )
    print(
        "Holdouts accessed       : NO"
    )
    print(
        "Dataset admission       : NO"
    )
    print(
        "Final registry SHA      :",
        post_registry_sha,
    )
    print("=" * 116)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
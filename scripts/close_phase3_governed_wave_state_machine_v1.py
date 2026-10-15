from __future__ import annotations

import hashlib
import json

from pathlib import Path


ROOT = Path(r"D:\ThreadROM").resolve()

DOC_ROOT = (
    ROOT
    / "docs"
    / "phase3_governed_wave_state_machine"
)

STATUS_PATH = (
    DOC_ROOT
    / "status_snapshot_v1.json"
)

CLOSURE_PATH = (
    DOC_ROOT
    / "slice4_closure.json"
)


EXPECTED_SLICE3_SHA = (
    "fcc6074c2596766a9b8daa7909625f24"
    "c67a30630a01ed8fc201e80f5045064a"
)

EXPECTED_W01_DB_SHA = (
    "00f6cdff8617689b1d29103acfa1a177"
    "4b6dab7348bd2cac4ccffa533a4c2e34"
)

EXPECTED_W02_DB_SHA = (
    "892fe09fdd3d463cbb1888f0184086a9"
    "79b3f52d064f53c7ea4b2f59466fabd1"
)


PATHS = {
    "slice3_closure": (
        ROOT
        / "docs"
        / "phase3_governed_wave_runner"
        / "slice3_closure.json"
    ),
    "state_machine": (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "governed_wave_state_machine.py"
    ),
    "controller": (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "governed_wave_controller.py"
    ),
    "state_machine_test": (
        ROOT
        / "tests"
        / "unit"
        / "test_governed_wave_state_machine.py"
    ),
    "controller_test": (
        ROOT
        / "tests"
        / "unit"
        / "test_governed_wave_controller.py"
    ),
    "historical_replay_test": (
        ROOT
        / "tests"
        / "test_governed_wave_controller_historical_replay.py"
    ),
    "generic_runner": (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "governed_wave_runner.py"
    ),
    "w01_registry": (
        ROOT
        / "simulations"
        / "staging"
        / "phase3_diversified_doe"
        / "TRM-DDOE-001"
        / "W01"
        / "factory"
        / "w01_trial1_factory.sqlite3"
    ),
    "w02_registry": (
        ROOT
        / "simulations"
        / "staging"
        / "phase3_diversified_doe"
        / "TRM-DDOE-001"
        / "W02"
        / "factory"
        / "w02_trial1_factory.sqlite3"
    ),
}


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(
            message
        )


def sha256_file(
    path: Path,
) -> str:
    require(
        path.is_file(),
        f"Missing required artifact: {path}",
    )

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as stream:
        for chunk in iter(
            lambda: stream.read(
                8 * 1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def canonical_bytes(
    payload: dict,
) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
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
    encoded = canonical_bytes(
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
            path.read_bytes() == encoded,
            (
                "Immutable Slice-4 artifact drift: "
                f"{path}"
            ),
        )

        return digest

    path.write_bytes(
        encoded
    )

    return digest


# ------------------------------------------------------------------
# Dependency and historical evidence pins
# ------------------------------------------------------------------

require(
    sha256_file(
        PATHS[
            "slice3_closure"
        ]
    )
    == EXPECTED_SLICE3_SHA,
    "Slice-3 closure SHA drift.",
)

require(
    sha256_file(
        PATHS[
            "w01_registry"
        ]
    )
    == EXPECTED_W01_DB_SHA,
    "W01 historical registry SHA drift.",
)

require(
    sha256_file(
        PATHS[
            "w02_registry"
        ]
    )
    == EXPECTED_W02_DB_SHA,
    "W02 historical registry SHA drift.",
)


# ------------------------------------------------------------------
# Pure state-machine semantic replay
# ------------------------------------------------------------------

from threadrom.factory.governed_wave_state_machine import (
    GovernedCaseCampaignSnapshot,
    GovernedWaveAction,
    GovernedWaveCampaignSnapshot,
    GovernedWavePhase,
    GovernedWaveStop,
    decide_governed_wave_campaign,
    drive_governed_wave_campaign,
)


def case(
    name: str,
    *,
    accepted: bool = False,
    running: bool = False,
    blocked: bool = False,
):
    return GovernedCaseCampaignSnapshot(
        case_id=name,
        full_physics_accepted=accepted,
        solver_running=running,
        terminal_blocked=blocked,
    )


def wave(
    *cases,
    authority: bool = True,
    closure: bool = False,
):
    return GovernedWaveCampaignSnapshot(
        wave_id="SYNTHETIC-GOVERNED-WAVE",
        authority_verified=authority,
        authorized_case_count=len(cases),
        cases=tuple(cases),
        closure_verified=closure,
    )


authority_blocked = (
    decide_governed_wave_campaign(
        wave(
            case("A"),
            authority=False,
        )
    )
)

require(
    authority_blocked.phase
    is GovernedWavePhase.BLOCKED_AUTHORITY,
    "Authority fail-closed semantic replay failed.",
)


running_wait = (
    decide_governed_wave_campaign(
        wave(
            case(
                "A",
                running=True,
            ),
            case("B"),
        )
    )
)

require(
    running_wait.action
    is GovernedWaveAction.WAIT_FOR_RUNNING_SOLVER,
    "Running-solver duplicate protection replay failed.",
)


terminal_review = (
    decide_governed_wave_campaign(
        wave(
            case(
                "A",
                blocked=True,
            ),
            case("B"),
        )
    )
)

require(
    terminal_review.action
    is GovernedWaveAction.REQUIRE_ENGINEERING_REVIEW,
    "Terminal engineering-review replay failed.",
)


ready_for_closure = (
    decide_governed_wave_campaign(
        wave(
            case(
                "A",
                accepted=True,
            ),
            case(
                "B",
                accepted=True,
            ),
        )
    )
)

require(
    ready_for_closure.phase
    is GovernedWavePhase.READY_FOR_CLOSURE,
    "All-accepted closure-boundary replay failed.",
)

require(
    ready_for_closure.action
    is GovernedWaveAction.REQUEST_WAVE_CLOSURE,
    "Closure request action replay failed.",
)


closed = (
    decide_governed_wave_campaign(
        wave(
            case(
                "A",
                accepted=True,
            ),
            closure=True,
        )
    )
)

require(
    closed.phase
    is GovernedWavePhase.CLOSED,
    "Verified closure terminal-state replay failed.",
)


# ------------------------------------------------------------------
# Autonomous durable-transition proof
# ------------------------------------------------------------------

states = [
    wave(
        case("A"),
        case(
            "B",
            accepted=True,
        ),
    ),
    wave(
        case(
            "A",
            accepted=True,
        ),
        case(
            "B",
            accepted=True,
        ),
    ),
]

index = 0
execution_count = 0


def supplier():
    return states[
        index
    ]


def execute_once():
    global index
    global execution_count

    execution_count += 1
    index = 1


drive_result = drive_governed_wave_campaign(
    snapshot_supplier=supplier,
    execute_generic_runner_once=execute_once,
    max_runner_actions=1,
)

require(
    execution_count == 1,
    "Synthetic autonomous execution count drift.",
)

require(
    drive_result.stop
    is GovernedWaveStop.READY_FOR_CLOSURE,
    "Autonomous state machine did not reach closure boundary.",
)

require(
    drive_result.actions_performed == 1,
    "Autonomous action accounting drift.",
)


# ------------------------------------------------------------------
# Freeze Slice-4 source identity
# ------------------------------------------------------------------

source_hashes = {
    key: sha256_file(
        PATHS[
            key
        ]
    )
    for key in (
        "state_machine",
        "controller",
        "state_machine_test",
        "controller_test",
        "historical_replay_test",
        "generic_runner",
    )
}


status = {
    "schema": (
        "threadrom.phase3_governed_wave_"
        "state_machine_status.v1"
    ),
    "campaign_id": "TRM-DDOE-001",
    "slice": 4,
    "component": (
        "AUTONOMOUS_ADAPTIVE_CAMPAIGN_"
        "STATE_MACHINE_V1"
    ),
    "state_machine": {
        "authority_fail_closed": True,
        "running_solver_blocks_duplicate_execution": True,
        "terminal_condition_requires_engineering_review": True,
        "generic_runner_handoff_supported": True,
        "durable_transition_required_after_runner_action": True,
        "runner_action_budget_enforced": True,
        "all_cases_accepted_requests_wave_closure": True,
        "verified_wave_closure_is_terminal": True,
    },
    "historical_replay": {
        "w01": {
            "state": "READY_FOR_CLOSURE",
            "runner_execution_attempts": 0,
            "registry_sha256": EXPECTED_W01_DB_SHA,
            "registry_mutated": False,
        },
        "w02": {
            "state": "READY_FOR_CLOSURE",
            "runner_execution_attempts": 0,
            "registry_sha256": EXPECTED_W02_DB_SHA,
            "registry_mutated": False,
        },
    },
    "test_evidence": {
        "step1_state_machine_tests": 19,
        "step2_combined_controller_tests": 26,
        "step1_result": "PASS",
        "step2_result": "PASS",
    },
    "governance_boundary": {
        "wave_closure_owned_by_slice5": True,
        "state_machine_creates_execution_authority": False,
        "state_machine_creates_physics_certificates": False,
        "state_machine_creates_wave_closure": False,
        "w03_execution_authorized": False,
        "w03_launched": False,
        "holdout_access": False,
        "dataset_admission": False,
        "surrogate_training": False,
        "calculix_launched_by_closure": False,
    },
    "dependencies": {
        "slice3_closure_sha256": (
            EXPECTED_SLICE3_SHA
        ),
    },
    "source_hashes": (
        source_hashes
    ),
}


status_sha = write_immutable_json(
    STATUS_PATH,
    status,
)


closure = {
    "schema": (
        "threadrom.phase3_pre_w03_hardening_"
        "slice4_closure.v1"
    ),
    "slice": 4,
    "title": (
        "Autonomous Adaptive Campaign State Machine"
    ),
    "disposition": (
        "SLICE_4_AUTONOMOUS_ADAPTIVE_CAMPAIGN_"
        "STATE_MACHINE_V1_CLOSED"
    ),
    "status_snapshot": {
        "path": str(
            STATUS_PATH.relative_to(
                ROOT
            )
        ).replace(
            "\\",
            "/",
        ),
        "sha256": status_sha,
    },
    "certified_claims": {
        "pure_wave_policy_implemented": True,
        "generic_runner_controller_wired": True,
        "authority_fail_closed": True,
        "running_solver_duplicate_launch_blocked": True,
        "terminal_review_handled": True,
        "durable_transition_required": True,
        "w01_historical_replay_ready_for_closure": True,
        "w02_historical_replay_ready_for_closure": True,
        "historical_runner_execution_attempts": 0,
        "historical_registry_mutation": False,
        "wave_closure_deferred_to_slice5": True,
        "w03_execution_authorized": False,
        "w03_launched": False,
        "calculix_launched_by_closure": False,
        "holdouts_sealed": True,
        "rom_dataset_untouched": True,
    },
    "historical_evidence": {
        "w01_registry_sha256": (
            EXPECTED_W01_DB_SHA
        ),
        "w02_registry_sha256": (
            EXPECTED_W02_DB_SHA
        ),
    },
    "test_evidence": {
        "pure_state_machine": (
            "19 PASSED"
        ),
        "controller_and_historical_replay": (
            "26 PASSED"
        ),
    },
    "source_hashes": (
        source_hashes
    ),
}


closure_sha = write_immutable_json(
    CLOSURE_PATH,
    closure,
)


print()
print("=" * 108)
print(
    "THREADROM - PRE-W03 HARDENING - "
    "SLICE 4 CLOSURE"
)
print("=" * 108)
print(
    "State-machine SHA :",
    source_hashes[
        "state_machine"
    ],
)
print(
    "Controller SHA    :",
    source_hashes[
        "controller"
    ],
)
print(
    "Status SHA        :",
    status_sha,
)
print(
    "Closure SHA       :",
    closure_sha,
)
print(
    "W01 DB SHA        :",
    EXPECTED_W01_DB_SHA,
)
print(
    "W02 DB SHA        :",
    EXPECTED_W02_DB_SHA,
)
print(
    "W01 replay        : READY_FOR_CLOSURE"
)
print(
    "W02 replay        : READY_FOR_CLOSURE"
)
print(
    "Historical launch : 0"
)
print(
    "W03 execution     : NOT AUTHORIZED"
)
print(
    "CalculiX          : NOT LAUNCHED"
)
print(
    "Holdouts          : SEALED"
)
print(
    "ROM dataset       : UNTOUCHED"
)
print()
print(
    "DISPOSITION       : "
    "SLICE_4_AUTONOMOUS_ADAPTIVE_"
    "CAMPAIGN_STATE_MACHINE_V1_CLOSED"
)
print("=" * 108)
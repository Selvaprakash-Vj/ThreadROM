from __future__ import annotations

import copy
import hashlib
import json

from datetime import UTC, datetime
from pathlib import Path


from threadrom.factory.governed_wave_contract import (
    build_governed_wave_execution_contract,
)

from threadrom.factory.governed_wave_owner_authorization import (
    load_and_verify_wave_owner_authorization,
    verify_owner_authorization_payload,
)

from threadrom.factory.governed_wave_runner import (
    build_governed_wave_runner,
)


ROOT = Path(r"D:\ThreadROM").resolve()

CAMPAIGN_ID = "TRM-DDOE-001"
WAVE_TOKEN = "W03"
WAVE_ID = "TRM-DDOE-001-W03"

CASE_COUNT = 4
MAXIMUM_CCX = 4
MAXIMUM_TRIAL = 6


# ============================================================================
# Frozen W03 evidence
# ============================================================================

EXPECTED_WAVE_SHA = (
    "3714441cb14386e2fcc3adf7b90300a1"
    "dcec6ebd2d4404212f2a1adbacb3b225"
)

EXPECTED_TRIAL1_PREPARATION_AUTH_SHA = (
    "3dedf60b0bf5a8a40d83ee9525d6f4f"
    "effaffef7f91edcc2a88610807dc7365e"
)

EXPECTED_GEOMETRY_MESH_AUTH_SHA = (
    "b08c6b514046313fc96a131420425597"
    "a77f0738664576c6cb7e9f2997c1eb6d"
)

EXPECTED_PREPARATION_SHA = (
    "813b602392dd66cf0b30e2089b3695c8"
    "e8ae0859946da775bfc1736efd404393"
)

EXPECTED_TRIAL1_EXECUTION_AUTH_SHA = (
    "60afcb826a2c8228ac405d4d0c772e7c"
    "fb2a6a625a18685b32d8c661c56b59fc"
)

EXPECTED_RUNNER_SHA = (
    "b944340afe9c94d1b2f0e503913745c1"
    "1d79d285883147520bed99479bf13128"
)

EXPECTED_REGISTRY_SHA = (
    "9280fed3afa13f26bc766dc6ee1d2724"
    "c4f07332d0e71c2af4b6bd6b1143ee1e"
)


# ============================================================================
# Known-good W02 adaptive authorization template
# ============================================================================

EXPECTED_W02_AUTH_SHA = (
    "19f5fa4bcd31eb8a1bff992f17d2c60"
    "a5ff70fdcf741521cc834401c99e6890a"
)


WAVE_ROOT = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "waves"
    / WAVE_ID
)

W02_AUTH_PATH = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "waves"
    / "TRM-DDOE-001-W02"
    / "adaptive_campaign_owner_authorization.json"
)

AUTH_PATH = (
    WAVE_ROOT
    / "adaptive_campaign_owner_authorization.json"
)

PREFLIGHT_EVIDENCE_PATH = (
    WAVE_ROOT
    / "adaptive_campaign_preflight.json"
)

WAVE_PATH = (
    WAVE_ROOT
    / "wave_plan.json"
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

TRIAL1_EXECUTION_AUTH_PATH = (
    WAVE_ROOT
    / "trial1_execution_owner_authorization.json"
)

TRIAL1_PREPARATION_AUTH_PATH = (
    WAVE_ROOT
    / "trial1_owner_authorization.json"
)

GEOMETRY_MESH_AUTH_PATH = (
    WAVE_ROOT
    / "geometry_mesh_owner_authorization.json"
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
        f"Missing required file: {path}",
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


def canonical_json_bytes(
    payload: object,
) -> bytes:

    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def read_json(
    path: Path,
) -> dict:

    payload = json.loads(
        path.read_text(
            encoding="utf-8-sig",
        )
    )

    require(
        isinstance(payload, dict),
        f"{path}: expected JSON object.",
    )

    return payload


def require_sha(
    path: Path,
    expected: str,
    label: str,
) -> None:

    actual = sha256(
        path
    )

    require(
        actual == expected,
        (
            f"{label} SHA drift. "
            f"expected={expected} actual={actual}"
        ),
    )

    print(
        f"PASS: {label} {actual}",
        flush=True,
    )


print()
print("=" * 108)
print("W03 ADAPTIVE OWNER AUTHORIZATION - FROZEN INPUT PINS")
print("=" * 108)


require_sha(
    WAVE_PATH,
    EXPECTED_WAVE_SHA,
    "W03 wave plan",
)

require_sha(
    PREPARATION_PATH,
    EXPECTED_PREPARATION_SHA,
    "W03 Trial-1 preparation",
)

require_sha(
    RUNNER_PATH,
    EXPECTED_RUNNER_SHA,
    "repaired generic runner",
)

require_sha(
    REGISTRY_PATH,
    EXPECTED_REGISTRY_SHA,
    "W03 mixed-state factory registry",
)

require_sha(
    TRIAL1_EXECUTION_AUTH_PATH,
    EXPECTED_TRIAL1_EXECUTION_AUTH_SHA,
    "existing W03 CAL_01 execution authorization",
)

require_sha(
    TRIAL1_PREPARATION_AUTH_PATH,
    EXPECTED_TRIAL1_PREPARATION_AUTH_SHA,
    "W03 Trial-1 preparation authorization",
)

require_sha(
    GEOMETRY_MESH_AUTH_PATH,
    EXPECTED_GEOMETRY_MESH_AUTH_SHA,
    "W03 geometry/mesh preparation authorization",
)

require_sha(
    W02_AUTH_PATH,
    EXPECTED_W02_AUTH_SHA,
    "known-good W02 adaptive authorization template",
)


# ============================================================================
# Build W03 authorization from exact known-good schema
# ============================================================================

created_authorization = False


if AUTH_PATH.exists():

    authorization = read_json(
        AUTH_PATH
    )

    authorization_bytes = (
        AUTH_PATH.read_bytes()
    )

    authorization_sha = hashlib.sha256(
        authorization_bytes
    ).hexdigest()

    print()
    print(
        "Existing W03 adaptive authorization found:",
        authorization_sha,
    )

else:

    template = read_json(
        W02_AUTH_PATH
    )

    authorization = copy.deepcopy(
        template
    )

    authorization[
        "approval_status"
    ] = "OWNER_APPROVED"

    authorization[
        "approved_by"
    ] = (
        "Selva - ThreadROM project owner"
    )

    if (
        "approved_at_utc"
        in authorization
    ):
        authorization[
            "approved_at_utc"
        ] = datetime.now(
            UTC
        ).isoformat()

    elif (
        "approved_at"
        in authorization
    ):
        authorization[
            "approved_at"
        ] = datetime.now(
            UTC
        ).isoformat()

    else:
        raise RuntimeError(
            "Authorization template has no approval timestamp field."
        )

    authorization[
        "authorization_type"
    ] = (
        "OWNER_BOUNDED_ADAPTIVE_WAVE_CAMPAIGN_AUTHORIZATION"
    )

    authorization[
        "campaign_id"
    ] = CAMPAIGN_ID

    authorization[
        "wave_id"
    ] = WAVE_ID

    authorization[
        "engineering_intent"
    ] = (
        "One owner launch authorizes the generic governed adaptive "
        "factory for the four frozen W03 cases. The factory may reuse "
        "already-completed valid CAL_01 results, execute the one still-"
        "PREPARED authorized CAL_01 without regeneration, automatically "
        "continue CAL_02 through CAL_06 where required, and perform "
        "governed full-physics certification until every case reaches "
        "governed full-physics acceptance or a defined terminal condition. "
        "No manual approval is required between governed calibration "
        "trials inside this bounded W03 scope."
    )

    bound = authorization[
        "bound_artifacts"
    ]

    require(
        isinstance(
            bound,
            dict,
        ),
        "Authorization template bound_artifacts missing.",
    )

    # Remove prior wave's preparation-specific binding.
    for key in tuple(
        bound
    ):
        if (
            key.endswith(
                "_trial1_preparation_sha256"
            )
        ):
            del bound[key]

    bound[
        "geometry_mesh_owner_authorization_sha256"
    ] = (
        EXPECTED_GEOMETRY_MESH_AUTH_SHA
    )

    bound[
        "trial1_owner_authorization_sha256"
    ] = (
        EXPECTED_TRIAL1_PREPARATION_AUTH_SHA
    )

    bound[
        "w03_trial1_preparation_sha256"
    ] = (
        EXPECTED_PREPARATION_SHA
    )

    bound[
        "wave_plan_sha256"
    ] = (
        EXPECTED_WAVE_SHA
    )


    execution_contract = authorization[
        "execution_contract"
    ]

    require(
        isinstance(
            execution_contract,
            dict,
        ),
        "Authorization execution_contract missing.",
    )

    execution_contract[
        "automatic_governed_adaptation"
    ] = True

    execution_contract[
        "continue_until_physics_acceptance"
    ] = True

    execution_contract[
        "duplicate_solver_execution_forbidden"
    ] = True

    execution_contract[
        "full_physics_certification"
    ] = True

    execution_contract[
        "maximum_concurrent_calculix"
    ] = MAXIMUM_CCX

    execution_contract[
        "maximum_trial_index_per_case"
    ] = MAXIMUM_TRIAL

    execution_contract[
        "preload_calibration_continuation"
    ] = True

    execution_contract[
        "preserve_all_valid_realized_trials"
    ] = True

    execution_contract[
        "reuse_existing_valid_trials"
    ] = True

    execution_contract[
        "stop_on_governed_terminal_condition"
    ] = True

    execution_contract[
        "stop_on_non_monotonic_response"
    ] = True

    execution_contract[
        "stop_on_provenance_or_identity_failure"
    ] = True

    execution_contract[
        "stop_on_unrecoverable_solver_failure"
    ] = True


    authorization[
        "required_completion_state"
    ] = (
        "GOVERNED_FULL_PHYSICS_ACCEPTED"
    )


    scope = authorization[
        "scope"
    ]

    require(
        isinstance(
            scope,
            dict,
        ),
        "Authorization scope missing.",
    )

    scope[
        "authorized_case_count"
    ] = CASE_COUNT

    scope[
        "additional_doe_cases_authorized"
    ] = False

    scope[
        "additional_waves_authorized"
    ] = False

    scope[
        "artifact_retirement_authorized"
    ] = False

    scope[
        "dataset_admission_authorized"
    ] = False

    scope[
        "holdout_access_authorized"
    ] = False

    scope[
        "independent_human_review_claimed"
    ] = False

    scope[
        "surrogate_training_authorized"
    ] = False


    authorization_bytes = (
        canonical_json_bytes(
            authorization
        )
    )

    authorization_sha = hashlib.sha256(
        authorization_bytes
    ).hexdigest()


# ============================================================================
# Build contract around the actual immutable authorization SHA
# ============================================================================

contract = (
    build_governed_wave_execution_contract(
        campaign_id=CAMPAIGN_ID,
        wave_token=WAVE_TOKEN,
        expected_owner_authorization_sha256=(
            authorization_sha
        ),
        expected_preparation_index_sha256=(
            EXPECTED_PREPARATION_SHA
        ),
        authorized_case_count=(
            CASE_COUNT
        ),
        maximum_concurrent_solver_slots=(
            MAXIMUM_CCX
        ),
        maximum_trial_index=(
            MAXIMUM_TRIAL
        ),
    )
)


# ============================================================================
# Canonical authorization verification BEFORE publication
# ============================================================================

verify_owner_authorization_payload(
    payload=authorization,
    contract=contract,
    authorization_sha256=(
        authorization_sha
    ),
)


if not AUTH_PATH.exists():

    AUTH_PATH.write_bytes(
        authorization_bytes
    )

    created_authorization = True


require(
    sha256(
        AUTH_PATH
    )
    == authorization_sha,
    "Published W03 adaptive authorization SHA drift.",
)


verified = (
    load_and_verify_wave_owner_authorization(
        repository_root=ROOT,
        contract=contract,
    )
)


print()
print("=" * 108)
print("W03 ADAPTIVE OWNER AUTHORIZATION - VERIFIED")
print("=" * 108)

print(
    "Authorization SHA :",
    authorization_sha,
)

print(
    "Cases             :",
    CASE_COUNT,
)

print(
    "Max CAL index     :",
    MAXIMUM_TRIAL,
)

print(
    "Max concurrent ccx:",
    MAXIMUM_CCX,
)

print(
    "Adaptive CAL_n    : AUTHORIZED",
)

print(
    "Physics certify   : AUTHORIZED",
)

print(
    "Duplicate solves  : FORBIDDEN",
)

print(
    "Holdouts          : SEALED",
)

print(
    "Dataset admission : BLOCKED",
)


# ============================================================================
# REAL GENERIC PREFLIGHT
# ============================================================================

registry_sha_before = sha256(
    REGISTRY_PATH
)


try:

    print()
    print("=" * 108)
    print("REAL GENERIC W03 ADAPTIVE FACTORY PREFLIGHT")
    print("execute=False / NO SOLVER LAUNCH")
    print("=" * 108)

    runner = build_governed_wave_runner(
        repository_root=ROOT,
        contract=contract,
    )

    result = runner.preflight()

    require(
        result == 0,
        (
            "Generic W03 adaptive preflight "
            f"returned non-zero result: {result}"
        ),
    )


    # ------------------------------------------------------------------
    # Safety invariants after preflight
    # ------------------------------------------------------------------

    registry_sha_after = sha256(
        REGISTRY_PATH
    )

    require(
        registry_sha_after
        == registry_sha_before
        == EXPECTED_REGISTRY_SHA,
        "W03 registry mutated during preflight.",
    )


    # ------------------------------------------------------------------
    # Freeze successful preflight evidence.
    #
    # This intentionally binds both:
    #   1. the generic adaptive owner authorization, and
    #   2. the already-existing explicit CAL_01 execution authority.
    #
    # Therefore the remaining PREPARED steel CAL_01 has not lost its
    # original explicit owner authority while entering the generic factory.
    # ------------------------------------------------------------------

    preflight_evidence = {
        "schema": (
            "threadrom.phase3_governed_wave_"
            "adaptive_preflight.v1"
        ),
        "record_status": "FINAL",
        "campaign_id": CAMPAIGN_ID,
        "wave_id": WAVE_ID,
        "runner_sha256": (
            EXPECTED_RUNNER_SHA
        ),
        "wave_plan_sha256": (
            EXPECTED_WAVE_SHA
        ),
        "preparation_index_sha256": (
            EXPECTED_PREPARATION_SHA
        ),
        "adaptive_owner_authorization_sha256": (
            authorization_sha
        ),
        "trial1_execution_owner_authorization_sha256": (
            EXPECTED_TRIAL1_EXECUTION_AUTH_SHA
        ),
        "factory_registry_sha256": (
            registry_sha_after
        ),
        "execution_contract": {
            "authorized_case_count": (
                CASE_COUNT
            ),
            "maximum_concurrent_calculix": (
                MAXIMUM_CCX
            ),
            "maximum_trial_index_per_case": (
                MAXIMUM_TRIAL
            ),
            "automatic_governed_adaptation": True,
            "full_physics_certification": True,
            "duplicate_solver_execution_forbidden": True,
        },
        "safety": {
            "calculix_launched": False,
            "registry_mutated": False,
            "dataset_admission_authorized": False,
            "holdout_access_authorized": False,
        },
        "expected_first_cycle": {
            "calibration_accepted_pending_physics": 2,
            "existing_prepared_cal_01": 1,
            "adaptive_cal_02_plus": 1,
        },
        "overall_disposition": (
            "W03_GENERIC_ADAPTIVE_PREFLIGHT_PASS_"
            "EXECUTION_NOT_STARTED"
        ),
    }

    evidence_bytes = (
        canonical_json_bytes(
            preflight_evidence
        )
    )

    if PREFLIGHT_EVIDENCE_PATH.exists():

        require(
            PREFLIGHT_EVIDENCE_PATH.read_bytes()
            == evidence_bytes,
            (
                "Existing adaptive preflight evidence "
                "differs from current governed state."
            ),
        )

    else:

        PREFLIGHT_EVIDENCE_PATH.write_bytes(
            evidence_bytes
        )


    evidence_sha = sha256(
        PREFLIGHT_EVIDENCE_PATH
    )


    print()
    print("=" * 108)
    print("W03 GENERIC ADAPTIVE PREFLIGHT - PASS")
    print("=" * 108)

    print(
        "Authorization SHA :",
        authorization_sha,
    )

    print(
        "Preflight SHA     :",
        evidence_sha,
    )

    print(
        "Runner SHA        :",
        EXPECTED_RUNNER_SHA,
    )

    print(
        "Registry SHA      :",
        registry_sha_after,
    )

    print()
    print(
        "First cycle       : "
        "2 PHYSICS + 1 PREPARED CAL_01 + 1 CAL_02"
    )

    print(
        "CalculiX launched : NO"
    )

    print(
        "Registry mutated  : NO"
    )

    print(
        "Holdouts accessed : NO"
    )

    print(
        "Dataset admission : NO"
    )

    print()
    print(
        "NEXT ACTION       : ONE GENERIC ADAPTIVE EXECUTE"
    )

    print("=" * 108)


except Exception:

    # A newly-created execution authorization must never remain behind
    # after a failed first preflight.
    if created_authorization:
        try:
            AUTH_PATH.unlink()
            print(
                "ROLLBACK: newly-created W03 adaptive "
                "authorization removed.",
                flush=True,
            )
        except FileNotFoundError:
            pass

    raise
from __future__ import annotations

import hashlib
import json
import math

from pathlib import Path

import threadrom.factory.fem_case_definition_bundle as bundle_mod

from threadrom.factory.fem_solver_orchestrator import (
    orchestrate_calculix_run,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)
from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
)


ROOT = Path(r"D:\ThreadROM")
CONFIG = ROOT / "config"

CAMPAIGN_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp8_production_doe"
    / "TRM-PDOE-C01"
)

SOLVER_ROOT = (
    CAMPAIGN_ROOT
    / "solver_preparation"
)

DOE_POLICY_PATH = (
    CONFIG
    / "phase3_production_doe.toml"
)

CAMPAIGN_MANIFEST_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_campaign_manifest.json"
)

PREPARATION_CERT_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_preparation_certification_record.json"
)

V21_POLICY_PATH = (
    CONFIG
    / "phase3_warm_start_delta_t_v2_1.toml"
)

PREDICTION_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_prospective_prediction.json"
)

CASE_ID = "D-INT-008"

CASE_HASH = (
    "1faafccbbc3b9eb2068af0f45c8d91951a29d85917c60871d82535d2ca857315"
)

CASE_RUN_ID = (
    "trm_fem_1faafccbbc3b"
)

RUN_ID = (
    "trm_fem_1faafccbbc3b_cal_01_wsv21"
)

RUN_DIR = (
    SOLVER_ROOT
    / CASE_RUN_ID
    / RUN_ID
)

PREP_PATH = (
    RUN_DIR
    / "production_doe_v2_1_prospective_solver_preparation_record.json"
)

MANIFEST_PATH = (
    RUN_DIR
    / "fem_run_manifest.json"
)

EXPECTED_DOE_POLICY_SHA256 = (
    "43032557cb2abead0118362bcfc6a9b2e"
    "5246a7d363ca83eef5fcf35054befc1"
)

EXPECTED_CAMPAIGN_SHA256 = (
    "84516519bbb188664268936e2d116e133"
    "431d90d037bed407ffb2d1fe92d2a67"
)

EXPECTED_PREPARATION_CERT_SHA256 = (
    "ad49cc35b61e95147ae669f0f915b8d7a"
    "e403145d098729e5540285f319befd5"
)

EXPECTED_V21_POLICY_SHA256 = (
    "db2a2af4a2954801d7e1db931672a197"
    "629a5dfcab19431c3a38db65b580268c"
)

EXPECTED_PREDICTION_SHA256 = (
    "36b0230083c98fc2674adf98b5d5f3ab"
    "a75c736888cfb44c113b86272c53ec4f"
)

EXPECTED_PREP_SHA256 = (
    "5abbac8e1ddf4912f6e3f9ec1059986c"
    "2d447285e39573cf429acbdc58ab755d"
)

EXPECTED_DECK_SHA256 = (
    "dce4cc59db039f7a054020ae491ab1e9f"
    "d22cd41b8d2e7397ef2e5e69af51714"
)

EXPECTED_DELTA_T_C = (
    -223.85290919588718
)


def sha256(path: Path) -> str:
    if (
        not path.is_file()
        or path.stat().st_size <= 0
    ):
        raise FileNotFoundError(path)

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


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:

    actual = sha256(path)

    if actual != expected:
        raise RuntimeError(
            f"{label} SHA drift.\n"
            f"Expected: {expected}\n"
            f"Actual  : {actual}\n"
            f"Path    : {path}"
        )

    return actual


def load_json(
    path: Path,
) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


# ============================================================
# 1. GOVERNANCE INTEGRITY
# ============================================================

require_sha256(
    DOE_POLICY_PATH,
    EXPECTED_DOE_POLICY_SHA256,
    "Production DOE policy",
)

require_sha256(
    CAMPAIGN_MANIFEST_PATH,
    EXPECTED_CAMPAIGN_SHA256,
    "Production DOE campaign manifest",
)

require_sha256(
    PREPARATION_CERT_PATH,
    EXPECTED_PREPARATION_CERT_SHA256,
    "Production DOE preparation certification",
)

require_sha256(
    V21_POLICY_PATH,
    EXPECTED_V21_POLICY_SHA256,
    "Warm-Start V2.1 policy",
)

require_sha256(
    PREDICTION_PATH,
    EXPECTED_PREDICTION_SHA256,
    "Frozen V2.1 prospective prediction",
)

prep_sha = require_sha256(
    PREP_PATH,
    EXPECTED_PREP_SHA256,
    "V2.1 prospective solver preparation",
)


# ============================================================
# 2. PREPARATION SIDECAR
# ============================================================

prep_sidecar = (
    PREP_PATH.with_suffix(
        ".sha256"
    )
)

expected_sidecar = (
    f"{prep_sha}  {PREP_PATH.name}\n"
)

if (
    not prep_sidecar.is_file()
    or prep_sidecar.read_text(
        encoding="ascii"
    )
    != expected_sidecar
):
    raise RuntimeError(
        "V2.1 preparation SHA sidecar drift."
    )


# ============================================================
# 3. FROZEN DOE IDENTITY
# ============================================================

policy = (
    load_phase3_production_doe_policy(
        DOE_POLICY_PATH
    )
)

campaign = (
    build_phase3_production_doe(
        policy
    )
)

matches = tuple(
    item
    for item in campaign.design_cases
    if item.case_id == CASE_ID
)

if len(matches) != 1:
    raise RuntimeError(
        f"{CASE_ID}: expected exactly one "
        f"Production DOE design case; "
        f"found {len(matches)}."
    )

doe_case = matches[0]

if (
    doe_case.case_hash
    != CASE_HASH
):
    raise RuntimeError(
        "Prospective case-hash drift."
    )

if (
    doe_case.source_case_id
    is not None
):
    raise RuntimeError(
        "Prospective sentinel unexpectedly "
        "became an existing anchor."
    )


# ============================================================
# 4. EXACT PREPARATION BINDING
# ============================================================

prep = load_json(
    PREP_PATH
)

if (
    prep[
        "record_status"
    ]
    != "FINAL"
):
    raise RuntimeError(
        "V2.1 prospective preparation is not FINAL."
    )

if (
    prep[
        "overall_disposition"
    ]
    != (
        "V2_1_PROSPECTIVE_"
        "SOLVER_PREPARATION_PASS"
    )
):
    raise RuntimeError(
        "Unexpected V2.1 preparation disposition."
    )

case = prep[
    "case"
]

if (
    case[
        "case_id"
    ]
    != CASE_ID
    or case[
        "case_hash"
    ]
    != CASE_HASH
):
    raise RuntimeError(
        "Prepared prospective case identity mismatch."
    )

if (
    case[
        "prospective_trial_run_id"
    ]
    != RUN_ID
):
    raise RuntimeError(
        "Prepared prospective run-ID mismatch."
    )

if (
    prep[
        "fem_preflight"
    ][
        "status"
    ]
    != "PASS"
    or int(
        prep[
            "fem_preflight"
        ][
            "blocking_error_count"
        ]
    )
    != 0
):
    raise RuntimeError(
        "Prospective FEM preflight is not clean."
    )

authorization = prep[
    "solve_authorization"
]

if (
    authorization[
        "calculix_invoked"
    ]
    is not False
    or authorization[
        "solver_authorized_by_this_script"
    ]
    is not False
    or authorization[
        "holdout_accessed"
    ]
    is not False
):
    raise RuntimeError(
        "Prospective preparation provenance "
        "is not clean."
    )

if (
    prep[
        "governance"
    ][
        "v2_1_policy_sha256"
    ]
    != EXPECTED_V21_POLICY_SHA256
):
    raise RuntimeError(
        "V2.1 policy binding drift."
    )

if (
    prep[
        "governance"
    ][
        "prospective_prediction_sha256"
    ]
    != EXPECTED_PREDICTION_SHA256
):
    raise RuntimeError(
        "Prospective prediction binding drift."
    )


# ============================================================
# 5. EXACT TRIAL / DECK BINDING
# ============================================================

trial = prep[
    "trial_1"
]

if (
    int(
        trial[
            "trial_index"
        ]
    )
    != 1
):
    raise RuntimeError(
        "Prospective FEM must remain Trial 1."
    )

if (
    trial[
        "run_id"
    ]
    != RUN_ID
):
    raise RuntimeError(
        "Prospective trial run-ID drift."
    )

trial_dt = float(
    trial[
        "delta_temperature_c"
    ]
)

if not math.isclose(
    trial_dt,
    EXPECTED_DELTA_T_C,
    rel_tol=0.0,
    abs_tol=1.0e-10,
):
    raise RuntimeError(
        "Prospective frozen delta-T drift."
    )

deck_path = (
    ROOT
    / prep[
        "deck"
    ][
        "relative_path"
    ]
)

deck_sha = require_sha256(
    deck_path,
    EXPECTED_DECK_SHA256,
    "V2.1 prospective FEM deck",
)

if (
    deck_sha
    != prep[
        "deck"
    ][
        "sha256"
    ]
):
    raise RuntimeError(
        "Deck hash differs from preparation record."
    )

if (
    deck_path.stat().st_size
    != int(
        prep[
            "deck"
        ][
            "size_bytes"
        ]
    )
):
    raise RuntimeError(
        "Prospective deck size drift."
    )

if (
    deck_path.name
    != f"{RUN_ID}.inp"
):
    raise RuntimeError(
        "Prospective deck filename/run-ID mismatch."
    )

if not math.isclose(
    float(
        prep[
            "deck"
        ][
            "delta_temperature_c"
        ]
    ),
    EXPECTED_DELTA_T_C,
    rel_tol=0.0,
    abs_tol=1.0e-10,
):
    raise RuntimeError(
        "Prospective deck delta-T metadata drift."
    )


# ============================================================
# 6. DUPLICATE-SOLVE GUARD
# ============================================================

if MANIFEST_PATH.exists():
    raise RuntimeError(
        "Prospective FEM run manifest already exists. "
        "Refusing accidental duplicate solve:\n"
        f"{MANIFEST_PATH}"
    )


# ============================================================
# 7. CERTIFIED SOLVER BACKEND
# ============================================================

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
    job_name=RUN_ID,
    timeout_seconds=None,
)


# ============================================================
# 8. LAUNCH EXACTLY ONE PROSPECTIVE FEM
# ============================================================

print("=" * 128, flush=True)
print(
    "THREADROM - WARM-START V2.1 "
    "SINGLE PROSPECTIVE FEM START",
    flush=True,
)
print("=" * 128, flush=True)

print(
    "Case ID              :",
    CASE_ID,
    flush=True,
)

print(
    "Case hash            :",
    CASE_HASH,
    flush=True,
)

print(
    "Run ID               :",
    RUN_ID,
    flush=True,
)

print(
    "Target preload N     :",
    case[
        "target_preload_n"
    ],
    flush=True,
)

print(
    "Frozen delta T C     :",
    trial_dt,
    flush=True,
)

print(
    "Deck SHA256          :",
    deck_sha,
    flush=True,
)

print(
    "Preparation SHA256   :",
    prep_sha,
    flush=True,
)

print(
    "Prediction SHA256    :",
    EXPECTED_PREDICTION_SHA256,
    flush=True,
)

print(
    "V2.1 policy SHA256   :",
    EXPECTED_V21_POLICY_SHA256,
    flush=True,
)

print(
    "Timeout              : NONE",
    flush=True,
)

print(
    "Blind holdouts used  : NO",
    flush=True,
)

print(
    "Manifest             :",
    MANIFEST_PATH,
    flush=True,
)

print("=" * 128, flush=True)


result = orchestrate_calculix_run(
    project_root=ROOT,
    input_path=deck_path,
    definition=definition,
    run_id=RUN_ID,
    case_hash=CASE_HASH,
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
        MANIFEST_PATH
    ),
)


# ============================================================
# 9. FINISH REPORT
# ============================================================

print()
print("=" * 128, flush=True)
print(
    "THREADROM - WARM-START V2.1 "
    "SINGLE PROSPECTIVE FEM FINISHED",
    flush=True,
)
print("=" * 128, flush=True)

print(
    "Case ID              :",
    CASE_ID,
    flush=True,
)

print(
    "Run ID               :",
    RUN_ID,
    flush=True,
)

print(
    "Disposition          :",
    result.manifest.disposition,
    flush=True,
)

print(
    "Job finished         :",
    result.manifest.job_finished,
    flush=True,
)

print(
    "Manifest             :",
    result.manifest_path,
    flush=True,
)

print("=" * 128, flush=True)
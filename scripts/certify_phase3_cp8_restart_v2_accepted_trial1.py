from __future__ import annotations

import argparse
import hashlib
import json
import math
import re

from pathlib import Path

from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)
from threadrom.factory.preload_calibration_controller import (
    evaluate_preload_calibration,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)
from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
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

WARM_V1_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_warm_start_knowledge_record.json"
)

V21_POLICY_PATH = (
    CONFIG
    / "phase3_warm_start_delta_t_v2_1.toml"
)

FROZEN_PREDICTION_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_prospective_prediction.json"
)

ROLLOUT_CERT_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_rollout_preparation_certification.json"
)

RV2_WAVE_PREP_PATH = (
    CAMPAIGN_ROOT
    / "cp8_restart_v2_wave_01_preparation_manifest.json"
)

RV2_EXEC_CERT_PATH = (
    CAMPAIGN_ROOT
    / "cp8_restart_v2_wave_01_execution_certification.json"
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

EXPECTED_WARM_V1_SHA256 = (
    "21e525db65d36a13ca6e2ee96514307f"
    "6234b2518bd60423f872f6dfa6fae8f7"
)

EXPECTED_V21_POLICY_SHA256 = (
    "db2a2af4a2954801d7e1db931672a197"
    "629a5dfcab19431c3a38db65b580268c"
)

EXPECTED_FROZEN_PREDICTION_SHA256 = (
    "36b0230083c98fc2674adf98b5d5f3ab"
    "a75c736888cfb44c113b86272c53ec4f"
)

EXPECTED_ROLLOUT_CERT_SHA256 = (
    "a11662817427d9131b92f798e953d116"
    "269ad672c49434365a75f68dac4709a7"
)

EXPECTED_RV2_WAVE_PREP_SHA256 = (
    "081db1e1b27424b509b82476716ed6f9"
    "6ab5bd96de5f6b91c7730d11dba2c37b"
)

EXPECTED_RV2_EXEC_CERT_SHA256 = (
    "f608970e67124d05e6c47885d032a54e"
    "7c422cd8500714a1f593157d180eceb7"
)

AUTHORIZED_CASE_IDS = (
    "D-INT-001",
    "D-INT-003",
    "D-INT-005",
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Certify one accepted restart-v2 replacement "
            "Warm-Start V2.1 Trial-1 Production DOE FEM result."
        )
    )

    parser.add_argument(
        "--case-id",
        required=True,
        choices=AUTHORIZED_CASE_IDS,
    )

    return parser.parse_args()


def sha256(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)

    if path.stat().st_size <= 0:
        raise RuntimeError(
            f"Required artifact is empty: {path}"
        )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
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


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def relative(path: Path) -> str:
    return (
        path.resolve()
        .relative_to(ROOT.resolve())
        .as_posix()
    )


def write_immutable_json(
    path: Path,
    payload: dict,
) -> tuple[str, str]:
    serialized = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    if path.exists():
        existing = path.read_text(
            encoding="utf-8"
        )

        if existing != serialized:
            raise RuntimeError(
                "Accepted FEM evidence already exists "
                "with different content. Refusing overwrite: "
                f"{path}"
            )

        action = "UNCHANGED / IDENTICAL"

    else:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = path.with_suffix(
            ".json.tmp"
        )

        temporary.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )

        temporary.replace(path)

        action = "CREATED"

    record_sha = sha256(path)

    sidecar = path.with_suffix(
        ".sha256"
    )

    expected_sidecar = (
        f"{record_sha}  {path.name}\n"
    )

    if sidecar.exists():
        observed = sidecar.read_text(
            encoding="ascii"
        )

        if observed != expected_sidecar:
            raise RuntimeError(
                "Accepted-evidence SHA sidecar drift: "
                f"{sidecar}"
            )

    else:
        sidecar.write_text(
            expected_sidecar,
            encoding="ascii",
            newline="\n",
        )

    return action, record_sha


def find_unique(
    rows,
    case_id: str,
    *,
    label: str,
):
    matches = [
        row
        for row in rows
        if (
            getattr(row, "case_id", None)
            if not isinstance(row, dict)
            else row.get("case_id")
        )
        == case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected exactly one {label}; "
            f"found {len(matches)}."
        )

    return matches[0]


def accepted_sta_rows(
    sta_path: Path,
) -> list[list[str]]:
    rows = []

    pattern = re.compile(
        r"^\s*\d+\s+\d+\s+\d+\s+\d+"
        r"\s+[0-9.Ee+\-]+"
        r"\s+[0-9.Ee+\-]+"
        r"\s+[0-9.Ee+\-]+"
    )

    for line in sta_path.read_text(
        encoding="utf-8-sig"
    ).splitlines():
        if pattern.match(line):
            rows.append(
                line.strip().split()
            )

    return rows


args = parse_arguments()


# ============================================================
# 1. LOCK GOVERNANCE
# ============================================================

doe_policy_sha = require_sha256(
    DOE_POLICY_PATH,
    EXPECTED_DOE_POLICY_SHA256,
    "Production DOE policy",
)

campaign_sha = require_sha256(
    CAMPAIGN_MANIFEST_PATH,
    EXPECTED_CAMPAIGN_SHA256,
    "Production DOE campaign manifest",
)

prep_cert_sha = require_sha256(
    PREPARATION_CERT_PATH,
    EXPECTED_PREPARATION_CERT_SHA256,
    "Production DOE preparation certification",
)

warm_v1_sha = require_sha256(
    WARM_V1_PATH,
    EXPECTED_WARM_V1_SHA256,
    "Warm-Start V1 knowledge",
)

v21_policy_sha = require_sha256(
    V21_POLICY_PATH,
    EXPECTED_V21_POLICY_SHA256,
    "Frozen Warm-Start V2.1 policy",
)

frozen_prediction_sha = require_sha256(
    FROZEN_PREDICTION_PATH,
    EXPECTED_FROZEN_PREDICTION_SHA256,
    "Frozen V2.1 prediction",
)

rollout_cert_sha = require_sha256(
    ROLLOUT_CERT_PATH,
    EXPECTED_ROLLOUT_CERT_SHA256,
    "V2.1 rollout certification",
)

rv2_wave_prep_sha = require_sha256(
    RV2_WAVE_PREP_PATH,
    EXPECTED_RV2_WAVE_PREP_SHA256,
    "Restart-v2 wave preparation",
)

rv2_exec_cert_sha = require_sha256(
    RV2_EXEC_CERT_PATH,
    EXPECTED_RV2_EXEC_CERT_SHA256,
    "Restart-v2 execution certification",
)


# ============================================================
# 2. RESOLVE EXACT PRODUCTION DOE CASE
# ============================================================

policy = load_phase3_production_doe_policy(
    DOE_POLICY_PATH
)

campaign = build_phase3_production_doe(
    policy
)

doe_case = find_unique(
    campaign.design_cases,
    args.case_id,
    label="Production DOE design case",
)

if doe_case.source_case_id is not None:
    raise RuntimeError(
        "Existing certified anchors cannot enter "
        "restart-v2 Trial-1 acceptance certification."
    )

case_hash = doe_case.case_hash

case_run_id = (
    f"trm_fem_{case_hash[:12]}"
)

expected_run_id = (
    f"{case_run_id}_cal_01_wsv21_rv2"
)

case_root = (
    SOLVER_ROOT
    / case_run_id
)

run_dir = (
    case_root
    / expected_run_id
)

accepted_path = (
    case_root
    / "production_doe_accepted_fem_evidence.json"
)


# ============================================================
# 3. VERIFY RESTART-V2 EXECUTION AUTHORIZATION
# ============================================================

execution_cert = load_json(
    RV2_EXEC_CERT_PATH
)

if (
    execution_cert.get("record_status")
    != "FINAL"
    or execution_cert.get(
        "overall_disposition"
    )
    != (
        "CP8_RESTART_V2_WAVE_EXECUTION_"
        "CERTIFIED_READY_FOR_FEM"
    )
):
    raise RuntimeError(
        "Restart-v2 execution certification is not FINAL."
    )

authorization = execution_cert[
    "execution_authorization"
]

if (
    authorization.get("authorized")
    is not True
    or authorization.get(
        "v2_1_model_must_remain_frozen"
    )
    is not True
    or authorization.get(
        "blind_holdout_execution_authorized"
    )
    is not False
    or authorization.get(
        "replacement_execution_is_new_calibration_attempt"
    )
    is not False
):
    raise RuntimeError(
        "Restart-v2 execution authorization drift."
    )

if args.case_id not in authorization[
    "authorized_case_ids"
]:
    raise RuntimeError(
        "Case is outside restart-v2 execution authorization."
    )

if expected_run_id not in authorization[
    "authorized_run_ids"
]:
    raise RuntimeError(
        "Exact restart-v2 run is not execution-authorized."
    )

certified = find_unique(
    execution_cert[
        "certified_restart_v2_cases"
    ],
    args.case_id,
    label="certified restart-v2 execution row",
)

if (
    certified["case_hash"]
    != case_hash
    or certified[
        "authorized_restart_v2_run_id"
    ]
    != expected_run_id
    or int(
        certified["trial_index"]
    )
    != 1
):
    raise RuntimeError(
        "Certified restart-v2 case identity drift."
    )


# ============================================================
# 4. VERIFY PREPARATION / DECK / SOLVER COMPLETION
# ============================================================

prep_path = (
    ROOT
    / certified[
        "preparation_relative_path"
    ]
)

deck_path = (
    ROOT
    / certified[
        "deck_relative_path"
    ]
)

if (
    prep_path.parent.resolve()
    != run_dir.resolve()
    or deck_path.parent.resolve()
    != run_dir.resolve()
):
    raise RuntimeError(
        "Restart-v2 artifact directory identity drift."
    )

prep_sha = sha256(
    prep_path
)

deck_sha = sha256(
    deck_path
)

if (
    prep_sha
    != certified[
        "preparation_sha256"
    ]
    or deck_sha
    != certified[
        "deck_sha256"
    ]
):
    raise RuntimeError(
        "Restart-v2 preparation/deck SHA drift."
    )

prep = load_json(
    prep_path
)

if (
    prep.get("record_status")
    != "FINAL"
    or prep.get(
        "overall_disposition"
    )
    != (
        "CP8_RESTART_V2_SIBLING_PREPARATION_PASS_"
        "AWAITING_INDEPENDENT_EXECUTION_CERTIFICATION"
    )
):
    raise RuntimeError(
        "Restart-v2 preparation evidence drift."
    )

if (
    prep["case"]["case_id"]
    != args.case_id
    or prep["case"]["case_hash"]
    != case_hash
    or prep["case"][
        "restart_v2_trial_run_id"
    ]
    != expected_run_id
    or int(
        prep["case"]["trial_index"]
    )
    != 1
):
    raise RuntimeError(
        "Restart-v2 Trial-1 preparation identity drift."
    )

if (
    prep["replacement_semantics"][
        "new_calibration_attempt"
    ]
    is not False
    or prep["replacement_semantics"][
        "physics_prediction_changed"
    ]
    is not False
    or prep["replacement_semantics"][
        "resume_from_historical_checkpoint"
    ]
    is not False
    or prep["governance"][
        "v2_1_model_refit_performed"
    ]
    is not False
    or prep["governance"][
        "holdout_accessed"
    ]
    is not False
):
    raise RuntimeError(
        "Restart-v2 replacement provenance is not clean."
    )

manifest_path = (
    run_dir
    / "fem_run_manifest.json"
)

dat_path = (
    run_dir
    / f"{expected_run_id}.dat"
)

sta_path = (
    run_dir
    / f"{expected_run_id}.sta"
)

for required in (
    manifest_path,
    dat_path,
    sta_path,
):
    if not required.is_file():
        raise FileNotFoundError(required)

manifest = load_json(
    manifest_path
)

if (
    manifest.get("disposition")
    != "succeeded"
    or int(
        manifest.get("return_code")
    )
    != 0
    or manifest.get(
        "job_finished"
    )
    is not True
    or int(
        manifest.get(
            "accepted_increment_count"
        )
    )
    != 20
):
    raise RuntimeError(
        "Restart-v2 solver outcome is not a clean "
        "20/20 successful CalculiX result."
    )

sta_rows = accepted_sta_rows(
    sta_path
)

if len(sta_rows) != 20:
    raise RuntimeError(
        f"Expected exactly 20 accepted STA rows; "
        f"found {len(sta_rows)}."
    )

last = sta_rows[-1]

if (
    int(last[0]) != 20
    or int(last[1]) != 1
    or int(last[2]) != 1
    or not math.isclose(
        float(last[4]),
        1.0,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    )
):
    raise RuntimeError(
        "Final accepted checkpoint identity drift."
    )


# ============================================================
# 5. INDEPENDENT FINAL PHYSICS EVALUATION
# ============================================================

contact = (
    load_complete_joint_contact_definition(
        CONFIG
        / "complete_joint_contact.toml"
    )
)

preload = (
    load_complete_joint_preload_definition(
        CONFIG
        / "complete_joint_preload.toml"
    )
)

target_force_n = float(
    prep["case"][
        "target_preload_n"
    ]
)

delta_temperature_c = float(
    prep[
        "replacement_semantics"
    ][
        "frozen_v2_1_delta_temperature_c"
    ]
)

if not math.isclose(
    delta_temperature_c,
    float(
        certified[
            "frozen_delta_temperature_c"
        ]
    ),
    rel_tol=0.0,
    abs_tol=1.0e-12,
):
    raise RuntimeError(
        "Frozen V2.1 delta-temperature provenance drift."
    )

extraction = (
    extract_clamp_force_measurement_from_dat(
        dat_path=dat_path,
        contact_pairs=contact.contact_pairs,
    )
)

if not math.isclose(
    float(extraction.time),
    1.0,
    rel_tol=0.0,
    abs_tol=1.0e-12,
):
    raise RuntimeError(
        "Final clamp-force extraction did not resolve "
        "to synchronized pseudo-time 1.0."
    )

measurement = extraction.measurement

evaluation = evaluate_preload_calibration(
    target_force_n=target_force_n,
    target_relative_tolerance=(
        preload.target_relative_tolerance
    ),
    spread_relative_tolerance=(
        preload.interface_spread_relative_tolerance
    ),
    measurement=measurement,
    previous_point=None,
    current_delta_temperature_c=(
        delta_temperature_c
    ),
)

disposition = getattr(
    evaluation.disposition,
    "value",
    str(evaluation.disposition),
)

if str(disposition).lower() != "accept":
    raise RuntimeError(
        f"{args.case_id}: restart-v2 Trial 1 is NOT "
        f"physically accepted. Decision={disposition}. "
        "Accepted evidence will not be written."
    )

mean_force_n = float(
    measurement.mean_force_n
)

target_relative_error = (
    mean_force_n - target_force_n
) / target_force_n

spread_n = float(
    measurement.spread_n
)

spread_relative = float(
    measurement.spread_relative
)

if (
    abs(target_relative_error)
    > preload.target_relative_tolerance
    or spread_relative
    > preload.interface_spread_relative_tolerance
):
    raise RuntimeError(
        "Independent acceptance gates disagree "
        "with governed controller decision."
    )


# ============================================================
# 6. BUILD STANDARD REUSABLE ACCEPTED-EVIDENCE CONTRACT
# ============================================================

measurement_record = {
    "member_interface_force_n": float(
        measurement.member_interface_force_n
    ),
    "nut_bearing_force_n": float(
        measurement.nut_bearing_force_n
    ),
    "under_head_force_n": float(
        measurement.under_head_force_n
    ),
}

trial_record = {
    "delta_temperature_c": (
        delta_temperature_c
    ),
    "run_id": expected_run_id,
    "source": "fem_warm_start",
    "trial_index": 1,
}

decision_record = {
    "disposition": "accept",
    "measurement": measurement_record,
    "next_delta_temperature_c": None,
    "spread_relative_tolerance": float(
        preload.interface_spread_relative_tolerance
    ),
    "target_force_n": (
        target_force_n
    ),
    "target_relative_error": (
        target_relative_error
    ),
    "target_relative_tolerance": float(
        preload.target_relative_tolerance
    ),
}

manifest_sha = sha256(
    manifest_path
)

dat_sha = sha256(
    dat_path
)

calibration_history = [
    {
        "dat_relative_path": (
            relative(dat_path)
        ),
        "dat_sha256": dat_sha,
        "evaluation": {
            "completed_trial": (
                trial_record
            ),
            "decision": (
                decision_record
            ),
            "next_trial": None,
        },
        "manifest_relative_path": (
            relative(manifest_path)
        ),
        "manifest_sha256": (
            manifest_sha
        ),
        "measurement": (
            measurement_record
        ),
        "preparation_record_relative_path": (
            relative(prep_path)
        ),
        "preparation_record_sha256": (
            prep_sha
        ),
        "solver_manifest_summary": {
            "accepted_increment_count": 20,
            "disposition": "succeeded",
            "job_finished": True,
            "return_code": 0,
        },
        "trial": (
            trial_record
        ),
    }
]

record = {
    "schema_version": 1,

    "record_id": (
        "TRM-PDOE-C01-"
        f"{args.case_id}-"
        "RV2-TRIAL1-FEM-ACCEPT-P01"
    ),

    "record_status": "FINAL",

    "case": {
        "case_hash": (
            case_hash
        ),
        "case_id": (
            args.case_id
        ),
        "case_run_id": (
            case_run_id
        ),
        "mesh_policy_name": (
            prep["case"][
                "mesh_policy_name"
            ]
        ),
        "target_preload_n": (
            target_force_n
        ),
    },

    "accepted_calibration": {
        "accepted_delta_temperature_c": (
            delta_temperature_c
        ),
        "accepted_run_id": (
            expected_run_id
        ),
        "accepted_trial_index": 1,
        "decision": (
            decision_record
        ),
        "interface_spread_force_n": (
            spread_n
        ),
        "interface_spread_relative": (
            spread_relative
        ),
        "mean_clamp_force_n": (
            mean_force_n
        ),
        "measurement": (
            measurement_record
        ),
        "spread_relative_tolerance": float(
            preload.interface_spread_relative_tolerance
        ),
        "target_relative_error": (
            target_relative_error
        ),
        "target_relative_tolerance": float(
            preload.target_relative_tolerance
        ),
    },

    "calibration_history": (
        calibration_history
    ),

    "governance": {
        "campaign_manifest_relative_path": (
            relative(
                CAMPAIGN_MANIFEST_PATH
            )
        ),
        "campaign_manifest_sha256": (
            campaign_sha
        ),

        "doe_policy_relative_path": (
            relative(
                DOE_POLICY_PATH
            )
        ),
        "doe_policy_sha256": (
            doe_policy_sha
        ),

        "preparation_certification_relative_path": (
            relative(
                PREPARATION_CERT_PATH
            )
        ),
        "preparation_certification_sha256": (
            prep_cert_sha
        ),

        "warm_start_v1_relative_path": (
            relative(
                WARM_V1_PATH
            )
        ),
        "warm_start_v1_sha256": (
            warm_v1_sha
        ),

        "v2_1_policy_relative_path": (
            relative(
                V21_POLICY_PATH
            )
        ),
        "v2_1_policy_sha256": (
            v21_policy_sha
        ),

        "frozen_v2_1_prediction_relative_path": (
            relative(
                FROZEN_PREDICTION_PATH
            )
        ),
        "frozen_v2_1_prediction_sha256": (
            frozen_prediction_sha
        ),

        "v2_1_rollout_certification_relative_path": (
            relative(
                ROLLOUT_CERT_PATH
            )
        ),
        "v2_1_rollout_certification_sha256": (
            rollout_cert_sha
        ),

        "restart_v2_wave_preparation_relative_path": (
            relative(
                RV2_WAVE_PREP_PATH
            )
        ),
        "restart_v2_wave_preparation_sha256": (
            rv2_wave_prep_sha
        ),

        "restart_v2_execution_certification_relative_path": (
            relative(
                RV2_EXEC_CERT_PATH
            )
        ),
        "restart_v2_execution_certification_sha256": (
            rv2_exec_cert_sha
        ),

        "restart_v2_trial1_preparation_relative_path": (
            relative(
                prep_path
            )
        ),
        "restart_v2_trial1_preparation_sha256": (
            prep_sha
        ),
    },

    "evidence_semantics": {
        "additional_calibration_required": False,
        "eligible_for_v2_anchor_use": True,
        "eligible_for_warm_start_knowledge": True,
        "governed_calibration_accept_verified": True,
        "holdout_accessed": False,
        "solver_success_verified": True,
        "trial_1_preserved": True,
        "trial_2_is_accepted_physics_solve": False,

        "accepted_physics_trial_index": 1,
        "accepted_execution_is_restart_v2_replacement": True,
        "accepted_execution_is_new_calibration_attempt": False,
        "historical_source_trial_preserved": True,
        "historical_checkpoint_resume_used": False,
        "frozen_v2_1_prediction_preserved": True,
        "v2_1_refit_performed": False,
    },

    "overall_disposition": (
        "PRODUCTION_DOE_FEM_CALIBRATION_ACCEPTED"
    ),
}


# ============================================================
# 7. WRITE IMMUTABLE ACCEPTED EVIDENCE
# ============================================================

action, record_sha = write_immutable_json(
    accepted_path,
    record,
)


print("=" * 112)
print(
    "THREADROM — CP8 RESTART-V2 "
    "TRIAL-1 ACCEPTED FEM CERTIFICATION"
)
print("=" * 112)

print(
    "Case ID                      :",
    args.case_id,
)
print(
    "Case hash                    :",
    case_hash,
)
print(
    "Accepted run                 :",
    expected_run_id,
)
print(
    "Accepted trial index         : 1"
)
print(
    "Frozen V2.1 delta T C        :",
    delta_temperature_c,
)

print()
print(
    "Target preload N             :",
    target_force_n,
)
print(
    "Mean clamp force N           :",
    mean_force_n,
)
print(
    "Target relative error %      :",
    100.0 * target_relative_error,
)
print(
    "Interface spread N           :",
    spread_n,
)
print(
    "Interface spread %           :",
    100.0 * spread_relative,
)
print(
    "Thread normal force N        :",
    extraction.thread_normal_force_n,
)

print()
print(
    "Solver disposition           : succeeded"
)
print(
    "Return code                  : 0"
)
print(
    "Job finished                 : True"
)
print(
    "Accepted checkpoints         : 20 / 20"
)
print(
    "Governed preload decision    : ACCEPT"
)

print()
print(
    "Trial 1 preserved            : YES"
)
print(
    "New calibration attempt      : NO"
)
print(
    "V2.1 prediction changed      : NO"
)
print(
    "V2.1 refit performed         : NO"
)
print(
    "Holdout accessed             : NO"
)

print()
print(
    "Accepted evidence            :",
    accepted_path,
)
print(
    "Accepted evidence SHA256     :",
    record_sha,
)
print(
    "Record action                :",
    action,
)

print()
print(
    "OVERALL DISPOSITION          : "
    "PRODUCTION_DOE_FEM_CALIBRATION_ACCEPTED"
)
print("=" * 112)

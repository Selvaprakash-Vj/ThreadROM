from __future__ import annotations

import dataclasses
import hashlib
import json
import math

from enum import Enum
from pathlib import Path

from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationDisposition,
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
    evaluate_preload_calibration_trial,
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
    CAMPAIGN_ROOT
    / "solver_preparation"
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

PREDICTION_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_prospective_prediction.json"
)

V21_POLICY_PATH = (
    CONFIG
    / "phase3_warm_start_delta_t_v2_1.toml"
)

V2_POLICY_PATH = (
    CONFIG
    / "phase3_warm_start_delta_t_v2.toml"
)

V2_DIAGNOSTIC_SCRIPT_PATH = (
    ROOT
    / "scripts"
    / "diagnose_phase3_warm_start_delta_t_v2.py"
)

V2_FAILURE_RECORD_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_retrospective_diagnostic.txt"
)

OUTPUT_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_prospective_validation.json"
)

EXPECTED_PREP_SHA256 = (
    "5abbac8e1ddf4912f6e3f9ec1059986c"
    "2d447285e39573cf429acbdc58ab755d"
)

EXPECTED_DECK_SHA256 = (
    "dce4cc59db039f7a054020ae491ab1e9f"
    "d22cd41b8d2e7397ef2e5e69af51714"
)

EXPECTED_PREDICTION_SHA256 = (
    "36b0230083c98fc2674adf98b5d5f3ab"
    "a75c736888cfb44c113b86272c53ec4f"
)

EXPECTED_V21_POLICY_SHA256 = (
    "db2a2af4a2954801d7e1db931672a197"
    "629a5dfcab19431c3a38db65b580268c"
)

EXPECTED_V2_POLICY_SHA256 = (
    "a548e95b538a7ec94eeb76d77502c7e7"
    "5e2394d5847ab50e6b57d497e7f0a941"
)

EXPECTED_V2_DIAGNOSTIC_SCRIPT_SHA256 = (
    "d6f79049af8091e75e1d997a2344c298"
    "f171419188f7e37bca75f5818543b525"
)

EXPECTED_V2_FAILURE_RECORD_SHA256 = (
    "743f55b3f21904249422aa3e22aad0bd"
    "64c350780587ea56be2a0f549fb3fad3"
)

EXPECTED_DELTA_T_C = (
    -223.85290919588718
)

EXPECTED_TARGET_FORCE_N = (
    16693.44363468897
)


def sha256(
    path: Path,
    *,
    allow_empty: bool = False,
) -> str:

    if not path.is_file():
        raise FileNotFoundError(path)

    if (
        not allow_empty
        and path.stat().st_size <= 0
    ):
        raise RuntimeError(
            f"Required artifact is empty: {path}"
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


def relative(
    path: Path,
) -> str:

    return (
        path
        .relative_to(ROOT)
        .as_posix()
    )


def jsonable(value):

    if dataclasses.is_dataclass(value):
        return {
            field.name: jsonable(
                getattr(
                    value,
                    field.name,
                )
            )
            for field in dataclasses.fields(
                value
            )
        }

    if isinstance(
        value,
        Enum,
    ):
        return value.value

    if isinstance(
        value,
        Path,
    ):
        return str(value)

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): jsonable(child)
            for key, child in value.items()
        }

    if isinstance(
        value,
        (tuple, list),
    ):
        return [
            jsonable(child)
            for child in value
        ]

    return value


def require_close(
    label: str,
    actual: float,
    expected: float,
    *,
    tolerance: float = 1.0e-10,
) -> None:

    if not math.isclose(
        actual,
        expected,
        rel_tol=0.0,
        abs_tol=tolerance,
    ):
        raise RuntimeError(
            f"{label} drift.\n"
            f"Expected: {expected}\n"
            f"Actual  : {actual}"
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
                "Prospective validation record "
                "already exists with different content. "
                f"Refusing overwrite: {path}"
            )

        action = (
            "UNCHANGED / IDENTICAL"
        )

    else:

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = (
            path.with_suffix(
                ".json.tmp"
            )
        )

        temporary.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )

        temporary.replace(
            path
        )

        action = "CREATED"

    record_hash = sha256(
        path
    )

    sidecar = (
        path.with_suffix(
            ".sha256"
        )
    )

    sidecar_text = (
        f"{record_hash}  {path.name}\n"
    )

    if sidecar.exists():

        existing_sidecar = (
            sidecar.read_text(
                encoding="ascii"
            )
        )

        if (
            existing_sidecar
            != sidecar_text
        ):
            raise RuntimeError(
                "Prospective validation SHA "
                "sidecar drift."
            )

    else:

        sidecar.write_text(
            sidecar_text,
            encoding="ascii",
            newline="\n",
        )

    return (
        action,
        record_hash,
    )


# ============================================================
# 1. FREEZE THE COMPLETE DEVELOPMENT PROVENANCE CHAIN
# ============================================================

prep_sha = require_sha256(
    PREP_PATH,
    EXPECTED_PREP_SHA256,
    "V2.1 prospective preparation",
)

prediction_sha = require_sha256(
    PREDICTION_PATH,
    EXPECTED_PREDICTION_SHA256,
    "V2.1 prospective prediction",
)

v21_policy_sha = require_sha256(
    V21_POLICY_PATH,
    EXPECTED_V21_POLICY_SHA256,
    "V2.1 policy",
)

v2_policy_sha = require_sha256(
    V2_POLICY_PATH,
    EXPECTED_V2_POLICY_SHA256,
    "V2 policy",
)

v2_diagnostic_script_sha = (
    require_sha256(
        V2_DIAGNOSTIC_SCRIPT_PATH,
        EXPECTED_V2_DIAGNOSTIC_SCRIPT_SHA256,
        "V2 retrospective diagnostic script",
    )
)

v2_failure_sha = require_sha256(
    V2_FAILURE_RECORD_PATH,
    EXPECTED_V2_FAILURE_RECORD_SHA256,
    "V2 retrospective failure record",
)

certifier_sha = sha256(
    Path(__file__).resolve()
)


# ============================================================
# 2. PREPARATION MUST STILL BE THE FROZEN PASS
# ============================================================

prep = load_json(
    PREP_PATH
)

if (
    prep.get(
        "record_status"
    )
    != "FINAL"
):
    raise RuntimeError(
        "V2.1 preparation is not FINAL."
    )

if (
    prep.get(
        "overall_disposition"
    )
    != (
        "V2_1_PROSPECTIVE_"
        "SOLVER_PREPARATION_PASS"
    )
):
    raise RuntimeError(
        "V2.1 preparation is not governed PASS."
    )

if (
    prep[
        "case"
    ][
        "case_id"
    ]
    != CASE_ID
    or prep[
        "case"
    ][
        "case_hash"
    ]
    != CASE_HASH
):
    raise RuntimeError(
        "Prospective preparation case identity drift."
    )

if (
    prep[
        "case"
    ][
        "prospective_trial_run_id"
    ]
    != RUN_ID
):
    raise RuntimeError(
        "Prospective preparation run-ID drift."
    )

if (
    prep[
        "governance"
    ][
        "v2_1_policy_sha256"
    ]
    != v21_policy_sha
):
    raise RuntimeError(
        "V2.1 policy/preparation binding drift."
    )

if (
    prep[
        "governance"
    ][
        "prospective_prediction_sha256"
    ]
    != prediction_sha
):
    raise RuntimeError(
        "Prediction/preparation binding drift."
    )

target_force_n = float(
    prep[
        "case"
    ][
        "target_preload_n"
    ]
)

require_close(
    "Target preload",
    target_force_n,
    EXPECTED_TARGET_FORCE_N,
)

trial_data = prep[
    "trial_1"
]

if (
    int(
        trial_data[
            "trial_index"
        ]
    )
    != 1
    or trial_data[
        "run_id"
    ]
    != RUN_ID
):
    raise RuntimeError(
        "Prospective trial identity drift."
    )

delta_t_c = float(
    trial_data[
        "delta_temperature_c"
    ]
)

require_close(
    "Frozen V2.1 delta T",
    delta_t_c,
    EXPECTED_DELTA_T_C,
)


# ============================================================
# 3. VERIFY SOLVER MANIFEST + EVERY RECORDED ARTIFACT
# ============================================================

manifest_sha = sha256(
    MANIFEST_PATH
)

manifest = load_json(
    MANIFEST_PATH
)

if (
    int(
        manifest.get(
            "schema_version",
            -1,
        )
    )
    != 1
):
    raise RuntimeError(
        "Unexpected FEM manifest schema."
    )

if (
    manifest.get(
        "run_id"
    )
    != RUN_ID
    or manifest.get(
        "job_name"
    )
    != RUN_ID
):
    raise RuntimeError(
        "FEM manifest run identity mismatch."
    )

if (
    manifest.get(
        "case_hash"
    )
    != CASE_HASH
):
    raise RuntimeError(
        "FEM manifest case-hash mismatch."
    )

if (
    manifest.get(
        "disposition"
    )
    != "succeeded"
):
    raise RuntimeError(
        "Prospective FEM solver did not succeed."
    )

if (
    manifest.get(
        "return_code"
    )
    != 0
):
    raise RuntimeError(
        "Prospective FEM return code is not zero."
    )

if (
    manifest.get(
        "job_finished"
    )
    is not True
):
    raise RuntimeError(
        "Prospective FEM did not reach Job finished."
    )

if (
    int(
        manifest.get(
            "accepted_increment_count",
            -1,
        )
    )
    != 20
):
    raise RuntimeError(
        "Prospective FEM does not contain "
        "the expected 20 accepted increments."
    )

if (
    int(
        manifest.get(
            "final_step",
            -1,
        )
    )
    != 1
    or int(
        manifest.get(
            "final_increment",
            -1,
        )
    )
    != 20
):
    raise RuntimeError(
        "Prospective FEM final accepted state drift."
    )

artifacts = manifest.get(
    "artifacts"
)

if not isinstance(
    artifacts,
    list,
):
    raise RuntimeError(
        "Manifest artifact list missing."
    )

artifact_by_role = {}

for artifact in artifacts:

    role = artifact[
        "role"
    ]

    if role in artifact_by_role:
        raise RuntimeError(
            f"Duplicate manifest artifact role: {role}"
        )

    artifact_by_role[
        role
    ] = artifact


required_roles = {
    "input_deck",
    "dat",
    "frd",
    "sta",
    "cvg",
    "stdout",
    "stderr",
}

missing_roles = (
    required_roles
    - set(
        artifact_by_role
    )
)

if missing_roles:
    raise RuntimeError(
        "Missing governed FEM artifacts: "
        + ", ".join(
            sorted(
                missing_roles
            )
        )
    )


verified_artifacts = []

for role in sorted(
    required_roles
):

    artifact = artifact_by_role[
        role
    ]

    path = (
        ROOT
        / artifact[
            "relative_path"
        ]
    )

    if not path.is_file():
        raise FileNotFoundError(
            path
        )

    actual_size = (
        path.stat().st_size
    )

    expected_size = int(
        artifact[
            "size_bytes"
        ]
    )

    if (
        actual_size
        != expected_size
    ):
        raise RuntimeError(
            f"{role}: artifact size drift."
        )

    actual_hash = sha256(
        path,
        allow_empty=True,
    )

    if (
        actual_hash
        != artifact[
            "sha256"
        ]
    ):
        raise RuntimeError(
            f"{role}: artifact SHA drift."
        )

    verified_artifacts.append(
        {
            "role": role,
            "relative_path": (
                relative(path)
            ),
            "size_bytes": (
                actual_size
            ),
            "sha256": (
                actual_hash
            ),
        }
    )


deck_artifact = (
    artifact_by_role[
        "input_deck"
    ]
)

if (
    deck_artifact[
        "sha256"
    ]
    != EXPECTED_DECK_SHA256
    or prep[
        "deck"
    ][
        "sha256"
    ]
    != EXPECTED_DECK_SHA256
):
    raise RuntimeError(
        "Prospective deck binding drift."
    )

dat_path = (
    ROOT
    / artifact_by_role[
        "dat"
    ][
        "relative_path"
    ]
)


# ============================================================
# 4. RECOMPUTE REAL CLAMP MEASUREMENT FROM FROZEN DAT
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

extraction = (
    extract_clamp_force_measurement_from_dat(
        dat_path=dat_path,
        contact_pairs=(
            contact.contact_pairs
        ),
    )
)

measurement = (
    extraction.measurement
)

forces = (
    float(
        measurement.under_head_force_n
    ),
    float(
        measurement.nut_bearing_force_n
    ),
    float(
        measurement.member_interface_force_n
    ),
)

mean_force_n = float(
    measurement.mean_force_n
)

spread_n = (
    max(forces)
    - min(forces)
)

spread_relative = (
    spread_n
    / mean_force_n
)

target_relative_error = (
    (
        mean_force_n
        - target_force_n
    )
    / target_force_n
)


# ============================================================
# 5. RE-RUN THE GOVERNED CALIBRATION CONTROLLER
# ============================================================

trial = PreloadCalibrationTrial(
    trial_index=1,
    run_id=RUN_ID,
    delta_temperature_c=(
        delta_t_c
    ),
    source=(
        PreloadCalibrationTrialSource.FEM_WARM_START
    ),
)

evaluation = (
    evaluate_preload_calibration_trial(
        case_run_id=(
            CASE_RUN_ID
        ),
        target_force_n=(
            target_force_n
        ),
        target_relative_tolerance=(
            preload.target_relative_tolerance
        ),
        spread_relative_tolerance=(
            preload.interface_spread_relative_tolerance
        ),
        current_trial=(
            trial
        ),
        measurement=(
            measurement
        ),
    )
)

decision = (
    evaluation.decision
)

if (
    decision.disposition
    is not PreloadCalibrationDisposition.ACCEPT
):
    raise RuntimeError(
        "Governed controller did not ACCEPT "
        "the prospective first shot."
    )

if (
    evaluation.accepted
    is not True
):
    raise RuntimeError(
        "Prospective evaluation accepted flag is false."
    )

if (
    evaluation.next_trial
    is not None
):
    raise RuntimeError(
        "A second calibration trial was derived "
        "despite first-shot acceptance."
    )

if (
    abs(
        decision.target_relative_error
    )
    > preload.target_relative_tolerance
):
    raise RuntimeError(
        "Target error exceeds governed tolerance."
    )


# ============================================================
# 6. PROSPECTIVE PASS — ROLLOUT AUTHORIZATION
# ============================================================

record = {
    "schema_version": 1,

    "record_id": (
        "TRM-P3-CP8-WSV21-"
        "PROSPECTIVE-VALIDATION-P01"
    ),

    "record_status": "FINAL",

    "campaign_id": (
        "TRM-PDOE-C01"
    ),

    "validation_role": (
        "PROSPECTIVE_INTERIOR_VALIDATION_SENTINEL"
    ),

    "case": {
        "case_id": (
            CASE_ID
        ),
        "case_hash": (
            CASE_HASH
        ),
        "run_id": (
            RUN_ID
        ),
        "target_preload_n": (
            target_force_n
        ),
        "frozen_delta_temperature_c": (
            delta_t_c
        ),
    },

    "development_provenance": {
        "v2_policy": {
            "relative_path": (
                relative(
                    V2_POLICY_PATH
                )
            ),
            "sha256": (
                v2_policy_sha
            ),
        },

        "v2_retrospective_diagnostic_script": {
            "relative_path": (
                relative(
                    V2_DIAGNOSTIC_SCRIPT_PATH
                )
            ),
            "sha256": (
                v2_diagnostic_script_sha
            ),
        },

        "v2_retrospective_failure_record": {
            "relative_path": (
                relative(
                    V2_FAILURE_RECORD_PATH
                )
            ),
            "sha256": (
                v2_failure_sha
            ),
            "verdict": (
                "PROXY_FAIL"
            ),
        },

        "v2_1_policy": {
            "relative_path": (
                relative(
                    V21_POLICY_PATH
                )
            ),
            "sha256": (
                v21_policy_sha
            ),
        },

        "prospective_prediction": {
            "relative_path": (
                relative(
                    PREDICTION_PATH
                )
            ),
            "sha256": (
                prediction_sha
            ),
        },

        "prospective_solver_preparation": {
            "relative_path": (
                relative(
                    PREP_PATH
                )
            ),
            "sha256": (
                prep_sha
            ),
        },

        "certifier": {
            "relative_path": (
                relative(
                    Path(
                        __file__
                    ).resolve()
                )
            ),
            "sha256": (
                certifier_sha
            ),
        },
    },

    "solver_execution": {
        "manifest_relative_path": (
            relative(
                MANIFEST_PATH
            )
        ),
        "manifest_sha256": (
            manifest_sha
        ),
        "disposition": (
            manifest[
                "disposition"
            ]
        ),
        "return_code": (
            manifest[
                "return_code"
            ]
        ),
        "job_finished": (
            manifest[
                "job_finished"
            ]
        ),
        "accepted_increment_count": (
            manifest[
                "accepted_increment_count"
            ]
        ),
        "final_step": (
            manifest[
                "final_step"
            ]
        ),
        "final_increment": (
            manifest[
                "final_increment"
            ]
        ),
        "final_attempt": (
            manifest[
                "final_attempt"
            ]
        ),
        "final_iterations": (
            manifest[
                "final_iterations"
            ]
        ),
        "artifacts": (
            verified_artifacts
        ),
    },

    "first_shot_measurement": {
        "under_head_force_n": (
            forces[0]
        ),
        "nut_bearing_force_n": (
            forces[1]
        ),
        "member_interface_force_n": (
            forces[2]
        ),
        "mean_clamp_force_n": (
            mean_force_n
        ),
        "interface_spread_n": (
            spread_n
        ),
        "interface_spread_relative": (
            spread_relative
        ),
        "target_relative_error": (
            target_relative_error
        ),
        "target_error_percent": (
            100.0
            * target_relative_error
        ),
    },

    "governed_acceptance": {
        "target_relative_tolerance": (
            preload.target_relative_tolerance
        ),
        "interface_spread_relative_tolerance": (
            preload.interface_spread_relative_tolerance
        ),
        "decision": (
            jsonable(
                decision
            )
        ),
        "accepted": True,
        "next_trial_derived": False,
    },

    "prospective_validation": {
        "prediction_frozen_before_fem": True,
        "same_case_used_for_v2_1_parameter_fit": False,
        "actual_first_fem_trial_used": True,
        "posthoc_tolerance_change": False,
        "additional_fem_for_validation": False,
        "blind_holdout_accessed": False,
        "verdict": (
            "PROSPECTIVE_PASS"
        ),
    },

    "evidence_semantics": {
        "solver_success_verified": True,
        "governed_calibration_accept_verified": True,
        "first_shot_is_accepted_physics_solve": True,
        "additional_calibration_required": False,
        "eligible_for_production_dataset": True,

        # Preserve the exact prospectively validated V2.1 model.
        # D-INT-008 may become learning evidence later, but it
        # must NOT be used to refit V2.1 before this rollout.
        "eligible_for_v2_1_parameter_refit_before_rollout": False,

        "holdout_accessed": False,
    },

    "rollout_authorization": {
        "authorized": True,
        "predictor": (
            "warm_start_delta_t_v2_1"
        ),
        "scope": (
            "TRM-PDOE-C01_REMAINING_"
            "COVERED_DESIGN_CASES_ONLY"
        ),
        "remaining_design_cases_at_authorization": 14,
        "first_shot_target_relative_tolerance": (
            preload.target_relative_tolerance
        ),
        "first_shot_interface_spread_relative_tolerance": (
            preload.interface_spread_relative_tolerance
        ),
        "trial_2_only_if_governed_first_shot_rejects": True,
        "v2_1_model_must_remain_frozen_during_rollout": True,
        "blind_holdout_execution_authorized": False,
        "blind_holdouts_remain_sealed": True,
    },

    "overall_disposition": (
        "V2_1_PROSPECTIVE_PASS_"
        "ROLLOUT_AUTHORIZED"
    ),
}


action, record_sha = (
    write_immutable_json(
        OUTPUT_PATH,
        record,
    )
)


# ============================================================
# 7. REPORT
# ============================================================

print("=" * 128)
print(
    "THREADROM - WARM-START V2.1 "
    "PROSPECTIVE VALIDATION CERTIFICATION"
)
print("=" * 128)

print()
print(
    "Case ID                     :",
    CASE_ID,
)

print(
    "Run ID                      :",
    RUN_ID,
)

print(
    "Target preload N            :",
    target_force_n,
)

print(
    "Frozen delta T C            :",
    delta_t_c,
)

print()
print(
    "Under-head force N          :",
    forces[0],
)

print(
    "Nut-bearing force N         :",
    forces[1],
)

print(
    "Member-interface force N    :",
    forces[2],
)

print(
    "Mean clamp force N          :",
    mean_force_n,
)

print(
    "Target error percent        :",
    100.0
    * target_relative_error,
)

print(
    "Interface spread relative   :",
    spread_relative,
)

print()
print(
    "Solver success              : VERIFIED"
)

print(
    "Accepted increments         :",
    manifest[
        "accepted_increment_count"
    ],
)

print(
    "All manifest artifacts      : VERIFIED"
)

print(
    "Governed calibration        : ACCEPT"
)

print(
    "Next trial derived          : NO"
)

print()
print(
    "PROSPECTIVE VERDICT         : PROSPECTIVE_PASS"
)

print(
    "V2.1 rollout authorized     : YES"
)

print(
    "Rollout cases remaining     : 14"
)

print(
    "V2.1 refit before rollout   : FORBIDDEN"
)

print(
    "Blind holdouts accessed     : NO"
)

print(
    "Blind holdouts authorized   : NO"
)

print()
print(
    "Validation record           :",
    OUTPUT_PATH,
)

print(
    "Validation SHA256           :",
    record_sha,
)

print(
    "Record action               :",
    action,
)

print()
print(
    "CalculiX invoked            : NO"
)

print(
    "Additional FEM launched     : NO"
)

print()
print(
    "OVERALL DISPOSITION         : "
    "V2_1_PROSPECTIVE_PASS_ROLLOUT_AUTHORIZED"
)

print("=" * 128)
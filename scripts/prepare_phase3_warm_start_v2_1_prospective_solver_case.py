from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import tomllib

from enum import Enum
from pathlib import Path

from threadrom.case.preflight import (
    PreflightSeverity,
    PreflightTarget,
)
from threadrom.case.preflight_engine import (
    preflight_case,
)
from threadrom.case.resolver import (
    resolve_case,
)

from threadrom.factory.fem_case_definition_bundle import (
    build_generic_fem_definition_bundle,
)
from threadrom.factory.fem_preload_calibration_deck import (
    write_fem_preload_calibration_trial_deck,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)

from threadrom.solver.complete_joint_boundary_regions import (
    load_complete_joint_boundary_region_definition,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
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

V21_POLICY_PATH = (
    CONFIG
    / "phase3_warm_start_delta_t_v2_1.toml"
)

PREDICTION_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_prospective_prediction.json"
)

CASE_ID = "D-INT-008"

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


def relative(
    path: Path,
) -> str:
    return (
        path
        .relative_to(ROOT)
        .as_posix()
    )


def load_json(
    path: Path,
) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
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


def write_immutable_json(
    path: Path,
    payload: dict,
) -> tuple[
    str,
    str,
]:

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
                "V2.1 prospective preparation "
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

        observed = (
            sidecar.read_text(
                encoding="ascii"
            )
        )

        if observed != sidecar_text:
            raise RuntimeError(
                "V2.1 preparation SHA "
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


def reference_temperature_c() -> float:

    path = (
        CONFIG
        / "complete_joint_preload.toml"
    )

    data = tomllib.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )

    matches = []

    def walk(value):

        if isinstance(
            value,
            dict,
        ):
            for key, child in value.items():

                if (
                    key
                    == "reference_temperature_c"
                ):
                    matches.append(
                        float(child)
                    )

                else:
                    walk(
                        child
                    )

        elif isinstance(
            value,
            list,
        ):
            for child in value:
                walk(
                    child
                )

    walk(
        data
    )

    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one governed "
            "reference_temperature_c."
        )

    result = matches[0]

    if not math.isfinite(
        result
    ):
        raise RuntimeError(
            "Reference temperature "
            "is not finite."
        )

    return result


def find_preparation_row(
    certification: dict,
    case_id: str,
) -> dict:

    matches = [
        row
        for row in certification[
            "design_case_preparation_evidence"
        ]
        if row[
            "case_id"
        ] == case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected one "
            "certified preparation row; "
            f"found {len(matches)}."
        )

    return matches[0]


def verify_sha_sidecar(
    path: Path,
) -> str:

    actual = sha256(
        path
    )

    sidecar = (
        path.with_suffix(
            ".sha256"
        )
    )

    if not sidecar.is_file():
        raise RuntimeError(
            f"Missing SHA sidecar: {sidecar}"
        )

    observed = (
        sidecar.read_text(
            encoding="ascii"
        )
    )

    expected = (
        f"{actual}  {path.name}\n"
    )

    if observed != expected:
        raise RuntimeError(
            f"SHA sidecar mismatch: {path}"
        )

    return actual


def solver_outputs_present(
    root: Path,
) -> tuple[str, ...]:

    if not root.exists():
        return ()

    forbidden_names = {
        "fem_run_manifest.json",
    }

    forbidden_suffixes = {
        ".dat",
        ".frd",
        ".sta",
        ".cvg",
        ".12d",
        ".eig",
        ".equ",
        ".rout",
    }

    found = []

    for path in root.rglob("*"):

        if not path.is_file():
            continue

        if (
            path.name
            in forbidden_names
            or path.suffix.lower()
            in forbidden_suffixes
        ):
            found.append(
                relative(path)
            )

    return tuple(
        sorted(
            found
        )
    )


# ============================================================
# 1. GOVERNANCE
# ============================================================

doe_policy_hash = (
    require_sha256(
        DOE_POLICY_PATH,
        EXPECTED_DOE_POLICY_SHA256,
        "Production DOE policy",
    )
)

campaign_hash = (
    require_sha256(
        CAMPAIGN_MANIFEST_PATH,
        EXPECTED_CAMPAIGN_SHA256,
        "Production DOE campaign",
    )
)

preparation_cert_hash = (
    require_sha256(
        PREPARATION_CERT_PATH,
        EXPECTED_PREPARATION_CERT_SHA256,
        "Production DOE preparation certification",
    )
)

v21_policy_hash = (
    require_sha256(
        V21_POLICY_PATH,
        EXPECTED_V21_POLICY_SHA256,
        "Warm-Start V2.1 policy",
    )
)

prediction_hash = (
    require_sha256(
        PREDICTION_PATH,
        EXPECTED_PREDICTION_SHA256,
        "Warm-Start V2.1 prospective prediction",
    )
)


# ============================================================
# 2. FROZEN DOE CASE
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
        f"{CASE_ID}: expected exactly "
        f"one design case; "
        f"found {len(matches)}."
    )

doe_case = matches[0]

if (
    doe_case.source_case_id
    is not None
):
    raise RuntimeError(
        "Prospective sentinel cannot "
        "be an existing anchor."
    )

resolved = (
    resolve_case(
        doe_case.case
    )
)

if (
    resolved.case_hash
    != doe_case.case_hash
):
    raise RuntimeError(
        "Resolved case-hash drift."
    )

canonical_case_run_id = (
    f"trm_fem_"
    f"{resolved.case_hash[:12]}"
)

canonical_trial1_run_id = (
    f"{canonical_case_run_id}_cal_01"
)

# The FEM bundle owns the canonical prepared-case identity.
# A predictor variant therefore remains a calibration trial
# beneath that case identity rather than inventing a new case ID.
v21_case_run_id = canonical_case_run_id

v21_trial_run_id = (
    f"{canonical_case_run_id}_cal_01_wsv21"
)


# ============================================================
# 3. FROZEN V2.1 PREDICTION
# ============================================================

prediction = load_json(
    PREDICTION_PATH
)

if (
    prediction.get(
        "record_status"
    )
    != "FINAL"
):
    raise RuntimeError(
        "Prospective prediction "
        "record is not FINAL."
    )

if (
    prediction.get(
        "overall_disposition"
    )
    != (
        "V2_1_PROSPECTIVE_"
        "PREDICTION_FROZEN_AWAITING_FEM"
    )
):
    raise RuntimeError(
        "Unexpected prospective "
        "prediction disposition."
    )

predicted = (
    prediction[
        "prospective_prediction"
    ]
)

if (
    predicted[
        "case_id"
    ]
    != CASE_ID
    or predicted[
        "case_hash"
    ]
    != doe_case.case_hash
):
    raise RuntimeError(
        "Prospective prediction "
        "case identity mismatch."
    )

if (
    predicted[
        "prediction_status"
    ]
    != (
        "FROZEN_BEFORE_FEM_RESULT_ACCESS"
    )
):
    raise RuntimeError(
        "Prediction was not frozen "
        "under prospective purity."
    )

predicted_delta_t = float(
    predicted[
        "predicted_delta_temperature_c"
    ]
)

if (
    not math.isfinite(
        predicted_delta_t
    )
    or predicted_delta_t >= 0.0
):
    raise RuntimeError(
        "Frozen prediction is not "
        "finite thermal contraction."
    )


# ============================================================
# 4. PROSPECTIVE PURITY / CANONICAL V1 PROTECTION
# ============================================================

canonical_trial_dir = (
    SOLVER_ROOT
    / canonical_case_run_id
    / canonical_trial1_run_id
)

canonical_prep_path = (
    canonical_trial_dir
    / "production_doe_solver_preparation_record.json"
)

canonical_prep_hash = (
    verify_sha_sidecar(
        canonical_prep_path
    )
)

canonical_prep = (
    load_json(
        canonical_prep_path
    )
)

if (
    canonical_prep[
        "record_status"
    ]
    != "FINAL"
    or canonical_prep[
        "overall_disposition"
    ]
    != (
        "PRODUCTION_DOE_TRIAL1_"
        "SOLVER_PREPARATION_PASS"
    )
):
    raise RuntimeError(
        "Canonical V1 Trial-1 "
        "preparation is not FINAL PASS."
    )

if (
    canonical_prep[
        "case"
    ][
        "case_hash"
    ]
    != doe_case.case_hash
):
    raise RuntimeError(
        "Canonical V1 preparation "
        "case identity mismatch."
    )

canonical_deck_path = (
    ROOT
    / canonical_prep[
        "deck"
    ][
        "relative_path"
    ]
)

canonical_deck_hash = (
    sha256(
        canonical_deck_path
    )
)

if (
    canonical_deck_hash
    != canonical_prep[
        "deck"
    ][
        "sha256"
    ]
):
    raise RuntimeError(
        "Canonical V1 deck hash drift."
    )

canonical_v1_delta_t = float(
    canonical_prep[
        "trial_1"
    ][
        "delta_temperature_c"
    ]
)

if math.isclose(
    canonical_v1_delta_t,
    predicted_delta_t,
    rel_tol=0.0,
    abs_tol=1.0e-10,
):
    raise RuntimeError(
        "V2.1 prediction unexpectedly "
        "equals canonical V1."
    )

case_root = (
    SOLVER_ROOT
    / canonical_case_run_id
)

existing_solver_outputs = (
    solver_outputs_present(
        case_root
    )
)

if existing_solver_outputs:
    raise RuntimeError(
        "Prospective purity violated: "
        "solver outputs already exist:\n"
        + "\n".join(
            existing_solver_outputs
        )
    )


# ============================================================
# 5. REAL GOVERNED FEM PREFLIGHT
# ============================================================

preflight = (
    preflight_case(
        doe_case.case,
        PreflightTarget.FEM,
    )
)

blocking = tuple(
    finding
    for finding in preflight.findings
    if (
        finding.severity
        is PreflightSeverity.ERROR
    )
)

if blocking:
    raise RuntimeError(
        "Prospective FEM preflight BLOCKED: "
        + "; ".join(
            str(finding)
            for finding in blocking
        )
    )


# ============================================================
# 6. CERTIFIED GEOMETRY / MESH BINDING
# ============================================================

preparation_cert = (
    load_json(
        PREPARATION_CERT_PATH
    )
)

preparation_row = (
    find_preparation_row(
        preparation_cert,
        CASE_ID,
    )
)

if (
    preparation_row[
        "case_hash"
    ]
    != doe_case.case_hash
):
    raise RuntimeError(
        "Certified preparation "
        "case-hash mismatch."
    )

if (
    preparation_row[
        "mesh_policy_name"
    ]
    != doe_case.mesh_policy_name
):
    raise RuntimeError(
        "Certified preparation "
        "mesh-policy mismatch."
    )

mesh_path = (
    ROOT
    / preparation_row[
        "mesh_relative_path"
    ]
)

step_path = (
    ROOT
    / preparation_row[
        "step_relative_path"
    ]
)

if (
    sha256(
        mesh_path
    )
    != preparation_row[
        "mesh_sha256"
    ]
):
    raise RuntimeError(
        "Certified prepared mesh "
        "hash drift."
    )

if (
    sha256(
        step_path
    )
    != preparation_row[
        "step_sha256"
    ]
):
    raise RuntimeError(
        "Certified prepared STEP "
        "hash drift."
    )


# ============================================================
# 7. CERTIFIED FEM DEFINITION BUNDLE
# ============================================================

transfer_template = (
    load_complete_joint_calculix_transfer_definition(
        CONFIG
        / "complete_joint_calculix_transfer.toml"
    )
)

contact_template = (
    load_complete_joint_contact_definition(
        CONFIG
        / "complete_joint_contact.toml"
    )
)

preload_template = (
    load_complete_joint_preload_definition(
        CONFIG
        / "complete_joint_preload.toml"
    )
)

boundary_template = (
    load_complete_joint_boundary_region_definition(
        CONFIG
        / "complete_joint_boundary_regions.toml"
    )
)

token = (
    resolved.case_hash[:16]
)

bundle = (
    build_generic_fem_definition_bundle(
        resolved,
        mesh_id=(
            f"mesh-{token}"
        ),
        geometry_id=(
            f"geometry-{token}"
        ),
        classification_id=(
            f"classification-{token}"
        ),
        source_mesh_name=(
            mesh_path.name
        ),
        transfer_template=(
            transfer_template
        ),
        contact_template=(
            contact_template
        ),
        boundary_template=(
            boundary_template
        ),
    )
)

if (
    bundle.calibration_seed.target_force_n
    != resolved.source_case.loading.target_preload_n
):
    raise RuntimeError(
        "Case preload did not propagate "
        "into FEM bundle."
    )

mesh_data = (
    read_grouped_complete_joint_mesh(
        mesh_path,
        bundle.transfer,
    )
)


# ============================================================
# 8. V2.1 PROSPECTIVE TRIAL OBJECT
# ============================================================

trial = PreloadCalibrationTrial(
    trial_index=1,
    run_id=v21_trial_run_id,
    delta_temperature_c=(
        predicted_delta_t
    ),
    source=(
        PreloadCalibrationTrialSource.FEM_WARM_START
    ),
)

if (
    trial.run_id
    == canonical_trial1_run_id
):
    raise RuntimeError(
        "V2.1 sibling run collided "
        "with canonical V1 Trial 1."
    )


# ============================================================
# 9. V2.1 SIBLING DECK
# ============================================================

run_dir = (
    SOLVER_ROOT
    / canonical_case_run_id
    / v21_trial_run_id
)

run_dir.mkdir(
    parents=True,
    exist_ok=True,
)

input_path = (
    run_dir
    / f"{v21_trial_run_id}.inp"
)

prior_deck_hash = (
    sha256(
        input_path
    )
    if input_path.exists()
    else None
)

deck = (
    write_fem_preload_calibration_trial_deck(
        mesh_data=mesh_data,
        bundle=bundle,
        trial=trial,
        reference_temperature_c=(
            reference_temperature_c()
        ),
        input_path=input_path,
    )
)

if (
    not input_path.is_file()
    or input_path.stat().st_size <= 0
):
    raise RuntimeError(
        "Generated V2.1 deck "
        "is missing or empty."
    )

actual_deck_hash = (
    sha256(
        input_path
    )
)

if (
    actual_deck_hash
    != deck.sha256
):
    raise RuntimeError(
        "Generated V2.1 deck SHA "
        "does not match metadata."
    )

if (
    prior_deck_hash is not None
    and prior_deck_hash
    != actual_deck_hash
):
    raise RuntimeError(
        "Existing V2.1 deck changed "
        "during deterministic regeneration."
    )

if (
    deck.trial_run_id
    != trial.run_id
):
    raise RuntimeError(
        "V2.1 deck/trial "
        "identity mismatch."
    )

if not math.isclose(
    deck.delta_temperature_c,
    predicted_delta_t,
    rel_tol=0.0,
    abs_tol=1.0e-10,
):
    raise RuntimeError(
        "V2.1 deck does not contain "
        "the frozen prospective delta T."
    )


# ============================================================
# 10. IMMUTABLE PROSPECTIVE SOLVER PREPARATION
# ============================================================

record = {
    "schema_version": 1,

    "record_id": (
        "TRM-P3-CP8-WSV21-"
        "D-INT-008-SOLVER-PREP-P01"
    ),

    "record_status": "FINAL",

    "case": {
        "case_id": (
            CASE_ID
        ),
        "case_hash": (
            doe_case.case_hash
        ),
        "canonical_case_run_id": (
            canonical_case_run_id
        ),
        "prospective_case_run_id": (
            v21_case_run_id
        ),
        "prospective_trial_run_id": (
            v21_trial_run_id
        ),
        "role": (
            "PROSPECTIVE_WARM_START_V2_1_SENTINEL"
        ),
        "normalized_coordinates": list(
            doe_case.normalized_coordinates
        ),
        "target_preload_n": (
            resolved.source_case.loading.target_preload_n
        ),
        "mesh_policy_name": (
            doe_case.mesh_policy_name
        ),
    },

    "governance": {
        "doe_policy_sha256": (
            doe_policy_hash
        ),
        "campaign_manifest_sha256": (
            campaign_hash
        ),
        "preparation_certification_sha256": (
            preparation_cert_hash
        ),
        "v2_1_policy_sha256": (
            v21_policy_hash
        ),
        "prospective_prediction_sha256": (
            prediction_hash
        ),
    },

    "execution_selection": {
        "canonical_v1_trial1_preserved": True,
        "canonical_v1_trial1_executed": False,
        "canonical_v1_trial1_run_id": (
            canonical_trial1_run_id
        ),
        "canonical_v1_preparation_relative_path": (
            relative(
                canonical_prep_path
            )
        ),
        "canonical_v1_preparation_sha256": (
            canonical_prep_hash
        ),
        "canonical_v1_deck_relative_path": (
            relative(
                canonical_deck_path
            )
        ),
        "canonical_v1_deck_sha256": (
            canonical_deck_hash
        ),
        "canonical_v1_delta_temperature_c": (
            canonical_v1_delta_t
        ),
        "prospective_execution_uses_v2_1_sibling": True,
        "canonical_v1_authorized_for_this_validation": False,
    },

    "prospective_prediction": {
        "relative_path": (
            relative(
                PREDICTION_PATH
            )
        ),
        "sha256": (
            prediction_hash
        ),
        "policy_relative_path": (
            relative(
                V21_POLICY_PATH
            )
        ),
        "policy_sha256": (
            v21_policy_hash
        ),
        "frozen_delta_temperature_c": (
            predicted_delta_t
        ),
        "prediction_status": (
            "FROZEN_BEFORE_FEM_RESULT_ACCESS"
        ),
    },

    "fem_preflight": {
        "target": "fem",
        "blocking_error_count": 0,
        "report": (
            jsonable(
                preflight
            )
        ),
        "status": "PASS",
    },

    "prepared_artifacts": {
        "preparation_evidence_kind": (
            preparation_row[
                "preparation_evidence_kind"
            ]
        ),
        "step_relative_path": (
            relative(
                step_path
            )
        ),
        "step_sha256": (
            preparation_row[
                "step_sha256"
            ]
        ),
        "mesh_relative_path": (
            relative(
                mesh_path
            )
        ),
        "mesh_sha256": (
            preparation_row[
                "mesh_sha256"
            ]
        ),
    },

    "analytical_seed": (
        jsonable(
            bundle.calibration_seed
        )
    ),

    "trial_1": (
        jsonable(
            trial
        )
    ),

    "deck": {
        "relative_path": (
            relative(
                input_path
            )
        ),
        "sha256": (
            actual_deck_hash
        ),
        "size_bytes": (
            input_path.stat().st_size
        ),
        "node_count": (
            deck.node_count
        ),
        "element_count": (
            deck.element_count
        ),
        "delta_temperature_c": (
            deck.delta_temperature_c
        ),
    },

    "calibration_acceptance": {
        "target_relative_tolerance": (
            preload_template.target_relative_tolerance
        ),
        "interface_spread_relative_tolerance": (
            preload_template.interface_spread_relative_tolerance
        ),
        "evaluation_status": (
            "NOT_RUN"
        ),
    },

    "prospective_purity": {
        "solver_outputs_detected_before_preparation": False,
        "prospective_result_read": False,
        "calculix_invoked": False,
        "blind_holdout_results_accessed": False,
    },

    "solve_authorization": {
        "calculix_invoked": False,
        "solver_authorized_by_this_script": False,
        "holdout_accessed": False,
    },

    "overall_disposition": (
        "V2_1_PROSPECTIVE_"
        "SOLVER_PREPARATION_PASS"
    ),
}


record_path = (
    run_dir
    / "production_doe_v2_1_prospective_solver_preparation_record.json"
)

action, record_hash = (
    write_immutable_json(
        record_path,
        record,
    )
)


# ============================================================
# 11. FINAL GUARDS
# ============================================================

if (
    sha256(
        canonical_prep_path
    )
    != canonical_prep_hash
):
    raise RuntimeError(
        "Canonical V1 preparation "
        "changed during V2.1 preparation."
    )

if (
    sha256(
        canonical_deck_path
    )
    != canonical_deck_hash
):
    raise RuntimeError(
        "Canonical V1 deck changed "
        "during V2.1 preparation."
    )

manifest_path = (
    run_dir
    / "fem_run_manifest.json"
)

if manifest_path.exists():
    raise RuntimeError(
        "Prospective manifest already exists. "
        "Solver execution purity violated."
    )


# ============================================================
# 12. REPORT
# ============================================================

print("=" * 128)
print(
    "THREADROM - WARM-START V2.1 "
    "PROSPECTIVE SOLVER PREPARATION"
)
print("=" * 128)

print()
print(
    "Case ID                         :",
    CASE_ID,
)

print(
    "Case hash                       :",
    doe_case.case_hash,
)

print(
    "Target preload N                :",
    resolved.source_case.loading.target_preload_n,
)

print()
print(
    "Canonical V1 Trial-1 run ID     :",
    canonical_trial1_run_id,
)

print(
    "Canonical V1 delta T C          :",
    canonical_v1_delta_t,
)

print(
    "Canonical V1 preserved          : YES"
)

print()
print(
    "V2.1 prospective run ID         :",
    v21_trial_run_id,
)

print(
    "Frozen V2.1 delta T C           :",
    predicted_delta_t,
)

print(
    "Delta vs V1 C                   :",
    predicted_delta_t
    - canonical_v1_delta_t,
)

print()
print(
    "Mesh policy                     :",
    doe_case.mesh_policy_name,
)

print(
    "Node count                      :",
    deck.node_count,
)

print(
    "Element count                   :",
    deck.element_count,
)

print(
    "FEM preflight                   : PASS"
)

print()
print(
    "Prediction SHA256               :",
    prediction_hash,
)

print(
    "V2.1 policy SHA256              :",
    v21_policy_hash,
)

print(
    "Deck SHA256                     :",
    actual_deck_hash,
)

print(
    "Preparation SHA256              :",
    record_hash,
)

print()
print(
    "Deck                            :",
    input_path,
)

print(
    "Preparation record              :",
    record_path,
)

print(
    "Record action                   :",
    action,
)

print()
print(
    "Prospective solver outputs      : NONE"
)

print(
    "CalculiX invoked                : NO"
)

print(
    "Prospective result read         : NO"
)

print(
    "Blind holdouts accessed         : NO"
)

print(
    "Solver authorized by this step  : NO"
)

print()
print(
    "Disposition                     : "
    "V2_1_PROSPECTIVE_SOLVER_PREPARATION_PASS"
)

print("=" * 128)
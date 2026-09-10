from __future__ import annotations

import dataclasses
import hashlib
import json
import math

from enum import Enum
from pathlib import Path

from threadrom.case.preflight import (
    PreflightSeverity,
    PreflightTarget,
)
from threadrom.case.preflight_engine import preflight_case
from threadrom.case.resolver import resolve_case

from threadrom.factory.fem_case_definition_bundle import (
    build_generic_fem_definition_bundle,
)
from threadrom.factory.fem_preload_calibration_deck import (
    write_fem_preload_calibration_trial_deck,
)
from threadrom.factory.fem_profile import (
    PHASE3_CP8_EXECUTION_RESILIENCE,
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

SOLVER_ROOT = CAMPAIGN_ROOT / "solver_preparation"

DOE_POLICY_PATH = CONFIG / "phase3_production_doe.toml"

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

FROZEN_PREDICTION_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_prospective_prediction.json"
)

ROLLOUT_CERT_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_rollout_preparation_certification.json"
)

WAVE_MANIFEST_PATH = (
    CAMPAIGN_ROOT
    / "cp8_restart_v2_wave_01_preparation_manifest.json"
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

EXPECTED_FROZEN_PREDICTION_SHA256 = (
    "36b0230083c98fc2674adf98b5d5f3ab"
    "a75c736888cfb44c113b86272c53ec4f"
)

EXPECTED_ROLLOUT_CERT_SHA256 = (
    "a11662817427d9131b92f798e953d116"
    "269ad672c49434365a75f68dac4709a7"
)

EXPECTED_RESILIENCE_POLICY_ID = (
    "phase3_cp8_thermal_calibration_restart_"
    "v2_windows_nonoverlay"
)

WAVE_CASE_IDS = (
    "D-INT-001",
    "D-INT-003",
    "D-INT-004",
    "D-INT-005",
)

INTERRUPTED_CASE_IDS = {
    "D-INT-001",
    "D-INT-003",
    "D-INT-004",
}

SOLVER_SUFFIXES = {
    ".dat",
    ".frd",
    ".sta",
    ".cvg",
    ".12d",
    ".eig",
    ".equ",
    ".rout",
}


def sha256(path: Path) -> str:
    if not path.is_file() or path.stat().st_size <= 0:
        raise FileNotFoundError(path)

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
        path.read_text(encoding="utf-8-sig")
    )


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def jsonable(value):
    if dataclasses.is_dataclass(value):
        return {
            field.name: jsonable(
                getattr(value, field.name)
            )
            for field in dataclasses.fields(value)
        }

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            str(key): jsonable(child)
            for key, child in value.items()
        }

    if isinstance(value, (tuple, list)):
        return [
            jsonable(child)
            for child in value
        ]

    return value


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
                "Immutable restart-v2 evidence already "
                "exists with different content. "
                f"Refusing overwrite: {path}"
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

    record_hash = sha256(path)

    sidecar = path.with_suffix(".sha256")

    expected_sidecar = (
        f"{record_hash}  {path.name}\n"
    )

    if sidecar.exists():
        observed = sidecar.read_text(
            encoding="ascii"
        )

        if observed != expected_sidecar:
            raise RuntimeError(
                "Immutable SHA sidecar drift: "
                f"{sidecar}"
            )
    else:
        sidecar.write_text(
            expected_sidecar,
            encoding="ascii",
            newline="\n",
        )

    return action, record_hash


def find_unique(
    rows,
    case_id: str,
    *,
    label: str,
):
    matches = [
        row
        for row in rows
        if row["case_id"] == case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected one {label}; "
            f"found {len(matches)}."
        )

    return matches[0]


def solver_outputs_present(
    root: Path,
) -> tuple[str, ...]:
    if not root.exists():
        return ()

    found = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if (
            path.name == "fem_run_manifest.json"
            or path.suffix.lower() in SOLVER_SUFFIXES
        ):
            found.append(relative(path))

    return tuple(sorted(found))


# ============================================================
# 1. LOCK GOVERNANCE
# ============================================================

doe_policy_hash = require_sha256(
    DOE_POLICY_PATH,
    EXPECTED_DOE_POLICY_SHA256,
    "Production DOE policy",
)

campaign_hash = require_sha256(
    CAMPAIGN_MANIFEST_PATH,
    EXPECTED_CAMPAIGN_SHA256,
    "Production DOE campaign manifest",
)

preparation_cert_hash = require_sha256(
    PREPARATION_CERT_PATH,
    EXPECTED_PREPARATION_CERT_SHA256,
    "Production DOE preparation certification",
)

v21_policy_hash = require_sha256(
    V21_POLICY_PATH,
    EXPECTED_V21_POLICY_SHA256,
    "Frozen V2.1 policy",
)

frozen_prediction_hash = require_sha256(
    FROZEN_PREDICTION_PATH,
    EXPECTED_FROZEN_PREDICTION_SHA256,
    "Frozen V2.1 prediction",
)

rollout_cert_hash = require_sha256(
    ROLLOUT_CERT_PATH,
    EXPECTED_ROLLOUT_CERT_SHA256,
    "V2.1 rollout certification",
)

resilience = PHASE3_CP8_EXECUTION_RESILIENCE

if (
    resilience.policy_id
    != EXPECTED_RESILIENCE_POLICY_ID
    or resilience.checkpoint_count != 20
    or resilience.write_enabled is not True
    or resilience.write_frequency_steps != 1
    or resilience.overlay_latest is not False
    or resilience.preserve_total_pseudo_time is not True
):
    raise RuntimeError(
        "CP8 restart-v2 execution-resilience "
        "policy drift."
    )


# ============================================================
# 2. LOAD FROZEN CAMPAIGN / CERTIFICATIONS
# ============================================================

policy = load_phase3_production_doe_policy(
    DOE_POLICY_PATH
)

campaign = build_phase3_production_doe(
    policy
)

preparation_cert = load_json(
    PREPARATION_CERT_PATH
)

rollout_cert = load_json(
    ROLLOUT_CERT_PATH
)

if (
    rollout_cert.get("record_status")
    != "FINAL"
    or rollout_cert.get("overall_disposition")
    != (
        "V2_1_ROLLOUT_PREPARATION_"
        "CERTIFIED_READY_FOR_FEM"
    )
):
    raise RuntimeError(
        "Frozen V2.1 rollout certification "
        "is not FINAL / READY_FOR_FEM."
    )

authorization = rollout_cert[
    "rollout_execution_authorization"
]

if (
    authorization.get("authorized") is not True
    or authorization.get("predictor")
    != "warm_start_delta_t_v2_1"
    or authorization.get(
        "v2_1_model_must_remain_frozen"
    )
    is not True
    or authorization.get(
        "blind_holdout_execution_authorized"
    )
    is not False
):
    raise RuntimeError(
        "Frozen rollout execution authorization drift."
    )

authorized_ids = set(
    authorization["authorized_case_ids"]
)

if not set(WAVE_CASE_IDS).issubset(
    authorized_ids
):
    raise RuntimeError(
        "Restart-v2 wave contains a case outside "
        "the frozen authorized rollout set."
    )


# ============================================================
# 3. LOAD PROVEN FEM TEMPLATES
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

reference_temperature_c = float(
    preload_template
    .thermal
    .reference_temperature_c
)


# ============================================================
# 4. BUILD FOUR RESTART-V2 TRIAL-1 SIBLINGS
# ============================================================

rows = []

for case_id in WAVE_CASE_IDS:
    matches = tuple(
        item
        for item in campaign.design_cases
        if item.case_id == case_id
    )

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected exactly one "
            "Production DOE design case."
        )

    doe_case = matches[0]

    if (
        doe_case.source_case_id is not None
        or case_id.startswith("H")
    ):
        raise RuntimeError(
            f"{case_id}: anchor/holdout execution "
            "is forbidden."
        )

    resolved = resolve_case(
        doe_case.case
    )

    if resolved.case_hash != doe_case.case_hash:
        raise RuntimeError(
            f"{case_id}: resolved case-hash drift."
        )

    certified = find_unique(
        rollout_cert["certified_rollout_cases"],
        case_id,
        label="certified V2.1 rollout row",
    )

    if certified["case_hash"] != doe_case.case_hash:
        raise RuntimeError(
            f"{case_id}: rollout case-hash drift."
        )

    canonical_case_run_id = (
        f"trm_fem_{doe_case.case_hash[:12]}"
    )

    source_trial_run_id = (
        f"{canonical_case_run_id}_cal_01_wsv21"
    )

    replacement_trial_run_id = (
        f"{canonical_case_run_id}_cal_01_wsv21_rv2"
    )

    if certified["run_id"] != source_trial_run_id:
        raise RuntimeError(
            f"{case_id}: frozen source run-ID drift."
        )

    frozen_delta_t = float(
        certified[
            "predicted_delta_temperature_c"
        ]
    )

    target_preload_n = float(
        certified["target_preload_n"]
    )

    # --------------------------------------------------------
    # Preserve / verify immutable source V2.1 preparation
    # --------------------------------------------------------

    source_deck = (
        ROOT
        / certified["deck_relative_path"]
    )

    source_prep_path = (
        ROOT
        / certified[
            "preparation_relative_path"
        ]
    )

    if sha256(source_deck) != certified[
        "deck_sha256"
    ]:
        raise RuntimeError(
            f"{case_id}: source deck SHA drift."
        )

    if sha256(source_prep_path) != certified[
        "preparation_sha256"
    ]:
        raise RuntimeError(
            f"{case_id}: source preparation SHA drift."
        )

    source_prep = load_json(
        source_prep_path
    )

    if (
        source_prep.get("record_status")
        != "FINAL"
        or source_prep.get(
            "overall_disposition"
        )
        != (
            "V2_1_ROLLOUT_CASE_PREPARATION_PASS_"
            "AWAITING_BATCH_CERTIFICATION"
        )
    ):
        raise RuntimeError(
            f"{case_id}: source V2.1 preparation "
            "is not the frozen FINAL PASS."
        )

    if (
        source_prep["case"]["case_id"]
        != case_id
        or source_prep["case"]["case_hash"]
        != doe_case.case_hash
        or source_prep["case"][
            "v2_1_trial1_run_id"
        ]
        != source_trial_run_id
    ):
        raise RuntimeError(
            f"{case_id}: source preparation "
            "identity drift."
        )

    if (
        source_prep["fem_preflight"]["status"]
        != "PASS"
    ):
        raise RuntimeError(
            f"{case_id}: source FEM preflight "
            "is not PASS."
        )

    source_lines = source_deck.read_text(
        encoding="utf-8-sig"
    ).splitlines()

    source_restart_lines = [
        line
        for line in source_lines
        if line.strip().upper().startswith(
            "*RESTART"
        )
    ]

    source_step_count = sum(
        1
        for line in source_lines
        if line.strip().upper().startswith(
            "*STEP"
        )
    )

    if source_restart_lines:
        raise RuntimeError(
            f"{case_id}: historical source deck "
            "unexpectedly contains restart keywords."
        )

    if source_step_count != 1:
        raise RuntimeError(
            f"{case_id}: historical source deck "
            "is no longer the expected monolithic "
            "one-step representation."
        )

    source_run_dir = source_deck.parent

    source_manifest = (
        source_run_dir
        / "fem_run_manifest.json"
    )

    source_outputs = tuple(
        sorted(
            path.name
            for path in source_run_dir.iterdir()
            if (
                path.is_file()
                and path.suffix.lower()
                in SOLVER_SUFFIXES
            )
        )
    )

    if source_manifest.exists():
        raise RuntimeError(
            f"{case_id}: historical source manifest "
            "unexpectedly exists."
        )

    if case_id in INTERRUPTED_CASE_IDS:
        required = {
            f"{source_trial_run_id}.cvg",
            f"{source_trial_run_id}.dat",
            f"{source_trial_run_id}.frd",
            f"{source_trial_run_id}.sta",
        }

        if not required.issubset(
            set(source_outputs)
        ):
            raise RuntimeError(
                f"{case_id}: expected interrupted "
                "historical outputs are incomplete."
            )

    else:
        if source_outputs:
            raise RuntimeError(
                f"{case_id}: supposedly untouched "
                "source Trial 1 already has solver outputs."
            )

    # --------------------------------------------------------
    # Bind to certified mesh / STEP preparation
    # --------------------------------------------------------

    prep_row = find_unique(
        preparation_cert[
            "design_case_preparation_evidence"
        ],
        case_id,
        label="certified FEM preparation row",
    )

    if (
        prep_row["case_hash"]
        != doe_case.case_hash
        or prep_row["mesh_policy_name"]
        != doe_case.mesh_policy_name
    ):
        raise RuntimeError(
            f"{case_id}: certified preparation "
            "identity drift."
        )

    mesh_path = (
        ROOT
        / prep_row["mesh_relative_path"]
    )

    step_path = (
        ROOT
        / prep_row["step_relative_path"]
    )

    mesh_hash = sha256(
        mesh_path
    )

    step_hash = sha256(
        step_path
    )

    if mesh_hash != prep_row["mesh_sha256"]:
        raise RuntimeError(
            f"{case_id}: certified mesh SHA drift."
        )

    if step_hash != prep_row["step_sha256"]:
        raise RuntimeError(
            f"{case_id}: certified STEP SHA drift."
        )

    # --------------------------------------------------------
    # Fresh FEM preflight
    # --------------------------------------------------------

    preflight = preflight_case(
        doe_case.case,
        PreflightTarget.FEM,
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
            f"{case_id}: FEM preflight BLOCKED: "
            + "; ".join(
                str(finding)
                for finding in blocking
            )
        )

    # --------------------------------------------------------
    # Rebuild certified physical FEM definition
    # --------------------------------------------------------

    token = resolved.case_hash[:16]

    bundle = (
        build_generic_fem_definition_bundle(
            resolved,
            mesh_id=f"mesh-{token}",
            geometry_id=f"geometry-{token}",
            classification_id=(
                f"classification-{token}"
            ),
            source_mesh_name=mesh_path.name,
            transfer_template=transfer_template,
            contact_template=contact_template,
            boundary_template=boundary_template,
        )
    )

    if not math.isclose(
        float(
            bundle
            .calibration_seed
            .target_force_n
        ),
        target_preload_n,
        rel_tol=0.0,
        abs_tol=1.0e-10,
    ):
        raise RuntimeError(
            f"{case_id}: target preload drift "
            "during bundle reconstruction."
        )

    mesh_data = (
        read_grouped_complete_joint_mesh(
            mesh_path,
            bundle.transfer,
        )
    )

    # --------------------------------------------------------
    # Replacement execution sibling is STILL Trial 1
    # --------------------------------------------------------

    trial = PreloadCalibrationTrial(
        trial_index=1,
        run_id=replacement_trial_run_id,
        delta_temperature_c=frozen_delta_t,
        source=(
            PreloadCalibrationTrialSource
            .FEM_WARM_START
        ),
    )

    run_dir = (
        SOLVER_ROOT
        / canonical_case_run_id
        / replacement_trial_run_id
    )

    manifest_path = (
        run_dir
        / "fem_run_manifest.json"
    )

    existing_solver_outputs = (
        solver_outputs_present(
            run_dir
        )
    )

    if existing_solver_outputs:
        raise RuntimeError(
            f"{case_id}: restart-v2 sibling "
            "already contains solver output:\n"
            + "\n".join(
                existing_solver_outputs
            )
        )

    if manifest_path.exists():
        raise RuntimeError(
            f"{case_id}: restart-v2 sibling "
            "manifest already exists."
        )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path = (
        run_dir
        / f"{replacement_trial_run_id}.inp"
    )

    candidate_path = (
        run_dir
        / f".{replacement_trial_run_id}.candidate.inp"
    )

    if candidate_path.exists():
        candidate_path.unlink()

    deck = (
        write_fem_preload_calibration_trial_deck(
            mesh_data=mesh_data,
            bundle=bundle,
            trial=trial,
            reference_temperature_c=(
                reference_temperature_c
            ),
            input_path=candidate_path,
        )
    )

    candidate_hash = sha256(
        candidate_path
    )

    if candidate_hash != deck.sha256:
        raise RuntimeError(
            f"{case_id}: generated candidate "
            "deck SHA mismatch."
        )

    candidate_text = candidate_path.read_text(
        encoding="utf-8-sig"
    )

    if (
        deck.trial_run_id
        != replacement_trial_run_id
        or deck.trial_index != 1
        or not math.isclose(
            deck.delta_temperature_c,
            frozen_delta_t,
            rel_tol=0.0,
            abs_tol=1.0e-10,
        )
    ):
        raise RuntimeError(
            f"{case_id}: restart-v2 Trial-1 "
            "identity / frozen ΔT drift."
        )

    if (
        deck.execution_resilience_policy_id
        != EXPECTED_RESILIENCE_POLICY_ID
        or deck.checkpoint_count != 20
        or deck.restart_write_count != 1
    ):
        raise RuntimeError(
            f"{case_id}: restart-v2 deck "
            "resilience metadata drift."
        )

    restart_lines = [
        line.strip()
        for line in candidate_text.splitlines()
        if line.strip().upper().startswith(
            "*RESTART"
        )
    ]

    step_count = sum(
        1
        for line in candidate_text.splitlines()
        if line.strip().upper().startswith(
            "*STEP"
        )
    )

    if restart_lines != [
        "*RESTART,WRITE,FREQUENCY=1"
    ]:
        raise RuntimeError(
            f"{case_id}: restart keyword drift: "
            f"{restart_lines}"
        )

    if ",OVERLAY" in candidate_text.upper():
        raise RuntimeError(
            f"{case_id}: Windows-unsafe OVERLAY "
            "leaked into restart-v2 deck."
        )

    if step_count != 20:
        raise RuntimeError(
            f"{case_id}: restart-v2 deck does "
            f"not contain 20 checkpoints."
        )

    if input_path.exists():
        existing_hash = sha256(
            input_path
        )

        if existing_hash != candidate_hash:
            candidate_path.unlink()

            raise RuntimeError(
                f"{case_id}: immutable restart-v2 "
                "deck already exists with different "
                "content."
            )

        candidate_path.unlink()
        deck_action = "UNCHANGED / IDENTICAL"

    else:
        candidate_path.replace(
            input_path
        )
        deck_action = "CREATED"

    actual_deck_hash = sha256(
        input_path
    )

    if actual_deck_hash != candidate_hash:
        raise RuntimeError(
            f"{case_id}: finalized restart-v2 "
            "deck SHA drift."
        )

    # --------------------------------------------------------
    # Immutable per-case preparation evidence
    # --------------------------------------------------------

    record = {
        "schema_version": 1,
        "record_id": (
            "TRM-P3-CP8-WSV21-RV2-"
            f"{case_id}-PREP-P01"
        ),
        "record_status": "FINAL",

        "case": {
            "case_id": case_id,
            "case_hash": doe_case.case_hash,
            "canonical_case_run_id": (
                canonical_case_run_id
            ),
            "trial_index": 1,
            "source_v2_1_trial_run_id": (
                source_trial_run_id
            ),
            "restart_v2_trial_run_id": (
                replacement_trial_run_id
            ),
            "target_preload_n": (
                target_preload_n
            ),
            "mesh_policy_name": (
                doe_case.mesh_policy_name
            ),
        },

        "replacement_semantics": {
            "calibration_trial_identity": (
                "TRIAL_1"
            ),
            "new_calibration_attempt": False,
            "physics_prediction_changed": False,
            "frozen_v2_1_delta_temperature_c": (
                frozen_delta_t
            ),
            "purpose": (
                "replace pre-resilience Trial-1 "
                "execution representation with "
                "governed restart-v2 execution "
                "resilience"
            ),
            "historical_source_preserved": True,
            "resume_from_historical_checkpoint": False,
            "fresh_full_solve_required": True,
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
            "frozen_v2_1_prediction_sha256": (
                frozen_prediction_hash
            ),
            "rollout_certification_relative_path": (
                relative(
                    ROLLOUT_CERT_PATH
                )
            ),
            "rollout_certification_sha256": (
                rollout_cert_hash
            ),
            "v2_1_model_refit_performed": False,
            "holdout_accessed": False,
        },

        "historical_source": {
            "run_id": source_trial_run_id,
            "preparation_relative_path": (
                relative(
                    source_prep_path
                )
            ),
            "preparation_sha256": (
                sha256(
                    source_prep_path
                )
            ),
            "deck_relative_path": (
                relative(
                    source_deck
                )
            ),
            "deck_sha256": (
                sha256(
                    source_deck
                )
            ),
            "deck_step_count": (
                source_step_count
            ),
            "deck_restart_keyword_count": 0,
            "manifest_present": False,
            "solver_outputs": list(
                source_outputs
            ),
            "historical_state": (
                "INTERRUPTED_WITH_PARTIAL_OUTPUTS"
                if case_id
                in INTERRUPTED_CASE_IDS
                else "PREPARED_NOT_EXECUTED"
            ),
        },

        "certified_prepared_artifacts": {
            "mesh_relative_path": (
                relative(mesh_path)
            ),
            "mesh_sha256": mesh_hash,
            "step_relative_path": (
                relative(step_path)
            ),
            "step_sha256": step_hash,
        },

        "fem_preflight": {
            "status": "PASS",
            "finding_count": len(
                preflight.findings
            ),
            "findings": jsonable(
                preflight.findings
            ),
        },

        "trial": jsonable(
            trial
        ),

        "execution_resilience": {
            "policy_id": (
                resilience.policy_id
            ),
            "checkpoint_count": (
                resilience.checkpoint_count
            ),
            "restart_write_enabled": (
                resilience.write_enabled
            ),
            "restart_write_frequency_steps": (
                resilience
                .write_frequency_steps
            ),
            "overlay_latest": (
                resilience.overlay_latest
            ),
            "preserve_total_pseudo_time": (
                resilience
                .preserve_total_pseudo_time
            ),
            "live_restart_smoke_previously_verified": True,
        },

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
            "checkpoint_count": (
                deck.checkpoint_count
            ),
            "checkpoint_step_time": (
                deck.checkpoint_step_time
            ),
            "restart_write_count": (
                deck.restart_write_count
            ),
            "execution_resilience_policy_id": (
                deck
                .execution_resilience_policy_id
            ),
        },

        "execution_authorization": {
            "calculix_invoked_by_this_record": False,
            "solver_results_read_for_replacement": False,
            "execution_authorized_by_this_record": False,
            "requires_independent_pre_execution_certification": True,
            "maximum_future_concurrency": 4,
            "blind_holdout_execution_authorized": False,
        },

        "overall_disposition": (
            "CP8_RESTART_V2_SIBLING_PREPARATION_PASS_"
            "AWAITING_INDEPENDENT_EXECUTION_CERTIFICATION"
        ),
    }

    record_path = (
        run_dir
        / "production_doe_restart_v2_solver_preparation_record.json"
    )

    record_action, record_hash = (
        write_immutable_json(
            record_path,
            record,
        )
    )

    rows.append(
        {
            "case_id": case_id,
            "case_hash": doe_case.case_hash,
            "trial_index": 1,
            "source_trial_run_id": (
                source_trial_run_id
            ),
            "restart_v2_trial_run_id": (
                replacement_trial_run_id
            ),
            "frozen_delta_temperature_c": (
                frozen_delta_t
            ),
            "deck_relative_path": (
                relative(input_path)
            ),
            "deck_sha256": (
                actual_deck_hash
            ),
            "preparation_relative_path": (
                relative(record_path)
            ),
            "preparation_sha256": (
                record_hash
            ),
            "deck_action": deck_action,
            "record_action": record_action,
        }
    )


# ============================================================
# 5. IMMUTABLE FOUR-CASE ZERO-SOLVE WAVE MANIFEST
# ============================================================

wave_manifest = {
    "schema_version": 1,
    "record_id": (
        "TRM-P3-CP8-WSV21-RV2-WAVE01-PREP-P01"
    ),
    "record_status": "FINAL",
    "campaign_id": "TRM-PDOE-C01",

    "wave": {
        "wave_id": "CP8-WSV21-RV2-WAVE01",
        "case_count": len(rows),
        "case_ids": list(
            WAVE_CASE_IDS
        ),
        "maximum_future_concurrency": 4,
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
        "frozen_v2_1_prediction_sha256": (
            frozen_prediction_hash
        ),
        "rollout_certification_sha256": (
            rollout_cert_hash
        ),
        "v2_1_model_remained_frozen": True,
        "holdout_accessed": False,
    },

    "replacement_semantics": {
        "all_cases_remain_trial_1": True,
        "no_new_calibration_attempt_created": True,
        "historical_runs_preserved": True,
        "historical_restart_resume_attempted": False,
        "fresh_full_solve_siblings_required": True,
    },

    "restart_v2_policy": {
        "policy_id": (
            resilience.policy_id
        ),
        "checkpoint_count": 20,
        "restart_write_frequency_steps": 1,
        "overlay_latest": False,
        "preserve_total_pseudo_time": True,
    },

    "cases": rows,

    "zero_solve_evidence": {
        "calculix_invoked": False,
        "solver_results_read_for_replacement": False,
        "execution_authorized": False,
        "independent_execution_certification_required": True,
        "blind_holdout_accessed": False,
    },

    "overall_disposition": (
        "CP8_RESTART_V2_WAVE_PREPARATION_PASS_"
        "AWAITING_INDEPENDENT_EXECUTION_CERTIFICATION"
    ),
}

manifest_action, manifest_hash = (
    write_immutable_json(
        WAVE_MANIFEST_PATH,
        wave_manifest,
    )
)


print("=" * 120)
print("THREADROM — CP8 RESTART-V2 WAVE PREPARATION")
print("=" * 120)
print("Wave cases               :", len(rows))
print("CalculiX invoked         : NO")
print("V2.1 refit               : NO")
print("Holdouts accessed        : NO")
print("All remain Trial 1       : YES")
print("Restart checkpoints      :", 20)
print("Restart OVERLAY          : NO")
print("Wave manifest action     :", manifest_action)
print("Wave manifest SHA256     :", manifest_hash)
print("Wave manifest            :", WAVE_MANIFEST_PATH)
print()

for row in rows:
    print(
        row["case_id"],
        "|",
        row["restart_v2_trial_run_id"],
        "| dT=",
        row["frozen_delta_temperature_c"],
        "| deck=",
        row["deck_action"],
        "| evidence=",
        row["record_action"],
    )

print()
print(
    "Disposition              : "
    "PREPARED — EXECUTION STILL BLOCKED "
    "PENDING INDEPENDENT CERTIFICATION"
)
print("=" * 120)

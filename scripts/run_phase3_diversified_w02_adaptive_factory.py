from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import hashlib
import inspect
import json
import math
import os
import time
import tomllib

from enum import Enum
from pathlib import Path
from typing import Any, Mapping


from threadrom.case.resolver import resolve_case

from threadrom.factory.diversified_doe_design import (
    _build_case,
)

from threadrom.materials.diversified_candidate_catalog import (
    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
)

from threadrom.factory.fem_case_definition_bundle import (
    PHASE2_CERTIFIED_FEM_PROFILE,
    build_generic_fem_definition_bundle,
)

from threadrom.factory.fem_preload_calibration_deck import (
    write_fem_preload_calibration_trial_deck,
)

from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)

from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationCampaignPolicy,
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
    evaluate_preload_calibration_trial,
)

from threadrom.factory.fem_factory_registry import (
    FemFactoryJobState,
    FemFactoryPriority,
    FemFactoryRegistry,
)

from threadrom.factory.diversified_parallel_admission import (
    claim_parallel_factory_slot,
)

from threadrom.factory.diversified_factory_worker import (
    execute_claimed_factory_job,
)

from threadrom.factory.diversified_calculix_worker_adapter import (
    GovernedCalculixExecutionSpec,
    make_claimed_calculix_executor,
)

from threadrom.factory.fem_result_extraction import (
    extract_fem_physics_result_evidence,
    load_fem_result_extraction_policy,
)

from threadrom.factory.fem_acceptance_policy import (
    derive_complete_joint_physics_acceptance_policy,
)

from threadrom.factory.fem_physics_acceptance import (
    evaluate_fem_physics_acceptance,
)

from threadrom.factory.diversified_fem_physics_certificate import (
    persist_governed_physics_certificate,
    recover_governed_physics_certificate,
)

from threadrom.postprocessing.calculix_nonlinear_progress import (
    write_nonlinear_progress_json,
)

from threadrom.postprocessing.calculix_total_force_dat import (
    write_total_force_json,
)

from threadrom.postprocessing.calculix_external_equilibrium import (
    write_external_equilibrium_resultant_json,
)

from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
)

from threadrom.solver.complete_joint_boundary_regions import (
    HEAD_SUPPORT,
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

from threadrom.solver.complete_joint_physical_pretension import (
    BOLT_HEAD_GUIDANCE_REFERENCE,
    NUT_MEMBER_GUIDANCE_REFERENCE,
    NUT_TRANSLATION_GUIDANCE_REFERENCE,
)


ROOT = Path(r"D:\ThreadROM").resolve()

CAMPAIGN_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / "TRM-DDOE-001"
    / "W02"
)

SOLVER_ROOT = (
    CAMPAIGN_ROOT
    / "solver_preparation"
)

FACTORY_ROOT = (
    CAMPAIGN_ROOT
    / "factory"
)

FACTORY_DB = (
    FACTORY_ROOT
    / "w02_trial1_factory.sqlite3"
)

ADMISSION_LOCK = (
    FACTORY_ROOT
    / "w02_adaptive_parallel_admission.lock"
)

AUTH_PATH = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "waves"
    / "TRM-DDOE-001-W02"
    / "adaptive_campaign_owner_authorization.json"
)

EXPECTED_AUTH_SHA256 = "19f5fa4bcd31eb8a1bff992f17d2c60a5ff70fdcf741521cc834401c99e6890a"

PREP_INDEX_PATH = (
    CAMPAIGN_ROOT
    / "w02_trial1_preparation.json"
)

EXPECTED_PREP_INDEX_SHA256 = "80f14936394ac4cc713f6628f10630e4805a0531b3624de4cb6f60cc293b8ff2"

PROPOSAL_PATH = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "design_proposal.json"
)

POLICY_PATH = (
    ROOT
    / "config"
    / "phase3_diversified_doe.toml"
)

TRANSFER_PATH = (
    ROOT
    / "config"
    / "complete_joint_calculix_transfer.toml"
)

CONTACT_PATH = (
    ROOT
    / "config"
    / "complete_joint_contact.toml"
)

BOUNDARY_PATH = (
    ROOT
    / "config"
    / "complete_joint_boundary_regions.toml"
)

PRELOAD_PATH = (
    ROOT
    / "config"
    / "complete_joint_preload.toml"
)

RESULT_POLICY_PATH = (
    ROOT
    / "config"
    / "fem_result_extraction.toml"
)

SCRIPT_RELATIVE_PATH = (
    "scripts/"
    "run_phase3_diversified_w02_adaptive_factory.py"
)

LEASE_SECONDS = 900
HEARTBEAT_SECONDS = 60
MAXIMUM_CONCURRENT_CCX = 4
MAXIMUM_TRIALS = 6

EXPECTED_CASE_COUNT = 4


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
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


def relative(path: Path) -> str:
    return (
        path.resolve()
        .relative_to(ROOT)
        .as_posix()
    )


def enum_value(value):
    return getattr(
        value,
        "value",
        value,
    )


def jsonable(value: Any):
    if dataclasses.is_dataclass(value):
        return {
            field.name: jsonable(
                getattr(value, field.name)
            )
            for field in dataclasses.fields(
                value
            )
        }

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, Path):
        try:
            return relative(value)
        except ValueError:
            return str(value)

    if isinstance(value, Mapping):
        return {
            str(key): jsonable(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
            frozenset,
        ),
    ):
        return [
            jsonable(item)
            for item in value
        ]

    if isinstance(value, float):
        require(
            math.isfinite(value),
            "Non-finite value encountered "
            "while serializing governed evidence.",
        )

    return value


def canonical_json_bytes(
    payload: Mapping[str, object],
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


def write_immutable_json(
    path: Path,
    payload: Mapping[str, object],
) -> str:
    content = canonical_json_bytes(
        payload
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if path.exists():
        require(
            path.read_bytes() == content,
            (
                "Immutable governed artifact drift: "
                f"{path}"
            ),
        )

        return sha256(path)

    path.write_bytes(content)

    return sha256(path)


def read_json(path: Path) -> dict:
    require(
        path.is_file(),
        f"JSON evidence missing: {path}",
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )

    require(
        isinstance(payload, dict),
        f"JSON root must be object: {path}",
    )

    return payload


def manifest_status(
    manifest_path: Path,
    *,
    run_id: str,
    case_hash: str,
) -> tuple[str, dict | None]:
    if not manifest_path.is_file():
        return "MISSING", None

    manifest = read_json(
        manifest_path
    )

    require(
        manifest.get("run_id")
        == run_id,
        f"{run_id}: manifest run identity drift.",
    )

    require(
        manifest.get("job_name")
        == run_id,
        f"{run_id}: manifest job identity drift.",
    )

    require(
        manifest.get("case_hash")
        == case_hash,
        f"{run_id}: manifest case-hash drift.",
    )

    disposition = str(
        manifest.get(
            "disposition",
            "",
        )
    ).lower()

    if disposition == "succeeded":
        require(
            manifest.get(
                "return_code"
            )
            == 0,
            f"{run_id}: succeeded manifest "
            "has nonzero return code.",
        )

        require(
            manifest.get(
                "job_finished"
            )
            is True,
            f"{run_id}: succeeded manifest "
            "lacks Job finished evidence.",
        )

        return "SUCCEEDED", manifest

    if disposition == "failed":
        return "FAILED", manifest

    raise RuntimeError(
        f"{run_id}: unsupported manifest "
        f"disposition {disposition!r}."
    )


def find_paths_with_suffix(
    value: object,
    suffix: str,
) -> list[Path]:
    raw_paths: list[str] = []

    def walk(item):
        if isinstance(item, dict):
            for child in item.values():
                walk(child)

        elif isinstance(item, list):
            for child in item:
                walk(child)

        elif (
            isinstance(item, str)
            and item.lower().endswith(
                suffix.lower()
            )
        ):
            raw_paths.append(item)

    walk(value)

    resolved: list[Path] = []

    for raw in raw_paths:
        candidate = Path(raw)

        if not candidate.is_absolute():
            candidate = ROOT / candidate

        candidate = candidate.resolve()

        if (
            candidate.is_file()
            and candidate.stat().st_size > 0
        ):
            resolved.append(
                candidate
            )

    unique: list[Path] = []

    for path in resolved:
        if path not in unique:
            unique.append(path)

    return unique


def resolve_governed_mesh(
    *,
    preparation: dict,
    case_run_id: str,
) -> Path:
    candidates = find_paths_with_suffix(
        preparation,
        ".msh",
    )

    if not candidates:
        case_root = (
            SOLVER_ROOT
            / case_run_id
        )

        if case_root.is_dir():
            candidates.extend(
                sorted(
                    case_root.rglob("*.msh")
                )
            )

    require(
        candidates,
        (
            f"{case_run_id}: no governed mesh "
            "could be resolved from preparation."
        ),
    )

    hashes = {
        sha256(path)
        for path in candidates
    }

    require(
        len(hashes) == 1,
        (
            f"{case_run_id}: preparation "
            "references multiple different meshes: "
            + ", ".join(
                str(path)
                for path in candidates
            )
        ),
    )

    return candidates[0]


def governed_reference_temperature_c(
    preload,
) -> float:
    thermal = getattr(
        preload,
        "thermal",
        None,
    )

    if thermal is not None:
        value = getattr(
            thermal,
            "reference_temperature_c",
            None,
        )

        if (
            isinstance(value, (int, float))
            and math.isfinite(
                float(value)
            )
        ):
            return float(value)

    value = getattr(
        preload,
        "reference_temperature_c",
        None,
    )

    if (
        isinstance(value, (int, float))
        and math.isfinite(
            float(value)
        )
    ):
        return float(value)

    raw = tomllib.loads(
        PRELOAD_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    found: list[float] = []

    def walk(item):
        if isinstance(item, dict):
            for key, child in item.items():
                if (
                    key
                    == "reference_temperature_c"
                    and isinstance(
                        child,
                        (int, float),
                    )
                ):
                    found.append(
                        float(child)
                    )
                else:
                    walk(child)

        elif isinstance(item, list):
            for child in item:
                walk(child)

    walk(raw)

    found = [
        value
        for value in found
        if math.isfinite(value)
    ]

    require(
        len(found) == 1,
        (
            "Could not uniquely resolve governed "
            "reference_temperature_c."
        ),
    )

    return found[0]


def verify_owner_authorization() -> dict:
    require(
        sha256(AUTH_PATH)
        == EXPECTED_AUTH_SHA256,
        "Adaptive campaign owner "
        "authorization SHA-256 drift.",
    )

    auth = read_json(
        AUTH_PATH
    )

    require(
        auth.get(
            "approval_status"
        )
        == "OWNER_APPROVED",
        "Owner authorization is not approved.",
    )

    contract = auth.get(
        "execution_contract"
    )

    scope = auth.get(
        "scope"
    )

    require(
        isinstance(contract, dict),
        "Missing adaptive execution contract.",
    )

    require(
        isinstance(scope, dict),
        "Missing adaptive authorization scope.",
    )

    require(
        contract.get(
            "automatic_governed_adaptation"
        )
        is True,
        "Automatic governed adaptation "
        "is not authorized.",
    )

    require(
        contract.get(
            "continue_until_physics_acceptance"
        )
        is True,
        "Continuation through physics acceptance "
        "is not authorized.",
    )

    require(
        contract.get(
            "preload_calibration_continuation"
        )
        is True,
        "Calibration continuation is not authorized.",
    )

    require(
        contract.get(
            "full_physics_certification"
        )
        is True,
        "Full physics certification "
        "is not authorized.",
    )

    require(
        contract.get(
            "maximum_trial_index_per_case"
        )
        == MAXIMUM_TRIALS,
        "Authorized trial ceiling drift.",
    )

    require(
        contract.get(
            "maximum_concurrent_calculix"
        )
        == MAXIMUM_CONCURRENT_CCX,
        "Authorized CalculiX concurrency drift.",
    )

    require(
        contract.get(
            "reuse_existing_valid_trials"
        )
        is True,
        "Existing valid trial reuse is required.",
    )

    require(
        contract.get(
            "duplicate_trial_1_execution_forbidden_if_valid_result_exists"
        )
        is True,
        "Duplicate-solve prohibition missing.",
    )

    require(
        scope.get(
            "authorized_case_count"
        )
        == EXPECTED_CASE_COUNT,
        "Authorized W02 case count drift.",
    )

    require(
        scope.get(
            "additional_doe_cases_authorized"
        )
        is False
        and scope.get(
            "additional_waves_authorized"
        )
        is False
        and scope.get(
            "holdout_access_authorized"
        )
        is False
        and scope.get(
            "dataset_admission_authorized"
        )
        is False
        and scope.get(
            "surrogate_training_authorized"
        )
        is False
        and scope.get(
            "artifact_retirement_authorized"
        )
        is False,
        "W02 authorization scope broadened.",
    )

    return auth


def load_campaign_inputs():
    require(
        sha256(PREP_INDEX_PATH)
        == EXPECTED_PREP_INDEX_SHA256,
        "W02 Trial-1 preparation index drift.",
    )

    prep_index = read_json(
        PREP_INDEX_PATH
    )

    proposal = read_json(
        PROPOSAL_PATH
    )

    policy = tomllib.loads(
        POLICY_PATH.read_text(
            encoding="utf-8-sig"
        )
    )

    rows = prep_index.get(
        "prepared_trials"
    )

    require(
        isinstance(rows, list)
        and len(rows)
        == EXPECTED_CASE_COUNT,
        "W02 must contain exactly four "
        "prepared Trial-1 rows.",
    )

    proposal_rows = {
        row["proposal_id"]: row
        for row in proposal["cases"]
    }

    return (
        rows,
        proposal_rows,
        policy,
    )


TRANSFER = (
    load_complete_joint_calculix_transfer_definition(
        TRANSFER_PATH
    )
)

CONTACT = (
    load_complete_joint_contact_definition(
        CONTACT_PATH
    )
)

BOUNDARY = (
    load_complete_joint_boundary_region_definition(
        BOUNDARY_PATH
    )
)

PRELOAD = (
    load_complete_joint_preload_definition(
        PRELOAD_PATH
    )
)

RESULT_POLICY = (
    load_fem_result_extraction_policy(
        RESULT_POLICY_PATH
    )
)

REFERENCE_TEMPERATURE_C = (
    governed_reference_temperature_c(
        PRELOAD
    )
)

BACKEND = (
    PHASE2_CERTIFIED_FEM_PROFILE.backend
)

CALIBRATION_POLICY = (
    PreloadCalibrationCampaignPolicy(
        maximum_trials=MAXIMUM_TRIALS,
    )
)


def build_case_contexts() -> list[dict]:
    (
        prepared_rows,
        proposal_rows,
        policy,
    ) = load_campaign_inputs()

    contexts = []

    for prepared in prepared_rows:
        case_id = prepared["case_id"]
        case_hash = prepared["case_hash"]
        case_run_id = prepared[
            "case_run_id"
        ]

        proposal_row = (
            proposal_rows.get(
                case_id
            )
        )

        require(
            proposal_row is not None,
            f"{case_id}: frozen proposal row missing.",
        )

        require(
            proposal_row[
                "case_hash"
            ]
            == case_hash,
            f"{case_id}: proposal case-hash drift.",
        )

        size = next(
            (
                row
                for row
                in policy[
                    "size_candidates"
                ]
                if row[
                    "designation"
                ]
                == proposal_row[
                    "thread_designation"
                ]
            ),
            None,
        )

        require(
            size is not None,
            f"{case_id}: size policy missing.",
        )

        case, _ = _build_case(
            policy,
            size,
            proposal_row[
                "member_material_id"
            ],
            tuple(
                proposal_row[
                    "normalized_coordinates"
                ]
            ),
        )

        resolved = resolve_case(
            case,
            material_catalog=(
                DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG
            ),
        )

        require(
            resolved.case_hash
            == case_hash,
            f"{case_id}: resolved case-hash drift.",
        )

        require(
            resolved.resolution_hash
            == case_run_id.replace(
                "trm_fem_",
                "",
                1,
            )
            or (
                resolved
                .source_case
                is not None
            ),
            f"{case_id}: invalid resolved identity.",
        )

        prep_record_path = (
            ROOT
            / prepared[
                "preparation_record"
            ]
        ).resolve()

        preparation = read_json(
            prep_record_path
        )

        trial_raw = preparation.get(
            "trial_1"
        )

        require(
            isinstance(
                trial_raw,
                dict,
            ),
            f"{case_id}: Trial-1 record missing.",
        )

        trial1 = PreloadCalibrationTrial(
            trial_index=int(
                trial_raw[
                    "trial_index"
                ]
            ),
            run_id=str(
                trial_raw[
                    "run_id"
                ]
            ),
            delta_temperature_c=float(
                trial_raw[
                    "delta_temperature_c"
                ]
            ),
            source=(
                PreloadCalibrationTrialSource(
                    trial_raw[
                        "source"
                    ]
                )
            ),
        )

        require(
            trial1.trial_index == 1,
            f"{case_id}: initial trial index drift.",
        )

        require(
            trial1.run_id
            == f"{case_run_id}_cal_01",
            f"{case_id}: initial trial run-id drift.",
        )

        mesh_path = resolve_governed_mesh(
            preparation=preparation,
            case_run_id=case_run_id,
        )

        bundle = (
            build_generic_fem_definition_bundle(
                resolved,
                mesh_id=(
                    f"mesh-{case_hash[:16]}"
                ),
                geometry_id=(
                    f"geometry-{case_hash[:16]}"
                ),
                classification_id=(
                    f"classification-{case_hash[:16]}"
                ),
                source_mesh_name=(
                    mesh_path.name
                ),
                transfer_template=TRANSFER,
                contact_template=CONTACT,
                boundary_template=BOUNDARY,
                material_catalog=(
                    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG
                ),
            )
        )

        require(
            bundle
            .preparation
            .identity
            .run_id
            == case_run_id,
            f"{case_id}: generic FEM bundle "
            "case-run identity drift.",
        )

        mesh_data = (
            read_grouped_complete_joint_mesh(
                mesh_path,
                bundle.transfer,
            )
        )

        contexts.append(
            {
                "case_id": case_id,
                "case_hash": case_hash,
                "case_run_id": (
                    case_run_id
                ),
                "prepared_row": prepared,
                "preparation": preparation,
                "preparation_path": (
                    prep_record_path
                ),
                "resolved": resolved,
                "mesh_path": mesh_path,
                "mesh_sha256": (
                    sha256(mesh_path)
                ),
                "mesh_data": mesh_data,
                "bundle": bundle,
                "trial1": trial1,
            }
        )

    require(
        len(contexts)
        == EXPECTED_CASE_COUNT,
        "Context count drift.",
    )

    require(
        len(
            {
                item["case_hash"]
                for item in contexts
            }
        )
        == EXPECTED_CASE_COUNT,
        "Duplicate W02 case identity.",
    )

    return contexts


def run_dir(
    context: dict,
    run_id: str,
) -> Path:
    return (
        SOLVER_ROOT
        / context[
            "case_run_id"
        ]
        / run_id
    )


def completed_measurement(
    context: dict,
    trial: PreloadCalibrationTrial,
):
    directory = run_dir(
        context,
        trial.run_id,
    )

    manifest_path = (
        directory
        / "fem_run_manifest.json"
    )

    status, manifest = (
        manifest_status(
            manifest_path,
            run_id=trial.run_id,
            case_hash=context[
                "case_hash"
            ],
        )
    )

    if status == "MISSING":
        return None

    require(
        status == "SUCCEEDED",
        (
            f"{trial.run_id}: governed solver "
            "failed; automatic calibration "
            "continuation stops."
        ),
    )

    dat_path = (
        directory
        / f"{trial.run_id}.dat"
    )

    require(
        dat_path.is_file()
        and dat_path.stat().st_size > 0,
        f"{trial.run_id}: DAT missing.",
    )

    before = sha256(
        dat_path
    )

    extraction = (
        extract_clamp_force_measurement_from_dat(
            dat_path=dat_path,
            contact_pairs=(
                CONTACT.contact_pairs
            ),
        )
    )

    require(
        sha256(dat_path)
        == before,
        f"{trial.run_id}: DAT changed "
        "during governed extraction.",
    )

    return {
        "directory": directory,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "dat_path": dat_path,
        "dat_sha256": before,
        "extraction": extraction,
        "measurement": (
            extraction.measurement
        ),
    }


def recover_calibration_state(
    context: dict,
) -> dict:
    current = context[
        "trial1"
    ]

    previous_trial = None
    previous_measurement = None
    history = []

    while True:
        completed = (
            completed_measurement(
                context,
                current,
            )
        )

        if completed is None:
            return {
                "status": (
                    "NEEDS_SOLVE"
                ),
                "current_trial": current,
                "previous_trial": (
                    previous_trial
                ),
                "previous_measurement": (
                    previous_measurement
                ),
                "history": history,
            }

        measurement = (
            completed[
                "measurement"
            ]
        )

        evaluation = (
            evaluate_preload_calibration_trial(
                case_run_id=(
                    context[
                        "case_run_id"
                    ]
                ),
                target_force_n=float(
                    context[
                        "resolved"
                    ]
                    .source_case
                    .loading
                    .target_preload_n
                ),
                target_relative_tolerance=(
                    PRELOAD
                    .target_relative_tolerance
                ),
                spread_relative_tolerance=(
                    PRELOAD
                    .interface_spread_relative_tolerance
                ),
                current_trial=current,
                measurement=measurement,
                previous_trial=(
                    previous_trial
                ),
                previous_measurement=(
                    previous_measurement
                ),
                policy=(
                    CALIBRATION_POLICY
                ),
            )
        )

        history.append(
            {
                "trial": current,
                "completed": completed,
                "evaluation": evaluation,
            }
        )

        disposition = enum_value(
            evaluation
            .decision
            .disposition
        )

        print(
            f"{context['case_id']} | "
            f"{current.run_id} | "
            f"mean={measurement.mean_force_n:.6f} N | "
            f"target_error="
            f"{100.0 * evaluation.decision.target_relative_error:+.6f}% | "
            f"spread="
            f"{100.0 * measurement.spread_relative:.6f}% | "
            f"{str(disposition).upper()}",
            flush=True,
        )

        if evaluation.accepted:
            require(
                evaluation.next_trial
                is None,
                f"{current.run_id}: ACCEPT "
                "unexpectedly produced continuation.",
            )

            return {
                "status": (
                    "CALIBRATION_ACCEPTED"
                ),
                "accepted_trial": current,
                "accepted_completed": (
                    completed
                ),
                "accepted_evaluation": (
                    evaluation
                ),
                "history": history,
            }

        if (
            str(disposition)
            != "continue"
        ):
            return {
                "status": (
                    "TERMINAL_CALIBRATION"
                ),
                "current_trial": current,
                "evaluation": evaluation,
                "history": history,
                "reason": str(
                    disposition
                ),
            }

        next_trial = (
            evaluation.next_trial
        )

        require(
            next_trial is not None,
            f"{current.run_id}: CONTINUE "
            "without next governed trial.",
        )

        require(
            next_trial.trial_index
            == current.trial_index + 1,
            "Calibration trial sequence drift.",
        )

        if (
            next_trial.trial_index
            > MAXIMUM_TRIALS
        ):
            return {
                "status": (
                    "TERMINAL_TRIAL_LIMIT"
                ),
                "current_trial": current,
                "evaluation": evaluation,
                "history": history,
                "reason": (
                    "maximum governed "
                    "trial count reached"
                ),
            }

        previous_trial = current
        previous_measurement = measurement
        current = next_trial


def preparation_record_path(
    context: dict,
    trial: PreloadCalibrationTrial,
) -> Path:
    return (
        run_dir(
            context,
            trial.run_id,
        )
        / "w02_adaptive_preparation.json"
    )


def prepare_governed_trial(
    context: dict,
    state: dict,
) -> tuple[
    Path,
    Path,
]:
    trial = state[
        "current_trial"
    ]

    require(
        trial.trial_index >= 2,
        (
            "Existing CAL_01 must be reused; "
            "adaptive preparation may not "
            "regenerate Trial 1."
        ),
    )

    directory = run_dir(
        context,
        trial.run_id,
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path = (
        directory
        / "fem_run_manifest.json"
    )

    require(
        not manifest_path.exists(),
        (
            f"{trial.run_id}: refusing "
            "to prepare over an existing "
            "solver manifest."
        ),
    )

    for suffix in (
        ".dat",
        ".frd",
        ".sta",
        ".cvg",
        ".rout",
        ".stdout.log",
        ".stderr.log",
    ):
        require(
            not (
                directory
                / f"{trial.run_id}{suffix}"
            ).exists(),
            (
                f"{trial.run_id}: duplicate "
                f"solver artifact exists: {suffix}"
            ),
        )

    candidate = (
        directory.parent
        / (
            "."
            + trial.run_id
            + ".adaptive_candidate.inp"
        )
    )

    if candidate.exists():
        candidate.unlink()

    deck = (
        write_fem_preload_calibration_trial_deck(
            mesh_data=(
                context[
                    "mesh_data"
                ]
            ),
            bundle=(
                context[
                    "bundle"
                ]
            ),
            trial=trial,
            reference_temperature_c=(
                REFERENCE_TEMPERATURE_C
            ),
            input_path=candidate,
        )
    )

    require(
        candidate.is_file()
        and candidate.stat().st_size > 0,
        f"{trial.run_id}: candidate deck missing.",
    )

    candidate_sha = sha256(
        candidate
    )

    require(
        candidate_sha
        == deck.sha256,
        f"{trial.run_id}: generated deck "
        "SHA mismatch.",
    )

    deck_path = (
        directory
        / f"{trial.run_id}.inp"
    )

    if deck_path.exists():
        require(
            sha256(deck_path)
            == candidate_sha,
            (
                f"{trial.run_id}: existing "
                "adaptive deck differs from "
                "deterministic regeneration."
            ),
        )

        candidate.unlink()

    else:
        candidate.replace(
            deck_path
        )

    predecessor = (
        state["history"][-1]
        if state["history"]
        else None
    )

    require(
        predecessor is not None,
        (
            f"{trial.run_id}: adaptive trial "
            "has no completed predecessor."
        ),
    )

    prep_payload = {
        "schema": (
            "threadrom.phase3_diversified_"
            "w02_adaptive_preparation.v1"
        ),
        "record_status": "FINAL",
        "campaign_id": (
            "TRM-DDOE-001"
        ),
        "wave_id": (
            "TRM-DDOE-001-W02"
        ),
        "case_id": (
            context["case_id"]
        ),
        "case_hash": (
            context["case_hash"]
        ),
        "case_run_id": (
            context["case_run_id"]
        ),
        "trial": jsonable(
            trial
        ),
        "predecessor": {
            "trial": jsonable(
                predecessor[
                    "trial"
                ]
            ),
            "dat_relative_path": (
                relative(
                    predecessor[
                        "completed"
                    ][
                        "dat_path"
                    ]
                )
            ),
            "dat_sha256": (
                predecessor[
                    "completed"
                ][
                    "dat_sha256"
                ]
            ),
            "measurement": jsonable(
                predecessor[
                    "completed"
                ][
                    "measurement"
                ]
            ),
            "evaluation": jsonable(
                predecessor[
                    "evaluation"
                ]
            ),
        },
        "mesh": {
            "relative_path": relative(
                context[
                    "mesh_path"
                ]
            ),
            "sha256": (
                context[
                    "mesh_sha256"
                ]
            ),
        },
        "deck": {
            "relative_path": (
                relative(deck_path)
            ),
            "sha256": (
                sha256(deck_path)
            ),
            "size_bytes": (
                deck_path.stat().st_size
            ),
            "delta_temperature_c": (
                trial
                .delta_temperature_c
            ),
        },
        "authorization": {
            "owner_authorization_relative_path": (
                relative(
                    AUTH_PATH
                )
            ),
            "owner_authorization_sha256": (
                EXPECTED_AUTH_SHA256
            ),
            "automatic_governed_adaptation": True,
            "maximum_trial_index": (
                MAXIMUM_TRIALS
            ),
            "maximum_concurrent_calculix": (
                MAXIMUM_CONCURRENT_CCX
            ),
        },
        "scope": {
            "additional_cases_authorized": False,
            "additional_waves_authorized": False,
            "holdout_access_authorized": False,
            "dataset_admission_authorized": False,
            "artifact_retirement_authorized": False,
        },
        "overall_disposition": (
            "W02_ADAPTIVE_TRIAL_PREPARATION_PASS"
        ),
    }

    prep_path = (
        preparation_record_path(
            context,
            trial,
        )
    )

    prep_sha = (
        write_immutable_json(
            prep_path,
            prep_payload,
        )
    )

    print(
        f"PREPARED {trial.run_id} | "
        f"Delta-T={trial.delta_temperature_c:.12f} C | "
        f"deck={sha256(deck_path)} | "
        f"prep={prep_sha}",
        flush=True,
    )

    return (
        deck_path,
        prep_path,
    )


def register_prepared_trial(
    registry: FemFactoryRegistry,
    context: dict,
    trial: PreloadCalibrationTrial,
    prep_path: Path,
):
    record = registry.register_job(
        case_id=context[
            "case_id"
        ],
        case_hash=context[
            "case_hash"
        ],
        trial_index=(
            trial.trial_index
        ),
        run_id=(
            trial.run_id
        ),
        priority=(
            FemFactoryPriority.TRIAL2
        ),
    )

    if (
        record.state
        is FemFactoryJobState.PLANNED
    ):
        record = (
            registry.transition_job(
                case_hash=context[
                    "case_hash"
                ],
                trial_index=(
                    trial
                    .trial_index
                ),
                new_state=(
                    FemFactoryJobState.PREPARED
                ),
                preparation_record=(
                    relative(
                        prep_path
                    )
                ),
            )
        )

    require(
        record.state
        in {
            FemFactoryJobState.PREPARED,
            FemFactoryJobState.SOLVED,
            FemFactoryJobState.ACCEPTED,
        },
        (
            f"{trial.run_id}: unexpected "
            f"registry state "
            f"{record.state.value}."
        ),
    )

    return record


def build_execution_spec(
    context: dict,
    trial: PreloadCalibrationTrial,
    deck_path: Path,
):
    job = CalculixJobDefinition(
        executable_relative_path=(
            TRANSFER
            .executable_relative_path
        ),
        job_name=trial.run_id,
        timeout_seconds=None,
    )

    return GovernedCalculixExecutionSpec(
        project_root=ROOT,
        input_path=deck_path,
        definition=job,
        backend_policy_id=(
            BACKEND.policy_id
        ),
        solver_name=(
            BACKEND.solver_name
        ),
        solver_version=(
            BACKEND.solver_version
        ),
        manifest_path=(
            run_dir(
                context,
                trial.run_id,
            )
            / "fem_run_manifest.json"
        ),
    )


def run_one_factory_worker(
    *,
    registry: FemFactoryRegistry,
    worker_number: int,
    specs: Mapping[
        str,
        GovernedCalculixExecutionSpec,
    ],
):
    worker_id = (
        "TRM-DDOE-W02-adaptive-"
        f"worker-{worker_number:02d}"
    )

    admission = (
        claim_parallel_factory_slot(
            registry=registry,
            lock_path=ADMISSION_LOCK,
            worker_id=worker_id,
            lease_seconds=LEASE_SECONDS,
            maximum_authorized_ccx=(
                MAXIMUM_CONCURRENT_CCX
            ),
        )
    )

    if admission.claim is None:
        return {
            "worker": worker_id,
            "reason": admission.reason,
            "run_id": None,
        }

    claim = admission.claim

    require(
        claim.run_id in specs,
        (
            "Factory claimed a PREPARED job "
            "outside the current autonomous "
            "W02 execution set: "
            f"{claim.run_id}"
        ),
    )

    spec = specs[
        claim.run_id
    ]

    print(
        f"SOLVER START : {claim.run_id} | "
        f"{worker_id}",
        flush=True,
    )

    record = (
        execute_claimed_factory_job(
            registry=registry,
            claim=claim,
            lease_seconds=(
                LEASE_SECONDS
            ),
            heartbeat_interval_seconds=(
                HEARTBEAT_SECONDS
            ),
            execute=(
                make_claimed_calculix_executor(
                    spec
                )
            ),
        )
    )

    print(
        f"SOLVER END   : {claim.run_id} | "
        f"{record.state.value.upper()}",
        flush=True,
    )

    return {
        "worker": worker_id,
        "reason": "EXECUTED",
        "run_id": claim.run_id,
        "state": record.state.value,
    }


def execute_prepared_batch(
    *,
    registry: FemFactoryRegistry,
    specs: Mapping[
        str,
        GovernedCalculixExecutionSpec,
    ],
) -> None:
    if not specs:
        return

    outstanding = set(
        specs
    )

    while outstanding:
        for run_id in tuple(
            outstanding
        ):
            record = next(
                (
                    job
                    for job
                    in registry.list_jobs()
                    if job.run_id
                    == run_id
                ),
                None,
            )

            require(
                record is not None,
                f"{run_id}: registry job vanished.",
            )

            if (
                record.state
                is FemFactoryJobState.SOLVED
            ):
                outstanding.remove(
                    run_id
                )

            elif (
                record.state
                in {
                    FemFactoryJobState.FAILED,
                    FemFactoryJobState.QUARANTINED,
                    FemFactoryJobState.REJECTED,
                }
            ):
                raise RuntimeError(
                    f"{run_id}: factory reached "
                    f"terminal state "
                    f"{record.state.value}."
                )

            elif (
                record.state
                is FemFactoryJobState.ACCEPTED
            ):
                outstanding.remove(
                    run_id
                )

        if not outstanding:
            break

        prepared = [
            job
            for job in registry.list_jobs(
                state=(
                    FemFactoryJobState.PREPARED
                )
            )
            if job.run_id
            in outstanding
        ]

        if not prepared:
            running = [
                job
                for job in registry.list_jobs(
                    state=(
                        FemFactoryJobState.RUNNING
                    )
                )
                if job.run_id
                in outstanding
            ]

            require(
                running,
                (
                    "Outstanding adaptive jobs are "
                    "neither PREPARED nor RUNNING."
                ),
            )

            print(
                "WAIT: adaptive jobs already RUNNING.",
                flush=True,
            )

            time.sleep(30.0)
            continue

        worker_count = min(
            MAXIMUM_CONCURRENT_CCX,
            len(prepared),
        )

        with (
            concurrent.futures
            .ThreadPoolExecutor(
                max_workers=worker_count
            )
        ) as pool:
            futures = [
                pool.submit(
                    run_one_factory_worker,
                    registry=registry,
                    worker_number=index,
                    specs=specs,
                )
                for index
                in range(
                    1,
                    worker_count + 1,
                )
            ]

            results = [
                future.result()
                for future in futures
            ]

        executed = [
            item
            for item in results
            if item[
                "reason"
            ]
            == "EXECUTED"
        ]

        if not executed:
            print(
                "WAIT: no adaptive launch slot "
                "currently available.",
                flush=True,
            )

            time.sleep(30.0)


def physics_assessment_path(
    context: dict,
    trial: PreloadCalibrationTrial,
) -> Path:
    return (
        run_dir(
            context,
            trial.run_id,
        )
        / "w02_governed_full_physics_assessment_v2.json"
    )


def assess_full_physics(
    *,
    registry: FemFactoryRegistry,
    context: dict,
    calibration_state: dict,
) -> Path:
    trial = (
        calibration_state[
            "accepted_trial"
        ]
    )

    completed = (
        calibration_state[
            "accepted_completed"
        ]
    )

    evaluation = (
        calibration_state[
            "accepted_evaluation"
        ]
    )

    require(
        evaluation.accepted,
        (
            f"{trial.run_id}: full physics "
            "requested without calibration ACCEPT."
        ),
    )

    directory = (
        completed[
            "directory"
        ]
    )

    sta_path = (
        directory
        / f"{trial.run_id}.sta"
    )

    cvg_path = (
        directory
        / f"{trial.run_id}.cvg"
    )

    dat_path = (
        directory
        / f"{trial.run_id}.dat"
    )

    frd_path = (
        directory
        / f"{trial.run_id}.frd"
    )

    stdout_path = (
        directory
        / f"{trial.run_id}.stdout.log"
    )

    manifest_path = (
        directory
        / "fem_run_manifest.json"
    )

    for path in (
        sta_path,
        cvg_path,
        dat_path,
        frd_path,
        stdout_path,
        manifest_path,
    ):
        require(
            path.is_file()
            and path.stat().st_size >= 0,
            f"{trial.run_id}: physics "
            f"artifact missing: {path.name}",
        )

    progress_path = (
        directory
        / "w02_nonlinear_progress.json"
    )

    total_force_path = (
        directory
        / "w02_external_translational_total_force.json"
    )

    equilibrium_path = (
        directory
        / "w02_external_translational_equilibrium.json"
    )

    write_nonlinear_progress_json(
        sta_path,
        cvg_path,
        progress_path,
    )

    support_set_name = (
        context[
            "bundle"
        ]
        .boundary
        .region(
            HEAD_SUPPORT
        )
        .name
    )

    translational_reaction_set_names = (
        support_set_name,
        BOLT_HEAD_GUIDANCE_REFERENCE,
        NUT_TRANSLATION_GUIDANCE_REFERENCE,
        NUT_MEMBER_GUIDANCE_REFERENCE,
    )

    write_total_force_json(
        dat_path,
        total_force_path,
        set_names=(
            translational_reaction_set_names
        ),
    )

    equilibrium = (
        write_external_equilibrium_resultant_json(
            progress_path,
            total_force_path,
            equilibrium_path,
            support_set_names=(
                translational_reaction_set_names
            ),
        )
    )

    require(
        equilibrium.get(
            "overall_status"
        )
        == "pass",
        (
            f"{trial.run_id}: external "
            "support equilibrium FAILED."
        ),
    )

    evidence = (
        extract_fem_physics_result_evidence(
            mesh_data=(
                context[
                    "mesh_data"
                ]
            ),
            policy=(
                RESULT_POLICY
            ),
            frd_path=(
                frd_path
            ),
            sta_path=(
                sta_path
            ),
            dat_path=(
                dat_path
            ),
            stdout_path=(
                stdout_path
            ),
            manifest_path=(
                manifest_path
            ),
            contact_pairs=tuple(
                CONTACT.contact_pairs
            ),
            thermal_expansion_coefficient_per_c=(
                context[
                    "bundle"
                ]
                .preparation
                .physics
                .bolt_thermal_expansion_per_c
            ),
            equivalent_delta_temperature_c=(
                trial
                .delta_temperature_c
            ),
        )
    )

    physics_policy = (
        derive_complete_joint_physics_acceptance_policy(
            context[
                "resolved"
            ].assembly
        )
    )

    require(
        getattr(
            physics_policy,
            "require_external_support_equilibrium",
            False,
        )
        is True,
        (
            "Current governed physics policy "
            "does not require external support "
            "equilibrium."
        ),
    )

    acceptance = (
        evaluate_fem_physics_acceptance(
            policy=physics_policy,
            preload_decision=(
                evaluation
                .decision
            ),
            thread_normal_force_n=(
                evidence
                .thread_normal_force_n
            ),
            axial_state=(
                evidence
                .axial_state
            ),
            deformation_state=(
                evidence
                .deformation_state
            ),
            thread_flank_state=(
                evidence
                .thread_flank_state
            ),
            accepted_increments=(
                evidence
                .accepted_increments
            ),
            external_equilibrium_payload=(
                equilibrium
            ),
            return_code=(
                evidence
                .return_code
            ),
            stdout=(
                evidence
                .stdout
            ),
            require_process_return_code=True,
        )
    )

    hard_gates = [
        check
        for check
        in acceptance.checks
        if enum_value(
            check.kind
        )
        == "hard_gate"
    ]

    failed_hard_gates = [
        check.name
        for check
        in hard_gates
        if not check.passed
    ]

    disposition = str(
        enum_value(
            acceptance.disposition
        )
    )

    print()
    print(
        "=" * 118,
        flush=True,
    )

    print(
        f"FULL PHYSICS — {context['case_id']}",
        flush=True,
    )

    print(
        "=" * 118,
        flush=True,
    )

    for check in acceptance.checks:
        print(
            (
                "PASS"
                if check.passed
                else "FAIL"
            ),
            "|",
            enum_value(
                check.kind
            ),
            "|",
            check.name,
            flush=True,
        )

    require(
        disposition == "pass"
        and not failed_hard_gates,
        (
            f"{trial.run_id}: governed full "
            "physics FAILED: "
            + ", ".join(
                failed_hard_gates
            )
        ),
    )

    assessment = {
        "schema": (
            "threadrom.phase3_diversified_"
            "w02_full_physics_assessment.v2"
        ),
        "record_status": "FINAL",
        "overall_disposition": (
            "GOVERNED_FULL_PHYSICS_ACCEPTED"
        ),
        "case_id": (
            context[
                "case_id"
            ]
        ),
        "case_hash": (
            context[
                "case_hash"
            ]
        ),
        "case_run_id": (
            context[
                "case_run_id"
            ]
        ),
        "run_id": (
            trial.run_id
        ),
        "trial_index": (
            trial.trial_index
        ),
        "accepted_delta_temperature_c": (
            trial
            .delta_temperature_c
        ),

        # ----------------------------------------------------------
        # Canonical diversified-physics certificate contract.
        # These are derived from the governed controller result;
        # they are not independently asserted aliases.
        # ----------------------------------------------------------

        "calibration_disposition": str(
            enum_value(
                evaluation
                .decision
                .disposition
            )
        ),

        "next_trial_run_id": (
            evaluation.next_trial.run_id
            if evaluation.next_trial
            is not None
            else None
        ),

        "calibration_target_force_n": float(
            evaluation
            .decision
            .target_force_n
        ),

        "calibration_mean_force_n": float(
            evaluation
            .decision
            .measurement
            .mean_force_n
        ),

        "calibration_target_error_percent": (
            float(
                evaluation
                .decision
                .target_relative_error
            )
            * 100.0
        ),

        "calibration_spread_percent": (
            float(
                evaluation
                .decision
                .measurement
                .spread_relative
            )
            * 100.0
        ),

        "result_policy_id": str(
            RESULT_POLICY.policy_id
        ),

        "physics_policy_id": str(
            physics_policy.policy_id
        ),

        # Preserve W02-local compatibility aliases.
        "calibration_decision": "accept",
        "calibration_accepted": True,
        "calibration": jsonable(
            evaluation
        ),
        "preload_measurement": jsonable(
            completed[
                "measurement"
            ]
        ),
        "target_preload_n": float(
            context[
                "resolved"
            ]
            .source_case
            .loading
            .target_preload_n
        ),
        "external_equilibrium_status": (
            equilibrium[
                "overall_status"
            ]
        ),
        "equilibrium_status": (
            equilibrium[
                "overall_status"
            ]
        ),

        "maximum_translational_resultant_n": (
            max(
                float(
                    item[
                        "maximum_absolute_component_n"
                    ]
                )
                for item
                in equilibrium[
                    "validations"
                ]
            )
        ),

        "translational_force_tolerance_n": (
            float(
                equilibrium[
                    "tolerances"
                ][
                    "force_absolute_n"
                ]
            )
        ),

        "external_support_equilibrium": (
            jsonable(
                equilibrium
            )
        ),
        "physics_disposition": (
            disposition
        ),
        "physics_gates": "pass",
        "physics_acceptance": jsonable(
            acceptance
        ),
        "physics_acceptance_policy": (
            jsonable(
                physics_policy
            )
        ),
        "physics_result_evidence": (
            jsonable(
                evidence
            )
        ),

        "accepted_increment_count": (
            len(
                evidence
                .accepted_increments
            )
        ),

        "thread_normal_force_n": float(
            evidence
            .thread_normal_force_n
        ),

        "physics_checks": [
            {
                "name": check.name,
                "kind": str(
                    enum_value(
                        check.kind
                    )
                ),
                "passed": bool(
                    check.passed
                ),
            }
            for check
            in acceptance.checks
        ],

        "full_physics_passed": True,

        "hard_gate_count": (
            len(hard_gates)
        ),
        "hard_gates_passed": (
            sum(
                1
                for check
                in hard_gates
                if check.passed
            )
        ),
        "failed_governed_checks": (
            failed_hard_gates
        ),
        "all_hard_gates_passed": True,
        "full_physics_accepted": True,
        "rotational_moment_equilibrium_status": (
            "not_assessed"
        ),
        "derived_artifacts": {
            "nonlinear_progress": (
                relative(
                    progress_path
                )
            ),
            "external_support_total_force": (
                relative(
                    total_force_path
                )
            ),
            "external_support_equilibrium": (
                relative(
                    equilibrium_path
                )
            ),
        },
        "governance": {
            "owner_authorization_sha256": (
                EXPECTED_AUTH_SHA256
            ),
            "new_fem_authorized_by_assessment": False,
            "additional_wave_authorized": False,
            "dataset_admission_authorized": False,
            "holdout_accessed": False,
            "artifact_retirement_authorized": False,
            "independent_human_review": False,
        },
    }

    assessment_path = (
        physics_assessment_path(
            context,
            trial,
        )
    )

    assessment_sha = (
        write_immutable_json(
            assessment_path,
            assessment,
        )
    )

    print(
        f"PHYSICS ASSESSMENT PASS | "
        f"{trial.run_id} | "
        f"{len(hard_gates)}/"
        f"{len(hard_gates)} hard gates | "
        f"SHA={assessment_sha}",
        flush=True,
    )

    source_default = (
        inspect.signature(
            persist_governed_physics_certificate
        )
        .parameters[
            "source_paths"
        ]
        .default
    )

    source_paths = tuple(
        source_default
    )

    if (
        SCRIPT_RELATIVE_PATH
        not in source_paths
    ):
        source_paths = (
            source_paths
            + (
                SCRIPT_RELATIVE_PATH,
            )
        )

    certificate_path = (
        persist_governed_physics_certificate(
            repo_root=ROOT,
            run_dir=directory,
            case_id=(
                context[
                    "case_id"
                ]
            ),
            case_hash=(
                context[
                    "case_hash"
                ]
            ),
            case_run_id=(
                context[
                    "case_run_id"
                ]
            ),
            run_id=(
                trial.run_id
            ),
            trial_index=(
                trial.trial_index
            ),
            assessment=assessment,
            source_paths=(
                source_paths
            ),
        )
    )

    recovered = (
        recover_governed_physics_certificate(
            repo_root=ROOT,
            run_dir=directory,
            case_id=(
                context[
                    "case_id"
                ]
            ),
            case_hash=(
                context[
                    "case_hash"
                ]
            ),
            case_run_id=(
                context[
                    "case_run_id"
                ]
            ),
            run_id=(
                trial.run_id
            ),
            trial_index=(
                trial.trial_index
            ),
            source_paths=(
                source_paths
            ),
        )
    )

    require(
        recovered is not None,
        (
            f"{trial.run_id}: persisted "
            "physics certificate could not "
            "be recovered."
        ),
    )

    certificate = read_json(
        certificate_path
    )

    cert_disposition = str(
        certificate.get(
            "disposition",
            certificate.get(
                "overall_disposition",
                "",
            ),
        )
    )

    require(
        (
            "ACCEPT"
            in cert_disposition.upper()
            or "CERTIF"
            in cert_disposition.upper()
        ),
        (
            f"{trial.run_id}: recovered "
            "certificate does not assert "
            "governed acceptance."
        ),
    )

    job = registry.get_job(
        case_hash=context[
            "case_hash"
        ],
        trial_index=(
            trial.trial_index
        ),
    )

    require(
        job is not None,
        f"{trial.run_id}: registry job missing.",
    )

    if (
        job.state
        is FemFactoryJobState.SOLVED
    ):
        registry.transition_job(
            case_hash=context[
                "case_hash"
            ],
            trial_index=(
                trial.trial_index
            ),
            new_state=(
                FemFactoryJobState.ACCEPTED
            ),
            acceptance_record=(
                relative(
                    certificate_path
                )
            ),
        )

    elif (
        job.state
        is not FemFactoryJobState.ACCEPTED
    ):
        raise RuntimeError(
            f"{trial.run_id}: cannot mark "
            "physics acceptance from registry "
            f"state {job.state.value}."
        )

    print(
        f"🔥 PHYSICS ACCEPTED : "
        f"{context['case_id']} | "
        f"{trial.run_id} | "
        f"certificate={sha256(certificate_path)}",
        flush=True,
    )

    return certificate_path


def preflight(
    contexts: list[dict],
) -> int:
    print()
    print(
        "=" * 118
    )
    print(
        "THREADROM — W02 AUTONOMOUS "
        "ADAPTIVE FACTORY PREFLIGHT"
    )
    print(
        "=" * 118
    )

    print(
        "Existing CAL_01 reruns : FORBIDDEN"
    )
    print(
        "Automatic CAL_n        : ENABLED"
    )
    print(
        "Full physics acceptance: ENABLED"
    )
    print(
        "Max trials / case      : 6"
    )
    print(
        "Max concurrent ccx     : 4"
    )
    print(
        "Holdouts               : SEALED"
    )
    print(
        "Dataset admission      : BLOCKED"
    )
    print()

    accepted = 0
    continue_count = 0

    for context in contexts:
        state = (
            recover_calibration_state(
                context
            )
        )

        status = state[
            "status"
        ]

        if (
            status
            == "CALIBRATION_ACCEPTED"
        ):
            accepted += 1

            trial = state[
                "accepted_trial"
            ]

            print(
                f"{context['case_id']} => "
                f"CALIBRATION ACCEPTED at "
                f"{trial.run_id}; "
                "full physics will run.",
            )

        elif (
            status
            == "NEEDS_SOLVE"
        ):
            continue_count += 1

            trial = state[
                "current_trial"
            ]

            require(
                trial.trial_index >= 2,
                (
                    "PRECHECK REFUSES CAL_01 "
                    "RERUN."
                ),
            )

            print(
                f"{context['case_id']} => "
                f"NEXT {trial.run_id} | "
                f"Delta-T "
                f"{trial.delta_temperature_c:.12f} C"
            )

        else:
            raise RuntimeError(
                f"{context['case_id']}: "
                f"terminal preflight state "
                f"{status}: "
                f"{state.get('reason')}"
            )

    print()
    print(
        f"Calibration already accepted : "
        f"{accepted}"
    )
    print(
        f"Need adaptive continuation   : "
        f"{continue_count}"
    )

    print()
    print(
        "PREFLIGHT PASS — ZERO FEM LAUNCHED"
    )

    return 0


def execute(
    contexts: list[dict],
) -> int:
    FACTORY_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    registry = FemFactoryRegistry(
        FACTORY_DB
    )

    registry.initialize()

    print()
    print(
        "=" * 118,
        flush=True,
    )

    print(
        "THREADROM — W02 AUTONOMOUS "
        "ADAPTIVE FACTORY",
        flush=True,
    )

    print(
        "=" * 118,
        flush=True,
    )

    print(
        "Human starts campaign : ONCE",
        flush=True,
    )

    print(
        "CAL_02+ decisions      : AUTOMATIC",
        flush=True,
    )

    print(
        "Physics assessment     : AUTOMATIC",
        flush=True,
    )

    print(
        "Stop condition         : "
        "PHYSICS ACCEPTED or TERMINAL",
        flush=True,
    )

    print(
        "Existing CAL_01 reruns : FORBIDDEN",
        flush=True,
    )

    print(
        "Holdouts               : SEALED",
        flush=True,
    )

    print(
        "Dataset admission      : BLOCKED",
        flush=True,
    )

    cycle = 0

    while True:
        cycle += 1

        require(
            cycle <= 12,
            (
                "Adaptive supervisor exceeded "
                "bounded campaign-cycle guard."
            ),
        )

        print()
        print(
            "=" * 118,
            flush=True,
        )

        print(
            f"ADAPTIVE CAMPAIGN CYCLE {cycle}",
            flush=True,
        )

        print(
            "=" * 118,
            flush=True,
        )

        accepted_contexts = []
        solve_requests = []
        terminal = []

        for context in contexts:
            state = (
                recover_calibration_state(
                    context
                )
            )

            status = state[
                "status"
            ]

            if (
                status
                == "CALIBRATION_ACCEPTED"
            ):
                accepted_contexts.append(
                    (
                        context,
                        state,
                    )
                )

            elif (
                status
                == "NEEDS_SOLVE"
            ):
                trial = state[
                    "current_trial"
                ]

                require(
                    trial.trial_index >= 2,
                    (
                        f"{context['case_id']}: "
                        "adaptive factory refuses "
                        "to rerun CAL_01."
                    ),
                )

                solve_requests.append(
                    (
                        context,
                        state,
                    )
                )

            else:
                terminal.append(
                    (
                        context,
                        state,
                    )
                )

        if terminal:
            details = "; ".join(
                (
                    f"{context['case_id']}:"
                    f"{state['status']}:"
                    f"{state.get('reason')}"
                )
                for context, state
                in terminal
            )

            raise RuntimeError(
                "GOVERNED TERMINAL CONDITION: "
                + details
            )

        # --------------------------------------------------
        # Physics-certify anything already calibration-accepted.
        # --------------------------------------------------

        for (
            context,
            state,
        ) in accepted_contexts:
            trial = state[
                "accepted_trial"
            ]

            job = registry.get_job(
                case_hash=context[
                    "case_hash"
                ],
                trial_index=(
                    trial
                    .trial_index
                ),
            )

            require(
                job is not None,
                (
                    f"{trial.run_id}: accepted "
                    "calibration trial absent "
                    "from factory registry."
                ),
            )

            if (
                job.state
                is FemFactoryJobState.ACCEPTED
            ):
                print(
                    f"RECOVERED PHYSICS ACCEPTED : "
                    f"{context['case_id']} | "
                    f"{trial.run_id}",
                    flush=True,
                )

                continue

            assess_full_physics(
                registry=registry,
                context=context,
                calibration_state=state,
            )

        # Recheck global completion after physics.
        all_accepted = True

        for context in contexts:
            state = (
                recover_calibration_state(
                    context
                )
            )

            if (
                state["status"]
                != "CALIBRATION_ACCEPTED"
            ):
                all_accepted = False
                break

            trial = state[
                "accepted_trial"
            ]

            job = registry.get_job(
                case_hash=context[
                    "case_hash"
                ],
                trial_index=(
                    trial
                    .trial_index
                ),
            )

            if (
                job is None
                or job.state
                is not FemFactoryJobState.ACCEPTED
            ):
                all_accepted = False
                break

        if all_accepted:
            print()
            print(
                "=" * 118,
                flush=True,
            )

            print(
                "🔥 TRM-DDOE-001-W02 — "
                "ALL FOUR CASES GOVERNED "
                "FULL-PHYSICS ACCEPTED 🔥",
                flush=True,
            )

            print(
                "=" * 118,
                flush=True,
            )

            print(
                "Duplicate CAL_01 reruns : 0",
                flush=True,
            )

            print(
                "Holdouts accessed       : 0",
                flush=True,
            )

            print(
                "Dataset admission       : NO",
                flush=True,
            )

            return 0

        # --------------------------------------------------
        # Prepare first unsolved governed trial for every
        # incomplete case.
        # --------------------------------------------------

        specs: dict[
            str,
            GovernedCalculixExecutionSpec,
        ] = {}

        for (
            context,
            state,
        ) in solve_requests:
            trial = state[
                "current_trial"
            ]

            directory = run_dir(
                context,
                trial.run_id,
            )

            manifest = (
                directory
                / "fem_run_manifest.json"
            )

            status, _ = (
                manifest_status(
                    manifest,
                    run_id=(
                        trial.run_id
                    ),
                    case_hash=(
                        context[
                            "case_hash"
                        ]
                    ),
                )
            )

            require(
                status == "MISSING",
                (
                    f"{trial.run_id}: solve request "
                    "would duplicate existing "
                    "manifest evidence."
                ),
            )

            deck_path, prep_path = (
                prepare_governed_trial(
                    context,
                    state,
                )
            )

            record = (
                register_prepared_trial(
                    registry,
                    context,
                    trial,
                    prep_path,
                )
            )

            if (
                record.state
                is FemFactoryJobState.PREPARED
            ):
                specs[
                    trial.run_id
                ] = (
                    build_execution_spec(
                        context,
                        trial,
                        deck_path,
                    )
                )

        if not specs:
            # This can occur if a previous process solved the work
            # after the recovery snapshot. Re-enter recovery rather
            # than creating duplicate solver work.
            print(
                "No fresh launches required; "
                "re-entering governed recovery.",
                flush=True,
            )

            continue

        print()
        print(
            f"LAUNCHING {len(specs)} "
            "GOVERNED ADAPTIVE TRIAL(S)",
            flush=True,
        )

        for run_id, spec in specs.items():
            print(
                f"  {run_id} | "
                f"{relative(spec.input_path)}",
                flush=True,
            )

        execute_prepared_batch(
            registry=registry,
            specs=specs,
        )

        # Loop immediately. Newly completed trials are recovered,
        # measured and either accepted or automatically continued.


def parse_args():
    parser = argparse.ArgumentParser()

    mode = parser.add_mutually_exclusive_group(
        required=True
    )

    mode.add_argument(
        "--preflight",
        action="store_true",
    )

    mode.add_argument(
        "--execute",
        action="store_true",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    verify_owner_authorization()

    contexts = (
        build_case_contexts()
    )

    if args.preflight:
        return preflight(
            contexts
        )

    return execute(
        contexts
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

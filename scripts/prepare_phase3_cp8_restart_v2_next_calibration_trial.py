from __future__ import annotations

import argparse
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
from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
    evaluate_preload_calibration_trial,
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

DOE_POLICY_PATH = CONFIG / "phase3_production_doe.toml"

CAMPAIGN_MANIFEST_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_campaign_manifest.json"
)

PREPARATION_CERT_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_preparation_certification_record.json"
)

WARM_KNOWLEDGE_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_warm_start_knowledge_record.json"
)

SOLVER_ROOT = (
    CAMPAIGN_ROOT
    / "solver_preparation"
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

EXPECTED_WARM_KNOWLEDGE_SHA256 = (
    "21e525db65d36a13ca6e2ee96514307f6"
    "234b2518bd60423f872f6dfa6fae8f7"
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate authoritative restart-v2 Production DOE "
            "Trial-1 results and prepare the next local "
            "governed calibration trial. Never launches CalculiX."
        )
    )

    parser.add_argument(
        "--case-id",
        required=True,
    )

    return parser.parse_args()


def sha256(path: Path) -> str:
    if (
        not path.is_file()
        or path.stat().st_size <= 0
    ):
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
            f"{label} drift detected.\n"
            f"Expected: {expected}\n"
            f"Actual  : {actual}\n"
            f"Path    : {path}"
        )

    return actual


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
                "Calibration solver-preparation evidence "
                "already exists with different content. "
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

    sidecar = path.with_suffix(
        ".sha256"
    )

    sidecar_text = (
        f"{record_hash}  {path.name}\n"
    )

    if sidecar.exists():
        if (
            sidecar.read_text(
                encoding="ascii"
            )
            != sidecar_text
        ):
            raise RuntimeError(
                "Calibration preparation SHA "
                "sidecar drift detected."
            )

    else:
        sidecar.write_text(
            sidecar_text,
            encoding="ascii",
            newline="\n",
        )

    return action, record_hash


def reference_temperature_c() -> float:
    path = (
        CONFIG
        / "complete_joint_preload.toml"
    )

    with path.open("rb") as stream:
        data = tomllib.load(stream)

    matches = []

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "reference_temperature_c":
                    matches.append(float(child))
                else:
                    walk(child)

        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)

    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one governed "
            "reference temperature."
        )

    value = matches[0]

    if not math.isfinite(value):
        raise RuntimeError(
            "Reference temperature is not finite."
        )

    return value


def find_preparation_row(
    certification: dict,
    case_id: str,
) -> dict:
    matches = [
        row
        for row in certification[
            "design_case_preparation_evidence"
        ]
        if row["case_id"] == case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected exactly one "
            "certified preparation row."
        )

    return matches[0]


def main() -> int:
    args = parse_arguments()

    # --------------------------------------------------
    # GOVERNANCE
    # --------------------------------------------------

    doe_policy_hash = require_sha256(
        DOE_POLICY_PATH,
        EXPECTED_DOE_POLICY_SHA256,
        "Production DOE policy",
    )

    campaign_hash = require_sha256(
        CAMPAIGN_MANIFEST_PATH,
        EXPECTED_CAMPAIGN_SHA256,
        "Production DOE campaign",
    )

    preparation_cert_hash = require_sha256(
        PREPARATION_CERT_PATH,
        EXPECTED_PREPARATION_CERT_SHA256,
        "Preparation certification",
    )

    warm_knowledge_hash = require_sha256(
        WARM_KNOWLEDGE_PATH,
        EXPECTED_WARM_KNOWLEDGE_SHA256,
        "Warm-start knowledge",
    )

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

    try:
        doe_case = next(
            item
            for item in campaign.design_cases
            if item.case_id == args.case_id
        )
    except StopIteration as exc:
        raise RuntimeError(
            "Case is not an authorized Production DOE "
            "design row. Holdouts remain inaccessible: "
            f"{args.case_id}"
        ) from exc

    if doe_case.source_case_id is not None:
        raise RuntimeError(
            "Certified FEM anchors must not enter "
            "new calibration preparation."
        )

    # --------------------------------------------------
    # FEM PREFLIGHT / RESOLUTION
    # --------------------------------------------------

    preflight = preflight_case(
        doe_case.case,
        PreflightTarget.FEM,
    )

    blocking = tuple(
        finding
        for finding in preflight.findings
        if finding.severity
        is PreflightSeverity.ERROR
    )

    if blocking:
        raise RuntimeError(
            f"{doe_case.case_id}: FEM preflight BLOCKED."
        )

    resolved = resolve_case(
        doe_case.case
    )

    if resolved.case_hash != doe_case.case_hash:
        raise RuntimeError(
            "Resolved case hash drift."
        )

    case_run_id = (
        f"trm_fem_{resolved.case_hash[:12]}"
    )

    # --------------------------------------------------
    # AUTHORITATIVE RESTART-V2 TRIAL-1 ROOT
    # --------------------------------------------------

    rv2_roots = {
        "D-INT-004": {
            "wave_prep": (
                CAMPAIGN_ROOT
                / "cp8_restart_v2_wave_01_preparation_manifest.json"
            ),
            "wave_prep_sha256": (
                "081db1e1b27424b509b82476716ed6f9"
                "6ab5bd96de5f6b91c7730d11dba2c37b"
            ),
            "execution_cert": (
                CAMPAIGN_ROOT
                / "cp8_restart_v2_wave_01_execution_certification.json"
            ),
            "execution_cert_sha256": (
                "f608970e67124d05e6c47885d032a54e"
                "7c422cd8500714a1f593157d180eceb7"
            ),
        },
        "D-INT-006": {
            "wave_prep": (
                CAMPAIGN_ROOT
                / "cp8_restart_v2_wave_02_preparation_manifest.json"
            ),
            "wave_prep_sha256": (
                "aa04b3c5ee14b32af4efb8bbd245b205"
                "e2984d5c6951070f3c78c9dec86f271b"
            ),
            "execution_cert": (
                CAMPAIGN_ROOT
                / "cp8_restart_v2_wave_02_execution_certification.json"
            ),
            "execution_cert_sha256": (
                "76889796cdcb1c07c00778b40d01531f"
                "76cfd72fa4c72ddea168a1ebc44aaaa0"
            ),
        },
        "D-INT-007": {
            "wave_prep": (
                CAMPAIGN_ROOT
                / "cp8_restart_v2_wave_02_preparation_manifest.json"
            ),
            "wave_prep_sha256": (
                "aa04b3c5ee14b32af4efb8bbd245b205"
                "e2984d5c6951070f3c78c9dec86f271b"
            ),
            "execution_cert": (
                CAMPAIGN_ROOT
                / "cp8_restart_v2_wave_02_execution_certification.json"
            ),
            "execution_cert_sha256": (
                "76889796cdcb1c07c00778b40d01531f"
                "76cfd72fa4c72ddea168a1ebc44aaaa0"
            ),
        },
        "D-INT-011": {
            "wave_prep": (
                CAMPAIGN_ROOT
                / "cp8_restart_v2_wave_02_preparation_manifest.json"
            ),
            "wave_prep_sha256": (
                "aa04b3c5ee14b32af4efb8bbd245b205"
                "e2984d5c6951070f3c78c9dec86f271b"
            ),
            "execution_cert": (
                CAMPAIGN_ROOT
                / "cp8_restart_v2_wave_02_execution_certification.json"
            ),
            "execution_cert_sha256": (
                "76889796cdcb1c07c00778b40d01531f"
                "76cfd72fa4c72ddea168a1ebc44aaaa0"
            ),
        },
    }

    if args.case_id not in rv2_roots:
        raise RuntimeError(
            "This RV2 Trial-2 preparer authorizes only "
            "D-INT-004, D-INT-006, D-INT-007, and D-INT-011."
        )

    rv2_cfg = rv2_roots[args.case_id]

    wave_prep_path = rv2_cfg["wave_prep"]
    execution_cert_path = rv2_cfg["execution_cert"]

    wave_prep_sha256 = require_sha256(
        wave_prep_path,
        rv2_cfg["wave_prep_sha256"],
        "Restart-v2 wave preparation manifest",
    )

    execution_cert_sha256 = require_sha256(
        execution_cert_path,
        rv2_cfg["execution_cert_sha256"],
        "Restart-v2 execution certification",
    )

    wave_prep = json.loads(
        wave_prep_path.read_text(
            encoding="utf-8-sig"
        )
    )

    execution_cert = json.loads(
        execution_cert_path.read_text(
            encoding="utf-8-sig"
        )
    )

    if (
        wave_prep.get("record_status") != "FINAL"
        or wave_prep.get("overall_disposition")
        != (
            "PREPARED_RESTART_V2_WAVE_"
            "AWAITING_INDEPENDENT_EXECUTION_CERTIFICATION"
        )
    ):
        # Preserve compatibility with the actual immutable Wave manifests:
        # the precise disposition string is secondary to FINAL state plus
        # independent execution certification below.
        if wave_prep.get("record_status") != "FINAL":
            raise RuntimeError(
                "Restart-v2 wave preparation is not FINAL."
            )

    if (
        execution_cert.get("record_status") != "FINAL"
        or execution_cert.get("overall_disposition")
        != (
            "CP8_RESTART_V2_WAVE_"
            "EXECUTION_CERTIFIED_READY_FOR_FEM"
        )
    ):
        raise RuntimeError(
            "Restart-v2 execution certification is not "
            "FINAL/authorized."
        )

    prep_rows = [
        row
        for row in wave_prep["cases"]
        if row["case_id"] == doe_case.case_id
    ]

    exec_rows = [
        row
        for row in execution_cert[
            "certified_restart_v2_cases"
        ]
        if row["case_id"] == doe_case.case_id
    ]

    if len(prep_rows) != 1 or len(exec_rows) != 1:
        raise RuntimeError(
            "Expected exactly one governed restart-v2 row "
            "in both preparation and execution certification."
        )

    rv2_row = prep_rows[0]
    certified = exec_rows[0]

    if (
        rv2_row["case_hash"] != doe_case.case_hash
        or certified["case_hash"] != doe_case.case_hash
    ):
        raise RuntimeError(
            "Restart-v2 case-hash provenance drift."
        )

    trial1_run_id = rv2_row[
        "restart_v2_trial_run_id"
    ]

    if (
        certified[
            "authorized_restart_v2_run_id"
        ]
        != trial1_run_id
        or int(rv2_row["trial_index"]) != 1
        or int(certified["trial_index"]) != 1
    ):
        raise RuntimeError(
            "Restart-v2 Trial-1 identity drift."
        )

    trial1_dir = (
        SOLVER_ROOT
        / case_run_id
        / trial1_run_id
    )

    trial1_prep_path = (
        ROOT
        / rv2_row[
            "preparation_relative_path"
        ]
    )

    deck_path = (
        ROOT
        / rv2_row[
            "deck_relative_path"
        ]
    )

    if (
        sha256(trial1_prep_path)
        != rv2_row["preparation_sha256"]
        or sha256(trial1_prep_path)
        != certified["preparation_sha256"]
    ):
        raise RuntimeError(
            "Restart-v2 preparation SHA drift."
        )

    deck_sha = sha256(deck_path)

    if (
        deck_sha != rv2_row["deck_sha256"]
        or deck_sha != certified["deck_sha256"]
    ):
        raise RuntimeError(
            "Restart-v2 deck SHA drift."
        )

    if (
        deck_path.parent.resolve()
        != trial1_dir.resolve()
    ):
        raise RuntimeError(
            "Restart-v2 run-directory identity drift."
        )

    trial1_prep = json.loads(
        trial1_prep_path.read_text(
            encoding="utf-8-sig"
        )
    )

    if (
        trial1_prep.get("record_status") != "FINAL"
        or trial1_prep.get("overall_disposition")
        != (
            "CP8_RESTART_V2_SIBLING_PREPARATION_PASS_"
            "AWAITING_INDEPENDENT_EXECUTION_CERTIFICATION"
        )
    ):
        raise RuntimeError(
            "Restart-v2 Trial-1 preparation is not "
            "the governed FINAL preparation record."
        )

    prep_case = trial1_prep["case"]

    if (
        prep_case["case_id"] != doe_case.case_id
        or prep_case["case_hash"] != doe_case.case_hash
        or prep_case["canonical_case_run_id"] != case_run_id
        or prep_case["restart_v2_trial_run_id"]
        != trial1_run_id
        or int(prep_case["trial_index"]) != 1
    ):
        raise RuntimeError(
            "Restart-v2 Trial-1 preparation identity drift."
        )

    if (
        trial1_prep["fem_preflight"]["status"]
        != "PASS"
        or int(
            trial1_prep["fem_preflight"][
                "finding_count"
            ]
        )
        != 0
    ):
        raise RuntimeError(
            "Restart-v2 FEM preflight is not clean PASS."
        )

    prep_exec = trial1_prep[
        "execution_authorization"
    ]

    if (
        prep_exec[
            "execution_authorized_by_this_record"
        ]
        is not False
        or prep_exec[
            "blind_holdout_execution_authorized"
        ]
        is not False
        or prep_exec[
            "requires_independent_pre_execution_certification"
        ]
        is not True
    ):
        raise RuntimeError(
            "Restart-v2 preparation authorization "
            "semantics drift."
        )

    predicted_dt = float(
        rv2_row[
            "frozen_delta_temperature_c"
        ]
    )

    if (
        not math.isclose(
            float(
                certified[
                    "frozen_delta_temperature_c"
                ]
            ),
            predicted_dt,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
        or not math.isclose(
            float(
                trial1_prep["deck"][
                    "delta_temperature_c"
                ]
            ),
            predicted_dt,
            rel_tol=0.0,
            abs_tol=1.0e-12,
        )
    ):
        raise RuntimeError(
            "Frozen V2.1 delta-temperature drift."
        )

    if (
        trial1_prep["deck"]["sha256"]
        != deck_sha
        or int(
            trial1_prep["deck"][
                "checkpoint_count"
            ]
        )
        != 20
        or int(
            certified[
                "checkpoint_count"
            ]
        )
        != 20
        or bool(
            trial1_prep["execution_resilience"][
                "overlay_latest"
            ]
        )
        or bool(
            certified[
                "overlay_latest"
            ]
        )
    ):
        raise RuntimeError(
            "Restart-v2 resilience/deck provenance drift."
        )

    solver_manifest_path = (
        trial1_dir
        / "fem_run_manifest.json"
    )

    solver_manifest = json.loads(
        solver_manifest_path.read_text(
            encoding="utf-8-sig"
        )
    )

    if (
        solver_manifest.get("disposition")
        != "succeeded"
        or int(
            solver_manifest.get(
                "return_code",
                -999,
            )
        )
        != 0
        or solver_manifest.get(
            "job_finished"
        )
        is not True
        or int(
            solver_manifest.get(
                "accepted_increment_count",
                -1,
            )
        )
        != 20
    ):
        raise RuntimeError(
            "Authoritative restart-v2 Trial-1 FEM "
            "did not close cleanly."
        )

    dat_path = (
        trial1_dir
        / f"{trial1_run_id}.dat"
    )

    if not dat_path.is_file():
        raise RuntimeError(
            "Authoritative restart-v2 Trial-1 DAT missing."
        )

    current_trial = (
        PreloadCalibrationTrial(
            trial_index=1,
            run_id=trial1_run_id,
            delta_temperature_c=(
                predicted_dt
            ),
            source=(
                PreloadCalibrationTrialSource
                .FEM_WARM_START
            ),
        )
    )

    root_trial_provenance = {
        "mode": (
            "certified_restart_v2_trial_1"
        ),
        "run_id": trial1_run_id,
        "source_v2_1_trial_run_id": (
            rv2_row[
                "source_trial_run_id"
            ]
        ),
        "preparation_relative_path": (
            relative(
                trial1_prep_path
            )
        ),
        "preparation_sha256": (
            sha256(
                trial1_prep_path
            )
        ),
        "wave_preparation_relative_path": (
            relative(
                wave_prep_path
            )
        ),
        "wave_preparation_sha256": (
            wave_prep_sha256
        ),
        "execution_certification_relative_path": (
            relative(
                execution_cert_path
            )
        ),
        "execution_certification_sha256": (
            execution_cert_sha256
        ),
        "solver_manifest_relative_path": (
            relative(
                solver_manifest_path
            )
        ),
        "solver_manifest_sha256": (
            sha256(
                solver_manifest_path
            )
        ),
        "deck_relative_path": (
            relative(
                deck_path
            )
        ),
        "deck_sha256": deck_sha,
        "frozen_v2_1_delta_temperature_c": (
            predicted_dt
        ),
        "trial_1_is_restart_v2_replacement": True,
        "historical_checkpoint_resume_used": False,
        "v2_1_refit_performed": False,
        "holdout_accessed": False,
    }

    # --------------------------------------------------
    # GOVERNED CALIBRATION HISTORY
    # --------------------------------------------------

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

    history = []

    previous_trial = None
    previous_measurement = None

    while True:
        current_dir = (
            SOLVER_ROOT
            / case_run_id
            / current_trial.run_id
        )

        dat_path = (
            current_dir
            / f"{current_trial.run_id}.dat"
        )

        if not dat_path.is_file():
            raise RuntimeError(
                "Calibration history is discontinuous: "
                f"missing DAT for {current_trial.run_id}."
            )

        extraction = (
            extract_clamp_force_measurement_from_dat(
                dat_path=dat_path,
                contact_pairs=contact.contact_pairs,
            )
        )

        measurement = extraction.measurement

        evaluation = (
            evaluate_preload_calibration_trial(
                case_run_id=case_run_id,
                target_force_n=(
                    resolved.source_case.loading.target_preload_n
                ),
                target_relative_tolerance=(
                    preload.target_relative_tolerance
                ),
                spread_relative_tolerance=(
                    preload.interface_spread_relative_tolerance
                ),
                current_trial=current_trial,
                measurement=measurement,
                previous_trial=previous_trial,
                previous_measurement=previous_measurement,
            )
        )

        history.append(
            {
                "trial": jsonable(current_trial),
                "measurement": jsonable(measurement),
                "evaluation": jsonable(evaluation),
                "dat_relative_path": relative(dat_path),
                "dat_sha256": sha256(dat_path),
            }
        )

        if evaluation.next_trial is None:
            print(
                "Calibration already accepted at "
                f"{current_trial.run_id}."
            )

            print(
                "No further trial preparation required."
            )

            return 0

        next_trial = evaluation.next_trial

        next_dir = (
            SOLVER_ROOT
            / case_run_id
            / next_trial.run_id
        )

        next_dat = (
            next_dir
            / f"{next_trial.run_id}.dat"
        )

        if not next_dat.is_file():
            break

        previous_trial = current_trial
        previous_measurement = measurement
        current_trial = next_trial

    # next_trial is now the first required unsolved trial.

    # --------------------------------------------------
    # CERTIFIED MESH BINDING
    # --------------------------------------------------

    preparation_cert = json.loads(
        PREPARATION_CERT_PATH.read_text(
            encoding="utf-8"
        )
    )

    preparation_row = find_preparation_row(
        preparation_cert,
        doe_case.case_id,
    )

    mesh_path = (
        ROOT
        / preparation_row["mesh_relative_path"]
    )

    step_path = (
        ROOT
        / preparation_row["step_relative_path"]
    )

    if (
        sha256(mesh_path)
        != preparation_row["mesh_sha256"]
    ):
        raise RuntimeError(
            "Certified mesh hash drift."
        )

    if (
        sha256(step_path)
        != preparation_row["step_sha256"]
    ):
        raise RuntimeError(
            "Certified STEP hash drift."
        )

    # --------------------------------------------------
    # FEM BUNDLE + NEXT-TRIAL DECK
    # --------------------------------------------------

    transfer = (
        load_complete_joint_calculix_transfer_definition(
            CONFIG
            / "complete_joint_calculix_transfer.toml"
        )
    )

    boundary = (
        load_complete_joint_boundary_region_definition(
            CONFIG
            / "complete_joint_boundary_regions.toml"
        )
    )

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
            transfer_template=transfer,
            contact_template=contact,
            boundary_template=boundary,
        )
    )

    mesh_data = (
        read_grouped_complete_joint_mesh(
            mesh_path,
            bundle.transfer,
        )
    )

    run_dir = (
        SOLVER_ROOT
        / case_run_id
        / next_trial.run_id
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path = (
        run_dir
        / f"{next_trial.run_id}.inp"
    )

    old_hash = (
        sha256(input_path)
        if input_path.exists()
        else None
    )

    deck = (
        write_fem_preload_calibration_trial_deck(
            mesh_data=mesh_data,
            bundle=bundle,
            trial=next_trial,
            reference_temperature_c=(
                reference_temperature_c()
            ),
            input_path=input_path,
        )
    )

    actual_hash = sha256(
        input_path
    )

    if actual_hash != deck.sha256:
        raise RuntimeError(
            "Generated next-trial deck SHA mismatch."
        )

    if (
        old_hash is not None
        and old_hash != actual_hash
    ):
        raise RuntimeError(
            "Deterministic regeneration changed "
            "the existing next-trial deck."
        )

    if deck.trial_run_id != next_trial.run_id:
        raise RuntimeError(
            "Deck/trial identity mismatch."
        )

    if not math.isclose(
        deck.delta_temperature_c,
        next_trial.delta_temperature_c,
        rel_tol=0.0,
        abs_tol=1.0e-10,
    ):
        raise RuntimeError(
            "Deck/trial ΔT mismatch."
        )

    # --------------------------------------------------
    # IMMUTABLE EVIDENCE
    # --------------------------------------------------

    record = {
        "schema_version": 1,

        "record_id": (
            "TRM-P3-CP8-PDOE-C01-"
            f"{doe_case.case_id}-"
            f"SOLVER-PREP-T{next_trial.trial_index:02d}"
        ),

        "record_status": "FINAL",

        "root_trial_provenance": (
            root_trial_provenance
        ),

        "case": {
            "case_id": doe_case.case_id,
            "case_hash": doe_case.case_hash,
            "run_id": case_run_id,
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
            "warm_start_knowledge_sha256": (
                warm_knowledge_hash
            ),
        },

        "fem_preflight": {
            "target": "fem",
            "blocking_error_count": 0,
            "status": "PASS",
        },

        "completed_calibration_history": history,

        "next_trial": jsonable(
            next_trial
        ),

        "prepared_artifacts": {
            "step_relative_path": relative(step_path),
            "step_sha256": (
                preparation_row["step_sha256"]
            ),
            "mesh_relative_path": relative(mesh_path),
            "mesh_sha256": (
                preparation_row["mesh_sha256"]
            ),
        },

        "deck": {
            "relative_path": relative(input_path),
            "sha256": actual_hash,
            "size_bytes": (
                input_path.stat().st_size
            ),
            "node_count": deck.node_count,
            "element_count": deck.element_count,
            "delta_temperature_c": (
                deck.delta_temperature_c
            ),
        },

        "solve_authorization": {
            "calculix_invoked": False,
            "solver_authorized_by_this_script": False,
            "holdout_accessed": False,
        },

        "overall_disposition": (
            "PRODUCTION_DOE_NEXT_CALIBRATION_"
            "SOLVER_PREPARATION_PASS"
        ),
    }

    record_path = (
        run_dir
        / "production_doe_calibration_solver_preparation_record.json"
    )

    action, record_hash = (
        write_immutable_json(
            record_path,
            record,
        )
    )

    print("=" * 120)
    print(
        "THREADROM — PRODUCTION DOE NEXT CALIBRATION PREPARATION"
    )
    print("=" * 120)

    print(
        "Case ID              :",
        doe_case.case_id,
    )

    print(
        "Completed trials     :",
        len(history),
    )

    print(
        "Next trial index     :",
        next_trial.trial_index,
    )

    print(
        "Next trial run ID    :",
        next_trial.run_id,
    )

    print(
        "Next trial source    :",
        next_trial.source.value,
    )

    print(
        "Next trial dT C      :",
        next_trial.delta_temperature_c,
    )

    print(
        "Deck SHA256          :",
        actual_hash,
    )

    print(
        "Preparation record   :",
        record_path,
    )

    print(
        "Record action        :",
        action,
    )

    print(
        "Record SHA256        :",
        record_hash,
    )

    print(
        "Disposition          : "
        "PRODUCTION_DOE_NEXT_CALIBRATION_"
        "SOLVER_PREPARATION_PASS"
    )

    print(
        "CalculiX invoked     : NO"
    )

    print(
        "Holdouts accessed    : NO"
    )

    print("=" * 120)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

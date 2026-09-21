from __future__ import annotations

from threadrom.factory.production_doe_gate0_evidence import (
    GATE0_CASE_IDS,
    inspect_gate0_trial1,
)

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

from threadrom.factory.production_doe_completed_trial import (
    verify_completed_trial,
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
    derive_fem_warm_start_preload_calibration_trial,
    evaluate_preload_calibration_trial,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)

from threadrom.factory.production_doe_reaction_observable_revision import (
    bridge_bundle_to_frozen_production_doe_identity,
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
            "Evaluate completed Production DOE preload "
            "calibration trials and prepare the next "
            "governed trial. Never launches CalculiX."
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
    # TRIAL-1 ROOT PROVENANCE
    # --------------------------------------------------

    rollout_cert_path = (
        CAMPAIGN_ROOT
        / "warm_start_delta_t_v2_1_rollout_preparation_certification.json"
    )

    expected_rollout_cert_sha256 = (
        "a11662817427d9131b92f798e953d116"
        "269ad672c49434365a75f68dac4709a7"
    )

    certified_rows = []

    if rollout_cert_path.is_file():
        actual_rollout_cert_sha256 = sha256(
            rollout_cert_path
        )

        if (
            actual_rollout_cert_sha256
            != expected_rollout_cert_sha256
        ):
            raise RuntimeError(
                "V2.1 rollout-certification SHA drift."
            )

        rollout_cert = json.loads(
            rollout_cert_path.read_text(
                encoding="utf-8"
            )
        )

        certified_rows = [
            row
            for row in rollout_cert[
                "certified_rollout_cases"
            ]
            if row["case_id"] == doe_case.case_id
        ]

        if len(certified_rows) > 1:
            raise RuntimeError(
                "Multiple certified V2.1 rollout rows "
                "exist for requested case."
            )

    if len(certified_rows) == 1:
        certified = certified_rows[0]

        if (
            certified["case_hash"]
            != doe_case.case_hash
        ):
            raise RuntimeError(
                "Certified V2.1 case-hash drift."
            )

        trial1_run_id = (
            f"{case_run_id}_cal_01_wsv21"
        )

        if (
            certified["run_id"]
            != trial1_run_id
        ):
            raise RuntimeError(
                "Certified V2.1 Trial-1 run-ID drift."
            )

        trial1_dir = (
            SOLVER_ROOT
            / case_run_id
            / trial1_run_id
        )

        trial1_prep_path = (
            ROOT
            / certified[
                "preparation_relative_path"
            ]
        )

        if (
            sha256(trial1_prep_path)
            != certified[
                "preparation_sha256"
            ]
        ):
            raise RuntimeError(
                "Certified V2.1 preparation SHA drift."
            )

        trial1_prep = json.loads(
            trial1_prep_path.read_text(
                encoding="utf-8"
            )
        )

        if (
            trial1_prep.get("record_status")
            != "FINAL"
            or trial1_prep.get(
                "overall_disposition"
            )
            != (
                "V2_1_ROLLOUT_CASE_PREPARATION_PASS_"
                "AWAITING_BATCH_CERTIFICATION"
            )
        ):
            raise RuntimeError(
                "V2.1 Trial-1 preparation is not "
                "the frozen FINAL PASS."
            )

        if (
            trial1_prep["case"]["case_id"]
            != doe_case.case_id
            or trial1_prep["case"]["case_hash"]
            != doe_case.case_hash
            or trial1_prep["case"][
                "v2_1_trial1_run_id"
            ]
            != trial1_run_id
        ):
            raise RuntimeError(
                "V2.1 Trial-1 preparation identity drift."
            )

        if (
            trial1_prep[
                "fem_preflight"
            ][
                "status"
            ]
            != "PASS"
            or trial1_prep[
                "fem_preflight"
            ][
                "blocking_error_count"
            ]
            != 0
        ):
            raise RuntimeError(
                "Certified V2.1 FEM preflight "
                "is not PASS."
            )

        zero = trial1_prep[
            "zero_solve_assertion"
        ]

        for field in (
            "solver_outputs_detected",
            "solver_results_read",
            "calculix_invoked",
            "solver_authorized_by_this_script",
            "blind_holdout_accessed",
            "v2_1_refit_performed",
        ):
            if zero.get(field) is not False:
                raise RuntimeError(
                    "Frozen V2.1 zero-solve "
                    "provenance drift for "
                    f"{field}."
                )

        prediction = trial1_prep[
            "frozen_v2_1_prediction"
        ]

        if (
            prediction.get(
                "model_refit_performed"
            )
            is not False
        ):
            raise RuntimeError(
                "V2.1 model-refit provenance drift."
            )

        predicted_dt = float(
            certified[
                "predicted_delta_temperature_c"
            ]
        )

        if not math.isclose(
            float(
                prediction[
                    "predicted_delta_temperature_c"
                ]
            ),
            predicted_dt,
            rel_tol=0.0,
            abs_tol=1.0e-10,
        ):
            raise RuntimeError(
                "Certified V2.1 prediction drift."
            )

        frozen_trial = trial1_prep[
            "trial_1"
        ]

        if (
            int(
                frozen_trial[
                    "trial_index"
                ]
            )
            != 1
            or frozen_trial["run_id"]
            != trial1_run_id
            or not math.isclose(
                float(
                    frozen_trial[
                        "delta_temperature_c"
                    ]
                ),
                predicted_dt,
                rel_tol=0.0,
                abs_tol=1.0e-10,
            )
        ):
            raise RuntimeError(
                "Frozen V2.1 Trial-1 identity/"
                "temperature drift."
            )

        deck_path = (
            ROOT
            / certified[
                "deck_relative_path"
            ]
        )

        deck_sha = sha256(
            deck_path
        )

        if (
            deck_sha
            != certified[
                "deck_sha256"
            ]
            or deck_sha
            != trial1_prep[
                "deck"
            ][
                "sha256"
            ]
        ):
            raise RuntimeError(
                "Certified V2.1 Trial-1 "
                "deck SHA drift."
            )

        if (
            deck_path.stat().st_size
            != int(
                certified[
                    "deck_size_bytes"
                ]
            )
        ):
            raise RuntimeError(
                "Certified V2.1 Trial-1 "
                "deck-size drift."
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
                "certified_v2_1_first_shot"
            ),
            "run_id": trial1_run_id,
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
            "rollout_certification_relative_path": (
                relative(
                    rollout_cert_path
                )
            ),
            "rollout_certification_sha256": (
                actual_rollout_cert_sha256
            ),
            "deck_relative_path": (
                relative(
                    deck_path
                )
            ),
            "deck_sha256": deck_sha,
            "v2_1_refit_performed": False,
            "holdout_accessed": False,
        }


        # D-INT-012: bind calibration history to the executed,
        # Gate-0-certified reaction-observable Trial 1.
        # The frozen V2.1 source checks above remain intact.
        if doe_case.case_id in GATE0_CASE_IDS:
            # The applicable Trial-1 preparation and solver output
            # must match this case's independently frozen Gate-0 row.
            gate0_evidence = inspect_gate0_trial1(
                repo_root=ROOT,
                requested_case_id=doe_case.case_id,
            )

            if (
                gate0_evidence.completion_status
                != "COMPLETED_INPUT_EVIDENCE_VERIFIED"
            ):
                raise RuntimeError(
                    f"{doe_case.case_id}: WAIT_FOR_TRIAL_1_COMPLETION. "
                    "Refusing to prepare a continuation from "
                    "unfinished or unverified FEM evidence."
                )

            rfobs1_run_id = (
                f"{case_run_id}_cal_01_wsv21_rfobs1"
            )
            rfobs1_dir = (
                SOLVER_ROOT
                / case_run_id
                / rfobs1_run_id
            )

            rfobs1_prep_path = (
                rfobs1_dir
                / "production_doe_reaction_observable_revision_record.json"
            )

            if gate0_evidence.run_id != rfobs1_run_id:
                raise RuntimeError(
                    "Frozen Gate-0 run identity differs from "
                    "the C01 calibration lineage."
                )

            rfobs1_prep_sha = require_sha256(
                rfobs1_prep_path,
                gate0_evidence.preparation_sha256,
                f"{doe_case.case_id} Gate-0 rfobs1 preparation",
            )

            rfobs1_prep = json.loads(
                rfobs1_prep_path.read_text(encoding="utf-8")
            )

            rf_case = rfobs1_prep["case"]
            rf_trial = rfobs1_prep["trial"]

            if (
                rfobs1_prep["record_status"] != "FINAL"
                or rf_case["case_id"] != doe_case.case_id
                or rf_case["case_hash"] != doe_case.case_hash
                or rf_case["source_v2_1_trial_run_id"] != trial1_run_id
                or rf_trial["run_id"] != rfobs1_run_id
                or rf_trial["trial_index"] != 1
                or not math.isclose(
                    float(rf_trial["delta_temperature_c"]),
                    predicted_dt,
                    rel_tol=0.0,
                    abs_tol=1.0e-10,
                )
                or rfobs1_prep["source_v2_1_preparation"][
                    "sha256"
                ] != sha256(trial1_prep_path)
                or rfobs1_prep["reaction_observability"][
                    "fully_observable"
                ] is not True
            ):
                raise RuntimeError(
                    "C01 Gate-0 rfobs1 Trial-1 lineage drift."
                )

            manifest_path = (
                rfobs1_dir / "fem_run_manifest.json"
            )
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )

            if (
                manifest.get("disposition") != "succeeded"
                or manifest.get("case_hash") != doe_case.case_hash
                or (
                    "run_id" in manifest
                    and manifest["run_id"] != rfobs1_run_id
                )
            ):
                raise RuntimeError(
                    "C01 Gate-0 rfobs1 Trial-1 run is not "
                    "the expected completed solver run."
                )

            dat_path = (
                rfobs1_dir / f"{rfobs1_run_id}.dat"
            )
            dat_entries = [
                artifact
                for artifact in manifest["artifacts"]
                if artifact["role"] == "dat"
                and artifact["relative_path"] == relative(dat_path)
            ]

            if len(dat_entries) != 1:
                raise RuntimeError(
                    "D-INT-012 completed-run DAT is not "
                    "uniquely bound to its immutable manifest."
                )

            dat_sha = require_sha256(
                dat_path,
                dat_entries[0]["sha256"],
                "C01 completed rfobs1 DAT",
            )

            current_trial = PreloadCalibrationTrial(
                trial_index=1,
                run_id=rfobs1_run_id,
                delta_temperature_c=predicted_dt,
                source=(
                    PreloadCalibrationTrialSource.FEM_WARM_START
                ),
            )

            root_trial_provenance = {
                "mode": "certified_rfobs1_completed_trial_1",
                "run_id": rfobs1_run_id,
                "source_v2_1_run_id": trial1_run_id,
                "rfobs1_preparation_relative_path": relative(
                    rfobs1_prep_path
                ),
                "rfobs1_preparation_sha256": rfobs1_prep_sha,
                "completed_run_manifest_relative_path": relative(
                    manifest_path
                ),
                "completed_run_manifest_sha256": sha256(
                    manifest_path
                ),
                "completed_dat_sha256": dat_sha,
                "v2_1_refit_performed": False,
                "holdout_accessed": False,
            }


    else:
        trial1_run_id = (
            f"{case_run_id}_cal_01"
        )

        trial1_dir = (
            SOLVER_ROOT
            / case_run_id
            / trial1_run_id
        )

        trial1_prep_path = (
            trial1_dir
            / "production_doe_solver_preparation_record.json"
        )

        if not trial1_prep_path.is_file():
            raise FileNotFoundError(
                "Trial-1 solver-preparation "
                "record missing."
            )

        trial1_prep = json.loads(
            trial1_prep_path.read_text(
                encoding="utf-8"
            )
        )

        predicted_dt = float(
            trial1_prep[
                "warm_start_prediction"
            ][
                "predicted_delta_temperature_c"
            ]
        )

        current_trial = (
            derive_fem_warm_start_preload_calibration_trial(
                predicted_delta_temperature_c=(
                    predicted_dt
                ),
                case_run_id=case_run_id,
            )
        )

        root_trial_provenance = {
            "mode": (
                "legacy_canonical_trial_1"
            ),
            "run_id": trial1_run_id,
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

        # Completed rfobs1 calibration trials must be bound to their
        # own immutable preparations and successful solver manifests
        # before their DAT data can influence the next trial.
        if (
            root_trial_provenance.get("mode")
            == "certified_rfobs1_completed_trial_1"
        ):
            if current_trial.trial_index == 1:
                expected_deck_sha = rfobs1_prep["deck"]["sha256"]

                if sha256(
                    current_dir / "fem_run_manifest.json"
                ) != root_trial_provenance[
                    "completed_run_manifest_sha256"
                ]:
                    raise RuntimeError(
                        "Frozen rfobs1 Trial-1 manifest SHA drift."
                    )

            else:
                completed_prep_path = (
                    current_dir
                    / "production_doe_calibration_solver_preparation_record.json"
                )
                completed_prep_hash = sha256(completed_prep_path)

                sidecar_path = completed_prep_path.with_suffix(".sha256")
                expected_sidecar = (
                    f"{completed_prep_hash}  "
                    f"{completed_prep_path.name}\n"
                )

                if (
                    sidecar_path.read_text(encoding="ascii")
                    != expected_sidecar
                ):
                    raise RuntimeError(
                        "Completed calibration-trial preparation "
                        "SHA sidecar drift."
                    )

                completed_prep = json.loads(
                    completed_prep_path.read_text(encoding="utf-8")
                )

                if (
                    completed_prep.get("record_status") != "FINAL"
                    or completed_prep.get("overall_disposition")
                    != "PRODUCTION_DOE_NEXT_CALIBRATION_SOLVER_PREPARATION_PASS"
                    or completed_prep["case"]["case_id"] != doe_case.case_id
                    or completed_prep["case"]["case_hash"] != doe_case.case_hash
                    or completed_prep["next_trial"]["run_id"]
                    != current_trial.run_id
                    or int(
                        completed_prep["next_trial"]["trial_index"]
                    ) != current_trial.trial_index
                    or not math.isclose(
                        float(
                            completed_prep["next_trial"][
                                "delta_temperature_c"
                            ]
                        ),
                        current_trial.delta_temperature_c,
                        rel_tol=0.0,
                        abs_tol=1.0e-10,
                    )
                    or completed_prep["deck"]["relative_path"]
                    != relative(
                        current_dir / f"{current_trial.run_id}.inp"
                    )
                ):
                    raise RuntimeError(
                        "Completed calibration-trial preparation "
                        "identity or temperature drift."
                    )

                expected_deck_sha = completed_prep["deck"]["sha256"]

            verified_trial = verify_completed_trial(
                repo_root=ROOT,
                manifest_path=current_dir / "fem_run_manifest.json",
                expected_run_id=current_trial.run_id,
                expected_case_hash=doe_case.case_hash,
                expected_deck_sha256=expected_deck_sha,
            )

            if verified_trial.dat_path != dat_path.resolve():
                raise RuntimeError(
                    "Verified calibration DAT path mismatch."
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
            if not evaluation.accepted:
                raise RuntimeError(
                    f"{doe_case.case_id}: calibration terminated "
                    "without preload acceptance; "
                    f"disposition={evaluation.decision.disposition}. "
                    "Refusing to report ACCEPT."
                )

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


    # Preserve the frozen case-hash execution lineage for the
    # independently verified C01 Gate-0 rfobs1 continuation.
    # The global deck identity guard remains unchanged.
    if doe_case.case_id in GATE0_CASE_IDS:
        if (
            root_trial_provenance.get("mode")
            != "certified_rfobs1_completed_trial_1"
            or root_trial_provenance.get("run_id")
            != f"{case_run_id}_cal_01_wsv21_rfobs1"
        ):
            raise RuntimeError(
                "C01 Gate-0 continuation lacks verified rfobs1 provenance."
            )

        bundle = bridge_bundle_to_frozen_production_doe_identity(
            bundle=bundle,
            case_hash=doe_case.case_hash,
            resolution_hash=resolved.resolution_hash,
            frozen_case_run_id=case_run_id,
        )

        if bundle.preparation.identity.run_id != case_run_id:
            raise RuntimeError(
                "C01 frozen execution identity was not restored."
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

    # Generate to a separate candidate: never write over an
    # existing governed deck before verifying byte identity.
    candidate_path = input_path.with_name(
        input_path.stem + ".__candidate__.inp"
    )

    if candidate_path.exists():
        raise RuntimeError(
            f"Stale calibration deck candidate exists: {candidate_path}"
        )

    old_hash = (
        sha256(input_path)
        if input_path.exists()
        else None
    )

    deck = write_fem_preload_calibration_trial_deck(
        mesh_data=mesh_data,
        bundle=bundle,
        trial=next_trial,
        reference_temperature_c=reference_temperature_c(),
        input_path=candidate_path,
    )

    candidate_hash = sha256(candidate_path)

    if candidate_hash != deck.sha256:
        raise RuntimeError(
            "Generated candidate deck SHA mismatch; "
            "existing deck remains untouched."
        )

    if old_hash is not None:
        if candidate_hash != old_hash:
            raise RuntimeError(
                "Regenerated calibration deck differs from "
                "existing immutable deck. Original preserved; "
                f"candidate retained for review: {candidate_path}"
            )

        candidate_path.unlink()
        actual_hash = old_hash

    else:
        # Refuse to replace a deck that appeared during preparation.
        if input_path.exists():
            raise RuntimeError(
                "Calibration deck appeared during candidate "
                "generation. Refusing overwrite."
            )

        candidate_path.rename(input_path)
        actual_hash = sha256(input_path)

        if actual_hash != candidate_hash:
            raise RuntimeError(
                "Published calibration deck SHA mismatch."
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

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json

from enum import Enum
from pathlib import Path

from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationDisposition,
    derive_fem_warm_start_preload_calibration_trial,
    evaluate_preload_calibration_trial,
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

SOLVER_ROOT = CAMPAIGN_ROOT / "solver_preparation"

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

WARM_KNOWLEDGE_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_warm_start_knowledge_record.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Certify one accepted Phase-3 Production DOE "
            "FEM calibration result as immutable reusable evidence."
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

    if isinstance(value, tuple):
        return [
            jsonable(item)
            for item in value
        ]

    if isinstance(value, list):
        return [
            jsonable(item)
            for item in value
        ]

    if isinstance(value, dict):
        return {
            key: jsonable(item)
            for key, item in value.items()
        }

    return value


def require_clean_manifest(
    path: Path,
    *,
    expected_run_id: str,
    expected_case_hash: str,
) -> dict:
    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if data.get("run_id") != expected_run_id:
        raise RuntimeError(
            f"Run-ID mismatch in {path}"
        )

    if data.get("case_hash") != expected_case_hash:
        raise RuntimeError(
            f"Case-hash mismatch in {path}"
        )

    if data.get("disposition") != "succeeded":
        raise RuntimeError(
            f"Solver disposition is not succeeded: {path}"
        )

    if data.get("job_finished") is not True:
        raise RuntimeError(
            f"Solver job is not finalized: {path}"
        )

    if data.get("return_code") != 0:
        raise RuntimeError(
            f"Solver return code is not zero: {path}"
        )

    return data


def main() -> int:
    args = parse_args()

    # ---------------------------------------------------------
    # GOVERNED CAMPAIGN INPUTS
    # ---------------------------------------------------------

    for path in (
        DOE_POLICY_PATH,
        CAMPAIGN_MANIFEST_PATH,
        PREPARATION_CERT_PATH,
        WARM_KNOWLEDGE_PATH,
    ):
        sha256(path)

    warm_raw = json.loads(
        WARM_KNOWLEDGE_PATH.read_text(
            encoding="utf-8"
        )
    )

    campaign_refs = warm_raw["campaign"]

    if (
        sha256(DOE_POLICY_PATH)
        != campaign_refs["doe_policy_sha256"]
    ):
        raise RuntimeError(
            "Production DOE policy drift detected."
        )

    if (
        sha256(CAMPAIGN_MANIFEST_PATH)
        != campaign_refs["campaign_manifest_sha256"]
    ):
        raise RuntimeError(
            "Production DOE campaign-manifest drift detected."
        )

    if (
        sha256(PREPARATION_CERT_PATH)
        != campaign_refs["preparation_certification_sha256"]
    ):
        raise RuntimeError(
            "Production DOE preparation-certification drift detected."
        )

    policy = load_phase3_production_doe_policy(
        DOE_POLICY_PATH
    )

    campaign = build_phase3_production_doe(
        policy
    )

    matches = tuple(
        item
        for item in campaign.design_cases
        if item.case_id == args.case_id
    )

    if len(matches) != 1:
        raise RuntimeError(
            "Requested case must resolve to exactly one "
            "Production DOE design case."
        )

    doe_case = matches[0]

    if doe_case.source_case_id is not None:
        raise RuntimeError(
            "Existing certified anchors are not recertified "
            "by this Production DOE certifier."
        )

    resolved = resolve_case(
        doe_case.case
    )

    if resolved.case_hash != doe_case.case_hash:
        raise RuntimeError(
            "Resolved case hash drift."
        )

    case_run_id = (
        f"trm_fem_{doe_case.case_hash[:12]}"
    )

    trial1_run_id = (
        f"{case_run_id}_cal_01"
    )

    trial2_run_id = (
        f"{case_run_id}_cal_02"
    )

    case_root = (
        SOLVER_ROOT
        / case_run_id
    )

    trial1_dir = (
        case_root
        / trial1_run_id
    )

    trial2_dir = (
        case_root
        / trial2_run_id
    )

    # ---------------------------------------------------------
    # IMMUTABLE PREPARATION EVIDENCE
    # ---------------------------------------------------------

    trial1_prep_path = (
        trial1_dir
        / "production_doe_solver_preparation_record.json"
    )

    trial2_prep_path = (
        trial2_dir
        / "production_doe_calibration_solver_preparation_record.json"
    )

    trial1_prep = json.loads(
        trial1_prep_path.read_text(
            encoding="utf-8"
        )
    )

    trial2_prep = json.loads(
        trial2_prep_path.read_text(
            encoding="utf-8"
        )
    )

    if trial1_prep.get("record_status") != "FINAL":
        raise RuntimeError(
            "Trial-1 preparation record is not FINAL."
        )

    if (
        trial1_prep.get("overall_disposition")
        != "PRODUCTION_DOE_TRIAL1_SOLVER_PREPARATION_PASS"
    ):
        raise RuntimeError(
            "Trial-1 solver preparation is not governed PASS."
        )

    if trial2_prep.get("record_status") != "FINAL":
        raise RuntimeError(
            "Trial-2 preparation record is not FINAL."
        )

    if (
        trial2_prep.get("overall_disposition")
        != (
            "PRODUCTION_DOE_NEXT_CALIBRATION_"
            "SOLVER_PREPARATION_PASS"
        )
    ):
        raise RuntimeError(
            "Trial-2 solver preparation is not governed PASS."
        )

    for prep in (
        trial1_prep,
        trial2_prep,
    ):
        if (
            prep["case"]["case_id"]
            != doe_case.case_id
            or prep["case"]["case_hash"]
            != doe_case.case_hash
        ):
            raise RuntimeError(
                "Solver-preparation case identity mismatch."
            )

        if (
            prep["fem_preflight"]["status"]
            != "PASS"
        ):
            raise RuntimeError(
                "Solver-preparation FEM preflight is not PASS."
            )

        solve_auth = prep["solve_authorization"]

        if (
            solve_auth["calculix_invoked"] is not False
            or solve_auth[
                "solver_authorized_by_this_script"
            ] is not False
            or solve_auth["holdout_accessed"] is not False
        ):
            raise RuntimeError(
                "Solver-preparation provenance is not clean."
            )

    # ---------------------------------------------------------
    # SOLVER EVIDENCE
    # ---------------------------------------------------------

    trial1_dat = (
        trial1_dir
        / f"{trial1_run_id}.dat"
    )

    trial2_dat = (
        trial2_dir
        / f"{trial2_run_id}.dat"
    )

    trial1_manifest_path = (
        trial1_dir
        / "fem_run_manifest.json"
    )

    trial2_manifest_path = (
        trial2_dir
        / "fem_run_manifest.json"
    )

    trial1_manifest = require_clean_manifest(
        trial1_manifest_path,
        expected_run_id=trial1_run_id,
        expected_case_hash=doe_case.case_hash,
    )

    trial2_manifest = require_clean_manifest(
        trial2_manifest_path,
        expected_run_id=trial2_run_id,
        expected_case_hash=doe_case.case_hash,
    )

    for path in (
        trial1_prep_path,
        trial2_prep_path,
        trial1_dat,
        trial2_dat,
        trial1_manifest_path,
        trial2_manifest_path,
    ):
        sha256(path)

    # ---------------------------------------------------------
    # RECONSTRUCT GOVERNED CALIBRATION HISTORY
    # ---------------------------------------------------------

    trial1 = (
        derive_fem_warm_start_preload_calibration_trial(
            predicted_delta_temperature_c=float(
                trial1_prep[
                    "warm_start_prediction"
                ][
                    "predicted_delta_temperature_c"
                ]
            ),
            case_run_id=case_run_id,
        )
    )

    frozen_trial2 = (
        trial2_prep["next_trial"]
    )

    if int(
        frozen_trial2["trial_index"]
    ) != 2:
        raise RuntimeError(
            "Expected governed Trial 2 preparation."
        )

    if (
        frozen_trial2["run_id"]
        != trial2_run_id
    ):
        raise RuntimeError(
            "Frozen Trial-2 run identity mismatch."
        )

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

    measurement1 = (
        extract_clamp_force_measurement_from_dat(
            dat_path=trial1_dat,
            contact_pairs=contact.contact_pairs,
        )
        .measurement
    )

    evaluation1 = (
        evaluate_preload_calibration_trial(
            case_run_id=case_run_id,
            target_force_n=(
                resolved
                .source_case
                .loading
                .target_preload_n
            ),
            target_relative_tolerance=(
                preload.target_relative_tolerance
            ),
            spread_relative_tolerance=(
                preload.interface_spread_relative_tolerance
            ),
            current_trial=trial1,
            measurement=measurement1,
        )
    )

    if evaluation1.next_trial is None:
        raise RuntimeError(
            "Trial 1 is already governed ACCEPT; "
            "unexpected Trial-2 history."
        )

    trial2 = evaluation1.next_trial

    if (
        trial2.run_id
        != frozen_trial2["run_id"]
    ):
        raise RuntimeError(
            "Reconstructed Trial-2 run ID drift."
        )

    if not abs(
        trial2.delta_temperature_c
        - float(
            frozen_trial2[
                "delta_temperature_c"
            ]
        )
    ) <= 1.0e-10:
        raise RuntimeError(
            "Reconstructed Trial-2 delta-T drift."
        )

    measurement2 = (
        extract_clamp_force_measurement_from_dat(
            dat_path=trial2_dat,
            contact_pairs=contact.contact_pairs,
        )
        .measurement
    )

    evaluation2 = (
        evaluate_preload_calibration_trial(
            case_run_id=case_run_id,
            target_force_n=(
                resolved
                .source_case
                .loading
                .target_preload_n
            ),
            target_relative_tolerance=(
                preload.target_relative_tolerance
            ),
            spread_relative_tolerance=(
                preload.interface_spread_relative_tolerance
            ),
            current_trial=trial2,
            measurement=measurement2,
            previous_trial=trial1,
            previous_measurement=measurement1,
        )
    )

    # ---------------------------------------------------------
    # CRITICAL ELIGIBILITY GATE:
    # SOLVER SUCCESS != CALIBRATION ACCEPTANCE
    # ---------------------------------------------------------

    if (
        evaluation2.decision.disposition
        is not PreloadCalibrationDisposition.ACCEPT
    ):
        raise RuntimeError(
            "Trial 2 is not governed ACCEPT. "
            "Reusable FEM certification refused."
        )

    if evaluation2.next_trial is not None:
        raise RuntimeError(
            "Governed ACCEPT unexpectedly produced "
            "another calibration trial."
        )

    forces = (
        measurement2.under_head_force_n,
        measurement2.nut_bearing_force_n,
        measurement2.member_interface_force_n,
    )

    mean_force = (
        sum(forces)
        / len(forces)
    )

    spread_force = (
        max(forces)
        - min(forces)
    )

    spread_relative = (
        spread_force
        / mean_force
    )

    # ---------------------------------------------------------
    # IMMUTABLE ACCEPTED-FEM EVIDENCE
    # ---------------------------------------------------------

    output = (
        case_root
        / "production_doe_accepted_fem_evidence.json"
    )

    record = {
        "schema_version": 1,

        "record_id": (
            "TRM-P3-CP8-PDOE-C01-"
            f"{args.case_id}-ACCEPTED-FEM-001"
        ),

        "record_status": "FINAL",

        "case": {
            "case_id": doe_case.case_id,
            "case_hash": doe_case.case_hash,
            "case_run_id": case_run_id,
            "target_preload_n": (
                resolved
                .source_case
                .loading
                .target_preload_n
            ),
            "mesh_policy_name": (
                doe_case.mesh_policy_name
            ),
        },

        "governance": {
            "doe_policy_relative_path": (
                relative(DOE_POLICY_PATH)
            ),
            "doe_policy_sha256": (
                sha256(DOE_POLICY_PATH)
            ),
            "campaign_manifest_relative_path": (
                relative(CAMPAIGN_MANIFEST_PATH)
            ),
            "campaign_manifest_sha256": (
                sha256(CAMPAIGN_MANIFEST_PATH)
            ),
            "preparation_certification_relative_path": (
                relative(PREPARATION_CERT_PATH)
            ),
            "preparation_certification_sha256": (
                sha256(PREPARATION_CERT_PATH)
            ),
            "warm_start_v1_relative_path": (
                relative(WARM_KNOWLEDGE_PATH)
            ),
            "warm_start_v1_sha256": (
                sha256(WARM_KNOWLEDGE_PATH)
            ),
        },

        "accepted_calibration": {
            "accepted_trial_index": 2,
            "accepted_run_id": (
                trial2.run_id
            ),
            "accepted_delta_temperature_c": (
                trial2.delta_temperature_c
            ),
            "measurement": (
                jsonable(measurement2)
            ),
            "mean_clamp_force_n": (
                mean_force
            ),
            "interface_spread_force_n": (
                spread_force
            ),
            "interface_spread_relative": (
                spread_relative
            ),
            "target_relative_error": (
                evaluation2
                .decision
                .target_relative_error
            ),
            "target_relative_tolerance": (
                evaluation2
                .decision
                .target_relative_tolerance
            ),
            "spread_relative_tolerance": (
                evaluation2
                .decision
                .spread_relative_tolerance
            ),
            "decision": (
                jsonable(
                    evaluation2.decision
                )
            ),
        },

        "calibration_history": [
            {
                "trial": jsonable(trial1),
                "measurement": (
                    jsonable(measurement1)
                ),
                "evaluation": (
                    jsonable(evaluation1)
                ),
                "solver_manifest_summary": {
                    "disposition": (
                        trial1_manifest[
                            "disposition"
                        ]
                    ),
                    "job_finished": (
                        trial1_manifest[
                            "job_finished"
                        ]
                    ),
                    "return_code": (
                        trial1_manifest[
                            "return_code"
                        ]
                    ),
                    "accepted_increment_count": (
                        trial1_manifest.get(
                            "accepted_increment_count"
                        )
                    ),
                },
                "preparation_record_relative_path": (
                    relative(
                        trial1_prep_path
                    )
                ),
                "preparation_record_sha256": (
                    sha256(
                        trial1_prep_path
                    )
                ),
                "dat_relative_path": (
                    relative(trial1_dat)
                ),
                "dat_sha256": (
                    sha256(trial1_dat)
                ),
                "manifest_relative_path": (
                    relative(
                        trial1_manifest_path
                    )
                ),
                "manifest_sha256": (
                    sha256(
                        trial1_manifest_path
                    )
                ),
            },
            {
                "trial": jsonable(trial2),
                "measurement": (
                    jsonable(measurement2)
                ),
                "evaluation": (
                    jsonable(evaluation2)
                ),
                "solver_manifest_summary": {
                    "disposition": (
                        trial2_manifest[
                            "disposition"
                        ]
                    ),
                    "job_finished": (
                        trial2_manifest[
                            "job_finished"
                        ]
                    ),
                    "return_code": (
                        trial2_manifest[
                            "return_code"
                        ]
                    ),
                    "accepted_increment_count": (
                        trial2_manifest.get(
                            "accepted_increment_count"
                        )
                    ),
                },
                "preparation_record_relative_path": (
                    relative(
                        trial2_prep_path
                    )
                ),
                "preparation_record_sha256": (
                    sha256(
                        trial2_prep_path
                    )
                ),
                "dat_relative_path": (
                    relative(trial2_dat)
                ),
                "dat_sha256": (
                    sha256(trial2_dat)
                ),
                "manifest_relative_path": (
                    relative(
                        trial2_manifest_path
                    )
                ),
                "manifest_sha256": (
                    sha256(
                        trial2_manifest_path
                    )
                ),
            },
        ],

        "evidence_semantics": {
            "solver_success_verified": True,
            "governed_calibration_accept_verified": True,
            "trial_1_preserved": True,
            "trial_2_is_accepted_physics_solve": True,
            "additional_calibration_required": False,
            "eligible_for_warm_start_knowledge": True,
            "eligible_for_v2_anchor_use": True,
            "holdout_accessed": False,
        },

        "overall_disposition": (
            "PRODUCTION_DOE_FEM_CALIBRATION_ACCEPTED"
        ),
    }

    serialized = (
        json.dumps(
            record,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    if output.exists():
        existing = output.read_text(
            encoding="utf-8"
        )

        if existing != serialized:
            raise RuntimeError(
                "Accepted FEM evidence already exists "
                "with different content."
            )

        action = "UNCHANGED / IDENTICAL"

    else:
        temporary = output.with_suffix(
            ".json.tmp"
        )

        temporary.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )

        temporary.replace(
            output
        )

        action = "CREATED"

    record_hash = sha256(
        output
    )

    sidecar = output.with_suffix(
        ".sha256"
    )

    sidecar_text = (
        f"{record_hash}  {output.name}\n"
    )

    if sidecar.exists():
        if (
            sidecar.read_text(
                encoding="ascii"
            )
            != sidecar_text
        ):
            raise RuntimeError(
                "Accepted FEM evidence SHA sidecar drift."
            )

    else:
        sidecar.write_text(
            sidecar_text,
            encoding="ascii",
            newline="\n",
        )

    print("=" * 118)
    print(
        "THREADROM — PRODUCTION DOE ACCEPTED FEM CERTIFICATION"
    )
    print("=" * 118)

    print(
        "Case ID                :",
        doe_case.case_id,
    )

    print(
        "Record action          :",
        action,
    )

    print(
        "Record status          : FINAL"
    )

    print(
        "Solver success         : VERIFIED"
    )

    print(
        "Governed calibration   : ACCEPT"
    )

    print(
        "Accepted trial         : 2"
    )

    print(
        "Accepted run ID        :",
        trial2.run_id,
    )

    print(
        "Accepted dT C          :",
        trial2.delta_temperature_c,
    )

    print(
        "Target preload N       :",
        resolved
        .source_case
        .loading
        .target_preload_n,
    )

    print(
        "Mean clamp N           :",
        mean_force,
    )

    print(
        "Target relative error  :",
        evaluation2
        .decision
        .target_relative_error,
    )

    print(
        "Interface spread rel   :",
        spread_relative,
    )

    print(
        "Warm-start eligible    : YES"
    )

    print(
        "V2 anchor eligible     : YES"
    )

    print(
        "Further trials         : NONE"
    )

    print(
        "Holdouts accessed      : NO"
    )

    print(
        "Disposition            : "
        "PRODUCTION_DOE_FEM_CALIBRATION_ACCEPTED"
    )

    print(
        "Record SHA256          :",
        record_hash,
    )

    print(
        "Record                 :",
        output,
    )

    print("=" * 118)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

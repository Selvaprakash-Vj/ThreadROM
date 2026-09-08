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

from threadrom.factory.fem_calibration_knowledge import (
    FemWarmStartSource,
    build_fem_calibration_knowledge_record,
    load_fem_warm_start_policy,
    predict_fem_warm_start,
)
from threadrom.factory.fem_case_definition_bundle import (
    build_generic_fem_definition_bundle,
)
from threadrom.factory.fem_preload_calibration_deck import (
    write_fem_preload_calibration_trial_deck,
)
from threadrom.factory.preload_calibration_campaign import (
    derive_fem_warm_start_preload_calibration_trial,
)
from threadrom.factory.preload_calibration_seed import (
    derive_analytical_thermal_preload_seed,
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

DOE_POLICY_PATH = (
    CONFIG
    / "phase3_production_doe.toml"
)

CAMPAIGN_MANIFEST_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_campaign_manifest.json"
)

ANCHOR_BINDING_PATH = (
    CAMPAIGN_ROOT
    / "existing_anchor_binding_record.json"
)

PREPARATION_CERT_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_preparation_certification_record.json"
)

WARM_KNOWLEDGE_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_warm_start_knowledge_record.json"
)

WARM_POLICY_PATH = (
    CONFIG
    / "fem_calibration_warm_start.toml"
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

EXPECTED_ANCHOR_BINDING_SHA256 = (
    "ab861ff62af6bbc4589b3a469e8dc159"
    "c92dd61116fd8275c02e8f1adcf813b2"
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
            "Prepare one frozen Phase-3 Production DOE "
            "design case through governed FEM preflight, "
            "warm-start prediction and Trial-1 CalculiX "
            "deck generation. This script NEVER launches "
            "CalculiX."
        )
    )

    parser.add_argument(
        "--case-id",
        required=True,
        help="Frozen Production DOE design case ID.",
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
                "Solver-preparation evidence already "
                "exists with different content. "
                f"Refusing immutable overwrite: {path}"
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
        existing = sidecar.read_text(
            encoding="ascii"
        )

        if existing != sidecar_text:
            raise RuntimeError(
                "Solver-preparation SHA sidecar "
                f"drift detected: {sidecar}"
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
                    matches.append(
                        float(child)
                    )
                else:
                    walk(child)

        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)

    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one governed "
            "reference_temperature_c."
        )

    result = matches[0]

    if not math.isfinite(result):
        raise RuntimeError(
            "Governed reference temperature "
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
        if row["case_id"] == case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected exactly one "
            "certified preparation row; "
            f"found {len(matches)}."
        )

    return matches[0]


def build_warm_start_knowledge(
    *,
    campaign,
    warm_record: dict,
):
    anchor_by_id = {
        item.case_id: item
        for item in campaign.design_cases
        if item.source_case_id is not None
    }

    if len(anchor_by_id) != 4:
        raise RuntimeError(
            "Expected exactly four frozen "
            "Production DOE anchors."
        )

    rows = warm_record["anchors"]

    if len(rows) != 4:
        raise RuntimeError(
            "Warm-start evidence record must "
            "contain exactly four anchors."
        )

    records = []

    for row in rows:
        case_id = row["case_id"]

        try:
            anchor = anchor_by_id[
                case_id
            ]
        except KeyError as exc:
            raise RuntimeError(
                "Warm-start knowledge contains "
                "an anchor absent from the frozen DOE: "
                f"{case_id}"
            ) from exc

        if (
            row["case_hash"]
            != anchor.case_hash
        ):
            raise RuntimeError(
                f"{case_id}: warm-start anchor "
                "case hash drift."
            )

        resolved = resolve_case(
            anchor.case
        )

        if (
            resolved.case_hash
            != anchor.case_hash
        ):
            raise RuntimeError(
                f"{case_id}: resolved anchor "
                "hash drift."
            )

        seed = (
            derive_analytical_thermal_preload_seed(
                resolved
            )
        )

        record = (
            build_fem_calibration_knowledge_record(
                resolved=resolved,
                seed=seed,
                accepted_run_id=(
                    row["accepted_run_id"]
                ),
                accepted_delta_temperature_c=(
                    float(
                        row[
                            "accepted_delta_temperature_c"
                        ]
                    )
                ),
                measured_mean_clamp_force_n=(
                    float(
                        row[
                            "measured_mean_clamp_force_n"
                        ]
                    )
                ),
            )
        )

        expected_factor = float(
            row["correction_factor"]
        )

        if not math.isclose(
            record.correction_factor,
            expected_factor,
            rel_tol=0.0,
            abs_tol=1.0e-10,
        ):
            raise RuntimeError(
                f"{case_id}: reconstructed warm-start "
                "correction factor does not match "
                "the frozen evidence record."
            )

        records.append(
            record
        )

    return tuple(
        sorted(
            records,
            key=lambda item: (
                item.case_hash,
                item.accepted_run_id,
            ),
        )
    )


def main() -> None:
    arguments = parse_arguments()

    # --------------------------------------------------
    # GOVERNANCE INTEGRITY
    # --------------------------------------------------

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

    anchor_binding_hash = require_sha256(
        ANCHOR_BINDING_PATH,
        EXPECTED_ANCHOR_BINDING_SHA256,
        "Existing-anchor binding record",
    )

    preparation_cert_hash = require_sha256(
        PREPARATION_CERT_PATH,
        EXPECTED_PREPARATION_CERT_SHA256,
        "Production DOE preparation certification",
    )

    warm_knowledge_hash = require_sha256(
        WARM_KNOWLEDGE_PATH,
        EXPECTED_WARM_KNOWLEDGE_SHA256,
        "Production DOE warm-start knowledge",
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

    # Search DESIGN cases only.
    # Holdouts remain sealed.
    try:
        doe_case = next(
            item
            for item in campaign.design_cases
            if item.case_id
            == arguments.case_id
        )
    except StopIteration as exc:
        raise RuntimeError(
            "Requested case is not an authorized "
            "Production DOE design case. "
            "Holdout cases are intentionally "
            f"inaccessible: {arguments.case_id}"
        ) from exc

    if doe_case.source_case_id is not None:
        raise RuntimeError(
            "Existing anchor cases already have "
            "certified FEM evidence and must not "
            "enter new solver preparation: "
            f"{doe_case.case_id}"
        )

    frozen_manifest = json.loads(
        CAMPAIGN_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    try:
        frozen_row = next(
            row
            for row in frozen_manifest[
                "design_cases"
            ]
            if row["case_id"]
            == doe_case.case_id
        )
    except StopIteration as exc:
        raise RuntimeError(
            "Generated DOE case is absent "
            "from the frozen manifest."
        ) from exc

    if (
        frozen_row["case_hash"]
        != doe_case.case_hash
    ):
        raise RuntimeError(
            "Generated DOE case hash does not "
            "match the frozen campaign."
        )

    if (
        frozen_row["mesh_policy_name"]
        != doe_case.mesh_policy_name
    ):
        raise RuntimeError(
            "Generated DOE mesh policy does not "
            "match the frozen campaign."
        )

    if frozen_row[
        "existing_evidence_reuse_planned"
    ]:
        raise RuntimeError(
            "New solver preparation cannot "
            "operate on an existing FEM anchor."
        )

    # --------------------------------------------------
    # REAL GOVERNED FEM PREFLIGHT
    # --------------------------------------------------

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
            "Production FEM preflight BLOCKED "
            f"{doe_case.case_id}: "
            + "; ".join(
                str(finding)
                for finding in blocking
            )
        )

    # --------------------------------------------------
    # RESOLUTION + PREPARED-MESH BINDING
    # --------------------------------------------------

    resolved = resolve_case(
        doe_case.case
    )

    if (
        resolved.case_hash
        != doe_case.case_hash
    ):
        raise RuntimeError(
            "Resolved case hash does not match "
            "the frozen Production DOE hash."
        )

    preparation_cert = json.loads(
        PREPARATION_CERT_PATH.read_text(
            encoding="utf-8"
        )
    )

    preparation_row = (
        find_preparation_row(
            preparation_cert,
            doe_case.case_id,
        )
    )

    if (
        preparation_row["case_hash"]
        != doe_case.case_hash
    ):
        raise RuntimeError(
            "Certified preparation row "
            "case-hash mismatch."
        )

    if (
        preparation_row["mesh_policy_name"]
        != doe_case.mesh_policy_name
    ):
        raise RuntimeError(
            "Certified preparation row "
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
        sha256(mesh_path)
        != preparation_row["mesh_sha256"]
    ):
        raise RuntimeError(
            "Certified prepared mesh hash drift."
        )

    if (
        sha256(step_path)
        != preparation_row["step_sha256"]
    ):
        raise RuntimeError(
            "Certified prepared STEP hash drift."
        )

    # --------------------------------------------------
    # WARM-START KNOWLEDGE
    # --------------------------------------------------

    warm_record = json.loads(
        WARM_KNOWLEDGE_PATH.read_text(
            encoding="utf-8"
        )
    )

    warm_policy_hash = sha256(
        WARM_POLICY_PATH
    )

    if (
        warm_policy_hash
        != warm_record[
            "warm_start_policy"
        ]["policy_sha256"]
    ):
        raise RuntimeError(
            "Warm-start policy drift relative "
            "to frozen knowledge evidence."
        )

    warm_policy = (
        load_fem_warm_start_policy(
            WARM_POLICY_PATH
        )
    )

    if (
        warm_policy.policy_id
        != warm_record[
            "warm_start_policy"
        ]["policy_id"]
    ):
        raise RuntimeError(
            "Warm-start policy identity drift."
        )

    knowledge = (
        build_warm_start_knowledge(
            campaign=campaign,
            warm_record=warm_record,
        )
    )

    seed = (
        derive_analytical_thermal_preload_seed(
            resolved
        )
    )

    prediction = predict_fem_warm_start(
        resolved=resolved,
        seed=seed,
        knowledge=knowledge,
        policy=warm_policy,
    )

    # A new DOE row must not masquerade as
    # exact accepted FEM evidence.
    if (
        prediction.source
        is FemWarmStartSource.EXACT_CASE
    ):
        raise RuntimeError(
            "New Production DOE case unexpectedly "
            "matched exact existing FEM evidence."
        )

    trial = (
        derive_fem_warm_start_preload_calibration_trial(
            predicted_delta_temperature_c=(
                prediction.predicted_delta_temperature_c
            ),
            case_run_id=(
                f"trm_fem_{resolved.case_hash[:12]}"
            ),
        )
    )

    if trial.trial_index != 1:
        raise RuntimeError(
            "Initial Production DOE calibration "
            "must begin with governed Trial 1."
        )

    # --------------------------------------------------
    # FEM DEFINITIONS
    # --------------------------------------------------

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
            "into the FEM definition bundle."
        )

    mesh_data = (
        read_grouped_complete_joint_mesh(
            mesh_path,
            bundle.transfer,
        )
    )

    # --------------------------------------------------
    # TRIAL-1 DECK
    # --------------------------------------------------

    case_run_id = (
        f"trm_fem_{resolved.case_hash[:12]}"
    )

    run_dir = (
        SOLVER_ROOT
        / case_run_id
        / trial.run_id
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path = (
        run_dir
        / f"{trial.run_id}.inp"
    )

    prior_deck_hash = None

    if input_path.exists():
        prior_deck_hash = sha256(
            input_path
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
            "Generated CalculiX deck is "
            "missing or empty."
        )

    actual_deck_hash = sha256(
        input_path
    )

    if actual_deck_hash != deck.sha256:
        raise RuntimeError(
            "Generated deck SHA does not "
            "match deck metadata."
        )

    if (
        prior_deck_hash is not None
        and prior_deck_hash
        != actual_deck_hash
    ):
        raise RuntimeError(
            "Existing solver-preparation deck "
            "changed on deterministic regeneration."
        )

    if deck.trial_run_id != trial.run_id:
        raise RuntimeError(
            "Deck/trial identity mismatch."
        )

    if not math.isclose(
        deck.delta_temperature_c,
        trial.delta_temperature_c,
        rel_tol=0.0,
        abs_tol=1.0e-10,
    ):
        raise RuntimeError(
            "Deck/trial temperature mismatch."
        )

    # --------------------------------------------------
    # IMMUTABLE SOLVER-PREPARATION EVIDENCE
    # --------------------------------------------------

    record = {
        "schema_version": 1,

        "record_id": (
            "TRM-P3-CP8-PDOE-C01-"
            f"{doe_case.case_id}-SOLVER-PREP-T01"
        ),

        "record_status": "FINAL",

        "case": {
            "case_id": doe_case.case_id,
            "case_hash": doe_case.case_hash,
            "run_id": case_run_id,
            "role": doe_case.role,
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
            "anchor_binding_sha256": (
                anchor_binding_hash
            ),
            "preparation_certification_sha256": (
                preparation_cert_hash
            ),
            "warm_start_knowledge_sha256": (
                warm_knowledge_hash
            ),
            "warm_start_policy_sha256": (
                warm_policy_hash
            ),
        },

        "fem_preflight": {
            "target": "fem",
            "blocking_error_count": 0,
            "report": jsonable(
                preflight
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
                relative(step_path)
            ),
            "step_sha256": (
                preparation_row["step_sha256"]
            ),
            "mesh_relative_path": (
                relative(mesh_path)
            ),
            "mesh_sha256": (
                preparation_row["mesh_sha256"]
            ),
        },

        "analytical_seed": (
            jsonable(seed)
        ),

        "warm_start_prediction": {
            **jsonable(prediction),
            "analytical_fallback_is_allowed": (
                True
            ),
            "forced_neighbor_interpolation": (
                False
            ),
        },

        "trial_1": (
            jsonable(trial)
        ),

        "deck": {
            "relative_path": (
                relative(input_path)
            ),
            "sha256": actual_deck_hash,
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

        "solve_authorization": {
            "calculix_invoked": False,
            "solver_authorized_by_this_script": False,
            "holdout_accessed": False,
        },

        "overall_disposition": (
            "PRODUCTION_DOE_TRIAL1_"
            "SOLVER_PREPARATION_PASS"
        ),
    }

    record_path = (
        run_dir
        / "production_doe_solver_preparation_record.json"
    )

    action, record_hash = (
        write_immutable_json(
            record_path,
            record,
        )
    )

    print("=" * 124)
    print(
        "THREADROM — PRODUCTION DOE SOLVER PREPARATION"
    )
    print("=" * 124)

    print(
        "Case ID               :",
        doe_case.case_id,
    )

    print(
        "Case hash             :",
        doe_case.case_hash,
    )

    print(
        "Mesh policy           :",
        doe_case.mesh_policy_name,
    )

    print(
        "FEM preflight         : PASS"
    )

    print(
        "Warm-start source     :",
        prediction.source.value,
    )

    print(
        "Applicability         :",
        prediction.applicability.value,
    )

    print(
        "Neighbors used        :",
        prediction.reused_evidence_count,
    )

    print(
        "Nearest distance      :",
        prediction.nearest_distance,
    )

    print(
        "Analytical dT C       :",
        prediction.analytical_delta_temperature_c,
    )

    print(
        "Predicted Trial-1 dT C:",
        trial.delta_temperature_c,
    )

    print(
        "Trial run ID          :",
        trial.run_id,
    )

    print(
        "Deck SHA256           :",
        actual_deck_hash,
    )

    print(
        "Deck size             :",
        input_path.stat().st_size,
    )

    print(
        "Solver-prep record    :",
        record_path,
    )

    print(
        "Record action         :",
        action,
    )

    print(
        "Record SHA256         :",
        record_hash,
    )

    print(
        "Disposition           : "
        "PRODUCTION_DOE_TRIAL1_"
        "SOLVER_PREPARATION_PASS"
    )

    print(
        "CalculiX invoked      : NO"
    )

    print(
        "Holdouts accessed     : NO"
    )

    print("=" * 124)


if __name__ == "__main__":
    main()

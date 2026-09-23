from __future__ import annotations

import argparse
import hashlib
import json

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
            "Execute one already-prepared Phase-3 "
            "Production DOE Trial-1 CalculiX deck."
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


# Independent Trial-1 launch pins.
# Empty until case-specific authorization and owner approval
# are separately reviewed and their record hashes pinned.
# Never populate from a CLI flag or a file being verified.
INITIAL_TRIAL_AUTHORIZATION_PINS: dict[str, dict[str, str]] = {}


def main() -> int:
    args = parse_arguments()

    # ----------------------------------------------
    # GOVERNANCE INTEGRITY
    # ----------------------------------------------

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

    try:
        doe_case = next(
            item
            for item in campaign.design_cases
            if item.case_id == args.case_id
        )
    except StopIteration as exc:
        raise RuntimeError(
            "Requested case is not an authorized "
            "Production DOE design case. "
            "Holdouts are intentionally inaccessible: "
            f"{args.case_id}"
        ) from exc

    if doe_case.source_case_id is not None:
        raise RuntimeError(
            "Certified FEM anchors must not be rerun: "
            f"{doe_case.case_id}"
        )

    # ----------------------------------------------
    # BIND TO IMMUTABLE TRIAL-1 PREPARATION
    # ----------------------------------------------

    case_run_id = (
        f"trm_fem_{doe_case.case_hash[:12]}"
    )

    trial_run_id = (
        f"{case_run_id}_cal_01"
    )

    run_dir = (
        SOLVER_ROOT
        / case_run_id
        / trial_run_id
    )

    prep_record_path = (
        run_dir
        / "production_doe_solver_preparation_record.json"
    )

    prep_sidecar_path = (
        run_dir
        / "production_doe_solver_preparation_record.sha256"
    )

    if not prep_record_path.is_file():
        raise FileNotFoundError(
            "FINAL solver-preparation record missing: "
            f"{prep_record_path}"
        )

    if not prep_sidecar_path.is_file():
        raise FileNotFoundError(
            "Solver-preparation SHA sidecar missing: "
            f"{prep_sidecar_path}"
        )

    prep = json.loads(
        prep_record_path.read_text(
            encoding="utf-8"
        )
    )

    if prep["record_status"] != "FINAL":
        raise RuntimeError(
            "Solver-preparation record is not FINAL."
        )

    if (
        prep["overall_disposition"]
        != "PRODUCTION_DOE_TRIAL1_SOLVER_PREPARATION_PASS"
    ):
        raise RuntimeError(
            "Solver-preparation disposition is not PASS."
        )

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
        or prep["fem_preflight"][
            "blocking_error_count"
        ]
        != 0
    ):
        raise RuntimeError(
            "FEM preflight is not clean."
        )

    if (
        prep["solve_authorization"]["calculix_invoked"]
        is not False
        or prep["solve_authorization"]["holdout_accessed"]
        is not False
    ):
        raise RuntimeError(
            "Solver-preparation provenance is invalid."
        )

    input_path = (
        ROOT
        / prep["deck"]["relative_path"]
    )

    if sha256(input_path) != prep["deck"]["sha256"]:
        raise RuntimeError(
            "Prepared Trial-1 deck hash drift."
        )

    if (
        input_path.stat().st_size
        != prep["deck"]["size_bytes"]
    ):
        raise RuntimeError(
            "Prepared Trial-1 deck size drift."
        )

    if input_path.name != f"{trial_run_id}.inp":
        raise RuntimeError(
            "Trial/deck identity mismatch."
        )

    # ----------------------------------------------
    # DUPLICATE-SOLVE GUARD
    # ----------------------------------------------

    manifest_path = (
        run_dir
        / "fem_run_manifest.json"
    )

    if manifest_path.exists():
        raise RuntimeError(
            "FEM run manifest already exists. "
            "Refusing accidental duplicate solve: "
            f"{manifest_path}"
        )

    # ----------------------------------------------
    # CERTIFIED BACKEND / TRANSFER
    # ----------------------------------------------

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
        job_name=trial_run_id,

        # Justified production Medium+ solves may
        # legitimately exceed ordinary timeout bounds.
        timeout_seconds=None,
    )

    print(
        "=" * 124,
        flush=True,
    )

    print(
        "THREADROM — PRODUCTION DOE TRIAL-1 FEM START",
        flush=True,
    )

    print(
        "=" * 124,
        flush=True,
    )

    print(
        "Case ID       :",
        doe_case.case_id,
        flush=True,
    )

    print(
        "Case hash     :",
        doe_case.case_hash,
        flush=True,
    )

    print(
        "Trial run ID  :",
        trial_run_id,
        flush=True,
    )

    print(
        "Target N      :",
        prep["case"]["target_preload_n"],
        flush=True,
    )

    print(
        "Trial dT C    :",
        prep["trial_1"]["delta_temperature_c"],
        flush=True,
    )

    print(
        "Warm source   :",
        prep["warm_start_prediction"]["source"],
        flush=True,
    )

    print(
        "Applicability :",
        prep["warm_start_prediction"]["applicability"],
        flush=True,
    )

    print(
        "Deck SHA256   :",
        prep["deck"]["sha256"],
        flush=True,
    )

    print(
        "Timeout       : NONE",
        flush=True,
    )

    print(
        "Manifest      :",
        manifest_path,
        flush=True,
    )

    print(
        "=" * 124,
        flush=True,
    )

    # Verify independently pinned, case/deck-specific permission.
    # This check does not reserve a solver slot or authorize a retry.
    from threadrom.factory.governed_fem_initial_launch_authorization import (
        require_initial_trial_authorization,
    )

    require_initial_trial_authorization(
        repo_root=ROOT,
        campaign_root=CAMPAIGN_MANIFEST_PATH.parent,
        pins=INITIAL_TRIAL_AUTHORIZATION_PINS,
        campaign_id="TRM-PDOE-C01",
        case_id=doe_case.case_id,
        case_hash=doe_case.case_hash,
        case_run_id=case_run_id,
        trial_run_id=trial_run_id,
        deck_sha256=prep["deck"]["sha256"],
        policy_sha256=EXPECTED_DOE_POLICY_SHA256,
        manifest_sha256=EXPECTED_CAMPAIGN_SHA256,
    )

    # The independent authorization check above remains mandatory.
    # The campaign lock stays held until the solver operation returns.
    from threadrom.factory.production_doe_launch_fence import (
        reserve_adaptive_trial_launch,
    )

    with reserve_adaptive_trial_launch(
        campaign_root=CAMPAIGN_MANIFEST_PATH.parent,
        case_run_id=case_run_id,
        trial_run_id=trial_run_id,
        maximum_authorized_ccx=1,
        allow_initial_trial=True,
    ):
        result = orchestrate_calculix_run(
            project_root=ROOT,
            input_path=input_path,
            definition=definition,
            run_id=trial_run_id,
            case_hash=doe_case.case_hash,
            backend_policy_id=backend.policy_id,
            solver_name=backend.solver_name,
            solver_version=backend.solver_version,
            manifest_path=manifest_path,
        )

    print()
    print(
        "=" * 124,
        flush=True,
    )

    print(
        "THREADROM — PRODUCTION DOE TRIAL-1 FEM FINISHED",
        flush=True,
    )

    print(
        "=" * 124,
        flush=True,
    )

    print(
        "Case ID      :",
        doe_case.case_id,
        flush=True,
    )

    print(
        "Trial run ID :",
        trial_run_id,
        flush=True,
    )

    print(
        "Disposition  :",
        result.manifest.disposition,
        flush=True,
    )

    print(
        "Manifest     :",
        result.manifest_path,
        flush=True,
    )

    print(
        "=" * 124,
        flush=True,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

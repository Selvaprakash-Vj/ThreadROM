from __future__ import annotations

import argparse
import hashlib
import json

from pathlib import Path

import math

from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationCampaignPolicy,
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
    evaluate_preload_calibration_trial,
)
from threadrom.factory.production_doe_adaptive_controller import (
    AdaptiveCalibrationAction,
    plan_adaptive_calibration,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)
from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
)

from threadrom.factory.production_doe_continuation_authorization import (
    verify_continuation_authorization,
)
from threadrom.factory.production_doe_launch_fence import (
    reserve_adaptive_trial_launch,
)
from threadrom.factory.fem_solver_orchestrator import (
    orchestrate_calculix_run,
)
from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
)
import threadrom.factory.fem_case_definition_bundle as bundle_mod

from threadrom.factory.adaptive_fem_c01_adapter import (
    decide_c01_lifecycle,
)
from threadrom.factory.adaptive_fem_lifecycle import (
    LifecycleAction,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationCampaignPolicy,
)

from threadrom.factory.production_doe_adaptive_history_planner import (
    plan_from_verified_history,
)

from threadrom.factory.production_doe_adaptive_planner import (
    plan_from_gate0_trial1,
)

from threadrom.factory.production_doe_gate0_evidence import (
    inspect_gate0_trial1,
)

from threadrom.factory.production_doe_case_registry import (
    resolve_governed_c01_case,
)

from threadrom.factory.production_doe_completed_trial import (
    verify_completed_trial,
)
from threadrom.factory.production_doe_launch_fence import (
    MAXIMUM_CONCURRENT_CCX,
    CLAIM_FILENAME,
    count_running_ccx,
)


ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ROOT = (
    ROOT
    / "simulations/staging/phase3_cp8_production_doe"
    / "TRM-PDOE-C01"
)

# First independently pinned real-case evidence. The coordinator
# must fail closed for cases not yet added through governed review.
# Deliberately EMPTY until a separately reviewed, immutable
# authorization is issued and its hash is independently pinned.
# Never derive a trusted hash from the certificate being checked.
# Empty until a real bounded campaign certificate is
# independently reviewed, approved and SHA-pinned.
CAMPAIGN_AUTHORIZATION_PINS = {}

CONTINUATION_AUTHORIZATION_PINS = {}


def execute_generic_governed_continuation(
    *,
    case_id: str,
    case_run_id: str,
    history_plan,
) -> None:
    """Run a governed adaptive C01 trial under bounded campaign approval.

    Approval covers a predefined adaptation envelope, not arbitrary
    model edits, extra trials, full-physics certification or cleanup.
    """

    from threadrom.factory.adaptive_fem_campaign_authorization import (
        verify_adaptive_campaign_authorization,
    )
    from threadrom.factory.adaptive_fem_c01_adapter import (
        C01_CORRECTIVE_RULE,
    )
    from threadrom.factory.production_doe_gate0_evidence import (
        GATE0_CASE_IDS,
    )

    trial_index = history_plan.completed_trial_count + 1
    trial_run_id = f"{case_run_id}_cal_{trial_index:02d}"

    require(
        case_id in GATE0_CASE_IDS
        and 2 <= trial_index <= 6
        and history_plan.state
        == "PREPARED_NEXT_TRIAL_REQUIRES_AUTHORIZATION"
        and history_plan.next_trial_run_id == trial_run_id,
        "BLOCKED_UNSAFE_LIFECYCLE: no governed prepared trial.",
    )

    # This registry must be populated ONLY after independent review
    # and approval of a real campaign certificate. A nearby file,
    # existing preparation or completed predecessor is not approval.
    registration = CAMPAIGN_AUTHORIZATION_PINS.get(
        "TRM-PDOE-C01"
    )

    if registration is None:
        raise RuntimeError(
            "BLOCKED_UNAUTHORIZED: no independently pinned "
            "bounded campaign authorization exists."
        )

    governed_cases = {}

    for governed_id in GATE0_CASE_IDS:
        governed = resolve_governed_c01_case(
            repo_root=ROOT,
            requested_case_id=governed_id,
        )
        governed_cases[governed_id] = (
            governed.case_run_id,
            governed.case_hash,
        )

    require(
        governed_cases[case_id][0] == case_run_id,
        "Governed case/run identity drift.",
    )

    run_dir = SOLVER_ROOT / case_run_id / trial_run_id
    prep_path = (
        run_dir
        / "production_doe_calibration_solver_preparation_record.json"
    )
    deck_path = run_dir / f"{trial_run_id}.inp"

    certificate_path = (
        ROOT / registration["certificate_relative_path"]
    )

    def verify_live_inputs():
        # A fresh history replay independently verifies the completed
        # predecessor, trial sequence and proposed next temperature.
        live = plan_from_verified_history(
            repo_root=ROOT,
            case_id=case_id,
        )

        require(
            live.state
            == "PREPARED_NEXT_TRIAL_REQUIRES_AUTHORIZATION"
            and live.completed_trial_count == trial_index - 1
            and live.last_completed_run_id
            == history_plan.last_completed_run_id
            and live.next_trial_run_id == trial_run_id
            and live.next_delta_temperature_c
            == history_plan.next_delta_temperature_c,
            "Calibration history changed before launch.",
        )

        authorized = verify_adaptive_campaign_authorization(
            certificate_path=certificate_path,
            independently_pinned_sha256=registration[
                "certificate_sha256"
            ],
            expected_campaign_id="TRM-PDOE-C01",
            expected_gate0_sha256=(
                "1de14304d291c8b5c4dfd763bafec414"
                "92128b2cba8eb9471b13c1390b6ecad6"
            ),
            expected_policy_sha256=(
                "43032557cb2abead0118362bcfc6a9b2"
                "e5246a7d363ca83eef5fcf35054befc1"
            ),
            governed_cases=governed_cases,
            case_id=case_id,
            trial_index=trial_index,
            trial_run_id=trial_run_id,
            delta_temperature_c=(
                live.next_delta_temperature_c
            ),
            required_corrective_rule_id=C01_CORRECTIVE_RULE,
            certified_solver_limit=MAXIMUM_CONCURRENT_CCX,
        )

        preparation_sha = sha256(prep_path)
        sidecar = prep_path.with_suffix(".sha256")

        require(
            sidecar.read_text(encoding="ascii")
            == (
                preparation_sha
                + "  "
                + prep_path.name
                + chr(10)
            ),
            "Immutable preparation sidecar drift.",
        )

        preparation = json.loads(
            prep_path.read_text(encoding="utf-8")
        )

        require(
            preparation.get("record_status") == "FINAL"
            and preparation.get("overall_disposition")
            == (
                "PRODUCTION_DOE_NEXT_CALIBRATION_"
                "SOLVER_PREPARATION_PASS"
            )
            and preparation["case"]["case_id"] == case_id
            and preparation["case"]["case_hash"]
            == governed_cases[case_id][1]
            and preparation["case"]["run_id"] == case_run_id
            and preparation["next_trial"]["run_id"]
            == trial_run_id
            and preparation["next_trial"]["trial_index"]
            == trial_index
            and abs(
                float(
                    preparation["next_trial"][
                        "delta_temperature_c"
                    ]
                )
                - authorized.delta_temperature_c
            ) <= 1.0e-10
            and preparation["deck"]["sha256"]
            == sha256(deck_path),
            "Prepared trial identity, temperature or deck drift.",
        )

        return authorized

    # Read-only preflight must succeed before a durable claim exists.
    verify_live_inputs()

    with reserve_adaptive_trial_launch(
        campaign_root=CAMPAIGN_ROOT,
        case_run_id=case_run_id,
        trial_run_id=trial_run_id,
    ):
        # The shared fence reserves the launch, rejects duplicates,
        # and checks live global CalculiX occupancy.
        authorization = verify_live_inputs()

        transfer = load_complete_joint_calculix_transfer_definition(
            ROOT / "config/complete_joint_calculix_transfer.toml"
        )
        backend = (
            bundle_mod.PHASE2_CERTIFIED_FEM_PROFILE.backend
        )
        definition = CalculixJobDefinition(
            executable_relative_path=(
                transfer.executable_relative_path
            ),
            job_name=trial_run_id,
            timeout_seconds=None,
        )

        print(
            "GOVERNED CAMPAIGN TRIAL AUTHORIZED:",
            case_id,
            trial_index,
            authorization.certificate_sha256,
            flush=True,
        )

        result = orchestrate_calculix_run(
            project_root=ROOT,
            input_path=deck_path,
            definition=definition,
            run_id=trial_run_id,
            case_hash=governed_cases[case_id][1],
            backend_policy_id=backend.policy_id,
            solver_name=backend.solver_name,
            solver_version=backend.solver_version,
            manifest_path=(
                run_dir / "fem_run_manifest.json"
            ),
        )

        require(
            str(result.manifest.disposition) == "succeeded",
            "CalculiX did not produce a successful run disposition.",
        )

        print(
            "GOVERNED TRIAL COMPLETED:",
            case_id,
            trial_index,
            trial_run_id,
            flush=True,
        )


def execute_governed_continuation(
    *,
    case_id: str,
    pins: dict,
    verified_predecessor,
    prep2_path: Path,
    trial2_dir: Path,
    trial2_id: str,
    deck_path: Path,
) -> None:
    registered = CONTINUATION_AUTHORIZATION_PINS.get(case_id)
    if registered is None:
        raise RuntimeError(
            "BLOCKED_UNAUTHORIZED: no independently pinned "
            "continuation authorization exists."
        )

    # Never infer authorization from preparation status or an adjacent
    # certificate sidecar. Its SHA must be approved independently.
    authorization = verify_continuation_authorization(
        certificate_path=ROOT / registered["certificate_relative_path"],
        expected_certificate_sha256=registered["certificate_sha256"],
        expected_gate0_certificate_sha256=registered["gate0_sha256"],
        expected_case_id=case_id,
        expected_case_run_id=pins["case_run_id"],
        requested_trial_index=2,
    )

    # Hold the shared campaign lock across the entire solver operation.
    # The fence checks live capacity and creates a durable, exclusive
    # launch claim. It never removes that claim automatically.
    with reserve_adaptive_trial_launch(
        campaign_root=CAMPAIGN_ROOT,
        case_run_id=pins["case_run_id"],
        trial_run_id=trial2_id,
    ):
        # Recheck immutable inputs *inside* the launch lock. The
        # decision was recomputed earlier from the pinned DAT evidence;
        # the same predecessor and preparation must still be present.
        reverified = verify_completed_trial(
            repo_root=ROOT,
            manifest_path=verified_predecessor.manifest_path,
            expected_run_id=verified_predecessor.run_id,
            expected_case_hash=pins["case_hash"],
            expected_deck_sha256=(
                verified_predecessor.deck_sha256
            ),
        )
        require(
            reverified.dat_sha256 == pins["trial1_dat_sha256"]
            and sha256(prep2_path) == pins["trial2_prep_sha256"]
            and sha256(deck_path) == pins["trial2_deck_sha256"],
            "Evidence changed between preflight and launch lock.",
        )

        # Pin the certified backend and transfer definition. A
        # preparation record cannot select an arbitrary executable.
        transfer = load_complete_joint_calculix_transfer_definition(
            ROOT / "config/complete_joint_calculix_transfer.toml"
        )
        backend = (
            bundle_mod.PHASE2_CERTIFIED_FEM_PROFILE.backend
        )
        definition = CalculixJobDefinition(
            executable_relative_path=(
                transfer.executable_relative_path
            ),
            job_name=trial2_id,
            timeout_seconds=None,
        )

        print(
            "GOVERNED CONTINUATION AUTHORIZED:",
            authorization.certificate_sha256,
            flush=True,
        )

        result = orchestrate_calculix_run(
            project_root=ROOT,
            input_path=deck_path,
            definition=definition,
            run_id=trial2_id,
            case_hash=pins["case_hash"],
            backend_policy_id=backend.policy_id,
            solver_name=backend.solver_name,
            solver_version=backend.solver_version,
            manifest_path=(
                trial2_dir / "fem_run_manifest.json"
            ),
        )

        require(
            str(result.manifest.disposition) == "succeeded",
            "CalculiX did not produce a successful run disposition.",
        )

        print(
            "CONTINUATION SOLVER FINISHED:",
            trial2_id,
            flush=True,
        )


CASE_PINS = {
    "D-INT-012": {
        "case_run_id": "trm_fem_d667bb1aca27",
        "case_hash": (
            "d667bb1aca2720b10e8a80dbcfba700"
            "b042b45a20289927feb5e97a33f3b244c"
        ),
        "trial1_suffix": "_cal_01_wsv21_rfobs1",
        "trial1_prep_sha256": (
            "b5a88ff926b49c774d1f209162e077409"
            "93eacd392ee8b72ede8c57a44f366be"
        ),
        "trial1_dat_sha256": (
            "bb39bee9dbb9ec612c94a26d454ce18"
            "aa5d50b478149952ec5102ce2e5bc55da"
        ),
        "trial2_prep_sha256": (
            "f6220448d9329ac36c696f0f1ec4e662"
            "363e4ea887543c7d708d735ba1bade2a"
        ),
        "trial2_deck_sha256": (
            "a26501fdf88b8b9ebe8bbef0f232875"
            "ce47d4b957eab810b8a59ef40c01c37ec"
        ),
    },
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only governed adaptive-factory preflight. "
            "No solver-launch option exists."
        )
    )
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    # All five cases enter through the same frozen Gate-0 evidence
    # boundary. An unfinished Trial 1 must never be rerun simply
    # because its completed manifest is not yet present.
    gate0_evidence = inspect_gate0_trial1(
        repo_root=ROOT,
        requested_case_id=args.case_id,
    )

    if (
        gate0_evidence.completion_status
        != "COMPLETED_INPUT_EVIDENCE_VERIFIED"
    ):
        if args.execute:
            raise RuntimeError(
                "BLOCKED_PENDING_PREDECESSOR: completed Trial-1 "
                "evidence is not available; no replacement solve "
                "or continuation is authorized."
            )

        print(
            args.case_id,
            gate0_evidence.completion_status,
            gate0_evidence.run_id,
        )
        print("Continuation disposition: BLOCKED_PENDING_PREDECESSOR")
        print("CalculiX invoked: NO")
        return 2

    # Every completed Gate-0 case uses its own verified DAT
    # measurement and governed calibration decision.
    trial1_plan = plan_from_gate0_trial1(
        repo_root=ROOT,
        case_id=args.case_id,
    )

    require(
        trial1_plan.completed_trial_run_id
        == gate0_evidence.run_id
        and trial1_plan.state != "WAIT_FOR_COMPLETED_TRIAL",
        "Adaptive planner disagrees with verified predecessor state.",
    )

    if trial1_plan.next_trial_run_id is None:
        if args.execute:
            raise RuntimeError(
                "BLOCKED_NO_CONTINUATION: calibration has no "
                "authorized next trial."
            )

        print(args.case_id, trial1_plan.state)
        print(
            "Calibration disposition: "
            "NO_NEXT_TRIAL; FULL_PHYSICS_REVIEW_SEPARATE"
        )
        print("CalculiX invoked: NO")
        return 0

    # Recover and recompute the complete verified calibration
    # history before entering the existing Trial-2 execution path.
    history_plan = plan_from_verified_history(
        repo_root=ROOT,
        case_id=args.case_id,
    )

    require(
        history_plan.case_id == args.case_id
        and history_plan.completed_trial_count >= 1
        and history_plan.last_completed_run_id is not None,
        "Recovered calibration history is inconsistent.",
    )

    # The universal lifecycle decides the next type of action.
    # The C01 adapter supplies only governed C01-specific state.
    case_run_id_from_gate0 = gate0_evidence.run_id.removesuffix(
        "_cal_01_wsv21_rfobs1"
    )

    lifecycle_decision = decide_c01_lifecycle(
        history_plan=history_plan,
        case_run_id=case_run_id_from_gate0,
        campaign_root=CAMPAIGN_ROOT,
        maximum_trials=(
            PreloadCalibrationCampaignPolicy().maximum_trials
        ),
    )

    print(
        "Universal lifecycle action:",
        lifecycle_decision.action.value,
    )

    if (
        args.execute
        and lifecycle_decision.action
        is not LifecycleAction.REQUEST_GOVERNED_LAUNCH
    ):
        raise RuntimeError(
            "BLOCKED_UNSAFE_LIFECYCLE: no new solver launch "
            "is permitted for the recovered run state."
        )

    # All governed C01 trials now use the same parametric
    # execution route. Never fall through to the legacy
    # D-INT-012/Trial-2-only launch function.
    if args.execute:
        execute_generic_governed_continuation(
            case_id=args.case_id,
            case_run_id=case_run_id_from_gate0,
            history_plan=history_plan,
        )
        return 0

    # A single completed Trial 1 must produce the same next-run
    # identity as the independently evaluated Trial-1 planner.
    if history_plan.completed_trial_count == 1:
        require(
            history_plan.next_trial_run_id
            == trial1_plan.next_trial_run_id,
            "Recovered history disagrees with the Trial-1 decision.",
        )

    # The existing execution function still targets Trial 2 only.
    # Later-trial decisions and unprepared trials must never fall
    # through to that function. Their generic execution path will
    # be implemented behind the same authorization/launch fence.
    if (
        history_plan.completed_trial_count != 1
        or history_plan.state
        != "PREPARED_NEXT_TRIAL_REQUIRES_AUTHORIZATION"
    ):
        if args.execute:
            raise RuntimeError(
                "BLOCKED_GENERIC_EXECUTION_NOT_CERTIFIED: "
                "recovered continuation requires the governed "
                "multi-trial execution path."
            )

        print("Case:", args.case_id)
        print("Recovered state:", history_plan.state)
        print(
            "Completed trials:",
            history_plan.completed_trial_count,
        )
        print(
            "Next trial:",
            history_plan.next_trial_run_id,
        )
        print(
            "Next delta T:",
            history_plan.next_delta_temperature_c,
        )
        print("CalculiX invoked: NO")

        return (
            0
            if history_plan.state
            == "CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS"
            else 2
        )

    if args.case_id not in CASE_PINS:
        # Every governed C01 case has already passed frozen Gate-0
        # verification, complete-history recovery and the universal
        # lifecycle decision above. Legacy CASE_PINS are specific to
        # D-INT-012's Trial-2 execution path, NOT a condition for
        # read-only planning of other C01 cases.
        #
        # No other case may fall through to that legacy runner.
        if args.execute:
            raise RuntimeError(
                "BLOCKED_GENERIC_EXECUTION_NOT_CERTIFIED: "
                "multi-case execution requires an independently "
                "authorized, trial-specific generic launch path."
            )

        print("=" * 76)
        print("THREADROM ? GOVERNED MULTI-CASE LIFECYCLE PREFLIGHT")
        print("=" * 76)
        print("Case:", args.case_id)
        print("Verified predecessor:", history_plan.last_completed_run_id)
        print("Completed trials:", history_plan.completed_trial_count)
        print("Recovered state:", history_plan.state)
        print("Universal action:", lifecycle_decision.action.value)
        print("Next trial:", history_plan.next_trial_run_id)
        print(
            "Next delta T:",
            history_plan.next_delta_temperature_c,
        )
        print("Generic execution: NOT YET CERTIFIED")
        print("CalculiX invoked: NO")
        print("=" * 76)
        return 0

    require(
        args.case_id in CASE_PINS,
        "Case has no independently pinned adaptive-factory evidence.",
    )
    governed_case = resolve_governed_c01_case(
        repo_root=ROOT,
        requested_case_id=args.case_id,
    )
    pins = CASE_PINS[args.case_id]

    require(
        pins["case_run_id"] == governed_case.case_run_id
        and pins["case_hash"] == governed_case.case_hash,
        "Pinned evidence differs from frozen C01 case identity.",
    )

    case_run_id = pins["case_run_id"]
    trial1_id = case_run_id + pins["trial1_suffix"]
    trial2_id = case_run_id + "_cal_02"

    case_dir = (
        CAMPAIGN_ROOT
        / "solver_preparation"
        / case_run_id
    )
    trial1_dir = case_dir / trial1_id
    trial2_dir = case_dir / trial2_id

    prep1_path = (
        trial1_dir
        / "production_doe_reaction_observable_revision_record.json"
    )
    prep2_path = (
        trial2_dir
        / "production_doe_calibration_solver_preparation_record.json"
    )

    require(
        sha256(prep1_path) == pins["trial1_prep_sha256"],
        "Frozen Trial-1 preparation SHA mismatch.",
    )
    prep1 = json.loads(prep1_path.read_text(encoding="utf-8"))

    require(
        prep1["case"]["case_id"] == args.case_id
        and prep1["case"]["case_hash"] == pins["case_hash"]
        and prep1["trial"]["run_id"] == trial1_id
        and prep1["trial"]["trial_index"] == 1,
        "Frozen Trial-1 preparation identity mismatch.",
    )

    verified1 = verify_completed_trial(
        repo_root=ROOT,
        manifest_path=trial1_dir / "fem_run_manifest.json",
        expected_run_id=trial1_id,
        expected_case_hash=pins["case_hash"],
        expected_deck_sha256=prep1["deck"]["sha256"],
    )

    require(
        verified1.dat_sha256 == pins["trial1_dat_sha256"],
        "Completed Trial-1 DAT differs from pinned evidence.",
    )

    require(
        sha256(prep2_path) == pins["trial2_prep_sha256"],
        "Frozen Trial-2 preparation SHA mismatch.",
    )

    sidecar_path = prep2_path.with_suffix(".sha256")
    expected_sidecar = (
        f'{pins["trial2_prep_sha256"]}  {prep2_path.name}\n'
    )
    require(
        sidecar_path.read_text(encoding="ascii")
        == expected_sidecar,
        "Trial-2 preparation SHA sidecar mismatch.",
    )

    prep2 = json.loads(prep2_path.read_text(encoding="utf-8"))
    trial2 = prep2["next_trial"]

    require(
        prep2["record_status"] == "FINAL"
        and prep2["overall_disposition"]
        == "PRODUCTION_DOE_NEXT_CALIBRATION_SOLVER_PREPARATION_PASS"
        and prep2["case"]["case_id"] == args.case_id
        and prep2["case"]["case_hash"] == pins["case_hash"]
        and trial2["run_id"] == trial2_id
        and trial2["trial_index"] == 2
        and prep2["fem_preflight"]["status"] == "PASS",
        "Trial-2 preparation status or lineage mismatch.",
    )

    solve_provenance = prep2["solve_authorization"]
    require(
        solve_provenance["calculix_invoked"] is False
        and solve_provenance["solver_authorized_by_this_script"] is False
        and solve_provenance["holdout_accessed"] is False,
        "Trial-2 preparation provenance is not clean.",
    )

    deck_path = trial2_dir / f"{trial2_id}.inp"
    require(
        prep2["deck"]["relative_path"]
        == deck_path.relative_to(ROOT).as_posix()
        and prep2["deck"]["sha256"]
        == pins["trial2_deck_sha256"]
        and deck_path.stat().st_size
        == prep2["deck"]["size_bytes"]
        and sha256(deck_path) == pins["trial2_deck_sha256"],
        "Prepared Trial-2 deck identity, size or SHA mismatch.",
    )

    # Recompute the calibration decision from verified predecessor
    # evidence. A prepared Trial 2 is never accepted merely because
    # its preparation record and deck are internally consistent.
    contact = load_complete_joint_contact_definition(
        ROOT / "config/complete_joint_contact.toml"
    )
    preload = load_complete_joint_preload_definition(
        ROOT / "config/complete_joint_preload.toml"
    )

    measurement = extract_clamp_force_measurement_from_dat(
        dat_path=verified1.dat_path,
        contact_pairs=contact.contact_pairs,
    ).measurement

    completed_trial = PreloadCalibrationTrial(
        trial_index=1,
        run_id=trial1_id,
        delta_temperature_c=float(
            prep1["trial"]["delta_temperature_c"]
        ),
        source=PreloadCalibrationTrialSource.FEM_WARM_START,
    )

    evaluation = evaluate_preload_calibration_trial(
        case_run_id=case_run_id,
        target_force_n=float(prep1["case"]["target_preload_n"]),
        target_relative_tolerance=preload.target_relative_tolerance,
        spread_relative_tolerance=(
            preload.interface_spread_relative_tolerance
        ),
        current_trial=completed_trial,
        measurement=measurement,
        previous_trial=None,
        previous_measurement=None,
    )

    plan = plan_adaptive_calibration(
        case_run_id=case_run_id,
        evaluation=evaluation,
        maximum_trials=(
            PreloadCalibrationCampaignPolicy().maximum_trials
        ),
    )

    require(
        plan.action
        is AdaptiveCalibrationAction.NEXT_TRIAL_REQUIRES_AUTHORIZATION
        and plan.completed_run_id == trial1_id
        and plan.next_run_id == trial2_id
        and evaluation.next_trial is not None
        and trial2["run_id"] == evaluation.next_trial.run_id
        and trial2["trial_index"]
        == evaluation.next_trial.trial_index
        and math.isclose(
            float(trial2["delta_temperature_c"]),
            evaluation.next_trial.delta_temperature_c,
            rel_tol=0.0,
            abs_tol=1.0e-10,
        ),
        "Prepared continuation does not match the independently "
        "recomputed, governed calibration decision.",
    )

    require(
        trial1_plan.state == plan.action.value
        and trial1_plan.next_trial_run_id == plan.next_run_id
        and trial1_plan.next_delta_temperature_c is not None
        and evaluation.next_trial is not None
        and math.isclose(
            trial1_plan.next_delta_temperature_c,
            evaluation.next_trial.delta_temperature_c,
            rel_tol=0.0,
            abs_tol=1.0e-10,
        ),
        "Shared case-independent planner disagrees with "
        "the independently recomputed continuation.",
    )

    duplicate_indicators = [
        trial2_dir / "fem_run_manifest.json",
        trial2_dir / CLAIM_FILENAME,
        *(
            trial2_dir / f"{trial2_id}.{extension}"
            for extension in (
                "sta", "dat", "frd", "rout", "cvg",
                "stdout.log", "stderr.log",
            )
        ),
    ]
    present = [
        path.name for path in duplicate_indicators
        if path.exists()
    ]
    require(
        not present,
        "Trial-2 launch evidence already exists; "
        f"manual disposition required: {present}",
    )

    running_ccx = count_running_ccx()

    print("=" * 76)
    print("THREADROM — ADAPTIVE FACTORY READ-ONLY PREFLIGHT")
    print("=" * 76)
    print("Case:", args.case_id)
    print("Verified predecessor:", verified1.run_id)
    print("Prepared continuation:", trial2_id)
    print("Prepared deck SHA256:", pins["trial2_deck_sha256"])
    print("Duplicate-run indicators: NONE")
    print(
        "CalculiX occupancy snapshot:",
        f"{running_ccx}/{MAXIMUM_CONCURRENT_CCX}",
    )
    print(
        "Capacity snapshot:",
        "FULL" if running_ccx >= MAXIMUM_CONCURRENT_CCX
        else "BELOW LIMIT — NOT A SLOT RESERVATION",
    )
    if args.execute:
        execute_governed_continuation(
            case_id=args.case_id,
            pins=pins,
            verified_predecessor=verified1,
            prep2_path=prep2_path,
            trial2_dir=trial2_dir,
            trial2_id=trial2_id,
            deck_path=deck_path,
        )
        return 0

    print("Continuation authorization: NOT YET PINNED")
    print("Launch disposition: BLOCKED_UNAUTHORIZED")
    print("CalculiX invoked: NO")
    print("=" * 76)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

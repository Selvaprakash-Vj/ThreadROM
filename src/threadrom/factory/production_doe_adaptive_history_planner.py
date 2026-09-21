from __future__ import annotations

import hashlib
import json
import math

from dataclasses import dataclass
from pathlib import Path

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
from threadrom.factory.production_doe_case_registry import (
    resolve_governed_c01_case,
)
from threadrom.factory.production_doe_completed_trial import (
    verify_completed_trial,
)
from threadrom.factory.production_doe_gate0_evidence import (
    inspect_gate0_trial1,
)
from threadrom.factory.production_doe_trial_history import (
    recover_trial_history,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)
from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
)


@dataclass(frozen=True, slots=True)
class AdaptiveHistoryPlan:
    case_id: str
    state: str
    completed_trial_count: int
    last_completed_run_id: str | None
    next_trial_run_id: str | None
    next_delta_temperature_c: float | None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def plan_from_verified_history(
    *,
    repo_root: Path,
    case_id: str,
) -> AdaptiveHistoryPlan:
    """Recompute every completed C01 calibration decision; never run FEM."""

    root = repo_root.resolve(strict=True)
    governed = resolve_governed_c01_case(
        repo_root=root,
        requested_case_id=case_id,
    )
    history = recover_trial_history(
        repo_root=root,
        case_id=case_id,
    )

    if history.state == "WAIT_FOR_TRIAL_1_COMPLETION":
        return AdaptiveHistoryPlan(
            case_id=case_id,
            state="WAIT_FOR_COMPLETED_TRIAL",
            completed_trial_count=0,
            last_completed_run_id=None,
            next_trial_run_id=None,
            next_delta_temperature_c=None,
        )

    evidence = inspect_gate0_trial1(
        repo_root=root,
        requested_case_id=case_id,
    )

    if (
        evidence.completion_status
        != "COMPLETED_INPUT_EVIDENCE_VERIFIED"
        or not history.completed_run_ids
        or history.completed_run_ids[0] != evidence.run_id
    ):
        raise RuntimeError("Gate-0 trial-history lineage mismatch.")

    case_dir = (
        root
        / "simulations/staging/phase3_cp8_production_doe"
        / "TRM-PDOE-C01/solver_preparation"
        / governed.case_run_id
    )

    trial1_prep = json.loads(
        (
            case_dir
            / evidence.run_id
            / "production_doe_reaction_observable_revision_record.json"
        ).read_text(encoding="utf-8-sig")
    )

    target_force_n = float(
        trial1_prep["case"]["target_preload_n"]
    )

    contact = load_complete_joint_contact_definition(
        root / "config/complete_joint_contact.toml"
    )
    preload = load_complete_joint_preload_definition(
        root / "config/complete_joint_preload.toml"
    )
    maximum_trials = (
        PreloadCalibrationCampaignPolicy().maximum_trials
    )

    if not 1 <= len(history.completed_run_ids) <= maximum_trials:
        raise RuntimeError("Completed trial count exceeds governed bounds.")

    previous_trial = None
    previous_measurement = None
    expected_current_trial = None
    final_evaluation = None
    final_plan = None

    for trial_index, run_id in enumerate(
        history.completed_run_ids,
        start=1,
    ):
        run_dir = case_dir / run_id

        if trial_index == 1:
            trial = PreloadCalibrationTrial(
                trial_index=1,
                run_id=run_id,
                delta_temperature_c=float(
                    trial1_prep["trial"]["delta_temperature_c"]
                ),
                source=PreloadCalibrationTrialSource.FEM_WARM_START,
            )
            expected_deck_sha = evidence.deck_sha256

        else:
            if expected_current_trial is None:
                raise RuntimeError(
                    "Calibration history continues after a terminal decision."
                )

            prep_path = (
                run_dir
                / "production_doe_calibration_solver_preparation_record.json"
            )
            prep = json.loads(
                prep_path.read_text(encoding="utf-8-sig")
            )
            prepared = prep["next_trial"]

            if (
                prepared["run_id"] != expected_current_trial.run_id
                or prepared["trial_index"]
                != expected_current_trial.trial_index
                or prepared["source"]
                != expected_current_trial.source.value
                or not math.isclose(
                    float(prepared["delta_temperature_c"]),
                    expected_current_trial.delta_temperature_c,
                    rel_tol=0.0,
                    abs_tol=1.0e-10,
                )
            ):
                raise RuntimeError(
                    "Completed trial differs from the preceding "
                    "governed calibration decision."
                )

            trial = expected_current_trial
            expected_deck_sha = prep["deck"]["sha256"]

        verified = verify_completed_trial(
            repo_root=root,
            manifest_path=run_dir / "fem_run_manifest.json",
            expected_run_id=run_id,
            expected_case_hash=governed.case_hash,
            expected_deck_sha256=expected_deck_sha,
        )

        if (
            trial_index == 1
            and verified.dat_sha256
            != evidence.completed_dat_sha256
        ):
            raise RuntimeError("Frozen Trial-1 DAT evidence drift.")

        measurement = extract_clamp_force_measurement_from_dat(
            dat_path=verified.dat_path,
            contact_pairs=contact.contact_pairs,
        ).measurement

        if _sha256(verified.dat_path) != verified.dat_sha256:
            raise RuntimeError(
                "Completed calibration DAT changed during evaluation."
            )

        evaluation = evaluate_preload_calibration_trial(
            case_run_id=governed.case_run_id,
            target_force_n=target_force_n,
            target_relative_tolerance=(
                preload.target_relative_tolerance
            ),
            spread_relative_tolerance=(
                preload.interface_spread_relative_tolerance
            ),
            current_trial=trial,
            measurement=measurement,
            previous_trial=previous_trial,
            previous_measurement=previous_measurement,
        )

        plan = plan_adaptive_calibration(
            case_run_id=governed.case_run_id,
            evaluation=evaluation,
            maximum_trials=maximum_trials,
        )

        if (
            trial_index < len(history.completed_run_ids)
            and plan.action
            is not AdaptiveCalibrationAction
            .NEXT_TRIAL_REQUIRES_AUTHORIZATION
        ):
            raise RuntimeError(
                "Completed FEM trial exists after calibration termination."
            )

        previous_trial = trial
        previous_measurement = measurement
        expected_current_trial = evaluation.next_trial
        final_evaluation = evaluation
        final_plan = plan

    if final_plan is None or final_evaluation is None:
        raise RuntimeError("No verified calibration decision.")

    next_trial = final_evaluation.next_trial

    if next_trial is None:
        if (
            final_plan.action
            is not AdaptiveCalibrationAction
            .CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS
        ):
            raise RuntimeError("Terminal calibration disposition mismatch.")

        if history.state == "PREPARED_TRIAL_NOT_COMPLETED":
            raise RuntimeError(
                "A later trial was prepared after calibration acceptance."
            )

        return AdaptiveHistoryPlan(
            case_id=case_id,
            state="CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS",
            completed_trial_count=len(history.completed_run_ids),
            last_completed_run_id=history.completed_run_ids[-1],
            next_trial_run_id=None,
            next_delta_temperature_c=None,
        )

    if (
        history.next_trial_index != next_trial.trial_index
        or final_plan.next_run_id != next_trial.run_id
    ):
        raise RuntimeError(
            "Recovered next-trial index differs from calibration decision."
        )

    if history.state == "PREPARED_TRIAL_NOT_COMPLETED":
        run_dir = case_dir / next_trial.run_id
        prep = json.loads(
            (
                run_dir
                / "production_doe_calibration_solver_preparation_record.json"
            ).read_text(encoding="utf-8-sig")
        )
        prepared = prep["next_trial"]

        if (
            prepared["run_id"] != next_trial.run_id
            or prepared["trial_index"] != next_trial.trial_index
            or prepared["source"] != next_trial.source.value
            or not math.isclose(
                float(prepared["delta_temperature_c"]),
                next_trial.delta_temperature_c,
                rel_tol=0.0,
                abs_tol=1.0e-10,
            )
        ):
            raise RuntimeError(
                "Prepared next trial differs from governed decision."
            )

        next_state = "PREPARED_NEXT_TRIAL_REQUIRES_AUTHORIZATION"

    elif history.state == "NEXT_TRIAL_NOT_PREPARED":
        next_state = "NEXT_TRIAL_PREPARATION_REQUIRED"

    else:
        raise RuntimeError(
            f"Inconsistent recovered history state: {history.state}"
        )

    return AdaptiveHistoryPlan(
        case_id=case_id,
        state=next_state,
        completed_trial_count=len(history.completed_run_ids),
        last_completed_run_id=history.completed_run_ids[-1],
        next_trial_run_id=next_trial.run_id,
        next_delta_temperature_c=next_trial.delta_temperature_c,
    )

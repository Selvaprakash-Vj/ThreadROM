from __future__ import annotations

import hashlib
import json

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
    plan_adaptive_calibration,
)
from threadrom.factory.production_doe_case_registry import (
    resolve_governed_c01_case,
)
from threadrom.factory.production_doe_gate0_evidence import (
    inspect_gate0_trial1,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)
from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
)


@dataclass(frozen=True, slots=True)
class AdaptiveTrial1State:
    case_id: str
    completed_trial_run_id: str
    state: str
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


def plan_from_gate0_trial1(
    *,
    repo_root: Path,
    case_id: str,
) -> AdaptiveTrial1State:
    """Recompute a case-specific decision from certified Trial-1 evidence.

    No file creation, solver authorization, or FEM execution occurs here.
    """

    root = repo_root.resolve(strict=True)

    evidence = inspect_gate0_trial1(
        repo_root=root,
        requested_case_id=case_id,
    )

    if evidence.completion_status == "PENDING_COMPLETED_MANIFEST":
        return AdaptiveTrial1State(
            case_id=case_id,
            completed_trial_run_id=evidence.run_id,
            state="WAIT_FOR_COMPLETED_TRIAL",
            next_trial_run_id=None,
            next_delta_temperature_c=None,
        )

    if evidence.completion_status != "COMPLETED_INPUT_EVIDENCE_VERIFIED":
        raise RuntimeError(
            f"Unrecognized completed-trial state: "
            f"{evidence.completion_status}"
        )

    governed_case = resolve_governed_c01_case(
        repo_root=root,
        requested_case_id=case_id,
    )

    case_dir = (
        root
        / "simulations/staging/phase3_cp8_production_doe"
        / "TRM-PDOE-C01/solver_preparation"
        / governed_case.case_run_id
    )

    trial_dir = case_dir / evidence.run_id
    prep_path = (
        trial_dir
        / "production_doe_reaction_observable_revision_record.json"
    )
    dat_path = trial_dir / f"{evidence.run_id}.dat"

    if _sha256(prep_path) != evidence.preparation_sha256:
        raise RuntimeError(
            "Trial-1 preparation changed after Gate-0 verification."
        )

    if _sha256(dat_path) != evidence.completed_dat_sha256:
        raise RuntimeError(
            "Completed Trial-1 DAT changed after verification."
        )

    prep = json.loads(
        prep_path.read_text(encoding="utf-8-sig")
    )

    if (
        prep["case"]["case_id"] != case_id
        or prep["case"]["case_hash"] != governed_case.case_hash
        or prep["trial"]["run_id"] != evidence.run_id
        or prep["trial"]["trial_index"] != 1
    ):
        raise RuntimeError("Calibration predecessor identity mismatch.")

    contact = load_complete_joint_contact_definition(
        root / "config/complete_joint_contact.toml"
    )
    preload = load_complete_joint_preload_definition(
        root / "config/complete_joint_preload.toml"
    )

    measurement = extract_clamp_force_measurement_from_dat(
        dat_path=dat_path,
        contact_pairs=contact.contact_pairs,
    ).measurement

    # Detect a DAT replacement during extraction as well.
    if _sha256(dat_path) != evidence.completed_dat_sha256:
        raise RuntimeError(
            "Completed Trial-1 DAT changed during calibration extraction."
        )

    trial = PreloadCalibrationTrial(
        trial_index=1,
        run_id=evidence.run_id,
        delta_temperature_c=float(
            prep["trial"]["delta_temperature_c"]
        ),
        source=PreloadCalibrationTrialSource.FEM_WARM_START,
    )

    evaluation = evaluate_preload_calibration_trial(
        case_run_id=governed_case.case_run_id,
        target_force_n=float(
            prep["case"]["target_preload_n"]
        ),
        target_relative_tolerance=(
            preload.target_relative_tolerance
        ),
        spread_relative_tolerance=(
            preload.interface_spread_relative_tolerance
        ),
        current_trial=trial,
        measurement=measurement,
        previous_trial=None,
        previous_measurement=None,
    )

    plan = plan_adaptive_calibration(
        case_run_id=governed_case.case_run_id,
        evaluation=evaluation,
        maximum_trials=(
            PreloadCalibrationCampaignPolicy().maximum_trials
        ),
    )

    next_trial = evaluation.next_trial

    return AdaptiveTrial1State(
        case_id=case_id,
        completed_trial_run_id=evidence.run_id,
        state=plan.action.value,
        next_trial_run_id=plan.next_run_id,
        next_delta_temperature_c=(
            next_trial.delta_temperature_c
            if next_trial is not None
            else None
        ),
    )

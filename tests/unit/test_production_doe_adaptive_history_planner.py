from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import tempfile
import sys

import threadrom.factory.production_doe_adaptive_history_planner as planner

from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
)
from threadrom.factory.preload_calibration_controller import (
    PreloadCalibrationDisposition,
)


@pytest.fixture
def tmp_path():
    """Keep deep synthetic FEM paths below Windows path limits."""
    root = Path.cwd().anchor if sys.platform == "win32" else None
    with tempfile.TemporaryDirectory(
        prefix="trm-test-",
        dir=root,
    ) as directory:
        yield Path(directory)


CASE_ID = "D-INT-012"
CASE_RUN_ID = "trm_fem_d667bb1aca27"
TRIAL1_ID = f"{CASE_RUN_ID}_cal_01_wsv21_rfobs1"


def build_synthetic_history(
    tmp_path,
    monkeypatch,
    *,
    completed_count,
    accepted_at=None,
    corrupt_trial=None,
):
    """Isolate the multi-trial state machine from real FEM evidence."""

    root = tmp_path
    case_dir = (
        root
        / "simulations/staging/phase3_cp8_production_doe"
        / "TRM-PDOE-C01/solver_preparation"
        / CASE_RUN_ID
    )
    case_dir.mkdir(parents=True)

    run_ids = [TRIAL1_ID] + [
        f"{CASE_RUN_ID}_cal_{index:02d}"
        for index in range(2, completed_count + 1)
    ]

    for index, run_id in enumerate(run_ids, start=1):
        run_dir = case_dir / run_id
        run_dir.mkdir()
        (run_dir / f"{run_id}.dat").write_text(
            str(index),
            encoding="ascii",
        )

        if index > 1:
            temperature = -260.0 - (index - 1)
            if index == corrupt_trial:
                temperature += 5.0

            prep = {
                "next_trial": {
                    "run_id": run_id,
                    "trial_index": index,
                    "source": (
                        PreloadCalibrationTrialSource.FEM_WARM_START.value
                    ),
                    "delta_temperature_c": temperature,
                },
                "deck": {"sha256": "b" * 64},
            }
            (run_dir /
             "production_doe_calibration_solver_preparation_record.json"
            ).write_text(
                __import__("json").dumps(prep),
                encoding="utf-8",
            )

    trial1_prep = {
        "case": {"target_preload_n": 20000.0},
        "trial": {"delta_temperature_c": -260.0},
    }
    (case_dir / TRIAL1_ID /
     "production_doe_reaction_observable_revision_record.json"
    ).write_text(
        __import__("json").dumps(trial1_prep),
        encoding="utf-8",
    )

    if accepted_at is None and completed_count < 6:
        next_index = completed_count + 1
        next_run_id = f"{CASE_RUN_ID}_cal_{next_index:02d}"
        next_dir = case_dir / next_run_id
        next_dir.mkdir()
        (next_dir /
         "production_doe_calibration_solver_preparation_record.json"
        ).write_text(
            __import__("json").dumps({
                "next_trial": {
                    "run_id": next_run_id,
                    "trial_index": next_index,
                    "source": (
                        PreloadCalibrationTrialSource.FEM_WARM_START.value
                    ),
                    "delta_temperature_c": -260.0 - completed_count,
                },
            }),
            encoding="utf-8",
        )
        history_state = "PREPARED_TRIAL_NOT_COMPLETED"
        next_trial_index = next_index

    else:
        history_state = (
            "TRIAL_LIMIT_REACHED_REQUIRES_CALIBRATION_DECISION"
            if completed_count == 6
            else "NEXT_TRIAL_NOT_PREPARED"
        )
        next_trial_index = (
            None if completed_count == 6
            else completed_count + 1
        )

    monkeypatch.setattr(
        planner,
        "resolve_governed_c01_case",
        lambda **kwargs: SimpleNamespace(
            case_run_id=CASE_RUN_ID,
            case_hash="d" * 64,
        ),
    )
    monkeypatch.setattr(
        planner,
        "recover_trial_history",
        lambda **kwargs: SimpleNamespace(
            state=history_state,
            completed_run_ids=tuple(run_ids),
            next_trial_index=next_trial_index,
        ),
    )
    monkeypatch.setattr(
        planner,
        "inspect_gate0_trial1",
        lambda **kwargs: SimpleNamespace(
            completion_status="COMPLETED_INPUT_EVIDENCE_VERIFIED",
            run_id=TRIAL1_ID,
            deck_sha256="a" * 64,
            completed_dat_sha256=planner._sha256(
                case_dir / TRIAL1_ID / f"{TRIAL1_ID}.dat"
            ),
        ),
    )
    monkeypatch.setattr(
        planner,
        "verify_completed_trial",
        lambda **kwargs: SimpleNamespace(
            dat_path=(
                kwargs["manifest_path"].parent
                / f'{kwargs["expected_run_id"]}.dat'
            ),
            dat_sha256=planner._sha256(
                kwargs["manifest_path"].parent
                / f'{kwargs["expected_run_id"]}.dat'
            ),
        ),
    )
    monkeypatch.setattr(
        planner,
        "load_complete_joint_contact_definition",
        lambda *args: SimpleNamespace(contact_pairs=()),
    )
    monkeypatch.setattr(
        planner,
        "load_complete_joint_preload_definition",
        lambda *args: SimpleNamespace(
            target_relative_tolerance=0.01,
            interface_spread_relative_tolerance=0.005,
        ),
    )
    monkeypatch.setattr(
        planner,
        "extract_clamp_force_measurement_from_dat",
        lambda *, dat_path, contact_pairs: SimpleNamespace(
            measurement=int(Path(dat_path).read_text(encoding="ascii"))
        ),
    )

    def evaluate(*, current_trial, previous_trial, **kwargs):
        index = current_trial.trial_index

        if index > 1:
            assert previous_trial is not None
            assert previous_trial.trial_index == index - 1
        else:
            assert previous_trial is None

        accepted = index == accepted_at

        next_trial = (
            None
            if accepted
            else PreloadCalibrationTrial(
                trial_index=index + 1,
                run_id=f"{CASE_RUN_ID}_cal_{index + 1:02d}",
                delta_temperature_c=-260.0 - index,
                source=PreloadCalibrationTrialSource.FEM_WARM_START,
            )
        )

        return SimpleNamespace(
            completed_trial=current_trial,
            next_trial=next_trial,
            accepted=accepted,
            decision=SimpleNamespace(
                disposition=(
                    PreloadCalibrationDisposition.ACCEPT
                    if accepted
                    else PreloadCalibrationDisposition.CONTINUE
                )
            ),
        )

    monkeypatch.setattr(
        planner,
        "evaluate_preload_calibration_trial",
        evaluate,
    )

    return root


@pytest.mark.parametrize("completed_count", [1, 2, 3, 4, 5])
def test_consecutive_trials_plan_next(
    tmp_path, monkeypatch, completed_count
):
    root = build_synthetic_history(
        tmp_path,
        monkeypatch,
        completed_count=completed_count,
    )

    result = planner.plan_from_verified_history(
        repo_root=root,
        case_id=CASE_ID,
    )

    assert result.completed_trial_count == completed_count
    assert result.state == (
        "PREPARED_NEXT_TRIAL_REQUIRES_AUTHORIZATION"
    )
    assert result.next_trial_run_id == (
        f"{CASE_RUN_ID}_cal_{completed_count + 1:02d}"
    )


@pytest.mark.parametrize("accepted_at", [2, 6])
def test_acceptance_stops_continuation(
    tmp_path, monkeypatch, accepted_at
):
    root = build_synthetic_history(
        tmp_path,
        monkeypatch,
        completed_count=accepted_at,
        accepted_at=accepted_at,
    )

    result = planner.plan_from_verified_history(
        repo_root=root,
        case_id=CASE_ID,
    )

    assert result.state == (
        "CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS"
    )
    assert result.next_trial_run_id is None


def test_trial_seven_is_rejected(tmp_path, monkeypatch):
    root = build_synthetic_history(
        tmp_path,
        monkeypatch,
        completed_count=6,
    )

    with pytest.raises(RuntimeError, match="trial limit reached"):
        planner.plan_from_verified_history(
            repo_root=root,
            case_id=CASE_ID,
        )


def test_corrupt_calibration_lineage_rejected(tmp_path, monkeypatch):
    root = build_synthetic_history(
        tmp_path,
        monkeypatch,
        completed_count=3,
        corrupt_trial=3,
    )

    with pytest.raises(RuntimeError, match="preceding governed"):
        planner.plan_from_verified_history(
            repo_root=root,
            case_id=CASE_ID,
        )


def test_completed_trial_after_acceptance_rejected(
    tmp_path, monkeypatch
):
    root = build_synthetic_history(
        tmp_path,
        monkeypatch,
        completed_count=3,
        accepted_at=2,
    )

    with pytest.raises(RuntimeError, match="after calibration termination"):
        planner.plan_from_verified_history(
            repo_root=root,
            case_id=CASE_ID,
        )

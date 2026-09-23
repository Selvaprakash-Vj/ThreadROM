"""Initial-case port: fresh preparation and no duplicate FEM."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess

import pytest

import threadrom.factory.governed_fem_initial_live_port as live
from threadrom.factory.adaptive_fem_lifecycle import RunPhase


CASE_HASH = "a" * 64
CASE_RUN = "trm_fem_" + CASE_HASH[:12]


def _port(tmp_path, monkeypatch):
    monkeypatch.setattr(
        live,
        "resolve_governed_c01_case",
        lambda **kwargs: SimpleNamespace(
            case_id=kwargs["requested_case_id"],
            case_hash=CASE_HASH,
            case_run_id=CASE_RUN,
        ),
    )
    monkeypatch.setattr(
        live,
        "PreloadCalibrationCampaignPolicy",
        lambda: SimpleNamespace(maximum_trials=6),
    )
    return live.GovernedInitialFEMLivePort(
        repo_root=tmp_path,
        case_id="TEST-DESIGN",
    )


def _trial(port, index, completed):
    run_id = port._trial_id(index)
    directory = port.case_root / run_id
    directory.mkdir(parents=True, exist_ok=True)
    content = b"*HEADING\nsynthetic deck\n"
    (directory / (run_id + ".inp")).write_bytes(content)
    record = {
        "case": {"case_hash": CASE_HASH},
        ("trial_1" if index == 1 else "next_trial"): {
            "run_id": run_id
        },
        "deck": {
            "sha256": hashlib.sha256(content).hexdigest()
        },
    }
    record_name = (
        "production_doe_solver_preparation_record.json"
        if index == 1
        else "production_doe_calibration_solver_preparation_record.json"
    )
    (directory / record_name).write_text(
        json.dumps(record), encoding="utf-8"
    )
    if completed:
        (directory / "fem_run_manifest.json").write_text(
            "{}", encoding="utf-8"
        )
    return directory


def test_fresh_case_is_not_prepared(tmp_path, monkeypatch):
    port = _port(tmp_path, monkeypatch)
    assert port.snapshot().phase is RunPhase.NOT_PREPARED
    assert port.recover_verified_trials() == ()


def test_prepared_case_is_not_a_completed_solve(
    tmp_path, monkeypatch,
):
    port = _port(tmp_path, monkeypatch)
    _trial(port, 1, completed=False)
    assert port.snapshot().phase is RunPhase.PREPARED
    assert port.recover_verified_trials() == ()


def test_completed_trials_recover_without_restart(
    tmp_path, monkeypatch,
):
    port = _port(tmp_path, monkeypatch)
    _trial(port, 1, completed=True)
    _trial(port, 2, completed=True)
    verified = []

    def verify(**kwargs):
        verified.append(kwargs["expected_run_id"])

    monkeypatch.setattr(live, "verify_completed_trial", verify)
    assert port.recover_verified_trials() == (
        port._trial_id(1),
        port._trial_id(2),
    )
    state = port.snapshot()
    assert state.phase is RunPhase.UNCERTAIN

    with pytest.raises(RuntimeError, match="state changed"):
        port.launch_authorized(state)

    assert verified


def test_uncertain_output_cannot_be_launched(
    tmp_path, monkeypatch,
):
    port = _port(tmp_path, monkeypatch)
    run_dir = _trial(port, 1, completed=False)
    (run_dir / (port._trial_id(1) + ".dat")).write_text(
        "interrupted"
    )
    assert port.snapshot().phase is RunPhase.UNCERTAIN


def test_claim_cannot_be_treated_as_prepared(
    tmp_path, monkeypatch,
):
    port = _port(tmp_path, monkeypatch)
    run_dir = _trial(port, 1, completed=False)
    (run_dir / live.CLAIM_FILENAME).write_text("{}")
    assert port.snapshot().phase is RunPhase.UNCERTAIN


def test_unauthorized_runner_defers_without_solver(
    tmp_path, monkeypatch,
):
    port = _port(tmp_path, monkeypatch)
    _trial(port, 1, completed=False)
    calls = []

    def blocked_runner(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args[0],
            2,
            stdout="",
            stderr="BLOCKED_UNAUTHORIZED_INITIAL_TRIAL",
        )

    monkeypatch.setattr(live.subprocess, "run", blocked_runner)
    assert port.launch_authorized(port.snapshot()) is False
    assert len(calls) == 1
    assert (
        "run_phase3_production_doe_trial1_case.py"
        in calls[0][0][0][1]
    )


def test_preparation_routes_through_existing_scripts(
    tmp_path, monkeypatch,
):
    port = _port(tmp_path, monkeypatch)
    calls = []

    def prepare_stage(name):
        calls.append(name)
        if name == "prepare_phase3_production_doe_case.py":
            record = (
                port.campaign_root / "prepared_cases"
                / CASE_RUN / "production_doe_preparation_record.json"
            )
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text("{}", encoding="utf-8")
        else:
            _trial(port, 1, completed=False)

    monkeypatch.setattr(
        port, "_run_preparation", prepare_stage,
    )

    port.prepare(port.snapshot())

    assert calls == [
        "prepare_phase3_production_doe_case.py",
        "prepare_phase3_production_doe_solver_case.py",
    ]
    assert port.snapshot().phase is RunPhase.PREPARED

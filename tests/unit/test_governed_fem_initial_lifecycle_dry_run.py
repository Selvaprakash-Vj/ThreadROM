"""Real supervisor + initial-case port; no physical FEM execution."""

from dataclasses import fields, is_dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

import threadrom.factory.governed_fem_initial_live_port as live
from threadrom.factory.adaptive_fem_lifecycle import RunPhase
from threadrom.factory.adaptive_fem_supervisor import (
    SupervisorStop,
    drive_fem_supervisor,
)


CASE_HASH = "b" * 64
CASE_RUN = "trm_fem_" + CASE_HASH[:12]
TRIAL_RUN = CASE_RUN + "_cal_01"


def _result_values(result):
    assert is_dataclass(result)
    return tuple(
        getattr(result, field.name)
        for field in fields(result)
    )


def _make_port(tmp_path, monkeypatch):
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
        case_id="SYNTHETIC-FRESH-CASE",
    )


def _install_synthetic_preparation(port, monkeypatch):
    preparation_calls = []

    def prepare_stage(name):
        preparation_calls.append(name)

        if name == "prepare_phase3_production_doe_case.py":
            record = (
                port.campaign_root
                / "prepared_cases"
                / CASE_RUN
                / "production_doe_preparation_record.json"
            )
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text("{}", encoding="utf-8")
            return

        if name != "prepare_phase3_production_doe_solver_case.py":
            raise AssertionError("Unexpected preparation stage")

        run_dir = port.case_root / TRIAL_RUN
        run_dir.mkdir(parents=True, exist_ok=True)

        deck = b"*HEADING\nSYNTHETIC DRY RUN\n"
        (run_dir / (TRIAL_RUN + ".inp")).write_bytes(deck)

        record = {
            "case": {"case_hash": CASE_HASH},
            "trial_1": {"run_id": TRIAL_RUN},
            "deck": {
                "sha256": hashlib.sha256(deck).hexdigest()
            },
        }

        (
            run_dir
            / "production_doe_solver_preparation_record.json"
        ).write_text(json.dumps(record), encoding="utf-8")

    monkeypatch.setattr(port, "_run_preparation", prepare_stage)
    return preparation_calls


def _forbid_real_subprocess(monkeypatch, replacement=None):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((tuple(argv), kwargs))

        assert any(
            str(arg).endswith(
                "run_phase3_production_doe_trial1_case.py"
            )
            for arg in argv
        )
        assert kwargs["capture_output"] is True

        if replacement is not None:
            return replacement(argv, kwargs)

        return subprocess.CompletedProcess(
            argv,
            3,
            stdout="",
            stderr="BLOCKED_UNAUTHORIZED_INITIAL_TRIAL",
        )

    monkeypatch.setattr(live.subprocess, "run", fake_run)
    return calls


def test_fresh_to_prepared_to_denied_launch(
    tmp_path, monkeypatch,
):
    port = _make_port(tmp_path, monkeypatch)
    preparation_calls = _install_synthetic_preparation(
        port, monkeypatch,
    )
    launch_calls = _forbid_real_subprocess(monkeypatch)

    assert port.snapshot().phase is RunPhase.NOT_PREPARED

    outcome = drive_fem_supervisor(port, max_actions=4)

    assert _result_values(outcome) == (
        SupervisorStop.WAIT_LAUNCH_GATE,
        1,
        TRIAL_RUN,
    )
    assert preparation_calls == [
        "prepare_phase3_production_doe_case.py",
        "prepare_phase3_production_doe_solver_case.py",
    ]
    assert len(launch_calls) == 1
    assert port.snapshot().phase is RunPhase.PREPARED
    assert port.recover_verified_trials() == ()
    assert not (
        port.case_root
        / TRIAL_RUN
        / live.CLAIM_FILENAME
    ).exists()


def test_synthetic_completion_requires_engineering_review(
    tmp_path, monkeypatch,
):
    port = _make_port(tmp_path, monkeypatch)
    _install_synthetic_preparation(port, monkeypatch)

    def simulate_completion(argv, kwargs):
        run_dir = port.case_root / TRIAL_RUN
        (run_dir / "fem_run_manifest.json").write_text(
            "{}", encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            argv, 0, stdout="GOVERNED TRIAL COMPLETED:", stderr="",
        )

    calls = _forbid_real_subprocess(
        monkeypatch, replacement=simulate_completion,
    )

    # Only the synthetic manifest in this test is accepted by the
    # mocked verifier. This does NOT certify real FEM evidence.
    verified = []

    def fake_verification(**kwargs):
        verified.append(kwargs["expected_run_id"])

    monkeypatch.setattr(
        live, "verify_completed_trial", fake_verification,
    )

    outcome = drive_fem_supervisor(port, max_actions=4)

    assert _result_values(outcome) == (
        SupervisorStop.ENGINEERING_REVIEW,
        2,
        TRIAL_RUN + "",
    )
    assert len(calls) == 1
    assert port.recover_verified_trials() == (TRIAL_RUN,)
    assert verified
    assert port.snapshot().phase is RunPhase.UNCERTAIN


def test_success_exit_without_verified_manifest_is_rejected(
    tmp_path, monkeypatch,
):
    port = _make_port(tmp_path, monkeypatch)
    _install_synthetic_preparation(port, monkeypatch)

    calls = _forbid_real_subprocess(
        monkeypatch,
        replacement=lambda argv, kwargs: (
            subprocess.CompletedProcess(
                argv, 0, stdout="success", stderr="",
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="without independently verified",
    ):
        drive_fem_supervisor(port, max_actions=4)

    assert len(calls) == 1
    assert port.recover_verified_trials() == ()


def test_uncertain_solver_output_stops_without_actions(
    tmp_path, monkeypatch,
):
    port = _make_port(tmp_path, monkeypatch)
    run_dir = port.case_root / TRIAL_RUN
    run_dir.mkdir(parents=True)

    (run_dir / (TRIAL_RUN + ".dat")).write_text(
        "interrupted synthetic run",
        encoding="utf-8",
    )

    def unexpected_subprocess(*args, **kwargs):
        raise AssertionError(
            "Supervisor tried to launch an uncertain trial."
        )

    monkeypatch.setattr(
        live.subprocess, "run", unexpected_subprocess,
    )

    outcome = drive_fem_supervisor(port, max_actions=4)

    assert _result_values(outcome) == (
        SupervisorStop.ENGINEERING_REVIEW,
        0,
        TRIAL_RUN,
    )


def test_existing_manifest_stops_without_duplicate_launch(
    tmp_path, monkeypatch,
):
    port = _make_port(tmp_path, monkeypatch)
    run_dir = port.case_root / TRIAL_RUN
    run_dir.mkdir(parents=True)

    (run_dir / "fem_run_manifest.json").write_text(
        "{}", encoding="utf-8",
    )

    def unexpected_subprocess(*args, **kwargs):
        raise AssertionError(
            "Supervisor tried to relaunch an existing trial."
        )

    monkeypatch.setattr(
        live.subprocess, "run", unexpected_subprocess,
    )

    outcome = drive_fem_supervisor(port, max_actions=4)

    assert _result_values(outcome) == (
        SupervisorStop.ENGINEERING_REVIEW,
        0,
        TRIAL_RUN,
    )

from pathlib import Path
from subprocess import CompletedProcess

from threadrom.factory.adaptive_fem_c01_live_port import (
    C01LiveFactoryPort,
)
from threadrom.factory.adaptive_fem_lifecycle import (
    FEMLifecycleSnapshot,
    RunPhase,
)
import threadrom.factory.adaptive_fem_c01_live_port as live_port


def prepared_port(monkeypatch):
    snapshot = FEMLifecycleSnapshot(
        run_id="synthetic_cal_02",
        trial_index=2,
        maximum_trials=6,
        phase=RunPhase.PREPARED,
    )

    # Do not access actual C01 files in these isolated tests.
    port = object.__new__(C01LiveFactoryPort)
    port.root = Path.cwd()
    port.case_id = "SYNTHETIC-001"
    monkeypatch.setattr(port, "snapshot", lambda: snapshot)
    return port, snapshot


def test_full_solver_queue_defers_without_calling_launcher(
    monkeypatch,
):
    port, snapshot = prepared_port(monkeypatch)

    monkeypatch.setattr(
        live_port,
        "count_running_ccx",
        lambda: live_port.MAXIMUM_CONCURRENT_CCX,
    )

    def forbidden_launcher(*args, **kwargs):
        raise AssertionError(
            "Launcher called despite a full solver queue."
        )

    monkeypatch.setattr(
        live_port.subprocess,
        "run",
        forbidden_launcher,
    )

    assert port.launch_authorized(snapshot) is False


def test_available_slot_does_not_bypass_authorization(
    monkeypatch,
):
    port, snapshot = prepared_port(monkeypatch)

    monkeypatch.setattr(
        live_port,
        "count_running_ccx",
        lambda: 0,
    )

    calls = []

    def blocked_launcher(args, **kwargs):
        calls.append(args)
        return CompletedProcess(
            args,
            1,
            stdout="",
            stderr="BLOCKED_UNAUTHORIZED: synthetic test",
        )

    monkeypatch.setattr(
        live_port.subprocess,
        "run",
        blocked_launcher,
    )

    assert port.launch_authorized(snapshot) is False
    assert len(calls) == 1
    assert "--execute" in calls[0]


def test_changed_snapshot_refuses_launch(monkeypatch):
    port, snapshot = prepared_port(monkeypatch)

    monkeypatch.setattr(
        port,
        "snapshot",
        lambda: FEMLifecycleSnapshot(
            run_id="synthetic_cal_03",
            trial_index=3,
            maximum_trials=6,
            phase=RunPhase.PREPARED,
        ),
    )

    try:
        port.launch_authorized(snapshot)
    except RuntimeError as exc:
        assert "snapshot changed" in str(exc)
    else:
        raise AssertionError(
            "Changed run identity was not rejected."
        )

"""Contract tests for the persistent Production-DOE runner."""

from pathlib import Path


RUNNER = Path(
    "scripts/run_phase3_production_doe_persistent_wave.py"
)


def test_persistent_runner_uses_registry_leases_and_heartbeats() -> None:
    source = RUNNER.read_text(
        encoding="utf-8"
    )

    required = (
        "FemFactoryRegistry",
        "claim_next_job",
        "heartbeat_claim",
        "transition_claimed_job",
        "subprocess.Popen",
        "recover_expired=False",
        "LEASE_SECONDS",
        "HEARTBEAT_SECONDS",
    )

    missing = [
        token
        for token in required
        if token not in source
    ]

    assert not missing, missing


def test_persistent_runner_does_not_use_blocking_subprocess_run() -> None:
    source = RUNNER.read_text(
        encoding="utf-8"
    )

    assert "subprocess.run(" not in source


def test_persistent_runner_governs_stale_recovery() -> None:
    source = RUNNER.read_text(
        encoding="utf-8"
    )

    required = (
        "list_expired_running_jobs",
        "adjudicate_live_fem_processes",
        "FemProcessStatus.LIVE_MATCH",
        "FemProcessStatus.UNKNOWN",
        "recover_expired_job",
        "expected_generation",
        "Automatic stale-job recovery : GOVERNED",
    )

    missing = [
        token
        for token in required
        if token not in source
    ]

    assert not missing, missing

import time
import pytest

from threadrom.factory.diversified_factory_worker import (
    WorkerExecutionResult,
    execute_claimed_factory_job,
)
from threadrom.factory.fem_factory_registry import (
    FemFactoryJobState,
    FemFactoryPriority,
    FemFactoryRegistry,
)


def claimed(tmp_path):
    registry = FemFactoryRegistry(tmp_path / "factory.sqlite3")
    registry.initialize()

    case_hash = "a" * 64

    registry.register_job(
        case_id="CASE-A",
        case_hash=case_hash,
        trial_index=1,
        run_id="trm_fem_aaaaaaaaaaaa_cal_01",
        priority=FemFactoryPriority.TRIAL2,
    )
    registry.transition_job(
        case_hash=case_hash,
        trial_index=1,
        new_state=FemFactoryJobState.PREPARED,
        preparation_record="prep.json",
    )

    claim = registry.claim_next_job(
        worker_id="worker-1",
        lease_seconds=60,
    )
    assert claim is not None
    return registry, claim


def test_success_becomes_solved(tmp_path):
    registry, claim = claimed(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")

    record = execute_claimed_factory_job(
        registry=registry,
        claim=claim,
        lease_seconds=60,
        execute=lambda _: WorkerExecutionResult(
            succeeded=True,
            manifest_path=manifest,
        ),
    )

    assert record.state is FemFactoryJobState.SOLVED


def test_failure_becomes_failed(tmp_path):
    registry, claim = claimed(tmp_path)

    record = execute_claimed_factory_job(
        registry=registry,
        claim=claim,
        lease_seconds=60,
        execute=lambda _: WorkerExecutionResult(
            succeeded=False,
            failure_category="solver_failure",
            failure_message="synthetic failure",
        ),
    )

    assert record.state is FemFactoryJobState.FAILED


def test_worker_exception_is_quarantined(tmp_path):
    registry, claim = claimed(tmp_path)

    def boom(_):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        execute_claimed_factory_job(
            registry=registry,
            claim=claim,
            lease_seconds=60,
            execute=boom,
        )

    record = registry.get_job(
        case_hash="a" * 64,
        trial_index=1,
    )
    assert record.state is FemFactoryJobState.QUARANTINED


def test_long_job_heartbeats(tmp_path):
    registry, claim = claimed(tmp_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}")

    def run(_):
        time.sleep(0.06)
        return WorkerExecutionResult(
            succeeded=True,
            manifest_path=manifest,
        )

    record = execute_claimed_factory_job(
        registry=registry,
        claim=claim,
        lease_seconds=60,
        heartbeat_interval_seconds=0.01,
        execute=run,
    )

    assert record.state is FemFactoryJobState.SOLVED

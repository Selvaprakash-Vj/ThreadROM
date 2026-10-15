from pathlib import Path

from threadrom.factory.diversified_parallel_admission import (
    claim_parallel_factory_slot,
)
from threadrom.factory.fem_factory_registry import (
    FemFactoryJobState,
    FemFactoryPriority,
    FemFactoryRegistry,
)
from threadrom.factory.windows_process_adjudication import (
    WindowsProcessSnapshot,
)


def _registry(tmp_path):
    registry = FemFactoryRegistry(
        tmp_path / "factory.sqlite3"
    )
    registry.initialize()
    return registry


def _prepare(registry, suffix):
    case_hash = suffix * 64
    run_id = f"trm_fem_{suffix * 12}_cal_01"

    registry.register_job(
        case_id=f"CASE-{suffix}",
        case_hash=case_hash,
        trial_index=1,
        run_id=run_id,
        priority=FemFactoryPriority.TRIAL2,
    )

    registry.transition_job(
        case_hash=case_hash,
        trial_index=1,
        new_state=FemFactoryJobState.PREPARED,
        preparation_record=f"prep-{suffix}.json",
    )


def test_two_workers_claim_two_parallel_slots(tmp_path):
    registry = _registry(tmp_path)
    _prepare(registry, "a")
    _prepare(registry, "b")

    query = lambda: ()

    one = claim_parallel_factory_slot(
        registry=registry,
        lock_path=tmp_path / "admission.lock",
        worker_id="worker-1",
        lease_seconds=600,
        maximum_authorized_ccx=2,
        process_query=query,
    )

    two = claim_parallel_factory_slot(
        registry=registry,
        lock_path=tmp_path / "admission.lock",
        worker_id="worker-2",
        lease_seconds=600,
        maximum_authorized_ccx=2,
        process_query=query,
    )

    assert one.reason == "CLAIMED"
    assert two.reason == "CLAIMED"
    assert one.occupied_slots == 1
    assert two.occupied_slots == 2


def test_prelaunch_claim_blocks_capacity_race(tmp_path):
    registry = _registry(tmp_path)
    _prepare(registry, "a")
    _prepare(registry, "b")

    query = lambda: ()

    first = claim_parallel_factory_slot(
        registry=registry,
        lock_path=tmp_path / "admission.lock",
        worker_id="worker-1",
        lease_seconds=600,
        maximum_authorized_ccx=1,
        process_query=query,
    )

    second = claim_parallel_factory_slot(
        registry=registry,
        lock_path=tmp_path / "admission.lock",
        worker_id="worker-2",
        lease_seconds=600,
        maximum_authorized_ccx=1,
        process_query=query,
    )

    assert first.reason == "CLAIMED"
    assert second.reason == "CAPACITY_FULL"
    assert second.claim is None


def test_external_ccx_consumes_capacity(tmp_path):
    registry = _registry(tmp_path)
    _prepare(registry, "a")

    snapshots = (
        WindowsProcessSnapshot(
            process_id=123,
            parent_process_id=1,
            executable_path=r"C:\CalculiX\ccx.exe",
            command_line="ccx.exe -i external_run",
        ),
    )

    result = claim_parallel_factory_slot(
        registry=registry,
        lock_path=tmp_path / "admission.lock",
        worker_id="worker-1",
        lease_seconds=600,
        maximum_authorized_ccx=1,
        process_query=lambda: snapshots,
    )

    assert result.reason == "CAPACITY_FULL"
    assert result.claim is None


def test_no_prepared_work_is_non_mutating(tmp_path):
    registry = _registry(tmp_path)

    result = claim_parallel_factory_slot(
        registry=registry,
        lock_path=tmp_path / "admission.lock",
        worker_id="worker-1",
        lease_seconds=600,
        maximum_authorized_ccx=1,
        process_query=lambda: (),
    )

    assert result.reason == "NO_PREPARED_WORK"
    assert result.claim is None

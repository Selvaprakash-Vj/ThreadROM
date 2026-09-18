"""Tests for the persistent governed FEM factory registry."""

from pathlib import Path

import pytest

from threadrom.factory.fem_factory_registry import (
    FemFactoryClaim,
    FemFactoryJobState,
    FemFactoryPriority,
    FemFactoryRegistry,
)


CASE_HASH = "a" * 64


def _registry(tmp_path: Path) -> FemFactoryRegistry:
    registry = FemFactoryRegistry(
        tmp_path / "factory.sqlite3"
    )
    registry.initialize()
    return registry


def test_registry_persists_job_across_reopen(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    created = registry.register_job(
        case_id="TRM-PDOE-X01",
        case_hash=CASE_HASH,
        trial_index=1,
        run_id="trm_fem_aaaaaaaaaaaa_cal_01",
        priority=(
            FemFactoryPriority.HIGH_INFORMATION_DOE
        ),
    )

    assert created.state is FemFactoryJobState.PLANNED

    reopened = FemFactoryRegistry(
        tmp_path / "factory.sqlite3"
    )
    reopened.initialize()

    loaded = reopened.get_job(
        case_hash=CASE_HASH,
        trial_index=1,
    )

    assert loaded is not None
    assert loaded.run_id == created.run_id
    assert loaded.state is FemFactoryJobState.PLANNED


def test_registration_is_idempotent_but_rejects_drift(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    first = registry.register_job(
        case_id="TRM-PDOE-X01",
        case_hash=CASE_HASH,
        trial_index=1,
        run_id="trm_fem_aaaaaaaaaaaa_cal_01",
        priority=FemFactoryPriority.BOUNDARY,
    )

    second = registry.register_job(
        case_id="TRM-PDOE-X01",
        case_hash=CASE_HASH,
        trial_index=1,
        run_id="trm_fem_aaaaaaaaaaaa_cal_01",
        priority=FemFactoryPriority.BOUNDARY,
    )

    assert second.job_id == first.job_id

    with pytest.raises(
        RuntimeError,
        match="identity drift",
    ):
        registry.register_job(
            case_id="TRM-PDOE-X01",
            case_hash=CASE_HASH,
            trial_index=1,
            run_id="different_run_id",
            priority=FemFactoryPriority.BOUNDARY,
        )


def test_governed_happy_path_is_persistent(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    registry.register_job(
        case_id="TRM-PDOE-X01",
        case_hash=CASE_HASH,
        trial_index=1,
        run_id="trm_fem_aaaaaaaaaaaa_cal_01",
        priority=FemFactoryPriority.HIGH_INFORMATION_DOE,
    )

    registry.transition_job(
        case_hash=CASE_HASH,
        trial_index=1,
        new_state=FemFactoryJobState.PREPARED,
        preparation_record=(
            "simulations/staging/preparation.json"
        ),
    )

    registry.transition_job(
        case_hash=CASE_HASH,
        trial_index=1,
        new_state=FemFactoryJobState.RUNNING,
    )

    registry.transition_job(
        case_hash=CASE_HASH,
        trial_index=1,
        new_state=FemFactoryJobState.SOLVED,
        manifest_path=(
            "simulations/staging/fem_run_manifest.json"
        ),
    )

    final = registry.transition_job(
        case_hash=CASE_HASH,
        trial_index=1,
        new_state=FemFactoryJobState.ACCEPTED,
        acceptance_record=(
            "simulations/staging/"
            "production_doe_accepted_fem_evidence.json"
        ),
    )

    assert final.state is FemFactoryJobState.ACCEPTED


def test_illegal_state_transition_fails_closed(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    registry.register_job(
        case_id="TRM-PDOE-X01",
        case_hash=CASE_HASH,
        trial_index=1,
        run_id="trm_fem_aaaaaaaaaaaa_cal_01",
        priority=FemFactoryPriority.EXPLORATORY,
    )

    with pytest.raises(
        RuntimeError,
        match="Illegal FEM factory state transition",
    ):
        registry.transition_job(
            case_hash=CASE_HASH,
            trial_index=1,
            new_state=FemFactoryJobState.ACCEPTED,
        )


def test_failed_state_preserves_failure_reason(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    registry.register_job(
        case_id="TRM-PDOE-X01",
        case_hash=CASE_HASH,
        trial_index=1,
        run_id="trm_fem_aaaaaaaaaaaa_cal_01",
        priority=FemFactoryPriority.RECOVERY,
    )

    failed = registry.transition_job(
        case_hash=CASE_HASH,
        trial_index=1,
        new_state=FemFactoryJobState.FAILED,
        failure_category="orchestration_error",
        failure_message="worker process interrupted",
    )

    assert failed.state is FemFactoryJobState.FAILED
    assert failed.failure_category == "orchestration_error"
    assert failed.failure_message == "worker process interrupted"


def test_scheduler_order_uses_governed_priority(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    jobs = (
        ("BND", "b" * 64, FemFactoryPriority.BOUNDARY),
        ("REC", "c" * 64, FemFactoryPriority.RECOVERY),
        (
            "DOE",
            "d" * 64,
            FemFactoryPriority.HIGH_INFORMATION_DOE,
        ),
        ("T2", "e" * 64, FemFactoryPriority.TRIAL2),
        (
            "EXP",
            "f" * 64,
            FemFactoryPriority.EXPLORATORY,
        ),
    )

    for case_id, case_hash, priority in jobs:
        registry.register_job(
            case_id=case_id,
            case_hash=case_hash,
            trial_index=1,
            run_id=f"run_{case_id}",
            priority=priority,
        )

    ordered = registry.list_jobs()

    assert [
        record.priority
        for record in ordered
    ] == [
        FemFactoryPriority.RECOVERY,
        FemFactoryPriority.TRIAL2,
        FemFactoryPriority.HIGH_INFORMATION_DOE,
        FemFactoryPriority.BOUNDARY,
        FemFactoryPriority.EXPLORATORY,
    ]

def _prepare_job(
    registry: FemFactoryRegistry,
    *,
    case_id: str,
    case_hash: str,
    priority: FemFactoryPriority,
) -> None:
    registry.register_job(
        case_id=case_id,
        case_hash=case_hash,
        trial_index=1,
        run_id=f"run_{case_id}",
        priority=priority,
    )

    registry.transition_job(
        case_hash=case_hash,
        trial_index=1,
        new_state=FemFactoryJobState.PREPARED,
        preparation_record=f"prep/{case_id}.json",
    )


def test_worker_atomically_claims_prepared_job(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    _prepare_job(
        registry,
        case_id="DOE",
        case_hash="1" * 64,
        priority=FemFactoryPriority.HIGH_INFORMATION_DOE,
    )

    claim = registry.claim_next_job(
        worker_id="worker-01",
        lease_seconds=60,
        now_utc="2026-09-16T10:00:00Z",
    )

    assert isinstance(claim, FemFactoryClaim)
    assert claim.worker_id == "worker-01"
    assert claim.lease_generation == 1
    assert claim.recovered is False

    persisted = registry.get_job(
        case_hash="1" * 64,
        trial_index=1,
    )

    assert persisted is not None
    assert persisted.state is FemFactoryJobState.RUNNING
    assert persisted.lease_owner == "worker-01"
    assert persisted.lease_generation == 1


def test_active_lease_prevents_double_claim(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    _prepare_job(
        registry,
        case_id="DOE",
        case_hash="2" * 64,
        priority=FemFactoryPriority.HIGH_INFORMATION_DOE,
    )

    first = registry.claim_next_job(
        worker_id="worker-01",
        lease_seconds=60,
        now_utc="2026-09-16T10:00:00Z",
    )

    assert first is not None

    second = registry.claim_next_job(
        worker_id="worker-02",
        lease_seconds=60,
        now_utc="2026-09-16T10:00:30Z",
    )

    assert second is None


def test_expired_running_job_is_recovered_before_new_work(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    _prepare_job(
        registry,
        case_id="OLD",
        case_hash="3" * 64,
        priority=FemFactoryPriority.EXPLORATORY,
    )

    old_claim = registry.claim_next_job(
        worker_id="worker-old",
        lease_seconds=60,
        now_utc="2026-09-16T10:00:00Z",
    )

    assert old_claim is not None

    _prepare_job(
        registry,
        case_id="NEW",
        case_hash="4" * 64,
        priority=FemFactoryPriority.TRIAL2,
    )

    recovered = registry.claim_next_job(
        worker_id="worker-recovery",
        lease_seconds=60,
        now_utc="2026-09-16T10:01:01Z",
        recover_expired=True,
    )

    assert recovered is not None
    assert recovered.case_hash == "3" * 64
    assert recovered.recovered is True
    assert recovered.lease_generation == 2


def test_recovery_fences_stale_worker(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    _prepare_job(
        registry,
        case_id="REC",
        case_hash="5" * 64,
        priority=FemFactoryPriority.BOUNDARY,
    )

    old = registry.claim_next_job(
        worker_id="worker-old",
        lease_seconds=60,
        now_utc="2026-09-16T10:00:00Z",
    )

    assert old is not None

    recovered = registry.claim_next_job(
        worker_id="worker-new",
        lease_seconds=60,
        now_utc="2026-09-16T10:01:01Z",
        recover_expired=True,
    )

    assert recovered is not None
    assert recovered.lease_generation == 2

    with pytest.raises(
        RuntimeError,
        match="lease ownership is stale",
    ):
        registry.heartbeat_claim(
            old,
            lease_seconds=60,
            now_utc="2026-09-16T10:01:02Z",
        )

    with pytest.raises(
        RuntimeError,
        match="lease ownership is stale",
    ):
        registry.transition_claimed_job(
            old,
            new_state=FemFactoryJobState.FAILED,
            failure_category="orchestration_error",
            failure_message="late stale worker",
            now_utc="2026-09-16T10:01:02Z",
        )


def test_heartbeat_extends_current_lease(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    _prepare_job(
        registry,
        case_id="HB",
        case_hash="6" * 64,
        priority=FemFactoryPriority.BOUNDARY,
    )

    claim = registry.claim_next_job(
        worker_id="worker-hb",
        lease_seconds=60,
        now_utc="2026-09-16T10:00:00Z",
    )

    assert claim is not None

    renewed = registry.heartbeat_claim(
        claim,
        lease_seconds=120,
        now_utc="2026-09-16T10:00:30Z",
    )

    assert (
        renewed.lease_expires_at_utc
        == "2026-09-16T10:02:30.000000Z"
    )


def test_claimed_worker_can_publish_solved_manifest(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    _prepare_job(
        registry,
        case_id="SOLVE",
        case_hash="7" * 64,
        priority=FemFactoryPriority.HIGH_INFORMATION_DOE,
    )

    claim = registry.claim_next_job(
        worker_id="worker-solve",
        lease_seconds=60,
        now_utc="2026-09-16T10:00:00Z",
    )

    assert claim is not None

    solved = registry.transition_claimed_job(
        claim,
        new_state=FemFactoryJobState.SOLVED,
        manifest_path="runs/fem_run_manifest.json",
        now_utc="2026-09-16T10:00:30Z",
    )

    assert solved.state is FemFactoryJobState.SOLVED
    assert solved.manifest_path == "runs/fem_run_manifest.json"
    assert solved.lease_owner is None
    assert solved.lease_expires_at_utc is None

def test_scheduler_can_defer_expired_recovery(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    _prepare_job(
        registry,
        case_id="STALE",
        case_hash="8" * 64,
        priority=FemFactoryPriority.RECOVERY,
    )

    old = registry.claim_next_job(
        worker_id="worker-old",
        lease_seconds=60,
        now_utc="2026-09-16T10:00:00Z",
    )

    assert old is not None

    _prepare_job(
        registry,
        case_id="FRESH",
        case_hash="9" * 64,
        priority=FemFactoryPriority.HIGH_INFORMATION_DOE,
    )

    fresh = registry.claim_next_job(
        worker_id="worker-safe",
        lease_seconds=60,
        now_utc="2026-09-16T10:01:01Z",
        recover_expired=False,
    )

    assert fresh is not None
    assert fresh.case_hash == "9" * 64
    assert fresh.recovered is False

def test_expired_jobs_are_listed_without_mutation(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    _prepare_job(
        registry,
        case_id="STALE-LIST",
        case_hash="a1" * 32,
        priority=FemFactoryPriority.BOUNDARY,
    )

    claim = registry.claim_next_job(
        worker_id="worker-old",
        lease_seconds=60,
        now_utc="2026-09-16T10:00:00Z",
    )

    assert claim is not None

    expired = registry.list_expired_running_jobs(
        now_utc="2026-09-16T10:01:01Z",
    )

    assert len(expired) == 1
    assert expired[0].case_hash == "a1" * 32
    assert expired[0].lease_generation == 1

    persisted = registry.get_job(
        case_hash="a1" * 32,
        trial_index=1,
    )

    assert persisted is not None
    assert persisted.lease_owner == "worker-old"
    assert persisted.lease_generation == 1


def test_targeted_recovery_is_generation_fenced(
    tmp_path: Path,
) -> None:
    registry = _registry(tmp_path)

    _prepare_job(
        registry,
        case_id="TARGET",
        case_hash="b2" * 32,
        priority=FemFactoryPriority.RECOVERY,
    )

    original = registry.claim_next_job(
        worker_id="worker-old",
        lease_seconds=60,
        now_utc="2026-09-16T10:00:00Z",
    )

    assert original is not None

    recovered = registry.recover_expired_job(
        case_hash="b2" * 32,
        trial_index=1,
        expected_generation=1,
        worker_id="worker-new",
        lease_seconds=60,
        now_utc="2026-09-16T10:01:01Z",
    )

    assert recovered.recovered is True
    assert recovered.lease_generation == 2

    with pytest.raises(
        RuntimeError,
        match="specifically adjudicated expired lease",
    ):
        registry.recover_expired_job(
            case_hash="b2" * 32,
            trial_index=1,
            expected_generation=1,
            worker_id="worker-third",
            lease_seconds=60,
            now_utc="2026-09-16T10:01:02Z",
        )

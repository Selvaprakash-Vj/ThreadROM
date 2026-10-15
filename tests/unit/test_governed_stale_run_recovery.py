from __future__ import annotations

import pytest

from threadrom.factory.fem_factory_registry import (
    FemFactoryJobState,
    FemFactoryPriority,
    FemFactoryRegistry,
)
from threadrom.factory.governed_stale_run_recovery import (
    StaleRunRecoveryDisposition,
    adjudicate_stale_running_job,
    recover_adjudicated_stale_job,
)
from threadrom.factory.windows_process_adjudication import (
    FemProcessAdjudication,
    FemProcessStatus,
)


CASE_HASH = "a" * 64
CASE_ID = "CASE-STALE-01"
RUN_ID = "trm_fem_aaaaaaaaaaaa_cal_01"

T0 = "2026-01-01T00:00:00Z"
EXPIRED = "2026-01-01T00:00:11Z"


def make_expired_running_job(
    tmp_path,
):
    registry = FemFactoryRegistry(
        tmp_path
        / "factory.sqlite3"
    )

    registry.initialize()

    registered = registry.register_job(
        case_id=CASE_ID,
        case_hash=CASE_HASH,
        trial_index=1,
        run_id=RUN_ID,
        priority=(
            FemFactoryPriority
            .HIGH_INFORMATION_DOE
        ),
    )

    assert (
        registered.state
        is FemFactoryJobState.PLANNED
    )

    prepared = registry.transition_job(
        case_hash=CASE_HASH,
        trial_index=1,
        new_state=FemFactoryJobState.PREPARED,
        preparation_record="prepared.json",
    )

    assert (
        prepared.state
        is FemFactoryJobState.PREPARED
    )

    claim = registry.claim_next_job(
        worker_id="old-worker",
        lease_seconds=10,
        now_utc=T0,
        recover_expired=False,
    )

    assert claim is not None

    expired = registry.list_expired_running_jobs(
        now_utc=EXPIRED
    )

    assert len(expired) == 1

    return (
        registry,
        claim,
        expired[0],
    )


def process_state(
    status: FemProcessStatus,
):
    return FemProcessAdjudication(
        status=status,
        matching_process_ids=(
            (1234,)
            if status is FemProcessStatus.LIVE_MATCH
            else ()
        ),
        reason=status.value,
    )


@pytest.mark.parametrize(
    "manifest_status",
    (
        "SUCCEEDED",
        "FAILED",
    ),
)
def test_terminal_manifest_authorizes_reconciliation(
    tmp_path,
    manifest_status,
):
    _, _, stale = (
        make_expired_running_job(
            tmp_path
        )
    )

    decision = adjudicate_stale_running_job(
        stale=stale,
        manifest_status=manifest_status,
    )

    assert decision.reconciliation_required is True
    assert decision.relaunch_authorized is False
    assert (
        decision.disposition
        is StaleRunRecoveryDisposition
        .RECOVER_MANIFEST_RECONCILIATION
    )


@pytest.mark.parametrize(
    "manifest_status",
    (
        "SUCCEEDED",
        "FAILED",
    ),
)
def test_terminal_manifest_cannot_enter_relaunch_api(
    tmp_path,
    manifest_status,
):
    registry, old_claim, stale = (
        make_expired_running_job(
            tmp_path
        )
    )

    decision = adjudicate_stale_running_job(
        stale=stale,
        manifest_status=manifest_status,
    )

    assert decision.reconciliation_required is True
    assert decision.relaunch_authorized is False

    with pytest.raises(
        RuntimeError,
        match="reconciliation.*relaunch is forbidden",
    ):
        recover_adjudicated_stale_job(
            registry=registry,
            decision=decision,
            worker_id="forbidden-relauncher",
            lease_seconds=30,
            now_utc=EXPIRED,
        )

    current = registry.get_job(
        case_hash=CASE_HASH,
        trial_index=1,
    )

    assert current is not None
    assert current.state is FemFactoryJobState.RUNNING
    assert (
        current.lease_generation
        == old_claim.lease_generation
    )
    assert current.lease_owner == "old-worker"


def test_invalid_manifest_fails_closed(
    tmp_path,
):
    _, _, stale = (
        make_expired_running_job(
            tmp_path
        )
    )

    decision = adjudicate_stale_running_job(
        stale=stale,
        manifest_status="INVALID",
    )

    assert decision.reconciliation_required is False
    assert decision.relaunch_authorized is False
    assert (
        decision.disposition
        is StaleRunRecoveryDisposition
        .HOLD_INVALID_MANIFEST
    )


def test_live_process_blocks_recovery(
    tmp_path,
):
    _, _, stale = (
        make_expired_running_job(
            tmp_path
        )
    )

    decision = adjudicate_stale_running_job(
        stale=stale,
        manifest_status="MISSING",
        process_state=process_state(
            FemProcessStatus.LIVE_MATCH
        ),
    )

    assert decision.reconciliation_required is False
    assert decision.relaunch_authorized is False
    assert (
        decision.disposition
        is StaleRunRecoveryDisposition
        .HOLD_LIVE_PROCESS
    )


def test_unknown_process_state_fails_closed(
    tmp_path,
):
    _, _, stale = (
        make_expired_running_job(
            tmp_path
        )
    )

    decision = adjudicate_stale_running_job(
        stale=stale,
        manifest_status="MISSING",
        process_state=process_state(
            FemProcessStatus.UNKNOWN
        ),
    )

    assert decision.reconciliation_required is False
    assert decision.relaunch_authorized is False
    assert (
        decision.disposition
        is StaleRunRecoveryDisposition
        .HOLD_PROCESS_UNKNOWN
    )


def test_missing_manifest_without_process_adjudication_rejected(
    tmp_path,
):
    _, _, stale = (
        make_expired_running_job(
            tmp_path
        )
    )

    with pytest.raises(
        RuntimeError,
        match="requires OS process adjudication",
    ):
        adjudicate_stale_running_job(
            stale=stale,
            manifest_status="MISSING",
        )


def test_no_live_process_authorizes_specific_recovery(
    tmp_path,
):
    registry, old_claim, stale = (
        make_expired_running_job(
            tmp_path
        )
    )

    decision = adjudicate_stale_running_job(
        stale=stale,
        manifest_status="MISSING",
        process_state=process_state(
            FemProcessStatus.NO_MATCH
        ),
    )

    recovered = recover_adjudicated_stale_job(
        registry=registry,
        decision=decision,
        worker_id="recovery-worker",
        lease_seconds=30,
        now_utc=EXPIRED,
    )

    assert (
        recovered.lease_generation
        == old_claim.lease_generation + 1
    )

    current = registry.get_job(
        case_hash=CASE_HASH,
        trial_index=1,
    )

    assert current is not None
    assert (
        current.state
        is FemFactoryJobState.RUNNING
    )
    assert (
        current.lease_owner
        == "recovery-worker"
    )
    assert (
        current.lease_generation
        == recovered.lease_generation
    )


def test_old_worker_cannot_finish_after_recovery(
    tmp_path,
):
    registry, old_claim, stale = (
        make_expired_running_job(
            tmp_path
        )
    )

    decision = adjudicate_stale_running_job(
        stale=stale,
        manifest_status="MISSING",
        process_state=process_state(
            FemProcessStatus.NO_MATCH
        ),
    )

    recover_adjudicated_stale_job(
        registry=registry,
        decision=decision,
        worker_id="recovery-worker",
        lease_seconds=30,
        now_utc=EXPIRED,
    )

    with pytest.raises(
        RuntimeError,
        match="stale|expired|recovered",
    ):
        registry.transition_claimed_job(
            old_claim,
            new_state=FemFactoryJobState.SOLVED,
            manifest_path="manifest.json",
        )


def test_hold_decision_cannot_be_recovered(
    tmp_path,
):
    registry, _, stale = (
        make_expired_running_job(
            tmp_path
        )
    )

    decision = adjudicate_stale_running_job(
        stale=stale,
        manifest_status="MISSING",
        process_state=process_state(
            FemProcessStatus.LIVE_MATCH
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="not authorized",
    ):
        recover_adjudicated_stale_job(
            registry=registry,
            decision=decision,
            worker_id="recovery-worker",
            lease_seconds=30,
            now_utc=EXPIRED,
        )


def test_expired_running_job_is_not_implicitly_reclaimed(
    tmp_path,
):
    registry, _, _ = (
        make_expired_running_job(
            tmp_path
        )
    )

    claim = registry.claim_next_job(
        worker_id="new-worker",
        lease_seconds=30,
        now_utc=EXPIRED,
        recover_expired=False,
    )

    assert claim is None


def test_registry_registration_is_idempotent_not_duplicate(
    tmp_path,
):
    registry = FemFactoryRegistry(
        tmp_path
        / "factory.sqlite3"
    )

    registry.initialize()

    first = registry.register_job(
        case_id=CASE_ID,
        case_hash=CASE_HASH,
        trial_index=1,
        run_id=RUN_ID,
        priority=(
            FemFactoryPriority
            .HIGH_INFORMATION_DOE
        ),
    )

    second = registry.register_job(
        case_id=CASE_ID,
        case_hash=CASE_HASH,
        trial_index=1,
        run_id=RUN_ID,
        priority=(
            FemFactoryPriority
            .HIGH_INFORMATION_DOE
        ),
    )

    assert first.job_id == second.job_id

    with pytest.raises(
        RuntimeError,
        match="identity drift",
    ):
        registry.register_job(
            case_id=CASE_ID,
            case_hash=CASE_HASH,
            trial_index=1,
            run_id=(
                "trm_fem_aaaaaaaaaaaa_cal_99"
            ),
            priority=(
                FemFactoryPriority
                .HIGH_INFORMATION_DOE
            ),
        )
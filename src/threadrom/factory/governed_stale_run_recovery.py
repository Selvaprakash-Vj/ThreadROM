"""Governed adjudication and recovery of expired RUNNING FEM jobs.

Lease expiry alone never authorizes relaunch.

Recovery is allowed only when:
- immutable terminal manifest evidence requires reconciliation, or
- the manifest is absent and OS process adjudication confirms NO_MATCH.

Invalid manifests, live matching processes and unknown process state
all fail closed.

The registry remains the single authority that atomically recovers a
specific expired lease generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from threadrom.factory.fem_factory_registry import (
    FemFactoryClaim,
    FemFactoryJobRecord,
    FemFactoryJobState,
    FemFactoryRegistry,
)
from threadrom.factory.windows_process_adjudication import (
    FemProcessAdjudication,
    FemProcessStatus,
)


class StaleRunRecoveryDisposition(StrEnum):
    HOLD_INVALID_MANIFEST = "hold_invalid_manifest"
    HOLD_LIVE_PROCESS = "hold_live_process"
    HOLD_PROCESS_UNKNOWN = "hold_process_unknown"
    RECOVER_MANIFEST_RECONCILIATION = (
        "recover_manifest_reconciliation"
    )
    RECOVER_NO_LIVE_PROCESS = "recover_no_live_process"


@dataclass(frozen=True, slots=True)
class StaleRunRecoveryDecision:
    case_id: str
    case_hash: str
    trial_index: int
    run_id: str
    lease_generation: int
    disposition: StaleRunRecoveryDisposition
    reason: str

    @property
    def reconciliation_required(self) -> bool:
        return self.disposition is (
            StaleRunRecoveryDisposition
            .RECOVER_MANIFEST_RECONCILIATION
        )

    @property
    def relaunch_authorized(self) -> bool:
        return self.disposition is (
            StaleRunRecoveryDisposition
            .RECOVER_NO_LIVE_PROCESS
        )


def adjudicate_stale_running_job(
    *,
    stale: FemFactoryJobRecord,
    manifest_status: str,
    process_state: FemProcessAdjudication | None = None,
) -> StaleRunRecoveryDecision:
    """Pure fail-safe stale-run adjudication.

    manifest_status must be one of the governed manifest states used by
    the production FEM machinery: MISSING, INVALID, SUCCEEDED or FAILED.
    """

    if stale.state is not FemFactoryJobState.RUNNING:
        raise RuntimeError(
            "Stale-run adjudication requires a RUNNING factory job."
        )

    if stale.lease_expires_at_utc is None:
        raise RuntimeError(
            "RUNNING job lacks a governed lease expiry."
        )

    status = str(
        manifest_status
    ).upper()

    if status in {
        "SUCCEEDED",
        "FAILED",
    }:
        return StaleRunRecoveryDecision(
            case_id=stale.case_id,
            case_hash=stale.case_hash,
            trial_index=stale.trial_index,
            run_id=stale.run_id,
            lease_generation=stale.lease_generation,
            disposition=(
                StaleRunRecoveryDisposition
                .RECOVER_MANIFEST_RECONCILIATION
            ),
            reason=(
                "Expired RUNNING lease has immutable terminal "
                f"manifest evidence: {status}."
            ),
        )

    if status == "INVALID":
        return StaleRunRecoveryDecision(
            case_id=stale.case_id,
            case_hash=stale.case_hash,
            trial_index=stale.trial_index,
            run_id=stale.run_id,
            lease_generation=stale.lease_generation,
            disposition=(
                StaleRunRecoveryDisposition
                .HOLD_INVALID_MANIFEST
            ),
            reason=(
                "Invalid manifest requires engineering review; "
                "automatic recovery is forbidden."
            ),
        )

    if status != "MISSING":
        raise RuntimeError(
            "Unsupported governed manifest status: "
            f"{manifest_status!r}"
        )

    if process_state is None:
        raise RuntimeError(
            "Missing manifest requires OS process adjudication."
        )

    if (
        process_state.status
        is FemProcessStatus.LIVE_MATCH
    ):
        return StaleRunRecoveryDecision(
            case_id=stale.case_id,
            case_hash=stale.case_hash,
            trial_index=stale.trial_index,
            run_id=stale.run_id,
            lease_generation=stale.lease_generation,
            disposition=(
                StaleRunRecoveryDisposition
                .HOLD_LIVE_PROCESS
            ),
            reason=(
                "Matching executor or CalculiX process remains live."
            ),
        )

    if (
        process_state.status
        is FemProcessStatus.UNKNOWN
    ):
        return StaleRunRecoveryDecision(
            case_id=stale.case_id,
            case_hash=stale.case_hash,
            trial_index=stale.trial_index,
            run_id=stale.run_id,
            lease_generation=stale.lease_generation,
            disposition=(
                StaleRunRecoveryDisposition
                .HOLD_PROCESS_UNKNOWN
            ),
            reason=(
                "Process-table state is unknown; automatic recovery "
                "fails closed."
            ),
        )

    if (
        process_state.status
        is not FemProcessStatus.NO_MATCH
    ):
        raise RuntimeError(
            "Unsupported FEM process adjudication state."
        )

    return StaleRunRecoveryDecision(
        case_id=stale.case_id,
        case_hash=stale.case_hash,
        trial_index=stale.trial_index,
        run_id=stale.run_id,
        lease_generation=stale.lease_generation,
        disposition=(
            StaleRunRecoveryDisposition
            .RECOVER_NO_LIVE_PROCESS
        ),
        reason=(
            "Expired lease has no terminal manifest and no matching "
            "live executor or CalculiX process."
        ),
    )


def recover_adjudicated_stale_job(
    *,
    registry: FemFactoryRegistry,
    decision: StaleRunRecoveryDecision,
    worker_id: str,
    lease_seconds: int,
    now_utc: str | None = None,
) -> FemFactoryClaim:
    """Atomically reacquire an expired generation for sanctioned relaunch."""

    if decision.reconciliation_required:
        raise RuntimeError(
            "Terminal manifest requires reconciliation; "
            "relaunch is forbidden."
        )

    if not decision.relaunch_authorized:
        raise RuntimeError(
            "Stale job is not authorized for automatic relaunch."
        )

    return registry.recover_expired_job(
        case_hash=decision.case_hash,
        trial_index=decision.trial_index,
        expected_generation=(
            decision.lease_generation
        ),
        worker_id=worker_id,
        lease_seconds=lease_seconds,
        now_utc=now_utc,
    )
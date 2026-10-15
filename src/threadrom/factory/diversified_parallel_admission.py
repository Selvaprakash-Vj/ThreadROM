from __future__ import annotations

import os
import ntpath
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from threadrom.factory.fem_factory_registry import (
    FemFactoryClaim,
    FemFactoryJobState,
    FemFactoryRegistry,
)
from threadrom.factory.production_doe_launch_fence import (
    MAXIMUM_CONCURRENT_CCX,
)
from threadrom.factory.windows_process_adjudication import (
    FemProcessStatus,
    WindowsProcessSnapshot,
    adjudicate_process_snapshots,
    query_windows_processes,
)


@dataclass(frozen=True, slots=True)
class ParallelAdmission:
    claim: FemFactoryClaim | None
    occupied_slots: int
    capacity: int
    reason: str


@contextmanager
def _short_process_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a+b") as stream:
        stream.seek(0, 2)

        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()

        stream.seek(0)

        if os.name == "nt":
            import msvcrt

            msvcrt.locking(
                stream.fileno(),
                msvcrt.LK_LOCK,
                1,
            )

            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(
                    stream.fileno(),
                    msvcrt.LK_UNLCK,
                    1,
                )
        else:
            import fcntl

            fcntl.flock(
                stream.fileno(),
                fcntl.LOCK_EX,
            )

            try:
                yield
            finally:
                fcntl.flock(
                    stream.fileno(),
                    fcntl.LOCK_UN,
                )


def claim_parallel_factory_slot(
    *,
    registry: FemFactoryRegistry,
    lock_path: Path,
    worker_id: str,
    lease_seconds: int,
    maximum_authorized_ccx: int,
    process_query: Callable[
        [],
        tuple[WindowsProcessSnapshot, ...],
    ] = query_windows_processes,
) -> ParallelAdmission:
    """Atomically reserve one short-lived parallel launch slot.

    The lock protects only admission. It is released before any solver
    operation. RUNNING registry claims without a visible solver count as
    reserved pre-launch slots so concurrent workers cannot oversubscribe
    the claim-to-spawn window.
    """

    if (
        type(maximum_authorized_ccx) is not int
        or not 1
        <= maximum_authorized_ccx
        <= MAXIMUM_CONCURRENT_CCX
    ):
        raise RuntimeError(
            "Invalid authorized parallel solver capacity."
        )

    if not worker_id.strip():
        raise RuntimeError(
            "Parallel factory worker ID is blank."
        )

    if lease_seconds <= 0:
        raise RuntimeError(
            "Parallel factory lease duration must be positive."
        )

    with _short_process_lock(lock_path):
        snapshots = process_query()

        visible_ccx = sum(
            1
            for snapshot in snapshots
            if ntpath.basename(
                snapshot.executable_path or ""
            ).lower().startswith("ccx")
        )

        running_jobs = registry.list_jobs(
            state=FemFactoryJobState.RUNNING
        )

        reserved_not_visible = 0

        for job in running_jobs:
            adjudication = adjudicate_process_snapshots(
                snapshots=snapshots,
                run_id=job.run_id,
                case_id=job.case_id,
            )

            if (
                adjudication.status
                is not FemProcessStatus.LIVE_MATCH
            ):
                reserved_not_visible += 1

        occupied = (
            visible_ccx
            + reserved_not_visible
        )

        if occupied >= maximum_authorized_ccx:
            return ParallelAdmission(
                claim=None,
                occupied_slots=occupied,
                capacity=maximum_authorized_ccx,
                reason="CAPACITY_FULL",
            )

        claim = registry.claim_next_job(
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            recover_expired=False,
        )

        if claim is None:
            return ParallelAdmission(
                claim=None,
                occupied_slots=occupied,
                capacity=maximum_authorized_ccx,
                reason="NO_PREPARED_WORK",
            )

        return ParallelAdmission(
            claim=claim,
            occupied_slots=occupied + 1,
            capacity=maximum_authorized_ccx,
            reason="CLAIMED",
        )

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from threadrom.factory.fem_factory_registry import (
    FemFactoryClaim,
    FemFactoryJobRecord,
    FemFactoryJobState,
    FemFactoryRegistry,
)


@dataclass(frozen=True, slots=True)
class WorkerExecutionResult:
    succeeded: bool
    manifest_path: Path | None = None
    failure_category: str | None = None
    failure_message: str | None = None


def execute_claimed_factory_job(
    *,
    registry: FemFactoryRegistry,
    claim: FemFactoryClaim,
    lease_seconds: int,
    execute: Callable[[FemFactoryClaim], WorkerExecutionResult],
    heartbeat_interval_seconds: float | None = None,
) -> FemFactoryJobRecord:
    """Run one claimed job while preserving registry ownership."""

    interval = (
        heartbeat_interval_seconds
        if heartbeat_interval_seconds is not None
        else max(1.0, lease_seconds / 3.0)
    )

    if interval <= 0 or interval >= lease_seconds:
        raise ValueError("Invalid worker heartbeat interval.")

    stop = threading.Event()
    heartbeat_errors: list[BaseException] = []

    def heartbeat() -> None:
        while not stop.wait(interval):
            try:
                registry.heartbeat_claim(
                    claim,
                    lease_seconds=lease_seconds,
                )
            except BaseException as exc:
                heartbeat_errors.append(exc)
                return

    thread = threading.Thread(
        target=heartbeat,
        name=f"threadrom-heartbeat-{claim.run_id}",
        daemon=True,
    )
    thread.start()

    try:
        try:
            result = execute(claim)
        except Exception as exc:
            stop.set()
            thread.join()

            if heartbeat_errors:
                raise RuntimeError(
                    "Worker lease heartbeat failed during execution."
                ) from heartbeat_errors[0]

            registry.transition_claimed_job(
                claim,
                new_state=FemFactoryJobState.QUARANTINED,
                failure_message=(
                    f"Unclassified worker exception: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )
            raise

        stop.set()
        thread.join()

        if heartbeat_errors:
            raise RuntimeError(
                "Worker lease heartbeat failed during execution; "
                "result requires recovery adjudication."
            ) from heartbeat_errors[0]

        if result.succeeded:
            if result.manifest_path is None:
                raise RuntimeError(
                    "Successful worker execution lacks manifest."
                )

            return registry.transition_claimed_job(
                claim,
                new_state=FemFactoryJobState.SOLVED,
                manifest_path=str(result.manifest_path),
            )

        if not result.failure_category or not result.failure_message:
            raise RuntimeError(
                "Failed worker execution lacks governed failure evidence."
            )

        return registry.transition_claimed_job(
            claim,
            new_state=FemFactoryJobState.FAILED,
            manifest_path=(
                None
                if result.manifest_path is None
                else str(result.manifest_path)
            ),
            failure_category=result.failure_category,
            failure_message=result.failure_message,
        )

    finally:
        stop.set()
        thread.join()

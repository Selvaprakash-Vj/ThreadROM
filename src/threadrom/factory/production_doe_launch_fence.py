from __future__ import annotations

import json
import msvcrt
import re
import subprocess

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


MAXIMUM_CONCURRENT_CCX = 4
CLAIM_FILENAME = "adaptive_launch_claim.json"


def count_running_ccx() -> int:
    """Count all Windows ccx.exe processes; fail closed if unavailable."""

    command = (
        "Get-CimInstance Win32_Process "
        "-Filter \"Name = 'ccx.exe'\" | "
        "Measure-Object | Select-Object -ExpandProperty Count"
    )

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            timeout=45,
            check=True,
        )
        output = result.stdout.strip()
        if not output.isdecimal():
            raise RuntimeError(
                f"Unparseable CalculiX process count: {output!r}"
            )
        return int(output)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            "Cannot establish global CalculiX process count; "
            "solver launch prohibited."
        ) from exc


@contextmanager
def reserve_adaptive_trial_launch(
    *,
    campaign_root: Path,
    case_run_id: str,
    trial_run_id: str,
    maximum_authorized_ccx: int | None = None,
    allow_initial_trial: bool = False,
) -> Iterator[Path]:
    """Hold the campaign launch lock across the ENTIRE solver operation.

    The durable claim is never automatically deleted, including on failure.
    A failed/interrupted run requires evidence review before any retry.
    This fence is not a substitute for separately verified authorization,
    predecessor evidence, or prepared-deck certification.
    """

    if not re.fullmatch(r"trm_fem_[0-9a-f]{12}", case_run_id):
        raise RuntimeError("Invalid governed case-run identity.")

    if type(allow_initial_trial) is not bool:
        raise RuntimeError("Invalid initial-trial reservation flag.")

    if allow_initial_trial:
        if trial_run_id != f"{case_run_id}_cal_01":
            raise RuntimeError(
                "Invalid bounded initial-trial identity."
            )
        if maximum_authorized_ccx is None:
            raise RuntimeError(
                "Initial-trial reservation requires an explicit "
                "authorized capacity limit."
            )
    elif not re.fullmatch(
        re.escape(case_run_id) + r"_cal_0[2-6]",
        trial_run_id,
    ):
        raise RuntimeError("Invalid bounded continuation-trial identity.")

    campaign_root = campaign_root.resolve(strict=True)
    run_dir = (
        campaign_root
        / "solver_preparation"
        / case_run_id
        / trial_run_id
    ).resolve(strict=True)

    expected_parent = (
        campaign_root
        / "solver_preparation"
        / case_run_id
    ).resolve(strict=True)

    if run_dir.parent != expected_parent:
        raise RuntimeError("Trial directory escaped its governed case.")

    lock_path = campaign_root / "adaptive_factory_launch.lock"

    with lock_path.open("a+b") as lock_file:
        # Windows byte-range locks require a byte to lock.
        if lock_file.seek(0, 2) == 0:
            lock_file.write(b"\0")
            lock_file.flush()

        lock_file.seek(0)

        try:
            msvcrt.locking(
                lock_file.fileno(),
                msvcrt.LK_NBLCK,
                1,
            )
        except OSError as exc:
            raise RuntimeError(
                "Another adaptive factory launch holds the campaign "
                "lock. Refusing a competing launch."
            ) from exc

        try:
            claim_path = run_dir / CLAIM_FILENAME
            manifest_path = run_dir / "fem_run_manifest.json"

            if manifest_path.exists():
                raise RuntimeError(
                    "Trial already has a FEM run manifest; "
                    "duplicate solve prohibited."
                )

            if claim_path.exists():
                raise RuntimeError(
                    "Trial already has a durable launch claim. "
                    "Inspect the existing run before any retry."
                )

            # Solver output without a manifest or claim may indicate an
            # interrupted legacy run; never silently overwrite it.
            for extension in (
                "sta",
                "dat",
                "frd",
                "rout",
                "cvg",
            ):
                artifact = run_dir / f"{trial_run_id}.{extension}"
                if artifact.exists():
                    raise RuntimeError(
                        "Pre-existing solver output requires review: "
                        f"{artifact}"
                    )

            running = count_running_ccx()

            if running >= MAXIMUM_CONCURRENT_CCX:
                raise RuntimeError(
                    f"CalculiX capacity exhausted: {running} running; "
                    f"limit {MAXIMUM_CONCURRENT_CCX}. No trial launched."
                )
            # Enforce the independently authorized capacity before
            # creating a durable launch claim.
            if maximum_authorized_ccx is not None:
                if (
                    type(maximum_authorized_ccx) is not int
                    or not 1 <= maximum_authorized_ccx <= MAXIMUM_CONCURRENT_CCX
                ):
                    raise RuntimeError(
                        "Invalid independently authorized solver-capacity limit."
                    )

                if running >= maximum_authorized_ccx:
                    raise RuntimeError(
                        "BLOCKED_SOLVER_CAPACITY: "
                        f"{running} CalculiX processes running; "
                        f"authorized limit {maximum_authorized_ccx}. "
                        "No launch claim created."
                    )
            # Atomic exclusive creation. A partial claim also fails closed.
            with claim_path.open("x", encoding="utf-8") as stream:
                json.dump(
                    {
                        "schema_version": 1,
                        "case_run_id": case_run_id,
                        "trial_run_id": trial_run_id,
                        "disposition": "LAUNCH_CLAIMED_NOT_COMPLETED",
                        "ccx_processes_at_admission": running,
                        "maximum_concurrent_ccx": (
                            MAXIMUM_CONCURRENT_CCX
                        ),
                        "automatic_retry_authorized": False,
                    },
                    stream,
                    indent=2,
                    sort_keys=True,
                )
                stream.write("\n")
                stream.flush()

            # The future coordinator must invoke and await its solver
            # inside this context. Do not release the lock at spawn.
            yield claim_path

        finally:
            lock_file.seek(0)
            msvcrt.locking(
                lock_file.fileno(),
                msvcrt.LK_UNLCK,
                1,
            )

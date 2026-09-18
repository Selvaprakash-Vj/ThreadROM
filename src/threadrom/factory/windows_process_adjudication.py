"""Fail-safe Windows process adjudication for stale FEM jobs."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

from dataclasses import dataclass
from enum import StrEnum


class FemProcessStatus(StrEnum):
    """Observed operating-system state for one stale FEM run."""

    LIVE_MATCH = "live_match"
    NO_MATCH = "no_match"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class WindowsProcessSnapshot:
    """Minimal immutable Windows process-table observation."""

    process_id: int
    parent_process_id: int
    executable_path: str | None
    command_line: str | None


@dataclass(frozen=True, slots=True)
class FemProcessAdjudication:
    """Result of comparing a stale FEM run with the process table."""

    status: FemProcessStatus
    matching_process_ids: tuple[int, ...]
    reason: str


def _contains_option_value(
    command_line: str,
    option: str,
    value: str,
) -> bool:
    pattern = (
        rf"(?:^|\s)"
        rf"{re.escape(option)}"
        rf"(?:\s+|=)"
        rf"[\"']?"
        rf"{re.escape(value)}"
        rf"[\"']?"
        rf"(?:\s|$)"
    )

    return re.search(
        pattern,
        command_line,
        flags=re.IGNORECASE,
    ) is not None


def adjudicate_process_snapshots(
    *,
    snapshots: tuple[WindowsProcessSnapshot, ...],
    run_id: str,
    case_id: str,
) -> FemProcessAdjudication:
    """Identify a live executor or CalculiX process for one run."""

    matching: list[int] = []

    for snapshot in snapshots:
        command_line = snapshot.command_line

        if not command_line:
            continue

        lower = command_line.lower()

        executor_match = (
            "run_phase3_production_doe_calibration_trial_case.py"
            in lower
            and _contains_option_value(
                command_line,
                "--case-id",
                case_id,
            )
        )

        executable_name = (
            os.path.basename(
                snapshot.executable_path or ""
            ).lower()
        )

        solver_match = (
            executable_name.startswith("ccx")
            and _contains_option_value(
                command_line,
                "-i",
                run_id,
            )
        )

        if executor_match or solver_match:
            matching.append(
                snapshot.process_id
            )

    if matching:
        return FemProcessAdjudication(
            status=FemProcessStatus.LIVE_MATCH,
            matching_process_ids=tuple(
                sorted(set(matching))
            ),
            reason=(
                "Matching Production-DOE executor or CalculiX "
                "process is still live."
            ),
        )

    return FemProcessAdjudication(
        status=FemProcessStatus.NO_MATCH,
        matching_process_ids=(),
        reason=(
            "No matching Production-DOE executor or CalculiX "
            "process is visible."
        ),
    )


def query_windows_processes() -> tuple[
    WindowsProcessSnapshot,
    ...,
]:
    """Query Windows processes without embedding FEM identity in PS."""

    if os.name != "nt":
        raise RuntimeError(
            "Windows FEM process adjudication requires Windows."
        )

    shell = (
        shutil.which("powershell.exe")
        or shutil.which("pwsh.exe")
        or shutil.which("pwsh")
    )

    if shell is None:
        raise RuntimeError(
            "No PowerShell executable is available for "
            "Windows process adjudication."
        )

    command = (
        "$ErrorActionPreference='Stop'; "
        "$p=@(Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,"
        "ExecutablePath,CommandLine); "
        "$p | ConvertTo-Json -Compress -Depth 3"
    )

    completed = subprocess.run(
        [
            shell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "Windows process query failed: "
            + completed.stderr[-1000:]
        )

    raw = completed.stdout.strip()

    if not raw:
        return ()

    payload = json.loads(raw)

    rows = (
        payload
        if isinstance(payload, list)
        else [payload]
    )

    snapshots = []

    for row in rows:
        snapshots.append(
            WindowsProcessSnapshot(
                process_id=int(
                    row["ProcessId"]
                ),
                parent_process_id=int(
                    row["ParentProcessId"]
                ),
                executable_path=(
                    None
                    if row.get("ExecutablePath") is None
                    else str(row["ExecutablePath"])
                ),
                command_line=(
                    None
                    if row.get("CommandLine") is None
                    else str(row["CommandLine"])
                ),
            )
        )

    return tuple(snapshots)


def adjudicate_live_fem_processes(
    *,
    run_id: str,
    case_id: str,
) -> FemProcessAdjudication:
    """Fail safely when OS process inspection itself is unavailable."""

    try:
        snapshots = query_windows_processes()
    except Exception as exc:
        return FemProcessAdjudication(
            status=FemProcessStatus.UNKNOWN,
            matching_process_ids=(),
            reason=(
                "Process-table inspection failed; recovery is "
                f"not authorized: {exc}"
            ),
        )

    return adjudicate_process_snapshots(
        snapshots=snapshots,
        run_id=run_id,
        case_id=case_id,
    )

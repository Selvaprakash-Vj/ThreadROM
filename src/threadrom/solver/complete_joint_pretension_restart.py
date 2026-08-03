"""Prepare non-destructive CalculiX pretension restart bundles."""

from __future__ import annotations

import json
import math
import re
import shutil
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

_STA_RECORD_PATTERN = re.compile(
    r"^\s*"
    r"(?P<step>\d+)\s+"
    r"(?P<increment>\d+)\s+"
    r"(?P<attempt>\d+)(?P<unsuccessful>U?)\s+"
    r"(?P<iterations>\d+)\s+"
    r"(?P<total_time>[+\-0-9.EeDd]+)\s+"
    r"(?P<step_time>[+\-0-9.EeDd]+)\s+"
    r"(?P<increment_time>[+\-0-9.EeDd]+)"
)

_STEP_MARKER_PATTERN = re.compile(
    r"(?m)^\*\* Step "
    r"(?P<checkpoint>\d+): "
    r"preload checkpoint .+$"
)


@dataclass(frozen=True)
class CalculixStaRecord:
    """One accepted or unsuccessful CalculiX STA record."""

    step: int
    increment: int
    attempt: int
    unsuccessful: bool
    iterations: int
    total_time: float
    step_time: float
    increment_time: float


@dataclass(frozen=True)
class PretensionRestartBundleSummary:
    """Summary of one prepared continuation bundle."""

    completed_checkpoint: int
    next_checkpoint: int
    checkpoint_count: int
    remaining_checkpoint_count: int
    continuation_job_name: str
    output_directory: Path
    continuation_input_path: Path
    restart_input_path: Path
    manifest_path: Path
    restart_size_bytes: int
    restart_sha256: str


def _fortran_float(value: str) -> float:
    """Parse either E- or D-formatted floating-point text."""

    return float(value.replace("D", "E").replace("d", "e"))


def parse_calculix_sta_records(
    text: str,
) -> tuple[CalculixStaRecord, ...]:
    """Parse nonlinear increment records from STA text."""

    records: list[CalculixStaRecord] = []

    for raw_line in text.splitlines():
        match = _STA_RECORD_PATTERN.match(raw_line)

        if match is None:
            continue

        records.append(
            CalculixStaRecord(
                step=int(match.group("step")),
                increment=int(match.group("increment")),
                attempt=int(match.group("attempt")),
                unsuccessful=bool(match.group("unsuccessful")),
                iterations=int(match.group("iterations")),
                total_time=_fortran_float(match.group("total_time")),
                step_time=_fortran_float(match.group("step_time")),
                increment_time=_fortran_float(match.group("increment_time")),
            )
        )

    return tuple(records)


def find_last_completed_checkpoint(
    records: tuple[CalculixStaRecord, ...],
    *,
    checkpoint_count: int,
    configured_step_time: float,
) -> int:
    """Return the latest fully completed preload step."""

    if checkpoint_count <= 0:
        raise ValueError("Checkpoint count must be positive.")

    if configured_step_time <= 0.0:
        raise ValueError("Configured step time must be positive.")

    completed_steps = {
        record.step
        for record in records
        if (
            not record.unsuccessful
            and 1 <= record.step <= checkpoint_count
            and math.isclose(
                record.step_time,
                configured_step_time,
                rel_tol=1.0e-8,
                abs_tol=1.0e-10,
            )
        )
    }

    if not completed_steps:
        raise ValueError("No fully completed preload checkpoint was found in the STA file.")

    return max(completed_steps)


def _sha256_file(path: Path) -> str:
    digest = sha256()

    with path.open("rb") as input_stream:
        for chunk in iter(
            lambda: input_stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _restart_write_keyword(
    *,
    write_frequency_steps: int,
    overlay_latest: bool,
) -> str:
    if write_frequency_steps <= 0:
        raise ValueError("Restart-write frequency must be positive.")

    keyword = f"*RESTART,WRITE,FREQUENCY={write_frequency_steps}"

    if overlay_latest:
        keyword += ",OVERLAY"

    return keyword


def _extract_remaining_steps(
    full_input_text: str,
    *,
    next_checkpoint: int,
    checkpoint_count: int,
    restart_write_keyword: str,
) -> str:
    """Extract remaining steps and reactivate restart output."""

    matches = tuple(_STEP_MARKER_PATTERN.finditer(full_input_text))

    checkpoints = tuple(int(match.group("checkpoint")) for match in matches)

    expected_checkpoints = tuple(range(1, checkpoint_count + 1))

    if checkpoints != expected_checkpoints:
        raise ValueError(
            "Input-deck checkpoint markers do not match the governed checkpoint sequence."
        )

    if not 1 <= next_checkpoint <= checkpoint_count:
        raise ValueError("Next checkpoint is outside the governed range.")

    marker_match = matches[next_checkpoint - 1]

    remaining_text = full_input_text[marker_match.start() :].strip()

    remaining_lines = [
        line
        for line in remaining_text.splitlines()
        if not line.upper().startswith("*RESTART,WRITE")
    ]

    static_index: int | None = None

    for line_index, line in enumerate(remaining_lines):
        if line.strip().upper() == "*STATIC":
            static_index = line_index
            break

    if static_index is None:
        raise ValueError("The first remaining checkpoint has no *STATIC keyword.")

    static_data_index: int | None = None

    for line_index in range(
        static_index + 1,
        len(remaining_lines),
    ):
        stripped = remaining_lines[line_index].strip()

        if not stripped or stripped.startswith("**"):
            continue

        if stripped.startswith("*"):
            raise ValueError("No static increment-control row was found.")

        static_data_index = line_index
        break

    if static_data_index is None:
        raise ValueError("No static increment-control row was found.")

    remaining_lines.insert(
        static_data_index + 1,
        restart_write_keyword,
    )

    return "*RESTART,READ\n" + "\n".join(remaining_lines) + "\n"


def prepare_pretension_restart_bundle(
    *,
    original_input_path: Path,
    sta_path: Path,
    restart_output_path: Path,
    output_directory: Path,
    continuation_job_name: str,
    checkpoint_count: int,
    configured_step_time: float,
    restart_write_frequency_steps: int,
    overlay_latest: bool,
) -> PretensionRestartBundleSummary:
    """Create an atomic, non-destructive restart bundle."""

    if not continuation_job_name.strip():
        raise ValueError("Continuation job name cannot be blank.")

    required_paths = (
        original_input_path,
        sta_path,
        restart_output_path,
    )

    for required_path in required_paths:
        if not required_path.is_file():
            raise FileNotFoundError(f"Required restart source missing: {required_path}")

    if restart_output_path.stat().st_size <= 0:
        raise ValueError("CalculiX restart output is empty.")

    records = parse_calculix_sta_records(
        sta_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    )

    completed_checkpoint = find_last_completed_checkpoint(
        records,
        checkpoint_count=checkpoint_count,
        configured_step_time=configured_step_time,
    )

    if completed_checkpoint >= checkpoint_count:
        raise ValueError(
            "All governed preload checkpoints are already complete; no continuation is required."
        )

    next_checkpoint = completed_checkpoint + 1

    restart_keyword = _restart_write_keyword(
        write_frequency_steps=(restart_write_frequency_steps),
        overlay_latest=overlay_latest,
    )

    continuation_text = _extract_remaining_steps(
        original_input_path.read_text(
            encoding="utf-8-sig",
        ),
        next_checkpoint=next_checkpoint,
        checkpoint_count=checkpoint_count,
        restart_write_keyword=restart_keyword,
    )

    if output_directory.exists():
        raise FileExistsError(f"Restart bundle already exists: {output_directory}")

    temporary_directory = output_directory.with_name(output_directory.name + ".tmp")

    if temporary_directory.exists():
        raise FileExistsError(f"Temporary restart bundle already exists: {temporary_directory}")

    temporary_directory.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_directory.mkdir()

    continuation_input_path = temporary_directory / f"{continuation_job_name}.inp"

    restart_input_path = temporary_directory / f"{continuation_job_name}.rin"

    manifest_path = temporary_directory / f"{continuation_job_name}.restart.json"

    try:
        continuation_input_path.write_text(
            continuation_text,
            encoding="utf-8",
            newline="\n",
        )

        shutil.copy2(
            restart_output_path,
            restart_input_path,
        )

        restart_digest = _sha256_file(restart_input_path)

        source_restart_digest = _sha256_file(restart_output_path)

        if restart_digest != source_restart_digest:
            raise RuntimeError("Copied restart input failed SHA-256 verification.")

        manifest = {
            "continuation_job_name": (continuation_job_name),
            "completed_checkpoint": (completed_checkpoint),
            "next_checkpoint": next_checkpoint,
            "checkpoint_count": checkpoint_count,
            "remaining_checkpoint_count": (checkpoint_count - completed_checkpoint),
            "configured_step_time": (configured_step_time),
            "restart_write_frequency_steps": (restart_write_frequency_steps),
            "overlay_latest": overlay_latest,
            "source": {
                "input_path": str(original_input_path.resolve()),
                "sta_path": str(sta_path.resolve()),
                "restart_output_path": str(restart_output_path.resolve()),
                "restart_output_size_bytes": (restart_output_path.stat().st_size),
                "restart_output_sha256": (source_restart_digest),
            },
            "bundle": {
                "input_name": (continuation_input_path.name),
                "restart_input_name": (restart_input_path.name),
                "restart_input_size_bytes": (restart_input_path.stat().st_size),
                "restart_input_sha256": (restart_digest),
            },
        }

        manifest_path.write_text(
            json.dumps(
                manifest,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

        temporary_directory.replace(output_directory)

    except Exception:
        shutil.rmtree(
            temporary_directory,
            ignore_errors=True,
        )
        raise

    final_input_path = output_directory / continuation_input_path.name

    final_restart_input_path = output_directory / restart_input_path.name

    final_manifest_path = output_directory / manifest_path.name

    return PretensionRestartBundleSummary(
        completed_checkpoint=completed_checkpoint,
        next_checkpoint=next_checkpoint,
        checkpoint_count=checkpoint_count,
        remaining_checkpoint_count=(checkpoint_count - completed_checkpoint),
        continuation_job_name=(continuation_job_name),
        output_directory=output_directory,
        continuation_input_path=final_input_path,
        restart_input_path=(final_restart_input_path),
        manifest_path=final_manifest_path,
        restart_size_bytes=(final_restart_input_path.stat().st_size),
        restart_sha256=_sha256_file(final_restart_input_path),
    )

"""Parse CalculiX nonlinear progress files."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

_FLOAT_TOKEN = (
    r"[+-]?"
    r"(?:\d+(?:\.\d*)?|\.\d+)"
    r"(?:[EeDd][+-]?\d+)?"
)

_STATUS_PATTERN = re.compile(
    rf"^\s*"
    rf"(\d+)\s+"
    rf"(\d+)\s+"
    rf"(\d+)\s+"
    rf"(\d+)\s+"
    rf"({_FLOAT_TOKEN})\s+"
    rf"({_FLOAT_TOKEN})\s+"
    rf"({_FLOAT_TOKEN})"
    rf"\s*$"
)

_CONVERGENCE_PATTERN = re.compile(
    rf"^\s*"
    rf"(\d+)\s+"
    rf"(\d+)\s+"
    rf"(\d+)\s+"
    rf"(\d+)\s+"
    rf"(\d+)\s+"
    rf"({_FLOAT_TOKEN})\s+"
    rf"({_FLOAT_TOKEN})\s+"
    rf"({_FLOAT_TOKEN})\s+"
    rf"({_FLOAT_TOKEN})"
    rf"\s*$"
)


@dataclass(frozen=True)
class AcceptedIncrement:
    """One accepted CalculiX nonlinear increment."""

    step: int
    increment: int
    attempt: int
    iterations: int
    total_time: float
    step_time: float
    increment_time: float


@dataclass(frozen=True)
class ConvergenceIteration:
    """One CalculiX nonlinear convergence iteration."""

    step: int
    increment: int
    attempt: int
    iteration: int
    contact_elements: int
    residual_force_percent: float
    correction_displacement_percent: float
    residual_flux_percent: float
    correction_temperature_percent: float


def _fortran_float(value: str) -> float:
    """Convert a Fortran E- or D-notation number."""

    return float(value.replace("D", "E").replace("d", "e"))


def parse_status_increments(
    content: str,
) -> tuple[AcceptedIncrement, ...]:
    """Parse accepted increments from CalculiX STA text."""

    increments: list[AcceptedIncrement] = []

    for line in content.splitlines():
        match = _STATUS_PATTERN.fullmatch(line)

        if match is None:
            continue

        increments.append(
            AcceptedIncrement(
                step=int(match.group(1)),
                increment=int(match.group(2)),
                attempt=int(match.group(3)),
                iterations=int(match.group(4)),
                total_time=_fortran_float(match.group(5)),
                step_time=_fortran_float(match.group(6)),
                increment_time=_fortran_float(match.group(7)),
            )
        )

    return tuple(increments)


def parse_convergence_iterations(
    content: str,
) -> tuple[ConvergenceIteration, ...]:
    """Parse iteration records from CalculiX CVG text."""

    iterations: list[ConvergenceIteration] = []

    for line in content.splitlines():
        match = _CONVERGENCE_PATTERN.fullmatch(line)

        if match is None:
            continue

        iterations.append(
            ConvergenceIteration(
                step=int(match.group(1)),
                increment=int(match.group(2)),
                attempt=int(match.group(3)),
                iteration=int(match.group(4)),
                contact_elements=int(match.group(5)),
                residual_force_percent=_fortran_float(match.group(6)),
                correction_displacement_percent=(_fortran_float(match.group(7))),
                residual_flux_percent=_fortran_float(match.group(8)),
                correction_temperature_percent=(_fortran_float(match.group(9))),
            )
        )

    return tuple(iterations)


def _read_live_text(path: Path) -> str:
    """Read a solver file that may still be growing."""

    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def build_nonlinear_progress_summary(
    sta_path: Path,
    cvg_path: Path,
) -> dict[str, object]:
    """Build a structured nonlinear-progress summary."""

    increments = parse_status_increments(_read_live_text(sta_path))

    iterations = parse_convergence_iterations(_read_live_text(cvg_path))

    latest_increment: dict[str, object] | None = None
    latest_iteration: dict[str, object] | None = None

    if increments:
        latest_increment = asdict(increments[-1])

    if iterations:
        latest_iteration = asdict(iterations[-1])

    return {
        "schema_version": 1,
        "sources": {
            "sta": str(sta_path),
            "cvg": str(cvg_path),
        },
        "accepted_increment_count": len(increments),
        "iteration_record_count": len(iterations),
        "latest_accepted_increment": latest_increment,
        "latest_iteration": latest_iteration,
        "accepted_increments": [asdict(increment) for increment in increments],
        "iterations": [asdict(iteration) for iteration in iterations],
    }


def write_nonlinear_progress_json(
    sta_path: Path,
    cvg_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Write the nonlinear-progress summary as JSON."""

    payload = build_nonlinear_progress_summary(
        sta_path,
        cvg_path,
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return payload

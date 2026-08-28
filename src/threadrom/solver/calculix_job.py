"""Generic governed CalculiX job execution."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from threadrom.solver.calculix_mesh_transfer import (
    CalculixRunResult,
)


class CalculixJobError(RuntimeError):
    """Structured CalculiX failure preserving RuntimeError compatibility."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        return_code: int | None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.return_code = return_code


@dataclass(frozen=True, slots=True)
class CalculixJobDefinition:
    """Minimal solver-execution contract."""

    executable_relative_path: Path
    job_name: str
    timeout_seconds: int

    def __post_init__(self) -> None:
        if not self.job_name.strip():
            raise ValueError("job_name must not be blank.")

        if self.timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be positive."
            )


def run_calculix_job(
    *,
    project_root: Path,
    input_path: Path,
    definition: CalculixJobDefinition,
) -> CalculixRunResult:
    """Execute one governed CalculiX input deck."""

    executable_path = (
        project_root
        / definition.executable_relative_path
    )

    if not executable_path.exists():
        raise FileNotFoundError(
            f"CalculiX executable not found: {executable_path}"
        )

    if (
        not input_path.exists()
        or input_path.stat().st_size <= 0
    ):
        raise FileNotFoundError(
            f"Valid CalculiX input not found: {input_path}"
        )

    if input_path.stem != definition.job_name:
        raise ValueError(
            "Input filename must match the configured job name."
        )

    working_directory = input_path.parent

    completed = subprocess.run(
        [
            str(executable_path),
            "-i",
            definition.job_name,
        ],
        cwd=working_directory,
        capture_output=True,
        text=True,
        timeout=definition.timeout_seconds,
        check=False,
    )

    stdout_log_path = (
        working_directory
        / f"{definition.job_name}.stdout.log"
    )
    stderr_log_path = (
        working_directory
        / f"{definition.job_name}.stderr.log"
    )

    stdout_log_path.write_text(
        completed.stdout,
        encoding="utf-8",
        errors="replace",
    )
    stderr_log_path.write_text(
        completed.stderr,
        encoding="utf-8",
        errors="replace",
    )

    dat_path = (
        working_directory
        / f"{definition.job_name}.dat"
    )
    frd_path = (
        working_directory
        / f"{definition.job_name}.frd"
    )
    sta_path = (
        working_directory
        / f"{definition.job_name}.sta"
    )

    combined_diagnostics = (
        completed.stdout
        + "\n"
        + completed.stderr
    )

    if dat_path.exists():
        combined_diagnostics += (
            "\n"
            + dat_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        )

    if completed.returncode != 0:
        raise CalculixJobError(
            "CalculiX returned a nonzero exit code.\n"
            + combined_diagnostics[-4000:],
            category="nonzero_exit",
            return_code=completed.returncode,
        )

    if "*ERROR" in combined_diagnostics.upper():
        raise CalculixJobError(
            "CalculiX reported an input or solution error.\n"
            + combined_diagnostics[-4000:],
            category="solver_reported_error",
            return_code=completed.returncode,
        )

    required_outputs = (
        dat_path,
        frd_path,
        sta_path,
    )

    missing_outputs = [
        path
        for path in required_outputs
        if (
            not path.exists()
            or path.stat().st_size <= 0
        )
    ]

    if missing_outputs:
        raise CalculixJobError(
            "CalculiX did not create required outputs: "
            + ", ".join(
                str(path)
                for path in missing_outputs
            ),
            category="missing_required_output",
            return_code=completed.returncode,
        )

    return CalculixRunResult(
        return_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        input_path=input_path,
        dat_path=dat_path,
        frd_path=frd_path,
        sta_path=sta_path,
        stdout_log_path=stdout_log_path,
        stderr_log_path=stderr_log_path,
    )

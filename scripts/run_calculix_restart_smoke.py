"""Run a real lightweight CalculiX restart smoke proof."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from threadrom.solver.complete_joint_pretension_restart import (
    parse_calculix_sta_records,
    prepare_pretension_restart_bundle,
)

CCX_PATH = (
    PROJECT_ROOT / "tools" / "calculix" / "2.23.0" / "CalculiX-2.23.0-win-x64" / "bin" / "ccx.exe"
)

FLOAT_PATTERN = (
    r"[+\-]?"
    r"(?:\d+(?:\.\d*)?|\.\d+)"
    r"(?:[EeDd][+\-]?\d+)?"
)

NODE_RESULT_PATTERN = re.compile(
    rf"^\s*7\s+"
    rf"(?P<x>{FLOAT_PATTERN})\s+"
    rf"(?P<y>{FLOAT_PATTERN})\s+"
    rf"(?P<z>{FLOAT_PATTERN})\s*$"
)


def _fortran_float(value: str) -> float:
    """Parse E- or D-formatted floating-point output."""

    return float(value.replace("D", "E").replace("d", "e"))


def _run_calculix(
    *,
    job_name: str,
    working_directory: Path,
) -> dict[str, object]:
    """Run one single-threaded CalculiX smoke job."""

    stdout_path = working_directory / f"{job_name}.solver.stdout.log"

    stderr_path = working_directory / f"{job_name}.solver.stderr.log"

    environment = os.environ.copy()

    environment.update(
        {
            "OMP_NUM_THREADS": "1",
            "CCX_NPROC_STIFFNESS": "1",
            "CCX_NPROC_EQUATION_SOLVER": "1",
            "CCX_NPROC_RESULTS": "1",
            "NUMBER_OF_CPUS": "1",
        }
    )

    with (
        stdout_path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as stdout_stream,
        stderr_path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as stderr_stream,
    ):
        completed = subprocess.run(
            [
                str(CCX_PATH),
                "-i",
                job_name,
            ],
            cwd=working_directory,
            stdout=stdout_stream,
            stderr=stderr_stream,
            timeout=120,
            env=environment,
            check=False,
            text=True,
        )

    if completed.returncode != 0:
        stdout_tail = stdout_path.read_text(
            encoding="utf-8",
            errors="replace",
        )[-4000:]

        stderr_tail = stderr_path.read_text(
            encoding="utf-8",
            errors="replace",
        )[-4000:]

        raise RuntimeError(
            "CalculiX smoke job failed.\n"
            f"Job: {job_name}\n"
            f"Return code: {completed.returncode}\n"
            f"STDOUT tail:\n{stdout_tail}\n"
            f"STDERR tail:\n{stderr_tail}"
        )

    return {
        "job_name": job_name,
        "return_code": completed.returncode,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }


def _monitor_z_displacement(
    dat_path: Path,
) -> float:
    """Read the final Z displacement of monitor node 7."""

    if not dat_path.is_file():
        raise FileNotFoundError(f"CalculiX DAT output missing: {dat_path}")

    values: list[float] = []

    for line in dat_path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        match = NODE_RESULT_PATTERN.match(line)

        if match is None:
            continue

        values.append(_fortran_float(match.group("z")))

    if not values:
        raise ValueError(f"No displacement result was found for monitor node 7 in {dat_path}.")

    return values[-1]


def _model_definition() -> str:
    """Return a single C3D8 elastic cube model."""

    return """*HEADING
ThreadROM CalculiX restart smoke model
*NODE
1, 0.0, 0.0, 0.0
2, 1.0, 0.0, 0.0
3, 1.0, 1.0, 0.0
4, 0.0, 1.0, 0.0
5, 0.0, 0.0, 1.0
6, 1.0, 0.0, 1.0
7, 1.0, 1.0, 1.0
8, 0.0, 1.0, 1.0
*ELEMENT, TYPE=C3D8, ELSET=CUBE
1, 1, 2, 3, 4, 5, 6, 7, 8
*NSET, NSET=BOTTOM
1, 2, 3, 4
*NSET, NSET=TOP
5, 6, 7, 8
*NSET, NSET=MONITOR
7
*MATERIAL, NAME=STEEL
*ELASTIC
210000.0, 0.30
*SOLID SECTION, ELSET=CUBE, MATERIAL=STEEL
"""


def _step_one() -> str:
    """Return the first checkpoint step."""

    return """** Step 1: preload checkpoint 0.500000
*STEP, NLGEOM=YES, INC=20
*STATIC
1.000000000000e+00, 1.000000000000e+00, 1.000000000000e-08, 1.000000000000e+00
*RESTART,WRITE,FREQUENCY=1,OVERLAY
*BOUNDARY
BOTTOM, 1, 3, 0.0
*CLOAD
TOP, 3, -2.500000000000e+02
*NODE PRINT, NSET=MONITOR
U
*END STEP
"""


def _step_two() -> str:
    """Return the second checkpoint step."""

    return """** Step 2: preload checkpoint 1.000000
*STEP, NLGEOM=YES, INC=20
*STATIC
1.000000000000e+00, 1.000000000000e+00, 1.000000000000e-08, 1.000000000000e+00
*CLOAD
TOP, 3, -5.000000000000e+02
*NODE PRINT, NSET=MONITOR
U
*END STEP
"""


def main() -> None:
    """Execute checkpoint, continuation, and direct solves."""

    if not CCX_PATH.is_file():
        raise FileNotFoundError(f"CalculiX executable missing: {CCX_PATH}")

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    smoke_root = PROJECT_ROOT / "simulations" / "staging" / "calculix_restart_smoke" / timestamp

    smoke_root.mkdir(
        parents=True,
        exist_ok=False,
    )

    source_directory = smoke_root / "source_checkpoint"
    direct_directory = smoke_root / "direct_solution"

    source_directory.mkdir()
    direct_directory.mkdir()

    source_job_name = "restart_smoke_source"
    continuation_job_name = "restart_smoke_resume"
    direct_job_name = "restart_smoke_direct"

    model_text = _model_definition()
    first_step_text = _step_one()
    second_step_text = _step_two()

    full_governed_text = model_text + first_step_text + second_step_text

    full_input_path = smoke_root / "governed_full.inp"

    full_input_path.write_text(
        full_governed_text,
        encoding="utf-8",
        newline="\n",
    )

    source_input_path = source_directory / f"{source_job_name}.inp"

    source_input_path.write_text(
        model_text + first_step_text,
        encoding="utf-8",
        newline="\n",
    )

    source_run = _run_calculix(
        job_name=source_job_name,
        working_directory=source_directory,
    )

    source_sta_path = source_directory / f"{source_job_name}.sta"

    source_restart_path = source_directory / f"{source_job_name}.rout"

    if not source_restart_path.is_file():
        raise FileNotFoundError(
            f"The source solve did not create a restart output: {source_restart_path}"
        )

    if source_restart_path.stat().st_size <= 0:
        raise ValueError("The source restart output is empty.")

    bundle_directory = smoke_root / "restart_bundle"

    bundle = prepare_pretension_restart_bundle(
        original_input_path=full_input_path,
        sta_path=source_sta_path,
        restart_output_path=source_restart_path,
        output_directory=bundle_directory,
        continuation_job_name=continuation_job_name,
        checkpoint_count=2,
        configured_step_time=1.0,
        restart_write_frequency_steps=1,
        overlay_latest=True,
    )

    continuation_text = bundle.continuation_input_path.read_text(encoding="utf-8")

    first_nonblank_line = next(
        line.strip() for line in continuation_text.splitlines() if line.strip()
    )

    if first_nonblank_line != "*RESTART,READ":
        raise RuntimeError("*RESTART,READ is not the first nonblank continuation line.")

    if "** Step 1:" in continuation_text:
        raise RuntimeError("Completed checkpoint 1 remains in the continuation input.")

    if "** Step 2:" not in continuation_text:
        raise RuntimeError("Remaining checkpoint 2 is absent from the continuation input.")

    continuation_run = _run_calculix(
        job_name=continuation_job_name,
        working_directory=bundle_directory,
    )

    continuation_sta_path = bundle_directory / f"{continuation_job_name}.sta"

    continuation_records = parse_calculix_sta_records(
        continuation_sta_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    )

    completed_continuation_steps = {
        record.step
        for record in continuation_records
        if (
            not record.unsuccessful
            and math.isclose(
                record.step_time,
                1.0,
                rel_tol=1.0e-8,
                abs_tol=1.0e-10,
            )
        )
    }

    if 2 not in completed_continuation_steps:
        raise RuntimeError("Continuation did not complete restart step 2.")

    direct_input_path = direct_directory / f"{direct_job_name}.inp"

    direct_input_path.write_text(
        full_governed_text,
        encoding="utf-8",
        newline="\n",
    )

    direct_run = _run_calculix(
        job_name=direct_job_name,
        working_directory=direct_directory,
    )

    continuation_displacement = _monitor_z_displacement(
        bundle_directory / f"{continuation_job_name}.dat"
    )

    direct_displacement = _monitor_z_displacement(direct_directory / f"{direct_job_name}.dat")

    displacement_difference = abs(continuation_displacement - direct_displacement)

    if not math.isclose(
        continuation_displacement,
        direct_displacement,
        rel_tol=1.0e-9,
        abs_tol=1.0e-12,
    ):
        raise RuntimeError(
            "Restarted and uninterrupted final "
            "displacements differ.\n"
            f"Restarted: {continuation_displacement:.12e}\n"
            f"Direct: {direct_displacement:.12e}\n"
            f"Difference: {displacement_difference:.12e}"
        )

    report = {
        "status": "pass",
        "calculix_executable": str(CCX_PATH),
        "source_run": source_run,
        "continuation_run": continuation_run,
        "direct_run": direct_run,
        "checkpoint": {
            "completed_checkpoint": (bundle.completed_checkpoint),
            "next_checkpoint": bundle.next_checkpoint,
            "remaining_checkpoint_count": (bundle.remaining_checkpoint_count),
            "restart_size_bytes": (bundle.restart_size_bytes),
            "restart_sha256": bundle.restart_sha256,
        },
        "verification": {
            "continuation_completed_steps": sorted(completed_continuation_steps),
            "continuation_monitor_z_displacement_mm": (continuation_displacement),
            "direct_monitor_z_displacement_mm": (direct_displacement),
            "absolute_difference_mm": (displacement_difference),
            "relative_tolerance": 1.0e-9,
            "absolute_tolerance_mm": 1.0e-12,
        },
        "artifact_directory": str(smoke_root),
    }

    report_path = smoke_root / "calculix_restart_smoke_report.json"

    report_path.write_text(
        json.dumps(
            report,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print("CALCULIX RESTART SMOKE: PASS")
    print(f"Completed checkpoint: {bundle.completed_checkpoint}/2")
    print(f"Resumed checkpoint: {bundle.next_checkpoint}/2")
    print(f"Restart size: {bundle.restart_size_bytes} bytes")
    print(f"Restart SHA256: {bundle.restart_sha256}")
    print(f"Restarted final UZ: {continuation_displacement:.12e} mm")
    print(f"Direct final UZ: {direct_displacement:.12e} mm")
    print(f"Absolute difference: {displacement_difference:.12e} mm")
    print(f"Report: {report_path}")
    print(f"Artifacts: {smoke_root}")


if __name__ == "__main__":
    main()

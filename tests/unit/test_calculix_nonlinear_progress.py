"""Tests for CalculiX nonlinear-progress parsing."""

from __future__ import annotations

import json
from pathlib import Path

from threadrom.postprocessing.calculix_nonlinear_progress import (
    build_nonlinear_progress_summary,
    parse_convergence_iterations,
    parse_status_increments,
    write_nonlinear_progress_json,
)


def test_parse_status_increments() -> None:
    """Accepted increments are parsed from STA text."""

    content = """
SUMMARY OF JOB INFORMATION
 STEP INC ATT ITRS TOT TIME STEP TIME INC TIME
 1 1 1 15 0.500000E-01 0.500000E-01 0.500000E-01
 1 2 2 8 0.750000D-01 0.750000D-01 0.250000D-01
 incomplete live line
"""

    increments = parse_status_increments(content)

    assert len(increments) == 2
    assert increments[0].increment == 1
    assert increments[0].iterations == 15
    assert increments[0].step_time == 0.05
    assert increments[1].attempt == 2
    assert increments[1].increment_time == 0.025


def test_parse_convergence_iterations() -> None:
    """Iteration metrics are parsed from CVG text."""

    content = """
SUMMARY OF CONVERGENCE INFORMATION
 1 1 1 1 511110 0.1124E+05 0.1000E+03 0.0 0.0
 1 1 1 15 135776 0.0000E+00 0.5810E-01 0.0 0.0
 incomplete live line
"""

    iterations = parse_convergence_iterations(content)

    assert len(iterations) == 2
    assert iterations[0].contact_elements == 511110
    assert iterations[0].residual_force_percent == 11240.0
    assert iterations[1].iteration == 15
    assert iterations[1].correction_displacement_percent == 0.0581


def test_build_summary_for_empty_files(
    tmp_path: Path,
) -> None:
    """Empty live files produce a valid empty summary."""

    sta_path = tmp_path / "job.sta"
    cvg_path = tmp_path / "job.cvg"

    sta_path.write_text("", encoding="utf-8")
    cvg_path.write_text("", encoding="utf-8")

    summary = build_nonlinear_progress_summary(
        sta_path,
        cvg_path,
    )

    assert summary["accepted_increment_count"] == 0
    assert summary["iteration_record_count"] == 0
    assert summary["latest_accepted_increment"] is None
    assert summary["latest_iteration"] is None


def test_write_progress_json(
    tmp_path: Path,
) -> None:
    """Structured progress is written as valid JSON."""

    sta_path = tmp_path / "job.sta"
    cvg_path = tmp_path / "job.cvg"
    output_path = tmp_path / "results" / "progress.json"

    sta_path.write_text(
        "1 1 1 4 0.1 0.1 0.1\n",
        encoding="utf-8",
    )

    cvg_path.write_text(
        "1 1 1 4 200 0.0 0.01 0.0 0.0\n",
        encoding="utf-8",
    )

    payload = write_nonlinear_progress_json(
        sta_path,
        cvg_path,
        output_path,
    )

    saved_payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["accepted_increment_count"] == 1
    assert saved_payload == payload

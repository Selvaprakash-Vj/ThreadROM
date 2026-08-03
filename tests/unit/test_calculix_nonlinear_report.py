"""Tests for nonlinear CalculiX progress reports."""

from __future__ import annotations

import json
from pathlib import Path

from threadrom.postprocessing.calculix_nonlinear_report import (
    NonlinearReportContext,
    write_nonlinear_progress_report,
)


def _write_progress(
    path: Path,
    *,
    step_time: float,
) -> None:
    increment = {
        "step": 1,
        "increment": 1,
        "attempt": 1,
        "iterations": 15,
        "total_time": step_time,
        "step_time": step_time,
        "increment_time": step_time,
    }

    iteration = {
        "step": 1,
        "increment": 2,
        "attempt": 1,
        "iteration": 5,
        "contact_elements": 178583,
        "residual_force_percent": 10.69,
        "correction_displacement_percent": 5.595,
        "residual_flux_percent": 0.0,
        "correction_temperature_percent": 0.0,
    }

    payload = {
        "accepted_increment_count": 1,
        "iteration_record_count": 20,
        "latest_accepted_increment": increment,
        "latest_iteration": iteration,
        "accepted_increments": [increment],
        "iterations": [iteration],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _write_validation(
    path: Path,
) -> None:
    payload = {
        "overall_status": "pass",
        "passed_count": 1,
        "failed_count": 0,
        "pending_count": 0,
        "validations": [
            {
                "step": 1,
                "increment": 1,
                "status": "pass",
                "expected_preload_n": 250.0,
                "actual_preload_n": 250.0,
                "force_error_n": 0.0,
                "control_displacement_mm": 1.512816e-5,
            }
        ],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _context(
    *,
    analysis_complete: bool = False,
) -> NonlinearReportContext:
    return NonlinearReportContext(
        simulation_id="TRM-SIM-000009",
        mesh_id="TRM-MSH-000008",
        element_type="C3D10",
        mesh_level="coarse",
        node_count=259267,
        element_count=166445,
        preload_force_n=5000.0,
        contact_pair_count=4,
        guidance_sample_count=304,
        boundary_region_node_count=1340,
        solver_description=("CalculiX 2.23 / SPOOLES / 1 CPU"),
        analysis_complete=analysis_complete,
    )


def test_write_live_progress_report(
    tmp_path: Path,
) -> None:
    """A live report remains explicitly in progress."""

    progress_path = tmp_path / "progress.json"
    figure_path = tmp_path / "convergence.svg"
    validation_path = tmp_path / "pretension_validation.json"
    report_path = tmp_path / "report.md"

    _write_progress(
        progress_path,
        step_time=0.05,
    )

    figure_path.write_text(
        "<svg></svg>",
        encoding="utf-8",
    )

    _write_validation(validation_path)

    write_nonlinear_progress_report(
        progress_path,
        figure_path,
        report_path,
        _context(),
        pretension_validation_json_path=(validation_path),
    )

    report = report_path.read_text(encoding="utf-8")

    assert "| Status | In progress |" in report
    assert "| Accepted step progress | 5.00% |" in report
    assert "| Nominal ramped preload | 250.000 N |" in report
    assert "## Pretension ramp validation" in report
    assert "| Validation status | Pass |" in report
    assert "| Expected ramped preload | 250.000000 N |" in report
    assert "| Extracted pretension force | 250.000000 N |" in report
    assert "| Pretension-force error | 0 N |" in report
    assert "not an equilibrium verification" in report
    assert "independent thread-turn result sets" in report


def test_write_completed_report(
    tmp_path: Path,
) -> None:
    """Completion status is controlled explicitly."""

    progress_path = tmp_path / "progress.json"
    figure_path = tmp_path / "convergence.svg"
    report_path = tmp_path / "report.md"

    _write_progress(
        progress_path,
        step_time=1.0,
    )

    figure_path.write_text(
        "<svg></svg>",
        encoding="utf-8",
    )

    write_nonlinear_progress_report(
        progress_path,
        figure_path,
        report_path,
        _context(analysis_complete=True),
    )

    report = report_path.read_text(encoding="utf-8")

    assert "| Status | Completed |" in report
    assert "| Accepted step progress | 100.00% |" in report
    assert "| Nominal ramped preload | 5000.000 N |" in report


def test_write_report_with_external_equilibrium(
    tmp_path: Path,
) -> None:
    """External-equilibrium evidence is governed and rendered."""

    progress_path = tmp_path / "progress.json"
    figure_path = tmp_path / "convergence.svg"
    equilibrium_path = tmp_path / "external_equilibrium.json"
    report_path = tmp_path / "report.md"

    _write_progress(
        progress_path,
        step_time=0.05,
    )

    figure_path.write_text(
        "<svg></svg>",
        encoding="utf-8",
    )

    equilibrium_path.write_text(
        """
{
  "overall_status": "pending",
  "support_set_name": "HEAD_MEMBER_SUPPORT_BAND",
  "passed_count": 1,
  "failed_count": 0,
  "pending_count": 1,
  "validations": [
    {
      "step": 1,
      "increment": 1,
      "accepted_time": 0.05,
      "status": "pass",
      "force_components_n": [
        6.355773e-08,
        3.999832e-08,
        -3.253635e-11
      ],
      "maximum_absolute_component_n": 6.355773e-08
    },
    {
      "step": 1,
      "increment": 2,
      "accepted_time": 0.10,
      "status": "pending",
      "reason": "No matching complete DAT record."
    }
  ]
}
""".strip()
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    write_nonlinear_progress_report(
        progress_path,
        figure_path,
        report_path,
        _context(),
        external_equilibrium_json_path=(equilibrium_path),
    )

    report = report_path.read_text(encoding="utf-8")

    assert "## External support equilibrium" in report

    assert "| Validation status | Pending |" in report

    assert "| Support set | `HEAD_MEMBER_SUPPORT_BAND` |" in report

    assert "| Pending increments | 1 |" in report

    assert "| Latest record status | Pending |" in report

    assert "| Support-force vector | Pending |" in report

    assert "| External-equilibrium JSON |" in report

"""Tests for CalculiX convergence plotting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from threadrom.postprocessing.calculix_convergence_plot import (
    load_iteration_points,
    write_convergence_figure,
)


def _write_progress_fixture(
    path: Path,
) -> None:
    payload = {
        "schema_version": 1,
        "accepted_increment_count": 1,
        "iterations": [
            {
                "step": 1,
                "increment": 1,
                "attempt": 1,
                "iteration": 1,
                "contact_elements": 500,
                "residual_force_percent": 1000.0,
                "correction_displacement_percent": 100.0,
                "residual_flux_percent": 0.0,
                "correction_temperature_percent": 0.0,
            },
            {
                "step": 1,
                "increment": 1,
                "attempt": 1,
                "iteration": 2,
                "contact_elements": 300,
                "residual_force_percent": 25.0,
                "correction_displacement_percent": 2.0,
                "residual_flux_percent": 0.0,
                "correction_temperature_percent": 0.0,
            },
            {
                "step": 1,
                "increment": 2,
                "attempt": 1,
                "iteration": 1,
                "contact_elements": 450,
                "residual_force_percent": 500.0,
                "correction_displacement_percent": 50.0,
                "residual_flux_percent": 0.0,
                "correction_temperature_percent": 0.0,
            },
        ],
    }

    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def test_load_iteration_points(
    tmp_path: Path,
) -> None:
    """Iteration records become ordered plot points."""

    input_path = tmp_path / "progress.json"
    _write_progress_fixture(input_path)

    points = load_iteration_points(input_path)

    assert len(points) == 3
    assert points[0].global_iteration == 1
    assert points[1].residual_force_percent == 25.0
    assert points[2].increment == 2


def test_write_convergence_figure(
    tmp_path: Path,
) -> None:
    """A non-empty PNG figure is produced."""

    input_path = tmp_path / "progress.json"
    output_path = tmp_path / "figures" / "convergence.png"

    _write_progress_fixture(input_path)

    result = write_convergence_figure(
        input_path,
        output_path,
    )

    assert result == output_path
    assert output_path.exists()
    assert output_path.stat().st_size > 1000


def test_empty_history_is_rejected(
    tmp_path: Path,
) -> None:
    """An empty history cannot produce a figure."""

    input_path = tmp_path / "progress.json"

    input_path.write_text(
        json.dumps(
            {
                "accepted_increment_count": 0,
                "iterations": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="empty iteration history",
    ):
        write_convergence_figure(
            input_path,
            tmp_path / "empty.png",
        )

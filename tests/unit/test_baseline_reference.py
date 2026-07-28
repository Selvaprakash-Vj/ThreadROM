"""Tests for the configured baseline analytical reference."""

from pathlib import Path

import pytest

from threadrom.engineering.baseline_reference import (
    load_baseline_thread_reference,
    render_baseline_thread_report,
)


def test_baseline_thread_reference_loads() -> None:
    """The baseline configuration produces the expected reference."""

    project_root = Path(__file__).resolve().parents[2]

    reference = load_baseline_thread_reference(
        project_root / "config" / "baseline_fastener.toml"
    )

    assert reference.geometry_id == "TRM-GEO-000001"
    assert reference.simulation_id == "TRM-SIM-000001"
    assert reference.designation == "M10x1.5"

    assert reference.dimensions.tensile_stress_area_mm2 == pytest.approx(
        57.9895969018,
    )


def test_baseline_report_contains_traceability() -> None:
    """The report includes the persistent engineering identities."""

    project_root = Path(__file__).resolve().parents[2]

    reference = load_baseline_thread_reference(
        project_root / "config" / "baseline_fastener.toml"
    )

    report = render_baseline_thread_report(reference)

    assert "TRM-GEO-000001" in report
    assert "TRM-SIM-000001" in report
    assert "M10 × 1.5" in report
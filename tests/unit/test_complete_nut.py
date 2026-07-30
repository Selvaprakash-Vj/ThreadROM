"""Tests for the complete internally threaded nut."""

from pathlib import Path

import pytest

from threadrom.geometry.complete_nut import (
    build_complete_nut,
    load_complete_nut_definitions,
    measure_complete_nut,
)
from threadrom.geometry.nut_blank import measure_nut_blank

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_complete_nut_definitions_are_consistent() -> None:
    """The governed nut and internal-thread definitions agree."""

    nut_definition, thread_definition = (
        load_complete_nut_definitions(PROJECT_ROOT)
    )

    assert nut_definition.geometry_id == "TRM-GEO-000001"
    assert nut_definition.assembly_id == "TRM-ASM-000001"

    assert nut_definition.nominal_diameter_mm == pytest.approx(
        thread_definition.nominal_diameter_mm
    )
    assert nut_definition.pitch_mm == pytest.approx(
        thread_definition.pitch_mm
    )
    assert nut_definition.bore_diameter_mm == pytest.approx(
        thread_definition.minor_diameter_mm
    )
    assert nut_definition.thickness_mm == pytest.approx(
        thread_definition.thread_length_mm
    )


def test_complete_threaded_nut_is_valid() -> None:
    """The helical cut produces one valid threaded nut solid."""

    nut_definition, thread_definition = (
        load_complete_nut_definitions(PROJECT_ROOT)
    )

    build = build_complete_nut(
        nut_definition,
        thread_definition,
    )
    measurements = measure_complete_nut(build)

    assert measurements.solid_count == 1
    assert measurements.is_valid
    assert measurements.complete_volume_mm3 > 0.0
    assert (
        measurements.complete_volume_mm3
        < measurements.blank_volume_mm3
    )
    assert measurements.removed_thread_volume_mm3 > 1.0
    assert (
        measurements.removed_thread_volume_mm3
        < measurements.cutter_volume_mm3
    )


def test_internal_thread_preserves_outer_nut_envelope() -> None:
    """Thread cutting preserves the governed external nut envelope."""

    nut_definition, thread_definition = (
        load_complete_nut_definitions(PROJECT_ROOT)
    )

    build = build_complete_nut(
        nut_definition,
        thread_definition,
    )

    blank_measurements = measure_nut_blank(build.nut_blank)
    complete_measurements = measure_complete_nut(build)

    assert complete_measurements.x_length_mm == pytest.approx(
        blank_measurements.x_length_mm
    )
    assert complete_measurements.y_length_mm == pytest.approx(
        blank_measurements.y_length_mm
    )
    assert complete_measurements.z_min_mm == pytest.approx(
        0.0,
        abs=2.0e-7,
    )
    assert complete_measurements.z_max_mm == pytest.approx(
        nut_definition.thickness_mm,
        abs=2.0e-7,
    )

    assert build.complete_nut.Area() > build.nut_blank.Area()

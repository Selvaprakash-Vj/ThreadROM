"""Tests for the parametric internal-thread cutter."""

from pathlib import Path

import pytest

from threadrom.geometry.internal_thread_cutter import (
    InternalThreadCutterDefinition,
    build_internal_thread_cutter,
    internal_cutter_profile_points,
    load_internal_thread_cutter_definition,
    measure_internal_thread_cutter,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_baseline_definition(
) -> InternalThreadCutterDefinition:
    """Load the baseline cutter used by the tests."""

    return load_internal_thread_cutter_definition(
        PROJECT_ROOT
        / "config"
        / "internal_thread_geometry.toml",
        PROJECT_ROOT / "config" / "nut_geometry.toml",
        PROJECT_ROOT / "config" / "baseline_fastener.toml",
        PROJECT_ROOT / "config" / "baseline_assembly.toml",
    )


def test_baseline_internal_cutter_definition() -> None:
    """The governed cutter dimensions are consistent."""

    definition = load_baseline_definition()

    assert definition.geometry_id == "TRM-GEO-000001"
    assert definition.assembly_id == "TRM-ASM-000001"
    assert definition.nominal_diameter_mm == pytest.approx(10.0)
    assert definition.pitch_mm == pytest.approx(1.5)
    assert definition.minor_diameter_mm == pytest.approx(
        8.3762023679,
    )
    assert definition.thread_length_mm == pytest.approx(8.0)
    assert definition.major_radius_mm == pytest.approx(5.0)
    assert definition.radial_thread_depth_mm == pytest.approx(
        0.81189881605,
    )
    assert definition.start_z_mm == pytest.approx(-1.5)
    assert definition.sweep_height_mm == pytest.approx(11.0)


def test_internal_cutter_profile_matches_basic_thread() -> None:
    """The cutter uses the internal crest and root widths."""

    definition = load_baseline_definition()
    points = internal_cutter_profile_points(definition)

    assert len(points) == 4

    outward_coordinate_mm = (
        definition.radial_thread_depth_mm
        + definition.radial_overlap_mm
    )

    assert points[0] == pytest.approx(
        (0.0, -0.1875)
    )
    assert points[1] == pytest.approx(
        (outward_coordinate_mm, -0.09375)
    )
    assert points[2] == pytest.approx(
        (outward_coordinate_mm, 0.09375)
    )
    assert points[3] == pytest.approx(
        (0.0, 0.1875)
    )


def test_internal_thread_cutter_is_valid() -> None:
    """The helical cutter is one valid solid covering the nut."""

    definition = load_baseline_definition()

    cutter = build_internal_thread_cutter(definition)
    measurements = measure_internal_thread_cutter(cutter)

    assert measurements.solid_count == 1
    assert measurements.is_valid
    assert measurements.volume_mm3 > 0.0

    assert measurements.z_min_mm < 0.0
    assert measurements.z_max_mm > definition.thread_length_mm

    assert measurements.x_length_mm > (
        2.0 * definition.minor_radius_mm
    )
    assert measurements.y_length_mm > (
        2.0 * definition.minor_radius_mm
    )

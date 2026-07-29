"""Tests for the external helical thread cutter."""

from pathlib import Path
from typing import cast

import cadquery as cq
import pytest

from threadrom.geometry.helical_thread_cutter import (
    build_helical_thread_cutter,
    cutter_profile_points,
    load_helical_thread_cutter_definition,
    measure_helical_thread_cutter,
)


def test_helical_thread_cutter_definition() -> None:
    """The baseline cutter configuration loads correctly."""

    project_root = Path(__file__).resolve().parents[2]

    definition = load_helical_thread_cutter_definition(
        project_root / "config" / "external_thread_geometry.toml",
        project_root / "config" / "baseline_fastener.toml",
    )

    assert definition.geometry_id == "TRM-GEO-000001"
    assert definition.nominal_diameter_mm == pytest.approx(10.0)
    assert definition.pitch_mm == pytest.approx(1.5)
    assert definition.thread_length_mm == pytest.approx(30.0)
    assert definition.start_z_mm == pytest.approx(-1.5)
    assert definition.sweep_height_mm == pytest.approx(33.0)
    assert definition.turn_count == pytest.approx(22.0)
    assert definition.radial_thread_depth_mm == pytest.approx(
        0.9201519915,
    )
    assert not definition.is_left_hand


def test_cutter_profile_uses_local_coordinates() -> None:
    """The cutter profile is positioned relative to the helix."""

    project_root = Path(__file__).resolve().parents[2]

    definition = load_helical_thread_cutter_definition(
        project_root / "config" / "external_thread_geometry.toml",
        project_root / "config" / "baseline_fastener.toml",
    )

    points = cutter_profile_points(definition)

    radial_coordinates = [
        point[0] for point in points
    ]

    assert min(radial_coordinates) == pytest.approx(
        -definition.radial_thread_depth_mm,
    )

    assert max(radial_coordinates) == pytest.approx(
        definition.radial_clearance_mm,
    )

    assert max(radial_coordinates) < 1.0
    assert min(radial_coordinates) > -1.0


def test_helical_thread_cutter_is_valid() -> None:
    """The swept cutter is one valid annular helical solid."""

    project_root = Path(__file__).resolve().parents[2]

    definition = load_helical_thread_cutter_definition(
        project_root / "config" / "external_thread_geometry.toml",
        project_root / "config" / "baseline_fastener.toml",
    )

    cutter = build_helical_thread_cutter(definition)
    measurements = measure_helical_thread_cutter(cutter)

    assert measurements.solid_count == 1
    assert measurements.is_valid
    assert measurements.volume_mm3 > 0.0

    assert measurements.z_min_mm < 0.0
    assert measurements.z_max_mm > definition.thread_length_mm

    maximum_expected_diameter = (
        definition.nominal_diameter_mm
        + 2.0 * definition.radial_clearance_mm
        + 0.1
    )

    assert measurements.x_length_mm < maximum_expected_diameter
    assert measurements.y_length_mm < maximum_expected_diameter

    protected_core_radius = (
        definition.minor_radius_mm - 0.05
    )

    protected_core = cq.Workplane("XY").circle(
        protected_core_radius
    ).extrude(
        definition.thread_length_mm
    )

    core_shape = cast(cq.Shape, protected_core.val())
    core_intersection = cutter.intersect(core_shape)

    assert (
        core_intersection.isNull()
        or core_intersection.Volume() < 1.0e-8
    )
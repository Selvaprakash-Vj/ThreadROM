"""Tests for the additive TRM-GEO-000001 threaded shank."""

from pathlib import Path

import pytest

from threadrom.geometry.external_thread_ridge import (
    build_helical_thread_ridge,
    measure_helical_thread_ridge,
    ridge_profile_points,
)
from threadrom.geometry.threaded_shank import (
    RADIAL_OVERLAP_MM,
    build_threaded_shank,
    load_threaded_shank_definitions,
    measure_threaded_shank,
)


def test_additive_ridge_profile_is_dimensionally_consistent() -> None:
    """The ridge is wide at its base and narrow at its crest."""

    project_root = Path(__file__).resolve().parents[2]

    _, thread_definition = load_threaded_shank_definitions(
        project_root
    )

    points = ridge_profile_points(
        thread_definition,
        RADIAL_OVERLAP_MM,
    )

    assert len(points) == 4

    base_width_mm = points[3][1] - points[0][1]
    crest_width_mm = points[2][1] - points[1][1]

    assert base_width_mm == pytest.approx(
        5.0 * thread_definition.pitch_mm / 6.0
    )

    assert crest_width_mm == pytest.approx(
        thread_definition.pitch_mm / 8.0
    )

    assert base_width_mm > crest_width_mm


def test_additive_helical_ridge_is_valid() -> None:
    """The additive thread ridge is one valid solid."""

    project_root = Path(__file__).resolve().parents[2]

    _, thread_definition = load_threaded_shank_definitions(
        project_root
    )

    ridge = build_helical_thread_ridge(
        thread_definition,
        RADIAL_OVERLAP_MM,
    )

    measurements = measure_helical_thread_ridge(ridge)

    assert measurements.solid_count == 1
    assert measurements.is_valid
    assert measurements.volume_mm3 > 0.0

    assert measurements.z_min_mm == pytest.approx(
        0.0,
        abs=1.0e-5,
    )

    assert measurements.z_max_mm == pytest.approx(
        thread_definition.thread_length_mm,
        abs=1.0e-5,
    )


def test_additive_threaded_shank_is_valid() -> None:
    """The fused core and ridge form one valid threaded solid."""

    project_root = Path(__file__).resolve().parents[2]

    blank_definition, thread_definition = (
        load_threaded_shank_definitions(project_root)
    )

    build = build_threaded_shank(
        blank_definition,
        thread_definition,
    )

    measurements = measure_threaded_shank(
        build,
        thread_definition,
    )

    assert measurements.solid_count == 1
    assert measurements.is_valid

    assert measurements.threaded_volume_mm3 > (
        measurements.core_volume_mm3
    )

    assert measurements.threaded_volume_mm3 < (
        measurements.major_cylinder_volume_mm3
    )

    assert measurements.radial_overlap_volume_mm3 > 0.0

    cad_envelope_tolerance_mm = 1.0e-3

    assert measurements.x_length_mm == pytest.approx(
        blank_definition.nominal_diameter_mm,
        abs=cad_envelope_tolerance_mm,
    )

    assert measurements.y_length_mm == pytest.approx(
        blank_definition.nominal_diameter_mm,
        abs=cad_envelope_tolerance_mm,
    )

    assert measurements.z_min_mm == pytest.approx(
        0.0,
        abs=1.0e-5,
    )

    assert measurements.z_max_mm == pytest.approx(
        blank_definition.underhead_length_mm,
        abs=1.0e-5,
    )

    assert measurements.face_count > 3
    assert measurements.edge_count > 3
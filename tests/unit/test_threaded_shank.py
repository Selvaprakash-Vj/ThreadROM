"""Tests for the additive TRM-GEO-000001 threaded shank."""

from pathlib import Path

import pytest

from threadrom.geometry.external_thread_ridge import (
    build_helical_thread_ridge,
    measure_helical_thread_ridge,
    ridge_profile_points,
)
from threadrom.geometry.geometry_quality import load_geometry_quality_policy
from threadrom.geometry.thread_flank_geometry import (
    boolean_overlap_axial_extension_mm,
)
from threadrom.geometry.threaded_shank import (
    build_threaded_shank,
    load_threaded_shank_definitions,
    measure_threaded_shank,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

GEOMETRY_QUALITY_POLICY = load_geometry_quality_policy(
    PROJECT_ROOT / "config" / "geometry_quality.toml"
)

THREAD_BOOLEAN_OVERLAP_MM = (
    GEOMETRY_QUALITY_POLICY.thread_boolean_overlap_mm
)


def test_additive_ridge_profile_is_dimensionally_consistent() -> None:
    """The ridge is wide at its base and narrow at its crest."""

    project_root = Path(__file__).resolve().parents[2]

    _, thread_definition = load_threaded_shank_definitions(
        project_root
    )

    points = ridge_profile_points(
        thread_definition,
        THREAD_BOOLEAN_OVERLAP_MM,
    )

    assert len(points) == 4

    base_width_mm = points[3][1] - points[0][1]
    crest_width_mm = points[2][1] - points[1][1]

    expected_base_width_mm = (
        5.0 * thread_definition.pitch_mm / 6.0
        + 2.0
        * boolean_overlap_axial_extension_mm(
            THREAD_BOOLEAN_OVERLAP_MM
        )
    )

    assert base_width_mm == pytest.approx(
        expected_base_width_mm
    )

    assert crest_width_mm == pytest.approx(
        thread_definition.pitch_mm / 8.0
    )

    assert base_width_mm > crest_width_mm


def test_mating_clearance_shifts_ridge_radially_inward() -> None:
    """Diagnostic mating clearance offsets the ridge without changing pitch."""

    project_root = Path(__file__).resolve().parents[2]

    _, thread_definition = load_threaded_shank_definitions(
        project_root
    )

    baseline = ridge_profile_points(
        thread_definition,
        THREAD_BOOLEAN_OVERLAP_MM,
    )

    clearance_mm = 0.05

    cleared = ridge_profile_points(
        thread_definition,
        THREAD_BOOLEAN_OVERLAP_MM,
        clearance_mm,
    )

    for baseline_point, cleared_point in zip(
        baseline,
        cleared,
        strict=True,
    ):
        assert cleared_point[0] == pytest.approx(
            baseline_point[0] - clearance_mm
        )
        assert cleared_point[1] == pytest.approx(
            baseline_point[1]
        )


def test_negative_mating_clearance_is_rejected() -> None:
    """A diagnostic mating clearance cannot enlarge the bolt thread."""

    project_root = Path(__file__).resolve().parents[2]

    _, thread_definition = load_threaded_shank_definitions(
        project_root
    )

    with pytest.raises(ValueError):
        ridge_profile_points(
            thread_definition,
            THREAD_BOOLEAN_OVERLAP_MM,
            -0.01,
        )



def test_additive_helical_ridge_is_valid() -> None:
    """The additive thread ridge is one valid solid."""

    project_root = Path(__file__).resolve().parents[2]

    _, thread_definition = load_threaded_shank_definitions(
        project_root
    )

    ridge = build_helical_thread_ridge(
        thread_definition,
        THREAD_BOOLEAN_OVERLAP_MM,
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
        GEOMETRY_QUALITY_POLICY,
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
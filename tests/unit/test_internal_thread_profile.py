"""Tests for the parametric internal metric-thread profile."""

import math

import pytest

from threadrom.geometry.internal_thread_profile import (
    calculate_internal_metric_thread_profile,
)
from threadrom.geometry.thread_profile import (
    calculate_flank_angle_deg,
)


def test_m10_internal_thread_profile_dimensions() -> None:
    """The ideal M10 x 1.5 internal profile is correct."""

    profile = calculate_internal_metric_thread_profile(
        nominal_diameter_mm=10.0,
        pitch_mm=1.5,
    )

    assert profile.major_radius_mm == pytest.approx(5.0)
    assert profile.pitch_radius_mm == pytest.approx(
        4.51286071035,
    )
    assert profile.minor_radius_mm == pytest.approx(
        4.18810118395,
    )
    assert profile.radial_thread_depth_mm == pytest.approx(
        0.81189881605,
    )

    assert profile.crest_flat_width_mm == pytest.approx(
        0.1875,
    )
    assert profile.root_flat_width_mm == pytest.approx(
        0.375,
    )

    assert len(profile.points) == 6


def test_internal_thread_flanks_are_sixty_degrees() -> None:
    """Both internal-thread flanks are 60 degrees to the axis."""

    profile = calculate_internal_metric_thread_profile(
        nominal_diameter_mm=10.0,
        pitch_mm=1.5,
    )

    left_angle = calculate_flank_angle_deg(
        profile.points[1],
        profile.points[2],
    )

    right_angle = calculate_flank_angle_deg(
        profile.points[3],
        profile.points[4],
    )

    assert left_angle == pytest.approx(60.0)
    assert right_angle == pytest.approx(60.0)

    assert math.isclose(
        left_angle + right_angle,
        120.0,
    )


def test_internal_profile_is_not_hard_coded_to_m10() -> None:
    """A second diameter and pitch produce a valid profile."""

    profile = calculate_internal_metric_thread_profile(
        nominal_diameter_mm=12.0,
        pitch_mm=1.75,
    )

    profile_span = (
        profile.points[-1].axial_mm
        - profile.points[0].axial_mm
    )

    assert profile.major_radius_mm == pytest.approx(6.0)
    assert profile.crest_flat_width_mm == pytest.approx(
        0.21875,
    )
    assert profile.root_flat_width_mm == pytest.approx(
        0.4375,
    )
    assert profile_span == pytest.approx(profile.pitch_mm)

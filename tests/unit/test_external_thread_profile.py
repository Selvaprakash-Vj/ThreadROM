"""Tests for the external M10 × 1.5 thread profile."""

import math

import pytest

from threadrom.geometry.external_thread_profile import (
    calculate_external_metric_thread_profile,
    calculate_flank_angle_deg,
)


def test_m10_external_thread_profile_dimensions() -> None:
    """The ideal M10 × 1.5 external profile is dimensionally correct."""

    profile = calculate_external_metric_thread_profile(
        nominal_diameter_mm=10.0,
        pitch_mm=1.5,
    )

    assert profile.major_radius_mm == pytest.approx(5.0)
    assert profile.pitch_radius_mm == pytest.approx(
        4.51286071035,
    )
    assert profile.minor_radius_mm == pytest.approx(
        4.0798480085,
    )
    assert profile.radial_thread_depth_mm == pytest.approx(
        0.9201519915,
    )

    assert profile.crest_flat_width_mm == pytest.approx(
        0.1875,
    )
    assert profile.root_flat_width_mm == pytest.approx(
        0.25,
    )

    assert len(profile.points) == 6


def test_external_thread_flanks_are_sixty_degrees_to_axis() -> None:
    """Both ideal thread flanks are 60 degrees to the bolt axis."""

    profile = calculate_external_metric_thread_profile(
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


def test_profile_spans_exactly_one_pitch() -> None:
    """The profile cell spans exactly one configured pitch."""

    profile = calculate_external_metric_thread_profile(
        nominal_diameter_mm=10.0,
        pitch_mm=1.5,
    )

    profile_span = (
        profile.points[-1].axial_mm
        - profile.points[0].axial_mm
    )

    assert profile_span == pytest.approx(profile.pitch_mm)
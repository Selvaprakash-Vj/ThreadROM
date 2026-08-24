"""Tests for the canonical conjugate screw-geometry contract."""

from __future__ import annotations

import math

import pytest

from threadrom.geometry.canonical_screw_geometry import (
    basic_internal_minor_diameter_mm,
    basic_internal_minor_radius_mm,
    basic_pitch_diameter_mm,
    basic_pitch_radius_mm,
    canonical_flank_half_width_mm,
    canonical_internal_radius_from_phase_mm,
    fundamental_height_mm,
    screw_point_xyz,
    screw_rotation_deg,
    validate_basic_internal_minor_diameter,
    wrap_thread_phase_mm,
)

PITCH_MM = 1.5
NOMINAL_DIAMETER_MM = 10.0


def test_m10x1p5_basic_profile_datums() -> None:
    """Canonical M10x1.5 datums reproduce the proven oracle."""

    assert fundamental_height_mm(
        PITCH_MM
    ) == pytest.approx(
        1.299038105676658,
        abs=1.0e-12,
    )

    assert basic_pitch_diameter_mm(
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
    ) == pytest.approx(
        9.025721420742506,
        abs=1.0e-12,
    )

    assert basic_pitch_radius_mm(
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
    ) == pytest.approx(
        4.512860710371253,
        abs=1.0e-12,
    )

    assert basic_internal_minor_diameter_mm(
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
    ) == pytest.approx(
        8.376202367902927,
        abs=2.0e-12,
    )


def test_canonical_flank_hits_basic_landmarks() -> None:
    """The same physical flank hits all three governing datums."""

    major_radius = (
        NOMINAL_DIAMETER_MM / 2.0
    )

    pitch_radius = basic_pitch_radius_mm(
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
    )

    internal_minor_radius = (
        basic_internal_minor_radius_mm(
            NOMINAL_DIAMETER_MM,
            PITCH_MM,
        )
    )

    assert canonical_flank_half_width_mm(
        major_radius,
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
    ) == pytest.approx(
        PITCH_MM / 16.0,
        abs=1.0e-12,
    )

    assert canonical_flank_half_width_mm(
        pitch_radius,
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
    ) == pytest.approx(
        PITCH_MM / 4.0,
        abs=1.0e-12,
    )

    assert canonical_flank_half_width_mm(
        internal_minor_radius,
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
    ) == pytest.approx(
        3.0 * PITCH_MM / 8.0,
        abs=1.0e-12,
    )


def test_internal_profile_radius_hits_landmarks() -> None:
    """Direct female profile uses the same canonical screw datum."""

    major_radius = (
        NOMINAL_DIAMETER_MM / 2.0
    )

    pitch_radius = basic_pitch_radius_mm(
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
    )

    minor_radius = (
        basic_internal_minor_radius_mm(
            NOMINAL_DIAMETER_MM,
            PITCH_MM,
        )
    )

    assert canonical_internal_radius_from_phase_mm(
        0.0,
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
    ) == pytest.approx(
        major_radius,
        abs=1.0e-12,
    )

    assert canonical_internal_radius_from_phase_mm(
        PITCH_MM / 16.0,
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
    ) == pytest.approx(
        major_radius,
        abs=1.0e-12,
    )

    assert canonical_internal_radius_from_phase_mm(
        PITCH_MM / 4.0,
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
    ) == pytest.approx(
        pitch_radius,
        abs=1.0e-12,
    )

    assert canonical_internal_radius_from_phase_mm(
        3.0 * PITCH_MM / 8.0,
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
    ) == pytest.approx(
        minor_radius,
        abs=1.0e-12,
    )


def test_registration_is_pure_screw_motion() -> None:
    """20 mm translation gives the proven 120-degree right-hand phase."""

    assert screw_rotation_deg(
        20.0,
        PITCH_MM,
        "right",
    ) == pytest.approx(
        120.0,
        abs=1.0e-12,
    )

    assert screw_rotation_deg(
        20.0,
        PITCH_MM,
        "left",
    ) == pytest.approx(
        240.0,
        abs=1.0e-12,
    )


def test_screw_point_preserves_right_hand_invariant() -> None:
    """Rigid screw motion preserves z - P*theta/(2*pi)."""

    radius = 4.5
    axial_offset = 0.375
    theta = 1.37

    x, y, z = screw_point_xyz(
        radius,
        axial_offset,
        theta,
        PITCH_MM,
        "right",
    )

    assert math.hypot(
        x,
        y,
    ) == pytest.approx(
        radius,
        abs=1.0e-12,
    )

    invariant = (
        z
        - PITCH_MM
        * theta
        / (2.0 * math.pi)
    )

    assert invariant == pytest.approx(
        axial_offset,
        abs=1.0e-12,
    )


def test_phase_wrapping_is_periodic() -> None:
    """Thread phase is invariant under complete pitch translations."""

    reference = wrap_thread_phase_mm(
        0.31,
        PITCH_MM,
    )

    assert wrap_thread_phase_mm(
        0.31 + 7.0 * PITCH_MM,
        PITCH_MM,
    ) == pytest.approx(
        reference,
        abs=1.0e-12,
    )


def test_baseline_internal_minor_diameter_is_accepted() -> None:
    """The governed baseline D1 is the canonical zero-line value."""

    validate_basic_internal_minor_diameter(
        8.376202367904177,
        NOMINAL_DIAMETER_MM,
        PITCH_MM,
        tolerance_mm=2.0e-12,
    )


def test_noncanonical_internal_minor_diameter_fails_closed() -> None:
    """A silent female-profile datum change is forbidden."""

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        validate_basic_internal_minor_diameter(
            8.40,
            NOMINAL_DIAMETER_MM,
            PITCH_MM,
            tolerance_mm=1.0e-9,
        )
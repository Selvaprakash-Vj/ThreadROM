"""Tests for shared thread-flank construction geometry."""

from __future__ import annotations

import math

import pytest

from threadrom.geometry.thread_flank_geometry import (
    THREAD_FLANK_ANGLE_DEG,
    boolean_overlap_axial_extension_mm,
    overlap_extended_flank_half_width_mm,
)


def test_baseline_overlap_axial_extension() -> None:
    """The 0.03 mm Boolean overlap follows the 60-degree flank."""

    extension = boolean_overlap_axial_extension_mm(
        0.03
    )

    assert THREAD_FLANK_ANGLE_DEG == pytest.approx(
        60.0
    )

    assert extension == pytest.approx(
        0.01732050807568877,
        abs=1.0e-15,
    )


def test_external_overlap_preserves_sixty_degree_slope() -> None:
    """External profile overlap does not distort its nominal flank."""

    pitch_mm = 1.5
    radial_depth_mm = 0.920151991520966
    radial_overlap_mm = 0.03

    nominal_axial_span_mm = (
        5.0 * pitch_mm / 12.0
        - pitch_mm / 16.0
    )

    extended_axial_span_mm = (
        overlap_extended_flank_half_width_mm(
            5.0 * pitch_mm / 12.0,
            radial_overlap_mm,
        )
        - pitch_mm / 16.0
    )

    assert (
        radial_depth_mm
        / nominal_axial_span_mm
    ) == pytest.approx(
        math.sqrt(3.0),
        abs=1.0e-12,
    )

    assert (
        (radial_depth_mm + radial_overlap_mm)
        / extended_axial_span_mm
    ) == pytest.approx(
        math.sqrt(3.0),
        abs=1.0e-12,
    )


def test_internal_overlap_preserves_sixty_degree_slope() -> None:
    """Internal cutter overlap does not distort its nominal flank."""

    pitch_mm = 1.5
    radial_depth_mm = 0.8118988160479113
    radial_overlap_mm = 0.03

    nominal_axial_span_mm = (
        3.0 * pitch_mm / 8.0
        - pitch_mm / 16.0
    )

    extended_axial_span_mm = (
        overlap_extended_flank_half_width_mm(
            3.0 * pitch_mm / 8.0,
            radial_overlap_mm,
        )
        - pitch_mm / 16.0
    )

    assert (
        radial_depth_mm
        / nominal_axial_span_mm
    ) == pytest.approx(
        math.sqrt(3.0),
        abs=1.0e-12,
    )

    assert (
        (radial_depth_mm + radial_overlap_mm)
        / extended_axial_span_mm
    ) == pytest.approx(
        math.sqrt(3.0),
        abs=1.0e-12,
    )


def test_zero_overlap_requires_zero_axial_extension() -> None:
    """Zero construction overlap leaves the nominal flank untouched."""

    assert (
        boolean_overlap_axial_extension_mm(0.0)
        == pytest.approx(0.0)
    )


def test_negative_overlap_is_rejected() -> None:
    """Negative Boolean construction overlap fails closed."""

    with pytest.raises(
        ValueError,
        match="non-negative",
    ):
        boolean_overlap_axial_extension_mm(
            -0.01
        )

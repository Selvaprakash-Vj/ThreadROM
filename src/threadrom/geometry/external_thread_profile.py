"""Verified external ISO metric-thread profile definition."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.engineering.metric_thread import (
    calculate_metric_thread_basic_dimensions,
)


@dataclass(frozen=True)
class ThreadProfilePoint:
    """Point in the axial-radius thread-profile plane."""

    axial_mm: float
    radius_mm: float


@dataclass(frozen=True)
class ExternalMetricThreadProfile:
    """One pitch of an ideal external ISO metric-thread profile."""

    nominal_diameter_mm: float
    pitch_mm: float
    major_radius_mm: float
    pitch_radius_mm: float
    minor_radius_mm: float
    fundamental_height_mm: float
    crest_flat_width_mm: float
    root_flat_width_mm: float
    flank_angle_deg: float
    points: tuple[ThreadProfilePoint, ...]

    @property
    def radial_thread_depth_mm(self) -> float:
        """Return the radial depth from major to minor radius."""

        return self.major_radius_mm - self.minor_radius_mm


def calculate_external_metric_thread_profile(
    nominal_diameter_mm: float,
    pitch_mm: float,
) -> ExternalMetricThreadProfile:
    """Calculate one verified pitch of the ideal external thread profile."""

    dimensions = calculate_metric_thread_basic_dimensions(
        nominal_diameter_mm=nominal_diameter_mm,
        pitch_mm=pitch_mm,
    )

    major_radius = nominal_diameter_mm / 2.0
    pitch_radius = dimensions.basic_pitch_diameter_mm / 2.0
    minor_radius = dimensions.basic_external_minor_diameter_mm / 2.0

    crest_half_width = pitch_mm / 16.0
    root_half_width = pitch_mm / 12.0

    points = (
        ThreadProfilePoint(
            axial_mm=-pitch_mm / 2.0,
            radius_mm=minor_radius,
        ),
        ThreadProfilePoint(
            axial_mm=-pitch_mm / 2.0 + root_half_width,
            radius_mm=minor_radius,
        ),
        ThreadProfilePoint(
            axial_mm=-crest_half_width,
            radius_mm=major_radius,
        ),
        ThreadProfilePoint(
            axial_mm=crest_half_width,
            radius_mm=major_radius,
        ),
        ThreadProfilePoint(
            axial_mm=pitch_mm / 2.0 - root_half_width,
            radius_mm=minor_radius,
        ),
        ThreadProfilePoint(
            axial_mm=pitch_mm / 2.0,
            radius_mm=minor_radius,
        ),
    )

    return ExternalMetricThreadProfile(
        nominal_diameter_mm=nominal_diameter_mm,
        pitch_mm=pitch_mm,
        major_radius_mm=major_radius,
        pitch_radius_mm=pitch_radius,
        minor_radius_mm=minor_radius,
        fundamental_height_mm=dimensions.fundamental_triangle_height_mm,
        crest_flat_width_mm=pitch_mm / 8.0,
        root_flat_width_mm=pitch_mm / 6.0,
        flank_angle_deg=60.0,
        points=points,
    )


def calculate_flank_angle_deg(
    first: ThreadProfilePoint,
    second: ThreadProfilePoint,
) -> float:
    """Calculate a flank angle relative to the bolt axis."""

    axial_change = second.axial_mm - first.axial_mm
    radial_change = second.radius_mm - first.radius_mm

    return math.degrees(
        math.atan2(
            abs(radial_change),
            abs(axial_change),
        )
    )
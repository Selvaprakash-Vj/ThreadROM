"""Shared metric-thread profile primitives."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ThreadProfilePoint:
    """Point in the axial-radius thread-profile plane."""

    axial_mm: float
    radius_mm: float


def calculate_flank_angle_deg(
    first: ThreadProfilePoint,
    second: ThreadProfilePoint,
) -> float:
    """Calculate a thread-flank angle relative to the axis."""

    axial_change = second.axial_mm - first.axial_mm
    radial_change = second.radius_mm - first.radius_mm

    return math.degrees(
        math.atan2(
            abs(radial_change),
            abs(axial_change),
        )
    )

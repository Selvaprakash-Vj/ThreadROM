"""Shared geometric rules for threaded-fastener mating flanks."""

from __future__ import annotations

import math

THREAD_FLANK_ANGLE_DEG = 60.0


def boolean_overlap_axial_extension_mm(
    radial_overlap_mm: float,
) -> float:
    """Return axial extension preserving a 60-degree thread flank.

    Boolean construction overlap must extend the existing flank line
    rather than stretch the profile purely in the radial direction.
    """

    if radial_overlap_mm < 0.0:
        raise ValueError(
            "Thread Boolean radial overlap must be non-negative."
        )

    return radial_overlap_mm / math.tan(
        math.radians(THREAD_FLANK_ANGLE_DEG)
    )


def overlap_extended_flank_half_width_mm(
    nominal_half_width_mm: float,
    radial_overlap_mm: float,
) -> float:
    """Return the half-width after extending along the 60-degree flank."""

    if nominal_half_width_mm <= 0.0:
        raise ValueError(
            "Nominal thread flank half-width must be positive."
        )

    return (
        nominal_half_width_mm
        + boolean_overlap_axial_extension_mm(
            radial_overlap_mm
        )
    )

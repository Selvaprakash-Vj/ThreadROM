"""ISO metric-thread basic-dimension calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class MetricThreadBasicDimensions:
    """Basic dimensions of an ISO metric thread."""

    nominal_diameter_mm: float
    pitch_mm: float
    fundamental_triangle_height_mm: float
    basic_pitch_diameter_mm: float
    basic_internal_minor_diameter_mm: float
    basic_external_minor_diameter_mm: float
    tensile_stress_area_mm2: float


def calculate_metric_thread_basic_dimensions(
    nominal_diameter_mm: float,
    pitch_mm: float,
) -> MetricThreadBasicDimensions:
    """Calculate ISO metric-thread basic dimensions."""

    if nominal_diameter_mm <= 0.0:
        raise ValueError("Nominal diameter must be positive.")

    if pitch_mm <= 0.0:
        raise ValueError("Thread pitch must be positive.")

    fundamental_height = math.sqrt(3.0) * pitch_mm / 2.0

    pitch_diameter = nominal_diameter_mm - (3.0 / 4.0) * fundamental_height

    internal_minor_diameter = (
        nominal_diameter_mm
        - (5.0 / 4.0) * fundamental_height
    )

    external_minor_diameter = (
        nominal_diameter_mm
        - (17.0 / 12.0) * fundamental_height
    )

    tensile_stress_area = (
        math.pi
        / 4.0
        * (nominal_diameter_mm - 0.938194 * pitch_mm) ** 2
    )

    return MetricThreadBasicDimensions(
        nominal_diameter_mm=nominal_diameter_mm,
        pitch_mm=pitch_mm,
        fundamental_triangle_height_mm=fundamental_height,
        basic_pitch_diameter_mm=pitch_diameter,
        basic_internal_minor_diameter_mm=internal_minor_diameter,
        basic_external_minor_diameter_mm=external_minor_diameter,
        tensile_stress_area_mm2=tensile_stress_area,
    )
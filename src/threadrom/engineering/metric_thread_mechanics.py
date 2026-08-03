"""Derived mechanics for parametric ISO metric threads."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.engineering.analytical_inputs import (
    MetricThreadInput,
)
from threadrom.engineering.metric_thread import (
    calculate_metric_thread_basic_dimensions,
)


@dataclass(frozen=True)
class MetricThreadMechanics:
    """Derived geometry and mechanics-ready properties of one thread."""

    method: str
    nominal_diameter_mm: float
    pitch_mm: float
    starts: int
    included_angle_deg: float
    flank_half_angle_deg: float
    lead_mm: float
    fundamental_triangle_height_mm: float
    basic_pitch_diameter_mm: float
    basic_internal_minor_diameter_mm: float
    basic_external_minor_diameter_mm: float
    nominal_area_mm2: float
    pitch_diameter_area_mm2: float
    tensile_stress_area_mm2: float
    external_root_area_mm2: float
    external_thread_radial_depth_mm: float
    internal_thread_radial_depth_mm: float
    helix_angle_at_pitch_diameter_deg: float
    engagement_length_mm: float
    engaged_pitch_count: float
    engaged_lead_turn_count: float
    tensile_to_nominal_area_ratio: float
    root_to_nominal_area_ratio: float


def calculate_metric_thread_mechanics(
    thread: MetricThreadInput,
    *,
    engagement_length_mm: float,
) -> MetricThreadMechanics:
    """Calculate mechanics-ready properties for an ISO metric thread."""

    if engagement_length_mm <= 0.0:
        raise ValueError("Thread engagement length must be positive.")

    if not math.isclose(
        thread.included_angle_deg,
        60.0,
        rel_tol=0.0,
        abs_tol=1.0e-9,
    ):
        raise NotImplementedError(
            "The ISO metric basic-profile method currently supports "
            "only a 60-degree included thread angle."
        )

    dimensions = calculate_metric_thread_basic_dimensions(
        nominal_diameter_mm=thread.nominal_diameter_mm,
        pitch_mm=thread.pitch_mm,
    )

    nominal_area_mm2 = math.pi / 4.0 * thread.nominal_diameter_mm**2

    pitch_diameter_area_mm2 = math.pi / 4.0 * dimensions.basic_pitch_diameter_mm**2

    external_root_area_mm2 = math.pi / 4.0 * dimensions.basic_external_minor_diameter_mm**2

    external_thread_radial_depth_mm = (
        thread.nominal_diameter_mm - dimensions.basic_external_minor_diameter_mm
    ) / 2.0

    internal_thread_radial_depth_mm = (
        thread.nominal_diameter_mm - dimensions.basic_internal_minor_diameter_mm
    ) / 2.0

    lead_mm = thread.pitch_mm * thread.starts

    helix_angle_deg = math.degrees(
        math.atan(lead_mm / (math.pi * dimensions.basic_pitch_diameter_mm))
    )

    engaged_pitch_count = engagement_length_mm / thread.pitch_mm

    engaged_lead_turn_count = engagement_length_mm / lead_mm

    return MetricThreadMechanics(
        method="iso_metric_basic_profile_60_deg",
        nominal_diameter_mm=thread.nominal_diameter_mm,
        pitch_mm=thread.pitch_mm,
        starts=thread.starts,
        included_angle_deg=thread.included_angle_deg,
        flank_half_angle_deg=(thread.included_angle_deg / 2.0),
        lead_mm=lead_mm,
        fundamental_triangle_height_mm=(dimensions.fundamental_triangle_height_mm),
        basic_pitch_diameter_mm=(dimensions.basic_pitch_diameter_mm),
        basic_internal_minor_diameter_mm=(dimensions.basic_internal_minor_diameter_mm),
        basic_external_minor_diameter_mm=(dimensions.basic_external_minor_diameter_mm),
        nominal_area_mm2=nominal_area_mm2,
        pitch_diameter_area_mm2=(pitch_diameter_area_mm2),
        tensile_stress_area_mm2=(dimensions.tensile_stress_area_mm2),
        external_root_area_mm2=external_root_area_mm2,
        external_thread_radial_depth_mm=(external_thread_radial_depth_mm),
        internal_thread_radial_depth_mm=(internal_thread_radial_depth_mm),
        helix_angle_at_pitch_diameter_deg=(helix_angle_deg),
        engagement_length_mm=engagement_length_mm,
        engaged_pitch_count=engaged_pitch_count,
        engaged_lead_turn_count=(engaged_lead_turn_count),
        tensile_to_nominal_area_ratio=(dimensions.tensile_stress_area_mm2 / nominal_area_mm2),
        root_to_nominal_area_ratio=(external_root_area_mm2 / nominal_area_mm2),
    )

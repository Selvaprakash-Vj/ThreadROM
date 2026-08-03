"""Closed-form compliance kernel for annular compression frustums."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class AnnularFrustumCompliance:
    """Compliance properties of one one-sided compression frustum."""

    method: str
    axial_length_mm: float
    youngs_modulus_mpa: float
    clearance_hole_diameter_mm: float
    bearing_diameter_mm: float
    member_outer_diameter_mm: float
    half_angle_deg: float
    unconstrained_end_diameter_mm: float
    effective_start_diameter_mm: float
    effective_end_diameter_mm: float
    frustum_length_mm: float
    cylindrical_length_mm: float
    minimum_area_mm2: float
    maximum_area_mm2: float
    compliance_mm_per_n: float
    axial_stiffness_n_per_mm: float
    equivalent_area_mm2: float


def calculate_annular_frustum_compliance(
    *,
    axial_length_mm: float,
    youngs_modulus_mpa: float,
    clearance_hole_diameter_mm: float,
    bearing_diameter_mm: float,
    member_outer_diameter_mm: float,
    half_angle_deg: float,
) -> AnnularFrustumCompliance:
    """Calculate exact annular-frustum compliance with an OD cap."""

    _validate_inputs(
        axial_length_mm=axial_length_mm,
        youngs_modulus_mpa=youngs_modulus_mpa,
        clearance_hole_diameter_mm=(clearance_hole_diameter_mm),
        bearing_diameter_mm=bearing_diameter_mm,
        member_outer_diameter_mm=(member_outer_diameter_mm),
        half_angle_deg=half_angle_deg,
    )

    half_angle_rad = math.radians(half_angle_deg)

    tangent = math.tan(half_angle_rad)

    unconstrained_end_diameter_mm = bearing_diameter_mm + 2.0 * axial_length_mm * tangent

    effective_start_diameter_mm = min(
        bearing_diameter_mm,
        member_outer_diameter_mm,
    )

    if bearing_diameter_mm >= member_outer_diameter_mm:
        frustum_length_mm = 0.0
    else:
        length_to_outer_limit_mm = (member_outer_diameter_mm - bearing_diameter_mm) / (
            2.0 * tangent
        )

        frustum_length_mm = min(
            axial_length_mm,
            length_to_outer_limit_mm,
        )

    cylindrical_length_mm = axial_length_mm - frustum_length_mm

    effective_end_diameter_mm = min(
        unconstrained_end_diameter_mm,
        member_outer_diameter_mm,
    )

    frustum_compliance_mm_per_n = _annular_frustum_compliance_mm_per_n(
        length_mm=frustum_length_mm,
        youngs_modulus_mpa=(youngs_modulus_mpa),
        hole_diameter_mm=(clearance_hole_diameter_mm),
        start_outer_diameter_mm=(bearing_diameter_mm),
        half_angle_rad=half_angle_rad,
    )

    cylindrical_compliance_mm_per_n = _annular_cylinder_compliance_mm_per_n(
        length_mm=cylindrical_length_mm,
        youngs_modulus_mpa=(youngs_modulus_mpa),
        hole_diameter_mm=(clearance_hole_diameter_mm),
        outer_diameter_mm=(member_outer_diameter_mm),
    )

    compliance_mm_per_n = frustum_compliance_mm_per_n + cylindrical_compliance_mm_per_n

    minimum_area_mm2 = _annular_area_mm2(
        outer_diameter_mm=(effective_start_diameter_mm),
        inner_diameter_mm=(clearance_hole_diameter_mm),
    )

    maximum_area_mm2 = _annular_area_mm2(
        outer_diameter_mm=(effective_end_diameter_mm),
        inner_diameter_mm=(clearance_hole_diameter_mm),
    )

    equivalent_area_mm2 = axial_length_mm / (youngs_modulus_mpa * compliance_mm_per_n)

    return AnnularFrustumCompliance(
        method=("closed_form_annular_frustum_with_outer_cap"),
        axial_length_mm=axial_length_mm,
        youngs_modulus_mpa=youngs_modulus_mpa,
        clearance_hole_diameter_mm=(clearance_hole_diameter_mm),
        bearing_diameter_mm=bearing_diameter_mm,
        member_outer_diameter_mm=(member_outer_diameter_mm),
        half_angle_deg=half_angle_deg,
        unconstrained_end_diameter_mm=(unconstrained_end_diameter_mm),
        effective_start_diameter_mm=(effective_start_diameter_mm),
        effective_end_diameter_mm=(effective_end_diameter_mm),
        frustum_length_mm=frustum_length_mm,
        cylindrical_length_mm=(cylindrical_length_mm),
        minimum_area_mm2=minimum_area_mm2,
        maximum_area_mm2=maximum_area_mm2,
        compliance_mm_per_n=(compliance_mm_per_n),
        axial_stiffness_n_per_mm=(1.0 / compliance_mm_per_n),
        equivalent_area_mm2=(equivalent_area_mm2),
    )


def _annular_frustum_compliance_mm_per_n(
    *,
    length_mm: float,
    youngs_modulus_mpa: float,
    hole_diameter_mm: float,
    start_outer_diameter_mm: float,
    half_angle_rad: float,
) -> float:
    """Return closed-form compliance of one annular frustum."""

    if length_mm == 0.0:
        return 0.0

    tangent = math.tan(half_angle_rad)

    end_outer_diameter_mm = start_outer_diameter_mm + 2.0 * length_mm * tangent

    diameter_change_mm = end_outer_diameter_mm - start_outer_diameter_mm

    if diameter_change_mm <= (1.0e-10 * start_outer_diameter_mm):
        return _annular_cylinder_compliance_mm_per_n(
            length_mm=length_mm,
            youngs_modulus_mpa=(youngs_modulus_mpa),
            hole_diameter_mm=(hole_diameter_mm),
            outer_diameter_mm=(start_outer_diameter_mm),
        )

    if hole_diameter_mm == 0.0:
        return (
            2.0
            / (math.pi * youngs_modulus_mpa * tangent)
            * (1.0 / start_outer_diameter_mm - 1.0 / end_outer_diameter_mm)
        )

    logarithmic_ratio = math.log(
        ((end_outer_diameter_mm - hole_diameter_mm) * (start_outer_diameter_mm + hole_diameter_mm))
        / (
            (end_outer_diameter_mm + hole_diameter_mm)
            * (start_outer_diameter_mm - hole_diameter_mm)
        )
    )

    return logarithmic_ratio / (math.pi * youngs_modulus_mpa * hole_diameter_mm * tangent)


def _annular_cylinder_compliance_mm_per_n(
    *,
    length_mm: float,
    youngs_modulus_mpa: float,
    hole_diameter_mm: float,
    outer_diameter_mm: float,
) -> float:
    """Return compliance of one uniform annular cylinder."""

    if length_mm == 0.0:
        return 0.0

    area_mm2 = _annular_area_mm2(
        outer_diameter_mm=outer_diameter_mm,
        inner_diameter_mm=hole_diameter_mm,
    )

    return length_mm / (youngs_modulus_mpa * area_mm2)


def _annular_area_mm2(
    *,
    outer_diameter_mm: float,
    inner_diameter_mm: float,
) -> float:
    """Return the area of one annular section."""

    return math.pi / 4.0 * (outer_diameter_mm**2 - inner_diameter_mm**2)


def _validate_inputs(
    *,
    axial_length_mm: float,
    youngs_modulus_mpa: float,
    clearance_hole_diameter_mm: float,
    bearing_diameter_mm: float,
    member_outer_diameter_mm: float,
    half_angle_deg: float,
) -> None:
    """Validate one annular-frustum definition."""

    if axial_length_mm <= 0.0:
        raise ValueError("Frustum axial length must be positive.")

    if youngs_modulus_mpa <= 0.0:
        raise ValueError("Young's modulus must be positive.")

    if clearance_hole_diameter_mm < 0.0:
        raise ValueError("Clearance-hole diameter must not be negative.")

    if bearing_diameter_mm <= clearance_hole_diameter_mm:
        raise ValueError("Bearing diameter must exceed the clearance-hole diameter.")

    if member_outer_diameter_mm <= clearance_hole_diameter_mm:
        raise ValueError("Member outer diameter must exceed the clearance-hole diameter.")

    if not 0.0 < half_angle_deg < 90.0:
        raise ValueError("Compression-cone half-angle must lie strictly between 0 and 90 degrees.")

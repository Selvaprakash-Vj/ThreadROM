"""Elastic stiffness inputs for engaged-thread load transfer."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
    ThreadLoadDistributionMethod,
)
from threadrom.engineering.metric_thread_mechanics import (
    calculate_metric_thread_mechanics,
)


@dataclass(frozen=True)
class AnalyticalThreadTransferStiffness:
    """Resolved axial-bar and thread-pair stiffness quantities."""

    method: str
    joint_id: str
    projection_convention: str
    bolt_material_id: str
    nut_material_id: str
    pitch_mm: float
    pitch_diameter_mm: float
    internal_minor_diameter_mm: float
    effective_nut_outer_diameter_mm: float
    helix_angle_deg: float
    bolt_axial_area_mm2: float
    nut_axial_area_mm2: float
    bolt_axial_compliance_per_force_inv_n: float
    nut_axial_compliance_per_force_inv_n: float
    bolt_thread_compliance_coefficient_mm2_per_n: float
    nut_thread_compliance_coefficient_mm2_per_n: float
    bolt_distributed_thread_stiffness_n_per_mm2: float
    nut_distributed_thread_stiffness_n_per_mm2: float
    combined_distributed_thread_stiffness_n_per_mm2: float
    transfer_parameter_per_mm: float
    characteristic_transfer_length_mm: float


def calculate_thread_transfer_stiffness(
    joint: AnalyticalJointInput,
) -> AnalyticalThreadTransferStiffness:
    """Calculate elastic quantities governing thread-load transfer."""

    if joint.methods.thread_load_distribution is not ThreadLoadDistributionMethod.DISCRETE_SPRING:
        raise ValueError(
            "Thread-transfer stiffness requires thread_load_distribution='discrete_spring'."
        )

    if joint.thread.starts != 1:
        raise NotImplementedError(
            "The V1 thread-transfer model supports single-start threads only."
        )

    thread = calculate_metric_thread_mechanics(
        joint.thread,
        engagement_length_mm=(joint.nut.thread_engagement_length_mm),
    )

    bolt_material = joint.material_by_id(joint.bolt.material_id)

    nut_material = joint.material_by_id(joint.nut.material_id)

    pitch_diameter_mm = thread.basic_pitch_diameter_mm

    internal_minor_diameter_mm = thread.basic_internal_minor_diameter_mm

    effective_nut_outer_diameter_mm = joint.nut.bearing_outer_diameter_mm

    if effective_nut_outer_diameter_mm <= internal_minor_diameter_mm:
        raise ValueError(
            "Effective nut outer diameter must exceed the internal thread minor diameter."
        )

    bolt_axial_area_mm2 = thread.external_root_area_mm2

    nut_axial_area_mm2 = _annular_area_mm2(
        outer_diameter_mm=(effective_nut_outer_diameter_mm),
        inner_diameter_mm=(internal_minor_diameter_mm),
    )

    bolt_thread_compliance = _iso_triangle_thread_compliance_coefficient(
        pitch_diameter_mm=pitch_diameter_mm,
        youngs_modulus_mpa=(bolt_material.youngs_modulus_mpa),
        poissons_ratio=(bolt_material.poissons_ratio),
    )

    nut_thread_compliance = _iso_triangle_thread_compliance_coefficient(
        pitch_diameter_mm=pitch_diameter_mm,
        youngs_modulus_mpa=(nut_material.youngs_modulus_mpa),
        poissons_ratio=(nut_material.poissons_ratio),
    )

    helix_angle_rad = math.radians(thread.helix_angle_at_pitch_diameter_deg)

    axial_projection = math.sin(helix_angle_rad)

    if axial_projection <= 0.0:
        raise ValueError("Thread helix-angle projection must be positive.")

    bolt_distributed_stiffness = axial_projection / bolt_thread_compliance

    nut_distributed_stiffness = axial_projection / nut_thread_compliance

    combined_distributed_stiffness = 1.0 / (
        1.0 / bolt_distributed_stiffness + 1.0 / nut_distributed_stiffness
    )

    bolt_axial_compliance = 1.0 / (bolt_material.youngs_modulus_mpa * bolt_axial_area_mm2)

    nut_axial_compliance = 1.0 / (nut_material.youngs_modulus_mpa * nut_axial_area_mm2)

    transfer_parameter_per_mm = math.sqrt(
        (bolt_axial_compliance + nut_axial_compliance) * combined_distributed_stiffness
    )

    if transfer_parameter_per_mm <= 0.0:
        raise ValueError("Thread-load transfer parameter must be positive.")

    return AnalyticalThreadTransferStiffness(
        method=("iso_triangle_elastic_transfer_stiffness_v1"),
        joint_id=joint.joint_id,
        projection_convention=("distributed_axial_stiffness_equals_helix_stiffness_times_sin_beta"),
        bolt_material_id=bolt_material.material_id,
        nut_material_id=nut_material.material_id,
        pitch_mm=thread.pitch_mm,
        pitch_diameter_mm=pitch_diameter_mm,
        internal_minor_diameter_mm=(internal_minor_diameter_mm),
        effective_nut_outer_diameter_mm=(effective_nut_outer_diameter_mm),
        helix_angle_deg=(thread.helix_angle_at_pitch_diameter_deg),
        bolt_axial_area_mm2=bolt_axial_area_mm2,
        nut_axial_area_mm2=nut_axial_area_mm2,
        bolt_axial_compliance_per_force_inv_n=(bolt_axial_compliance),
        nut_axial_compliance_per_force_inv_n=(nut_axial_compliance),
        bolt_thread_compliance_coefficient_mm2_per_n=(bolt_thread_compliance),
        nut_thread_compliance_coefficient_mm2_per_n=(nut_thread_compliance),
        bolt_distributed_thread_stiffness_n_per_mm2=(bolt_distributed_stiffness),
        nut_distributed_thread_stiffness_n_per_mm2=(nut_distributed_stiffness),
        combined_distributed_thread_stiffness_n_per_mm2=(combined_distributed_stiffness),
        transfer_parameter_per_mm=(transfer_parameter_per_mm),
        characteristic_transfer_length_mm=(1.0 / transfer_parameter_per_mm),
    )


def _iso_triangle_thread_compliance_coefficient(
    *,
    pitch_diameter_mm: float,
    youngs_modulus_mpa: float,
    poissons_ratio: float,
) -> float:
    """Return the ISO-triangle thread compliance coefficient."""

    if pitch_diameter_mm <= 0.0:
        raise ValueError("Pitch diameter must be positive.")

    if youngs_modulus_mpa <= 0.0:
        raise ValueError("Young's modulus must be positive.")

    if not -1.0 < poissons_ratio < 0.5:
        raise ValueError("Poisson's ratio must lie in (-1, 0.5).")

    bending_term = 0.5 * (1.0 - poissons_ratio**2)

    shear_term = 1.2 * (1.0 + poissons_ratio)

    return (bending_term + shear_term) / (math.pi * pitch_diameter_mm * youngs_modulus_mpa)


def _annular_area_mm2(
    *,
    outer_diameter_mm: float,
    inner_diameter_mm: float,
) -> float:
    """Return one annular axial area."""

    if outer_diameter_mm <= inner_diameter_mm:
        raise ValueError("Annular outer diameter must exceed the inner diameter.")

    if inner_diameter_mm < 0.0:
        raise ValueError("Annular inner diameter must not be negative.")

    return math.pi / 4.0 * (outer_diameter_mm**2 - inner_diameter_mm**2)

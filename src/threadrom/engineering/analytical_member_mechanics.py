"""Parametric compression mechanics for clamped members."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.engineering.analytical_inputs import (
    ElasticMaterial,
    MemberLayerInput,
)
from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
    MemberCompressionMethod,
)
from threadrom.engineering.analytical_member_cone_stack import (
    LayeredCompressionConeMechanics,
    calculate_layered_compression_cone_mechanics,
)


@dataclass(frozen=True)
class MemberLayerMechanics:
    """Compression mechanics of one resolved member region."""

    layer_id: str
    material_id: str
    thickness_mm: float
    clearance_hole_diameter_mm: float
    outer_diameter_mm: float
    compression_area_mm2: float
    youngs_modulus_mpa: float
    compliance_mm_per_n: float
    compressive_stress_mpa: float
    compressive_strain: float
    shortening_mm: float
    strain_energy_n_mm: float
    compression_model: str = "uniform_annular_cylinder"
    cone_side: str | None = None
    end_compression_area_mm2: float | None = None
    equivalent_compression_area_mm2: float | None = None


@dataclass(frozen=True)
class AnalyticalMemberMechanics:
    """Resolved compression mechanics of the member stack."""

    method: str
    joint_id: str
    preload_n: float
    layers: tuple[MemberLayerMechanics, ...]
    total_thickness_mm: float
    total_compliance_mm_per_n: float
    axial_stiffness_n_per_mm: float
    total_shortening_mm: float
    total_strain_energy_n_mm: float
    minimum_compression_area_mm2: float
    maximum_compressive_stress_mpa: float
    head_bearing_area_mm2: float
    nut_bearing_area_mm2: float
    head_mean_bearing_pressure_mpa: float
    nut_mean_bearing_pressure_mpa: float
    compression_cone_half_angle_deg: float | None = None


def calculate_analytical_member_mechanics(
    joint: AnalyticalJointInput,
) -> AnalyticalMemberMechanics:
    """Calculate the selected member-compression model."""

    if joint.methods.member_compression is MemberCompressionMethod.UNIFORM_ANNULAR_CYLINDER:
        return _calculate_uniform_annular_mechanics(joint)

    if joint.methods.member_compression is MemberCompressionMethod.COMPRESSION_CONE:
        return _calculate_compression_cone_mechanics(joint)

    raise NotImplementedError(
        f"Unsupported member-compression method: {joint.methods.member_compression.value}"
    )


def _calculate_uniform_annular_mechanics(
    joint: AnalyticalJointInput,
) -> AnalyticalMemberMechanics:
    """Calculate layered uniform annular-cylinder mechanics."""

    layer_records = tuple(
        _evaluate_uniform_member_layer(
            layer=layer,
            material=joint.material_by_id(layer.material_id),
            preload_n=joint.loading.preload_n,
        )
        for layer in joint.member_layers
    )

    return _assemble_member_result(
        joint=joint,
        layers=layer_records,
        compression_cone=None,
    )


def _calculate_compression_cone_mechanics(
    joint: AnalyticalJointInput,
) -> AnalyticalMemberMechanics:
    """Calculate opposed layered compression-cone mechanics."""

    cone = calculate_layered_compression_cone_mechanics(joint)

    layer_records = tuple(
        MemberLayerMechanics(
            layer_id=slice_record.slice_id,
            material_id=slice_record.material_id,
            thickness_mm=slice_record.thickness_mm,
            clearance_hole_diameter_mm=(slice_record.clearance_hole_diameter_mm),
            outer_diameter_mm=(slice_record.member_outer_diameter_mm),
            compression_area_mm2=(slice_record.minimum_area_mm2),
            youngs_modulus_mpa=(slice_record.youngs_modulus_mpa),
            compliance_mm_per_n=(slice_record.compliance_mm_per_n),
            compressive_stress_mpa=(slice_record.reference_compressive_stress_mpa),
            compressive_strain=(
                slice_record.reference_compressive_stress_mpa / slice_record.youngs_modulus_mpa
            ),
            shortening_mm=slice_record.shortening_mm,
            strain_energy_n_mm=(slice_record.strain_energy_n_mm),
            compression_model="compression_cone_slice",
            cone_side=slice_record.side.value,
            end_compression_area_mm2=(slice_record.maximum_area_mm2),
            equivalent_compression_area_mm2=(slice_record.equivalent_area_mm2),
        )
        for slice_record in cone.slices
    )

    return _assemble_member_result(
        joint=joint,
        layers=layer_records,
        compression_cone=cone,
    )


def _assemble_member_result(
    *,
    joint: AnalyticalJointInput,
    layers: tuple[MemberLayerMechanics, ...],
    compression_cone: LayeredCompressionConeMechanics | None,
) -> AnalyticalMemberMechanics:
    """Assemble common stack and bearing quantities."""

    if not layers:
        raise ValueError("At least one resolved member region is required.")

    total_compliance_mm_per_n = sum(layer.compliance_mm_per_n for layer in layers)

    if total_compliance_mm_per_n <= 0.0:
        raise ValueError("Total member compliance must be positive.")

    total_thickness_mm = sum(layer.thickness_mm for layer in layers)

    total_shortening_mm = sum(layer.shortening_mm for layer in layers)

    total_strain_energy_n_mm = sum(layer.strain_energy_n_mm for layer in layers)

    head_bearing_area_mm2 = _annular_area_mm2(
        outer_diameter_mm=(joint.bolt.head_bearing_outer_diameter_mm),
        inner_diameter_mm=(joint.bolt.head_bearing_inner_diameter_mm),
    )

    nut_bearing_area_mm2 = _annular_area_mm2(
        outer_diameter_mm=(joint.nut.bearing_outer_diameter_mm),
        inner_diameter_mm=(joint.nut.bearing_inner_diameter_mm),
    )

    if compression_cone is None:
        minimum_compression_area_mm2 = min(layer.compression_area_mm2 for layer in layers)

        maximum_compressive_stress_mpa = max(layer.compressive_stress_mpa for layer in layers)

        compression_cone_half_angle_deg = None
    else:
        minimum_compression_area_mm2 = compression_cone.minimum_compression_area_mm2

        maximum_compressive_stress_mpa = compression_cone.maximum_reference_compressive_stress_mpa

        compression_cone_half_angle_deg = compression_cone.half_angle_deg

    return AnalyticalMemberMechanics(
        method=joint.methods.member_compression.value,
        joint_id=joint.joint_id,
        preload_n=joint.loading.preload_n,
        layers=layers,
        total_thickness_mm=total_thickness_mm,
        total_compliance_mm_per_n=(total_compliance_mm_per_n),
        axial_stiffness_n_per_mm=(1.0 / total_compliance_mm_per_n),
        total_shortening_mm=total_shortening_mm,
        total_strain_energy_n_mm=(total_strain_energy_n_mm),
        minimum_compression_area_mm2=(minimum_compression_area_mm2),
        maximum_compressive_stress_mpa=(maximum_compressive_stress_mpa),
        head_bearing_area_mm2=head_bearing_area_mm2,
        nut_bearing_area_mm2=nut_bearing_area_mm2,
        head_mean_bearing_pressure_mpa=(joint.loading.preload_n / head_bearing_area_mm2),
        nut_mean_bearing_pressure_mpa=(joint.loading.preload_n / nut_bearing_area_mm2),
        compression_cone_half_angle_deg=(compression_cone_half_angle_deg),
    )


def _evaluate_uniform_member_layer(
    *,
    layer: MemberLayerInput,
    material: ElasticMaterial,
    preload_n: float,
) -> MemberLayerMechanics:
    """Evaluate one uniform annular compression layer."""

    compression_area_mm2 = _annular_area_mm2(
        outer_diameter_mm=layer.outer_diameter_mm,
        inner_diameter_mm=(layer.clearance_hole_diameter_mm),
    )

    compliance_mm_per_n = layer.thickness_mm / (material.youngs_modulus_mpa * compression_area_mm2)

    compressive_stress_mpa = preload_n / compression_area_mm2

    compressive_strain = compressive_stress_mpa / material.youngs_modulus_mpa

    shortening_mm = preload_n * compliance_mm_per_n

    strain_energy_n_mm = 0.5 * preload_n * shortening_mm

    return MemberLayerMechanics(
        layer_id=layer.layer_id,
        material_id=material.material_id,
        thickness_mm=layer.thickness_mm,
        clearance_hole_diameter_mm=(layer.clearance_hole_diameter_mm),
        outer_diameter_mm=layer.outer_diameter_mm,
        compression_area_mm2=compression_area_mm2,
        youngs_modulus_mpa=(material.youngs_modulus_mpa),
        compliance_mm_per_n=(compliance_mm_per_n),
        compressive_stress_mpa=(compressive_stress_mpa),
        compressive_strain=compressive_strain,
        shortening_mm=shortening_mm,
        strain_energy_n_mm=(strain_energy_n_mm),
        compression_model="uniform_annular_cylinder",
        end_compression_area_mm2=(compression_area_mm2),
        equivalent_compression_area_mm2=(compression_area_mm2),
    )


def _annular_area_mm2(
    *,
    outer_diameter_mm: float,
    inner_diameter_mm: float,
) -> float:
    """Return the area of one annular cross-section."""

    if outer_diameter_mm <= inner_diameter_mm:
        raise ValueError("Annular outer diameter must exceed the inner diameter.")

    if inner_diameter_mm < 0.0:
        raise ValueError("Annular inner diameter must not be negative.")

    return math.pi / 4.0 * (outer_diameter_mm**2 - inner_diameter_mm**2)

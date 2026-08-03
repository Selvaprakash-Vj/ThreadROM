"""Opposed compression-cone mechanics for layered member stacks."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from threadrom.engineering.analytical_compression_cone import (
    calculate_annular_frustum_compliance,
)
from threadrom.engineering.analytical_inputs import (
    MemberLayerInput,
)
from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
    MemberCompressionMethod,
)


class CompressionConeSide(StrEnum):
    """Bearing side from which one compression cone propagates."""

    HEAD = "head_side"
    NUT = "nut_side"


@dataclass(frozen=True)
class CompressionConeLayerSlice:
    """One material and geometry slice of a compression-cone path."""

    slice_id: str
    side: CompressionConeSide
    layer_id: str
    material_id: str
    distance_from_bearing_start_mm: float
    distance_from_bearing_end_mm: float
    thickness_mm: float
    clearance_hole_diameter_mm: float
    member_outer_diameter_mm: float
    start_effective_outer_diameter_mm: float
    end_effective_outer_diameter_mm: float
    frustum_length_mm: float
    cylindrical_length_mm: float
    minimum_area_mm2: float
    maximum_area_mm2: float
    equivalent_area_mm2: float
    youngs_modulus_mpa: float
    compliance_mm_per_n: float
    axial_stiffness_n_per_mm: float
    reference_compressive_stress_mpa: float
    shortening_mm: float
    strain_energy_n_mm: float


@dataclass(frozen=True)
class LayeredCompressionConeMechanics:
    """Resolved opposed-cone mechanics of a layered member stack."""

    method: str
    joint_id: str
    preload_n: float
    half_angle_deg: float
    split_plane_from_head_mm: float
    head_side_length_mm: float
    nut_side_length_mm: float
    slices: tuple[CompressionConeLayerSlice, ...]
    total_compliance_mm_per_n: float
    axial_stiffness_n_per_mm: float
    total_shortening_mm: float
    total_strain_energy_n_mm: float
    minimum_compression_area_mm2: float
    maximum_reference_compressive_stress_mpa: float


def calculate_layered_compression_cone_mechanics(
    joint: AnalyticalJointInput,
) -> LayeredCompressionConeMechanics:
    """Calculate opposed compression cones through layered members."""

    if joint.methods.member_compression is not MemberCompressionMethod.COMPRESSION_CONE:
        raise ValueError(
            "Layered compression-cone mechanics require member_compression='compression_cone'."
        )

    total_thickness_mm = sum(layer.thickness_mm for layer in joint.member_layers)

    if total_thickness_mm <= 0.0:
        raise ValueError("Total member-stack thickness must be positive.")

    split_plane_from_head_mm = 0.5 * total_thickness_mm

    head_side_length_mm = split_plane_from_head_mm
    nut_side_length_mm = total_thickness_mm - split_plane_from_head_mm

    head_slices = _evaluate_cone_side(
        joint=joint,
        side=CompressionConeSide.HEAD,
        layers=joint.member_layers,
        axial_length_mm=head_side_length_mm,
        initial_bearing_diameter_mm=(joint.bolt.head_bearing_outer_diameter_mm),
    )

    nut_slices = _evaluate_cone_side(
        joint=joint,
        side=CompressionConeSide.NUT,
        layers=tuple(reversed(joint.member_layers)),
        axial_length_mm=nut_side_length_mm,
        initial_bearing_diameter_mm=(joint.nut.bearing_outer_diameter_mm),
    )

    slices = head_slices + nut_slices

    if not slices:
        raise ValueError("At least one compression-cone slice is required.")

    total_compliance_mm_per_n = sum(slice_record.compliance_mm_per_n for slice_record in slices)

    if total_compliance_mm_per_n <= 0.0:
        raise ValueError("Total compression-cone compliance must be positive.")

    total_shortening_mm = sum(slice_record.shortening_mm for slice_record in slices)

    total_strain_energy_n_mm = sum(slice_record.strain_energy_n_mm for slice_record in slices)

    return LayeredCompressionConeMechanics(
        method="opposed_layered_annular_frustums",
        joint_id=joint.joint_id,
        preload_n=joint.loading.preload_n,
        half_angle_deg=(joint.methods.compression_cone_half_angle_deg),
        split_plane_from_head_mm=(split_plane_from_head_mm),
        head_side_length_mm=head_side_length_mm,
        nut_side_length_mm=nut_side_length_mm,
        slices=slices,
        total_compliance_mm_per_n=(total_compliance_mm_per_n),
        axial_stiffness_n_per_mm=(1.0 / total_compliance_mm_per_n),
        total_shortening_mm=total_shortening_mm,
        total_strain_energy_n_mm=(total_strain_energy_n_mm),
        minimum_compression_area_mm2=min(slice_record.minimum_area_mm2 for slice_record in slices),
        maximum_reference_compressive_stress_mpa=max(
            slice_record.reference_compressive_stress_mpa for slice_record in slices
        ),
    )


def _evaluate_cone_side(
    *,
    joint: AnalyticalJointInput,
    side: CompressionConeSide,
    layers: tuple[MemberLayerInput, ...],
    axial_length_mm: float,
    initial_bearing_diameter_mm: float,
) -> tuple[CompressionConeLayerSlice, ...]:
    """Propagate one cone from a bearing face to the split plane."""

    remaining_length_mm = axial_length_mm
    current_distance_mm = 0.0
    current_outer_diameter_mm = initial_bearing_diameter_mm

    records: list[CompressionConeLayerSlice] = []

    for layer in layers:
        if remaining_length_mm <= 1.0e-12:
            break

        slice_thickness_mm = min(
            layer.thickness_mm,
            remaining_length_mm,
        )

        material = joint.material_by_id(layer.material_id)

        frustum = calculate_annular_frustum_compliance(
            axial_length_mm=slice_thickness_mm,
            youngs_modulus_mpa=(material.youngs_modulus_mpa),
            clearance_hole_diameter_mm=(layer.clearance_hole_diameter_mm),
            bearing_diameter_mm=(current_outer_diameter_mm),
            member_outer_diameter_mm=(layer.outer_diameter_mm),
            half_angle_deg=(joint.methods.compression_cone_half_angle_deg),
        )

        shortening_mm = joint.loading.preload_n * frustum.compliance_mm_per_n

        distance_end_mm = current_distance_mm + slice_thickness_mm

        slice_index = len(records) + 1

        records.append(
            CompressionConeLayerSlice(
                slice_id=(f"{side.value}:{slice_index:03d}:{layer.layer_id}"),
                side=side,
                layer_id=layer.layer_id,
                material_id=layer.material_id,
                distance_from_bearing_start_mm=(current_distance_mm),
                distance_from_bearing_end_mm=(distance_end_mm),
                thickness_mm=slice_thickness_mm,
                clearance_hole_diameter_mm=(layer.clearance_hole_diameter_mm),
                member_outer_diameter_mm=(layer.outer_diameter_mm),
                start_effective_outer_diameter_mm=(frustum.effective_start_diameter_mm),
                end_effective_outer_diameter_mm=(frustum.effective_end_diameter_mm),
                frustum_length_mm=(frustum.frustum_length_mm),
                cylindrical_length_mm=(frustum.cylindrical_length_mm),
                minimum_area_mm2=(frustum.minimum_area_mm2),
                maximum_area_mm2=(frustum.maximum_area_mm2),
                equivalent_area_mm2=(frustum.equivalent_area_mm2),
                youngs_modulus_mpa=(material.youngs_modulus_mpa),
                compliance_mm_per_n=(frustum.compliance_mm_per_n),
                axial_stiffness_n_per_mm=(frustum.axial_stiffness_n_per_mm),
                reference_compressive_stress_mpa=(
                    joint.loading.preload_n / frustum.minimum_area_mm2
                ),
                shortening_mm=shortening_mm,
                strain_energy_n_mm=(0.5 * joint.loading.preload_n * shortening_mm),
            )
        )

        remaining_length_mm -= slice_thickness_mm
        current_distance_mm = distance_end_mm
        current_outer_diameter_mm = frustum.effective_end_diameter_mm

    if remaining_length_mm > 1.0e-9:
        raise ValueError(
            f"Insufficient member thickness on {side.value}; "
            f"{remaining_length_mm:.12g} mm remains unresolved."
        )

    return tuple(records)

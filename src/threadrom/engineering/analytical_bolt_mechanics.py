"""Parametric axial mechanics for analytical bolts."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.engineering.analytical_inputs import (
    BoltAxialSegmentInput,
    BoltSegmentKind,
    ElasticMaterial,
)
from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
    BoltComplianceMethod,
)
from threadrom.engineering.metric_thread_mechanics import (
    MetricThreadMechanics,
    calculate_metric_thread_mechanics,
)


@dataclass(frozen=True)
class BoltSegmentMechanics:
    """Axial mechanics of one effective bolt segment."""

    segment_id: str
    segment_kind: str
    material_id: str
    length_mm: float
    area_mm2: float
    youngs_modulus_mpa: float
    compliance_mm_per_n: float
    axial_stress_mpa: float
    axial_strain: float
    elongation_mm: float
    strain_energy_n_mm: float


@dataclass(frozen=True)
class AnalyticalBoltMechanics:
    """Resolved axial mechanics for one parametric bolt."""

    method: str
    joint_id: str
    bolt_id: str
    preload_n: float
    tensile_stress_area_mm2: float
    external_root_area_mm2: float
    head_participation_length_mm: float
    nut_participation_length_mm: float
    effective_length_mm: float
    segments: tuple[BoltSegmentMechanics, ...]
    total_compliance_mm_per_n: float
    axial_stiffness_n_per_mm: float
    total_elongation_mm: float
    total_strain_energy_n_mm: float
    nominal_tensile_stress_mpa: float
    root_section_reference_stress_mpa: float
    maximum_segment_stress_mpa: float
    proof_utilisation: float | None
    yield_utilisation: float | None
    ultimate_utilisation: float | None


def calculate_analytical_bolt_mechanics(
    joint: AnalyticalJointInput,
) -> AnalyticalBoltMechanics:
    """Calculate linear-elastic axial mechanics for one bolt."""

    thread = calculate_metric_thread_mechanics(
        joint.thread,
        engagement_length_mm=(joint.nut.thread_engagement_length_mm),
    )

    bolt_material = joint.material_by_id(joint.bolt.material_id)

    head_participation_length_mm = (
        joint.methods.head_participation_factor * joint.thread.nominal_diameter_mm
    )

    nut_participation_length_mm = (
        joint.methods.nut_participation_factor * joint.thread.nominal_diameter_mm
    )

    if joint.methods.bolt_compliance is BoltComplianceMethod.UNIFORM_TENSILE_AREA:
        segment_inputs = (
            _uniform_effective_segment(
                joint=joint,
                head_length_mm=head_participation_length_mm,
                nut_length_mm=nut_participation_length_mm,
            ),
        )

        segment_records = tuple(
            _evaluate_segment(
                segment=segment,
                material=bolt_material,
                thread=thread,
                preload_n=joint.loading.preload_n,
            )
            for segment in segment_inputs
        )

    elif joint.methods.bolt_compliance is BoltComplianceMethod.SEGMENTED:
        records: list[BoltSegmentMechanics] = []

        for segment in joint.bolt.axial_segments:
            material_id = segment.material_id or joint.bolt.material_id

            material = joint.material_by_id(material_id)

            records.append(
                _evaluate_segment(
                    segment=segment,
                    material=material,
                    thread=thread,
                    preload_n=joint.loading.preload_n,
                )
            )

        if head_participation_length_mm > 0.0:
            records.append(
                _evaluate_effective_participation(
                    segment_id="effective_head_participation",
                    segment_kind="effective_head_participation",
                    length_mm=head_participation_length_mm,
                    material=bolt_material,
                    thread=thread,
                    preload_n=joint.loading.preload_n,
                )
            )

        if nut_participation_length_mm > 0.0:
            records.append(
                _evaluate_effective_participation(
                    segment_id="effective_nut_participation",
                    segment_kind="effective_nut_participation",
                    length_mm=nut_participation_length_mm,
                    material=bolt_material,
                    thread=thread,
                    preload_n=joint.loading.preload_n,
                )
            )

        segment_records = tuple(records)

    else:
        raise NotImplementedError(
            f"Unsupported bolt-compliance method: {joint.methods.bolt_compliance.value}"
        )

    total_compliance_mm_per_n = sum(segment.compliance_mm_per_n for segment in segment_records)

    if total_compliance_mm_per_n <= 0.0:
        raise ValueError("Total bolt compliance must be positive.")

    axial_stiffness_n_per_mm = 1.0 / total_compliance_mm_per_n

    total_elongation_mm = sum(segment.elongation_mm for segment in segment_records)

    total_strain_energy_n_mm = sum(segment.strain_energy_n_mm for segment in segment_records)

    effective_length_mm = sum(segment.length_mm for segment in segment_records)

    nominal_tensile_stress_mpa = joint.loading.preload_n / thread.tensile_stress_area_mm2

    root_section_reference_stress_mpa = joint.loading.preload_n / thread.external_root_area_mm2

    maximum_segment_stress_mpa = max(segment.axial_stress_mpa for segment in segment_records)

    return AnalyticalBoltMechanics(
        method=joint.methods.bolt_compliance.value,
        joint_id=joint.joint_id,
        bolt_id=joint.bolt.bolt_id,
        preload_n=joint.loading.preload_n,
        tensile_stress_area_mm2=(thread.tensile_stress_area_mm2),
        external_root_area_mm2=(thread.external_root_area_mm2),
        head_participation_length_mm=(head_participation_length_mm),
        nut_participation_length_mm=(nut_participation_length_mm),
        effective_length_mm=effective_length_mm,
        segments=segment_records,
        total_compliance_mm_per_n=(total_compliance_mm_per_n),
        axial_stiffness_n_per_mm=(axial_stiffness_n_per_mm),
        total_elongation_mm=total_elongation_mm,
        total_strain_energy_n_mm=(total_strain_energy_n_mm),
        nominal_tensile_stress_mpa=(nominal_tensile_stress_mpa),
        root_section_reference_stress_mpa=(root_section_reference_stress_mpa),
        maximum_segment_stress_mpa=(maximum_segment_stress_mpa),
        proof_utilisation=_utilisation(
            nominal_tensile_stress_mpa,
            bolt_material.proof_stress_mpa,
        ),
        yield_utilisation=_utilisation(
            nominal_tensile_stress_mpa,
            bolt_material.yield_strength_mpa,
        ),
        ultimate_utilisation=_utilisation(
            nominal_tensile_stress_mpa,
            bolt_material.ultimate_strength_mpa,
        ),
    )


def _uniform_effective_segment(
    *,
    joint: AnalyticalJointInput,
    head_length_mm: float,
    nut_length_mm: float,
) -> BoltAxialSegmentInput:
    """Create the uniform tensile-area effective bolt segment."""

    return BoltAxialSegmentInput(
        segment_id="uniform_effective_bolt",
        kind=BoltSegmentKind.THREADED,
        length_mm=(joint.grip_length_mm + head_length_mm + nut_length_mm),
    )


def _evaluate_segment(
    *,
    segment: BoltAxialSegmentInput,
    material: ElasticMaterial,
    thread: MetricThreadMechanics,
    preload_n: float,
) -> BoltSegmentMechanics:
    """Evaluate one explicitly configured bolt segment."""

    area_mm2 = _segment_area_mm2(
        segment=segment,
        thread=thread,
    )

    return _evaluate_axial_region(
        segment_id=segment.segment_id,
        segment_kind=segment.kind.value,
        material=material,
        length_mm=segment.length_mm,
        area_mm2=area_mm2,
        preload_n=preload_n,
    )


def _evaluate_effective_participation(
    *,
    segment_id: str,
    segment_kind: str,
    length_mm: float,
    material: ElasticMaterial,
    thread: MetricThreadMechanics,
    preload_n: float,
) -> BoltSegmentMechanics:
    """Evaluate one effective head or nut participation region."""

    return _evaluate_axial_region(
        segment_id=segment_id,
        segment_kind=segment_kind,
        material=material,
        length_mm=length_mm,
        area_mm2=thread.tensile_stress_area_mm2,
        preload_n=preload_n,
    )


def _evaluate_axial_region(
    *,
    segment_id: str,
    segment_kind: str,
    material: ElasticMaterial,
    length_mm: float,
    area_mm2: float,
    preload_n: float,
) -> BoltSegmentMechanics:
    """Evaluate linear-elastic mechanics of one axial region."""

    compliance_mm_per_n = length_mm / (material.youngs_modulus_mpa * area_mm2)

    axial_stress_mpa = preload_n / area_mm2

    axial_strain = axial_stress_mpa / material.youngs_modulus_mpa

    elongation_mm = preload_n * compliance_mm_per_n

    strain_energy_n_mm = 0.5 * preload_n * elongation_mm

    return BoltSegmentMechanics(
        segment_id=segment_id,
        segment_kind=segment_kind,
        material_id=material.material_id,
        length_mm=length_mm,
        area_mm2=area_mm2,
        youngs_modulus_mpa=(material.youngs_modulus_mpa),
        compliance_mm_per_n=(compliance_mm_per_n),
        axial_stress_mpa=axial_stress_mpa,
        axial_strain=axial_strain,
        elongation_mm=elongation_mm,
        strain_energy_n_mm=(strain_energy_n_mm),
    )


def _segment_area_mm2(
    *,
    segment: BoltAxialSegmentInput,
    thread: MetricThreadMechanics,
) -> float:
    """Resolve the effective area of one configured bolt segment."""

    if segment.kind is BoltSegmentKind.THREADED:
        return thread.tensile_stress_area_mm2

    if segment.kind is BoltSegmentKind.UNTHREADED_SHANK:
        if segment.diameter_mm is None:
            raise ValueError("Unthreaded segment diameter is missing.")

        return math.pi / 4.0 * segment.diameter_mm**2

    if segment.kind is BoltSegmentKind.CUSTOM_AREA:
        if segment.area_mm2 is None:
            raise ValueError("Custom segment area is missing.")

        return segment.area_mm2

    raise NotImplementedError(f"Unsupported bolt segment kind: {segment.kind.value}")


def _utilisation(
    stress_mpa: float,
    strength_mpa: float | None,
) -> float | None:
    """Return stress utilisation when strength data is available."""

    if strength_mpa is None:
        return None

    return stress_mpa / strength_mpa

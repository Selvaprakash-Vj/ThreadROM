"""Strength references derived from the analytical joint envelope."""

from __future__ import annotations

from dataclasses import dataclass

from threadrom.engineering.analytical_bolt_mechanics import (
    calculate_analytical_bolt_mechanics,
)
from threadrom.engineering.analytical_joint_envelope import (
    AnalyticalJointEnvelope,
    JointCyclicResponse,
    PreloadCase,
    calculate_analytical_joint_envelope,
)
from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
)


@dataclass(frozen=True)
class JointCyclicStressResponse:
    """Bolt section-stress response for one cyclic preload case."""

    preload_case: PreloadCase
    bolt_force_minimum_n: float
    bolt_force_maximum_n: float
    bolt_force_mean_n: float
    bolt_force_amplitude_n: float
    bolt_force_range_n: float
    nominal_stress_minimum_mpa: float
    nominal_stress_maximum_mpa: float
    nominal_stress_mean_mpa: float
    nominal_stress_amplitude_mpa: float
    nominal_stress_range_mpa: float
    root_reference_stress_minimum_mpa: float
    root_reference_stress_maximum_mpa: float
    root_reference_stress_mean_mpa: float
    root_reference_stress_amplitude_mpa: float
    root_reference_stress_range_mpa: float
    separated_during_cycle: bool
    maximum_joint_opening_mm: float


@dataclass(frozen=True)
class AnalyticalJointStrengthEnvelope:
    """Bolt strength references over the complete joint envelope."""

    method: str
    joint_id: str
    bolt_id: str
    bolt_material_id: str
    tensile_stress_area_mm2: float
    external_root_area_mm2: float
    governing_point_id: str
    highest_bolt_force_n: float
    highest_nominal_tensile_stress_mpa: float
    highest_root_section_reference_stress_mpa: float
    proof_utilisation: float | None
    yield_utilisation: float | None
    ultimate_utilisation: float | None
    cyclic_responses: tuple[JointCyclicStressResponse, ...]
    maximum_nominal_stress_amplitude_mpa: float | None
    maximum_root_reference_stress_amplitude_mpa: float | None
    any_separation: bool
    maximum_joint_opening_mm: float


def calculate_analytical_joint_strength(
    joint: AnalyticalJointInput,
    *,
    envelope: AnalyticalJointEnvelope | None = None,
) -> AnalyticalJointStrengthEnvelope:
    """Calculate section-stress and utilisation references."""

    resolved_envelope = calculate_analytical_joint_envelope(joint) if envelope is None else envelope

    if resolved_envelope.joint_id != joint.joint_id:
        raise ValueError("Joint envelope identity does not match the input joint.")

    bolt = calculate_analytical_bolt_mechanics(joint)

    bolt_material = joint.material_by_id(joint.bolt.material_id)

    governing_point = max(
        resolved_envelope.points,
        key=lambda point: point.state.bolt_force_n,
    )

    highest_bolt_force_n = governing_point.state.bolt_force_n

    highest_nominal_stress_mpa = highest_bolt_force_n / bolt.tensile_stress_area_mm2

    highest_root_reference_stress_mpa = highest_bolt_force_n / bolt.external_root_area_mm2

    cyclic_responses = tuple(
        _calculate_cyclic_stress_response(
            response=response,
            tensile_stress_area_mm2=(bolt.tensile_stress_area_mm2),
            external_root_area_mm2=(bolt.external_root_area_mm2),
        )
        for response in resolved_envelope.cyclic_responses
    )

    if cyclic_responses:
        maximum_nominal_stress_amplitude_mpa = max(
            response.nominal_stress_amplitude_mpa for response in cyclic_responses
        )

        maximum_root_reference_stress_amplitude_mpa = max(
            response.root_reference_stress_amplitude_mpa for response in cyclic_responses
        )
    else:
        maximum_nominal_stress_amplitude_mpa = None
        maximum_root_reference_stress_amplitude_mpa = None

    return AnalyticalJointStrengthEnvelope(
        method="linear_axial_section_stress_envelope_v1",
        joint_id=joint.joint_id,
        bolt_id=joint.bolt.bolt_id,
        bolt_material_id=bolt_material.material_id,
        tensile_stress_area_mm2=(bolt.tensile_stress_area_mm2),
        external_root_area_mm2=(bolt.external_root_area_mm2),
        governing_point_id=(governing_point.point_id),
        highest_bolt_force_n=highest_bolt_force_n,
        highest_nominal_tensile_stress_mpa=(highest_nominal_stress_mpa),
        highest_root_section_reference_stress_mpa=(highest_root_reference_stress_mpa),
        proof_utilisation=_utilisation(
            highest_nominal_stress_mpa,
            bolt_material.proof_stress_mpa,
        ),
        yield_utilisation=_utilisation(
            highest_nominal_stress_mpa,
            bolt_material.yield_strength_mpa,
        ),
        ultimate_utilisation=_utilisation(
            highest_nominal_stress_mpa,
            bolt_material.ultimate_strength_mpa,
        ),
        cyclic_responses=cyclic_responses,
        maximum_nominal_stress_amplitude_mpa=(maximum_nominal_stress_amplitude_mpa),
        maximum_root_reference_stress_amplitude_mpa=(maximum_root_reference_stress_amplitude_mpa),
        any_separation=resolved_envelope.any_separation,
        maximum_joint_opening_mm=(resolved_envelope.maximum_joint_opening_mm),
    )


def _calculate_cyclic_stress_response(
    *,
    response: JointCyclicResponse,
    tensile_stress_area_mm2: float,
    external_root_area_mm2: float,
) -> JointCyclicStressResponse:
    """Convert one cyclic force response to section stresses."""

    return JointCyclicStressResponse(
        preload_case=response.preload_case,
        bolt_force_minimum_n=(response.bolt_force_minimum_n),
        bolt_force_maximum_n=(response.bolt_force_maximum_n),
        bolt_force_mean_n=response.bolt_force_mean_n,
        bolt_force_amplitude_n=(response.bolt_force_amplitude_n),
        bolt_force_range_n=response.bolt_force_range_n,
        nominal_stress_minimum_mpa=(response.bolt_force_minimum_n / tensile_stress_area_mm2),
        nominal_stress_maximum_mpa=(response.bolt_force_maximum_n / tensile_stress_area_mm2),
        nominal_stress_mean_mpa=(response.bolt_force_mean_n / tensile_stress_area_mm2),
        nominal_stress_amplitude_mpa=(response.bolt_force_amplitude_n / tensile_stress_area_mm2),
        nominal_stress_range_mpa=(response.bolt_force_range_n / tensile_stress_area_mm2),
        root_reference_stress_minimum_mpa=(response.bolt_force_minimum_n / external_root_area_mm2),
        root_reference_stress_maximum_mpa=(response.bolt_force_maximum_n / external_root_area_mm2),
        root_reference_stress_mean_mpa=(response.bolt_force_mean_n / external_root_area_mm2),
        root_reference_stress_amplitude_mpa=(
            response.bolt_force_amplitude_n / external_root_area_mm2
        ),
        root_reference_stress_range_mpa=(response.bolt_force_range_n / external_root_area_mm2),
        separated_during_cycle=(response.separated_during_cycle),
        maximum_joint_opening_mm=(response.maximum_joint_opening_mm),
    )


def _utilisation(
    stress_mpa: float,
    strength_mpa: float | None,
) -> float | None:
    """Return stress-to-strength utilisation when available."""

    if strength_mpa is None:
        return None

    if strength_mpa <= 0.0:
        raise ValueError("Material strength must be positive when specified.")

    return stress_mpa / strength_mpa

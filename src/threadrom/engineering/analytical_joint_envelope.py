"""Preload-scatter and cyclic envelopes for analytical joint behaviour."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from threadrom.engineering.analytical_joint_behaviour import (
    AnalyticalJointState,
    JointContactRegime,
    calculate_analytical_joint_state,
)
from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
)


class PreloadCase(StrEnum):
    """Resolved preload level within the specified scatter band."""

    MINIMUM = "minimum_preload"
    NOMINAL = "nominal_preload"
    MAXIMUM = "maximum_preload"


class ExternalLoadCase(StrEnum):
    """Configured external separating-load case."""

    STATIC = "static"
    CYCLIC_MINIMUM = "cyclic_minimum"
    CYCLIC_MAXIMUM = "cyclic_maximum"


@dataclass(frozen=True)
class JointEnvelopePoint:
    """One preload and external-load combination."""

    point_id: str
    preload_case: PreloadCase
    external_load_case: ExternalLoadCase
    state: AnalyticalJointState


@dataclass(frozen=True)
class JointCyclicResponse:
    """Cyclic force response at one preload level."""

    preload_case: PreloadCase
    minimum_state: AnalyticalJointState
    maximum_state: AnalyticalJointState
    bolt_force_minimum_n: float
    bolt_force_maximum_n: float
    bolt_force_mean_n: float
    bolt_force_amplitude_n: float
    bolt_force_range_n: float
    member_compression_maximum_n: float
    member_compression_minimum_n: float
    separated_during_cycle: bool
    maximum_joint_opening_mm: float


@dataclass(frozen=True)
class AnalyticalJointEnvelope:
    """Complete configured axial envelope of one analytical joint."""

    joint_id: str
    preload_scatter_fraction: float
    minimum_preload_n: float
    nominal_preload_n: float
    maximum_preload_n: float
    points: tuple[JointEnvelopePoint, ...]
    cyclic_responses: tuple[JointCyclicResponse, ...]
    highest_bolt_force_n: float
    lowest_member_compression_force_n: float
    minimum_separation_margin_n: float
    maximum_joint_opening_mm: float
    any_separation: bool


def calculate_analytical_joint_envelope(
    joint: AnalyticalJointInput,
) -> AnalyticalJointEnvelope:
    """Evaluate all configured preload and external-load combinations."""

    nominal_preload_n = joint.loading.preload_n
    scatter = joint.loading.preload_scatter_fraction

    preload_cases = (
        (
            PreloadCase.MINIMUM,
            nominal_preload_n * (1.0 - scatter),
        ),
        (
            PreloadCase.NOMINAL,
            nominal_preload_n,
        ),
        (
            PreloadCase.MAXIMUM,
            nominal_preload_n * (1.0 + scatter),
        ),
    )

    external_load_cases: list[tuple[ExternalLoadCase, float]] = [
        (
            ExternalLoadCase.STATIC,
            joint.loading.external_axial_load_n,
        )
    ]

    cyclic_minimum = joint.loading.cyclic_minimum_axial_load_n

    cyclic_maximum = joint.loading.cyclic_maximum_axial_load_n

    if cyclic_minimum is not None and cyclic_maximum is not None:
        external_load_cases.extend(
            [
                (
                    ExternalLoadCase.CYCLIC_MINIMUM,
                    cyclic_minimum,
                ),
                (
                    ExternalLoadCase.CYCLIC_MAXIMUM,
                    cyclic_maximum,
                ),
            ]
        )

    points = tuple(
        _evaluate_point(
            joint=joint,
            preload_case=preload_case,
            preload_n=preload_n,
            external_load_case=external_load_case,
            external_load_n=external_load_n,
        )
        for preload_case, preload_n in preload_cases
        for external_load_case, external_load_n in external_load_cases
    )

    cyclic_responses: tuple[JointCyclicResponse, ...]

    if cyclic_minimum is None or cyclic_maximum is None:
        cyclic_responses = ()
    else:
        cyclic_responses = tuple(
            _evaluate_cyclic_response(
                joint=joint,
                preload_case=preload_case,
                preload_n=preload_n,
                minimum_external_load_n=cyclic_minimum,
                maximum_external_load_n=cyclic_maximum,
            )
            for preload_case, preload_n in preload_cases
        )

    return AnalyticalJointEnvelope(
        joint_id=joint.joint_id,
        preload_scatter_fraction=scatter,
        minimum_preload_n=preload_cases[0][1],
        nominal_preload_n=preload_cases[1][1],
        maximum_preload_n=preload_cases[2][1],
        points=points,
        cyclic_responses=cyclic_responses,
        highest_bolt_force_n=max(point.state.bolt_force_n for point in points),
        lowest_member_compression_force_n=min(
            point.state.member_compression_force_n for point in points
        ),
        minimum_separation_margin_n=min(point.state.separation_margin_n for point in points),
        maximum_joint_opening_mm=max(point.state.joint_opening_mm for point in points),
        any_separation=any(point.state.regime is JointContactRegime.SEPARATED for point in points),
    )


def _evaluate_point(
    *,
    joint: AnalyticalJointInput,
    preload_case: PreloadCase,
    preload_n: float,
    external_load_case: ExternalLoadCase,
    external_load_n: float,
) -> JointEnvelopePoint:
    """Evaluate one joint-envelope point."""

    state = calculate_analytical_joint_state(
        joint,
        preload_n=preload_n,
        external_axial_load_n=external_load_n,
    )

    return JointEnvelopePoint(
        point_id=(f"{preload_case.value}:{external_load_case.value}"),
        preload_case=preload_case,
        external_load_case=external_load_case,
        state=state,
    )


def _evaluate_cyclic_response(
    *,
    joint: AnalyticalJointInput,
    preload_case: PreloadCase,
    preload_n: float,
    minimum_external_load_n: float,
    maximum_external_load_n: float,
) -> JointCyclicResponse:
    """Evaluate one cyclic response at a specified preload."""

    minimum_state = calculate_analytical_joint_state(
        joint,
        preload_n=preload_n,
        external_axial_load_n=minimum_external_load_n,
    )

    maximum_state = calculate_analytical_joint_state(
        joint,
        preload_n=preload_n,
        external_axial_load_n=maximum_external_load_n,
    )

    bolt_force_minimum_n = minimum_state.bolt_force_n
    bolt_force_maximum_n = maximum_state.bolt_force_n
    bolt_force_range_n = bolt_force_maximum_n - bolt_force_minimum_n

    return JointCyclicResponse(
        preload_case=preload_case,
        minimum_state=minimum_state,
        maximum_state=maximum_state,
        bolt_force_minimum_n=bolt_force_minimum_n,
        bolt_force_maximum_n=bolt_force_maximum_n,
        bolt_force_mean_n=(0.5 * (bolt_force_maximum_n + bolt_force_minimum_n)),
        bolt_force_amplitude_n=(0.5 * bolt_force_range_n),
        bolt_force_range_n=bolt_force_range_n,
        member_compression_maximum_n=(minimum_state.member_compression_force_n),
        member_compression_minimum_n=(maximum_state.member_compression_force_n),
        separated_during_cycle=(
            minimum_state.regime is JointContactRegime.SEPARATED
            or maximum_state.regime is JointContactRegime.SEPARATED
        ),
        maximum_joint_opening_mm=max(
            minimum_state.joint_opening_mm,
            maximum_state.joint_opening_mm,
        ),
    )

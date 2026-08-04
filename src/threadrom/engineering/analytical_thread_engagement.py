"""Governed axial discretization of engaged thread turns."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
    ThreadLoadDistributionMethod,
)


@dataclass(frozen=True)
class EngagedThreadTurn:
    """One complete or partial engaged thread turn."""

    turn_number: int
    axial_start_mm: float
    axial_end_mm: float
    axial_centroid_mm: float
    engagement_length_mm: float
    engagement_fraction: float
    is_partial: bool


@dataclass(frozen=True)
class ThreadEngagementDiscretization:
    """Resolved thread turns from nut bearing face to free end."""

    method: str
    joint_id: str
    axial_origin: str
    numbering_direction: str
    pitch_mm: float
    total_engagement_length_mm: float
    nominal_engaged_pitch_count: float
    active_turn_count: int
    complete_turn_count: int
    partial_turn_fraction: float
    turns: tuple[EngagedThreadTurn, ...]


def discretize_thread_engagement(
    joint: AnalyticalJointInput,
) -> ThreadEngagementDiscretization:
    """Discretize nut engagement into full and partial turns."""

    if joint.methods.thread_load_distribution is not ThreadLoadDistributionMethod.DISCRETE_SPRING:
        raise ValueError(
            "Thread engagement discretization requires thread_load_distribution='discrete_spring'."
        )

    if joint.thread.starts != 1:
        raise NotImplementedError(
            "The V1 discrete thread-load model currently supports single-start threads only."
        )

    pitch_mm = joint.thread.pitch_mm
    engagement_length_mm = joint.nut.thread_engagement_length_mm

    if pitch_mm <= 0.0:
        raise ValueError("Thread pitch must be positive.")

    if engagement_length_mm <= 0.0:
        raise ValueError("Thread engagement length must be positive.")

    nominal_pitch_count = engagement_length_mm / pitch_mm

    complete_turn_count = math.floor(nominal_pitch_count)

    partial_turn_fraction = nominal_pitch_count - complete_turn_count

    tolerance = 1.0e-12

    if math.isclose(
        partial_turn_fraction,
        0.0,
        rel_tol=0.0,
        abs_tol=tolerance,
    ):
        partial_turn_fraction = 0.0

    if math.isclose(
        partial_turn_fraction,
        1.0,
        rel_tol=0.0,
        abs_tol=tolerance,
    ):
        complete_turn_count += 1
        partial_turn_fraction = 0.0

    turns: list[EngagedThreadTurn] = []

    for turn_index in range(complete_turn_count):
        axial_start_mm = turn_index * pitch_mm

        axial_end_mm = axial_start_mm + pitch_mm

        turns.append(
            _make_turn(
                turn_number=turn_index + 1,
                axial_start_mm=axial_start_mm,
                axial_end_mm=axial_end_mm,
                pitch_mm=pitch_mm,
            )
        )

    if partial_turn_fraction > 0.0:
        axial_start_mm = complete_turn_count * pitch_mm

        turns.append(
            _make_turn(
                turn_number=complete_turn_count + 1,
                axial_start_mm=axial_start_mm,
                axial_end_mm=engagement_length_mm,
                pitch_mm=pitch_mm,
            )
        )

    if not turns:
        raise ValueError("At least one engaged thread turn is required.")

    resolved_length_mm = sum(turn.engagement_length_mm for turn in turns)

    if not math.isclose(
        resolved_length_mm,
        engagement_length_mm,
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    ):
        raise ValueError(
            "Resolved thread-turn lengths do not equal the configured engagement length."
        )

    resolved_fraction = sum(turn.engagement_fraction for turn in turns)

    if not math.isclose(
        resolved_fraction,
        nominal_pitch_count,
        rel_tol=1.0e-12,
        abs_tol=1.0e-12,
    ):
        raise ValueError(
            "Resolved thread-turn fractions do not equal the nominal engaged-pitch count."
        )

    return ThreadEngagementDiscretization(
        method="axial_pitch_cells_v1",
        joint_id=joint.joint_id,
        axial_origin="nut_bearing_face",
        numbering_direction=("bearing_face_to_nut_free_end"),
        pitch_mm=pitch_mm,
        total_engagement_length_mm=(engagement_length_mm),
        nominal_engaged_pitch_count=(nominal_pitch_count),
        active_turn_count=len(turns),
        complete_turn_count=complete_turn_count,
        partial_turn_fraction=(partial_turn_fraction),
        turns=tuple(turns),
    )


def _make_turn(
    *,
    turn_number: int,
    axial_start_mm: float,
    axial_end_mm: float,
    pitch_mm: float,
) -> EngagedThreadTurn:
    """Create one validated thread-turn record."""

    engagement_length_mm = axial_end_mm - axial_start_mm

    if engagement_length_mm <= 0.0:
        raise ValueError("Resolved thread-turn length must be positive.")

    engagement_fraction = engagement_length_mm / pitch_mm

    if not 0.0 < engagement_fraction <= 1.0:
        raise ValueError("Thread-turn engagement fraction must lie in (0, 1].")

    return EngagedThreadTurn(
        turn_number=turn_number,
        axial_start_mm=axial_start_mm,
        axial_end_mm=axial_end_mm,
        axial_centroid_mm=(0.5 * (axial_start_mm + axial_end_mm)),
        engagement_length_mm=(engagement_length_mm),
        engagement_fraction=(engagement_fraction),
        is_partial=not math.isclose(
            engagement_fraction,
            1.0,
            rel_tol=1.0e-12,
            abs_tol=1.0e-12,
        ),
    )

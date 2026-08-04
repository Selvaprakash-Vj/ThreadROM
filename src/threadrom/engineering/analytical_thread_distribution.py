"""Discrete elastic spring-chain thread-load distribution."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
)
from threadrom.engineering.analytical_thread_engagement import (
    ThreadEngagementDiscretization,
    discretize_thread_engagement,
)
from threadrom.engineering.analytical_thread_stiffness import (
    AnalyticalThreadTransferStiffness,
    calculate_thread_transfer_stiffness,
)


@dataclass(frozen=True)
class ThreadTurnLoad:
    """Resolved load carried by one engaged thread turn."""

    turn_number: int
    axial_centroid_mm: float
    engagement_fraction: float
    spring_stiffness_n_per_mm: float
    relative_displacement_mm: float
    load_n: float
    load_share: float
    cumulative_load_n: float
    cumulative_load_share: float
    remaining_bolt_force_n: float


@dataclass(frozen=True)
class AnalyticalThreadLoadDistribution:
    """Governed load distribution across engaged thread turns."""

    method: str
    joint_id: str
    boundary_condition: str
    total_transferred_load_n: float
    active_turn_count: int
    engagement: ThreadEngagementDiscretization
    stiffness: AnalyticalThreadTransferStiffness
    turn_loads: tuple[ThreadTurnLoad, ...]
    first_turn_load_n: float
    first_turn_load_share: float
    maximum_loaded_turn_number: int
    maximum_turn_load_n: float
    maximum_turn_load_share: float
    final_remaining_bolt_force_n: float
    load_conservation_error_n: float
    nut_bearing_reaction_n: float
    global_equilibrium_error_n: float


def calculate_thread_load_distribution(
    joint: AnalyticalJointInput,
    *,
    total_transferred_load_n: float | None = None,
) -> AnalyticalThreadLoadDistribution:
    """Resolve conservative per-turn loads using coupled axial bars."""

    load_n = (
        joint.loading.preload_n if total_transferred_load_n is None else total_transferred_load_n
    )

    if not math.isfinite(load_n):
        raise ValueError("Transferred thread load must be finite.")

    if load_n <= 0.0:
        raise ValueError("Transferred thread load must be positive.")

    engagement = discretize_thread_engagement(joint)

    stiffness = calculate_thread_transfer_stiffness(joint)

    coordinates_mm = _axial_coordinates(engagement)

    coordinate_index = {coordinate_mm: index for index, coordinate_mm in enumerate(coordinates_mm)}

    node_count = len(coordinates_mm)
    degree_count = 2 * node_count

    matrix = [[0.0 for _ in range(degree_count)] for _ in range(degree_count)]

    right_hand_side = [0.0 for _ in range(degree_count)]

    bolt_modulus_mpa = joint.material_by_id(joint.bolt.material_id).youngs_modulus_mpa

    nut_modulus_mpa = joint.material_by_id(joint.nut.material_id).youngs_modulus_mpa

    _add_axial_bar_chain(
        matrix=matrix,
        coordinates_mm=coordinates_mm,
        degree_offset=0,
        axial_rigidity_n=(bolt_modulus_mpa * stiffness.bolt_axial_area_mm2),
    )

    _add_axial_bar_chain(
        matrix=matrix,
        coordinates_mm=coordinates_mm,
        degree_offset=node_count,
        axial_rigidity_n=(nut_modulus_mpa * stiffness.nut_axial_area_mm2),
    )

    spring_stiffnesses_n_per_mm: list[float] = []

    for turn in engagement.turns:
        spring_stiffness_n_per_mm = (
            stiffness.combined_distributed_thread_stiffness_n_per_mm2 * turn.engagement_length_mm
        )

        spring_stiffnesses_n_per_mm.append(spring_stiffness_n_per_mm)

        node_index = coordinate_index[turn.axial_centroid_mm]

        _add_coupling_spring(
            matrix=matrix,
            first_degree=node_index,
            second_degree=(node_count + node_index),
            stiffness_n_per_mm=(spring_stiffness_n_per_mm),
        )

    bolt_bearing_degree = coordinate_index[0.0]

    nut_bearing_degree = node_count + coordinate_index[0.0]

    right_hand_side[bolt_bearing_degree] = load_n

    displacements_mm = _solve_with_fixed_degree(
        matrix=matrix,
        right_hand_side=right_hand_side,
        fixed_degree=nut_bearing_degree,
    )

    turn_loads: list[ThreadTurnLoad] = []
    cumulative_load_n = 0.0

    for turn, spring_stiffness_n_per_mm in zip(
        engagement.turns,
        spring_stiffnesses_n_per_mm,
        strict=True,
    ):
        node_index = coordinate_index[turn.axial_centroid_mm]

        relative_displacement_mm = (
            displacements_mm[node_index] - displacements_mm[node_count + node_index]
        )

        turn_load_n = spring_stiffness_n_per_mm * relative_displacement_mm

        force_tolerance_n = max(
            1.0e-10,
            load_n * 1.0e-12,
        )

        if turn_load_n < -force_tolerance_n:
            raise ValueError("The discrete thread model produced a negative turn load.")

        turn_load_n = max(
            turn_load_n,
            0.0,
        )

        cumulative_load_n += turn_load_n

        load_share = turn_load_n / load_n

        cumulative_load_share = cumulative_load_n / load_n

        turn_loads.append(
            ThreadTurnLoad(
                turn_number=turn.turn_number,
                axial_centroid_mm=(turn.axial_centroid_mm),
                engagement_fraction=(turn.engagement_fraction),
                spring_stiffness_n_per_mm=(spring_stiffness_n_per_mm),
                relative_displacement_mm=(relative_displacement_mm),
                load_n=turn_load_n,
                load_share=load_share,
                cumulative_load_n=(cumulative_load_n),
                cumulative_load_share=(cumulative_load_share),
                remaining_bolt_force_n=(load_n - cumulative_load_n),
            )
        )

    resolved_load_n = math.fsum(turn.load_n for turn in turn_loads)

    load_conservation_error_n = resolved_load_n - load_n

    nut_bearing_reaction_n = (
        math.fsum(
            matrix[nut_bearing_degree][degree] * displacements_mm[degree]
            for degree in range(degree_count)
        )
        - right_hand_side[nut_bearing_degree]
    )

    global_equilibrium_error_n = load_n + nut_bearing_reaction_n

    maximum_turn = max(
        turn_loads,
        key=lambda turn: turn.load_n,
    )

    first_turn = turn_loads[0]

    return AnalyticalThreadLoadDistribution(
        method=("two_axial_bars_centroid_springs_v1"),
        joint_id=joint.joint_id,
        boundary_condition=(
            "nut_fixed_at_bearing_face__"
            "bolt_force_at_bearing_face__"
            "both_bars_free_at_engagement_end"
        ),
        total_transferred_load_n=load_n,
        active_turn_count=len(turn_loads),
        engagement=engagement,
        stiffness=stiffness,
        turn_loads=tuple(turn_loads),
        first_turn_load_n=first_turn.load_n,
        first_turn_load_share=(first_turn.load_share),
        maximum_loaded_turn_number=(maximum_turn.turn_number),
        maximum_turn_load_n=(maximum_turn.load_n),
        maximum_turn_load_share=(maximum_turn.load_share),
        final_remaining_bolt_force_n=(turn_loads[-1].remaining_bolt_force_n),
        load_conservation_error_n=(load_conservation_error_n),
        nut_bearing_reaction_n=(nut_bearing_reaction_n),
        global_equilibrium_error_n=(global_equilibrium_error_n),
    )


def _axial_coordinates(
    engagement: ThreadEngagementDiscretization,
) -> tuple[float, ...]:
    """Return all axial bar nodes and spring-centroid nodes."""

    coordinates = {
        0.0,
        engagement.total_engagement_length_mm,
    }

    for turn in engagement.turns:
        coordinates.add(turn.axial_start_mm)

        coordinates.add(turn.axial_centroid_mm)

        coordinates.add(turn.axial_end_mm)

    ordered = tuple(sorted(coordinates))

    if len(ordered) < 3:
        raise ValueError("Thread-transfer grid requires at least three axial coordinates.")

    for first, second in pairwise(ordered):
        if second <= first:
            raise ValueError("Thread-transfer coordinates must be strictly increasing.")

    return ordered


def _add_axial_bar_chain(
    *,
    matrix: list[list[float]],
    coordinates_mm: tuple[float, ...],
    degree_offset: int,
    axial_rigidity_n: float,
) -> None:
    """Assemble one one-dimensional axial bar chain."""

    if axial_rigidity_n <= 0.0:
        raise ValueError("Axial rigidity must be positive.")

    for node_index in range(len(coordinates_mm) - 1):
        element_length_mm = coordinates_mm[node_index + 1] - coordinates_mm[node_index]

        if element_length_mm <= 0.0:
            raise ValueError("Axial bar element length must be positive.")

        element_stiffness_n_per_mm = axial_rigidity_n / element_length_mm

        first_degree = degree_offset + node_index

        second_degree = first_degree + 1

        _add_two_degree_stiffness(
            matrix=matrix,
            first_degree=first_degree,
            second_degree=second_degree,
            stiffness_n_per_mm=(element_stiffness_n_per_mm),
        )


def _add_coupling_spring(
    *,
    matrix: list[list[float]],
    first_degree: int,
    second_degree: int,
    stiffness_n_per_mm: float,
) -> None:
    """Assemble one bolt-to-nut thread spring."""

    if stiffness_n_per_mm <= 0.0:
        raise ValueError("Thread spring stiffness must be positive.")

    _add_two_degree_stiffness(
        matrix=matrix,
        first_degree=first_degree,
        second_degree=second_degree,
        stiffness_n_per_mm=stiffness_n_per_mm,
    )


def _add_two_degree_stiffness(
    *,
    matrix: list[list[float]],
    first_degree: int,
    second_degree: int,
    stiffness_n_per_mm: float,
) -> None:
    """Add a symmetric two-degree axial stiffness."""

    matrix[first_degree][first_degree] += stiffness_n_per_mm

    matrix[first_degree][second_degree] -= stiffness_n_per_mm

    matrix[second_degree][first_degree] -= stiffness_n_per_mm

    matrix[second_degree][second_degree] += stiffness_n_per_mm


def _solve_with_fixed_degree(
    *,
    matrix: list[list[float]],
    right_hand_side: list[float],
    fixed_degree: int,
) -> list[float]:
    """Solve the system after applying one zero-displacement constraint."""

    degree_count = len(right_hand_side)

    if len(matrix) != degree_count:
        raise ValueError("Stiffness matrix and load vector sizes differ.")

    free_degrees = [degree for degree in range(degree_count) if degree != fixed_degree]

    reduced_matrix = [[matrix[row][column] for column in free_degrees] for row in free_degrees]

    reduced_right_hand_side = [right_hand_side[row] for row in free_degrees]

    reduced_solution = _solve_linear_system(
        matrix=reduced_matrix,
        right_hand_side=(reduced_right_hand_side),
    )

    solution = [0.0 for _ in range(degree_count)]

    for degree, value in zip(
        free_degrees,
        reduced_solution,
        strict=True,
    ):
        solution[degree] = value

    return solution


def _solve_linear_system(
    *,
    matrix: list[list[float]],
    right_hand_side: list[float],
) -> list[float]:
    """Solve one dense linear system using pivoted elimination."""

    size = len(right_hand_side)

    if size == 0:
        raise ValueError("Linear system must not be empty.")

    if len(matrix) != size:
        raise ValueError("Linear-system matrix must be square.")

    augmented = [list(row) + [right_hand_side[index]] for index, row in enumerate(matrix)]

    if any(len(row) != size + 1 for row in augmented):
        raise ValueError("Linear-system matrix must be square.")

    for pivot_index in range(size):
        pivot_row = max(
            range(pivot_index, size),
            key=lambda row: abs(augmented[row][pivot_index]),
        )

        pivot_value = augmented[pivot_row][pivot_index]

        if abs(pivot_value) <= 1.0e-12:
            raise ValueError("Thread-transfer stiffness matrix is singular.")

        if pivot_row != pivot_index:
            augmented[pivot_index], augmented[pivot_row] = (
                augmented[pivot_row],
                augmented[pivot_index],
            )

        for row in range(
            pivot_index + 1,
            size,
        ):
            factor = augmented[row][pivot_index] / augmented[pivot_index][pivot_index]

            augmented[row][pivot_index] = 0.0

            for column in range(
                pivot_index + 1,
                size + 1,
            ):
                augmented[row][column] -= factor * augmented[pivot_index][column]

    solution = [0.0 for _ in range(size)]

    for row in range(
        size - 1,
        -1,
        -1,
    ):
        known_sum = math.fsum(
            augmented[row][column] * solution[column]
            for column in range(
                row + 1,
                size,
            )
        )

        solution[row] = (augmented[row][size] - known_sum) / augmented[row][row]

    return solution

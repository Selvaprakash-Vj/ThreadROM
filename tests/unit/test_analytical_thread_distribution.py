"""Tests for discrete engaged-thread load distribution."""

import math
from itertools import pairwise
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_thread_distribution import (
    calculate_thread_load_distribution,
)


def _benchmark_joint():
    """Load the governed M10 analytical benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def test_governed_m10_thread_load_distribution() -> None:
    """The M10 benchmark produces deterministic nonuniform shares."""

    result = calculate_thread_load_distribution(_benchmark_joint())

    assert result.method == ("two_axial_bars_centroid_springs_v1")

    assert result.total_transferred_load_n == pytest.approx(5000.0)

    assert result.active_turn_count == 6

    assert result.maximum_loaded_turn_number == 1

    assert result.first_turn_load_n == pytest.approx(1072.3548670254)

    assert result.first_turn_load_share == pytest.approx(0.214470973405)

    assert [turn.load_share for turn in result.turn_loads] == pytest.approx(
        [
            0.214470973405,
            0.197407303694,
            0.184631818015,
            0.175867000630,
            0.170922457620,
            0.056700446637,
        ]
    )


def test_turn_loads_conserve_applied_force() -> None:
    """Turn forces, bolt force and nut reaction remain conservative."""

    result = calculate_thread_load_distribution(_benchmark_joint())

    resolved_load_n = math.fsum(turn.load_n for turn in result.turn_loads)

    assert resolved_load_n == pytest.approx(
        result.total_transferred_load_n,
        abs=1.0e-8,
    )

    assert math.fsum(turn.load_share for turn in result.turn_loads) == pytest.approx(
        1.0,
        abs=1.0e-12,
    )

    assert result.load_conservation_error_n == pytest.approx(
        0.0,
        abs=1.0e-8,
    )

    assert result.final_remaining_bolt_force_n == pytest.approx(
        0.0,
        abs=1.0e-8,
    )

    assert result.nut_bearing_reaction_n == pytest.approx(
        -5000.0,
        abs=1.0e-8,
    )

    assert result.global_equilibrium_error_n == pytest.approx(
        0.0,
        abs=1.0e-8,
    )


def test_distribution_scales_linearly_with_total_load() -> None:
    """Linear elasticity preserves shares while forces scale."""

    joint = _benchmark_joint()

    baseline = calculate_thread_load_distribution(joint)

    doubled = calculate_thread_load_distribution(
        joint,
        total_transferred_load_n=10000.0,
    )

    for baseline_turn, doubled_turn in zip(
        baseline.turn_loads,
        doubled.turn_loads,
        strict=True,
    ):
        assert doubled_turn.load_share == pytest.approx(baseline_turn.load_share)

        assert doubled_turn.load_n == pytest.approx(2.0 * baseline_turn.load_n)

        assert doubled_turn.relative_displacement_mm == pytest.approx(
            2.0 * baseline_turn.relative_displacement_mm
        )


def test_full_turn_loads_decrease_toward_nut_free_end() -> None:
    """The benchmark full turns unload away from the bearing face."""

    result = calculate_thread_load_distribution(_benchmark_joint())

    full_turn_loads = [
        turn.load_n for turn in result.turn_loads if turn.engagement_fraction == pytest.approx(1.0)
    ]

    assert all(first > second for first, second in pairwise(full_turn_loads))


def test_partial_turn_spring_scales_with_engaged_length() -> None:
    """The final one-third turn receives one-third spring capacity."""

    result = calculate_thread_load_distribution(_benchmark_joint())

    first = result.turn_loads[0]
    final = result.turn_loads[-1]

    assert first.engagement_fraction == pytest.approx(1.0)

    assert final.engagement_fraction == pytest.approx(1.0 / 3.0)

    assert final.spring_stiffness_n_per_mm == pytest.approx(first.spring_stiffness_n_per_mm / 3.0)


@pytest.mark.parametrize(
    "invalid_load_n",
    [
        0.0,
        -1.0,
        math.inf,
        -math.inf,
        math.nan,
    ],
)
def test_invalid_transferred_load_is_rejected(
    invalid_load_n: float,
) -> None:
    """The distribution requires one finite positive load."""

    with pytest.raises(
        ValueError,
        match="Transferred thread load",
    ):
        calculate_thread_load_distribution(
            _benchmark_joint(),
            total_transferred_load_n=(invalid_load_n),
        )

"""Tests for thread-load distribution validation."""

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_thread_distribution import (
    calculate_thread_load_distribution,
)
from threadrom.engineering.analytical_thread_distribution_validation import (
    validate_thread_load_distribution,
)


def _benchmark_distribution():
    """Calculate the governed M10 thread distribution."""

    project_root = Path(__file__).resolve().parents[2]

    joint = load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")

    return calculate_thread_load_distribution(joint)


def test_governed_distribution_passes_validation() -> None:
    """The governed M10 distribution satisfies all invariants."""

    validation = validate_thread_load_distribution(_benchmark_distribution())

    assert validation.method == ("discrete_thread_spring_invariants_v1")

    assert validation.passed
    assert validation.failed_check_ids == ()
    assert len(validation.checks) == 14

    validation.require_valid()


def test_modified_turn_share_is_detected() -> None:
    """A corrupted reported turn share fails validation."""

    distribution = _benchmark_distribution()

    modified_first_turn = replace(
        distribution.turn_loads[0],
        load_share=(distribution.turn_loads[0].load_share + 0.01),
    )

    modified = replace(
        distribution,
        turn_loads=(
            modified_first_turn,
            *distribution.turn_loads[1:],
        ),
    )

    validation = validate_thread_load_distribution(modified)

    assert not validation.passed

    assert "turn_load_share_identity" in validation.failed_check_ids

    with pytest.raises(
        ValueError,
        match="turn_load_share_identity",
    ):
        validation.require_valid()


def test_modified_reaction_is_detected() -> None:
    """A corrupted nut reaction fails equilibrium validation."""

    distribution = _benchmark_distribution()

    modified = replace(
        distribution,
        nut_bearing_reaction_n=-4900.0,
        global_equilibrium_error_n=100.0,
    )

    validation = validate_thread_load_distribution(modified)

    assert not validation.passed

    assert "bearing_reaction_equilibrium" in validation.failed_check_ids


def test_modified_first_turn_summary_is_detected() -> None:
    """A corrupted first-turn summary fails identity validation."""

    distribution = _benchmark_distribution()

    modified = replace(
        distribution,
        first_turn_load_n=999.0,
    )

    validation = validate_thread_load_distribution(modified)

    assert not validation.passed

    assert "first_turn_identity" in validation.failed_check_ids

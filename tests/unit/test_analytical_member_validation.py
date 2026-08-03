"""Tests for analytical member-mechanics validation."""

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_member_mechanics import (
    calculate_analytical_member_mechanics,
)
from threadrom.engineering.analytical_member_validation import (
    validate_analytical_member_mechanics,
)


def _benchmark_mechanics():
    """Evaluate the governed M10 member benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    joint = load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")

    return calculate_analytical_member_mechanics(joint)


def test_m10_member_mechanics_pass_all_checks() -> None:
    """The governed member result satisfies all invariants."""

    validation = validate_analytical_member_mechanics(_benchmark_mechanics())

    assert validation.method == ("linear_member_compression_invariants_v1")

    assert validation.passed
    assert validation.failed_check_ids == ()
    assert len(validation.checks) == 13

    validation.require_valid()


def test_modified_stiffness_is_detected() -> None:
    """A corrupted stiffness result fails reciprocal validation."""

    mechanics = _benchmark_mechanics()

    corrupted = replace(
        mechanics,
        axial_stiffness_n_per_mm=(2.0 * mechanics.axial_stiffness_n_per_mm),
    )

    validation = validate_analytical_member_mechanics(corrupted)

    assert not validation.passed
    assert "stiffness_reciprocal" in validation.failed_check_ids

    with pytest.raises(
        ValueError,
        match=("Analytical member-mechanics validation failed"),
    ):
        validation.require_valid()


def test_modified_bearing_pressure_is_detected() -> None:
    """A corrupted bearing pressure fails its identity check."""

    mechanics = _benchmark_mechanics()

    corrupted = replace(
        mechanics,
        head_mean_bearing_pressure_mpa=(mechanics.head_mean_bearing_pressure_mpa + 1.0),
    )

    validation = validate_analytical_member_mechanics(corrupted)

    assert not validation.passed
    assert "head_bearing_pressure" in validation.failed_check_ids

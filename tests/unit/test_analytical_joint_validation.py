"""Tests for analytical joint-behaviour validation."""

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_envelope import (
    calculate_analytical_joint_envelope,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_joint_strength import (
    calculate_analytical_joint_strength,
)
from threadrom.engineering.analytical_joint_validation import (
    validate_analytical_joint_behaviour,
)


def _benchmark_inputs():
    """Return the governed envelope and strength result."""

    project_root = Path(__file__).resolve().parents[2]

    joint = load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")

    envelope = calculate_analytical_joint_envelope(joint)

    strength = calculate_analytical_joint_strength(
        joint,
        envelope=envelope,
    )

    return envelope, strength


def test_governed_joint_passes_all_checks() -> None:
    """The governed benchmark satisfies every invariant."""

    envelope, strength = _benchmark_inputs()

    validation = validate_analytical_joint_behaviour(
        envelope,
        strength,
    )

    assert validation.method == ("piecewise_two_spring_joint_invariants_v1")

    assert validation.passed
    assert validation.failed_check_ids == ()
    assert len(validation.checks) == 14

    validation.require_valid()


def test_corrupted_equilibrium_is_detected() -> None:
    """A modified equilibrium error fails validation."""

    envelope, strength = _benchmark_inputs()

    first_point = envelope.points[0]

    corrupted_point = replace(
        first_point,
        state=replace(
            first_point.state,
            external_load_equilibrium_error_n=1.0,
        ),
    )

    corrupted_envelope = replace(
        envelope,
        points=(
            corrupted_point,
            *envelope.points[1:],
        ),
    )

    validation = validate_analytical_joint_behaviour(
        corrupted_envelope,
        strength,
    )

    assert not validation.passed

    assert "external_load_equilibrium" in validation.failed_check_ids

    with pytest.raises(
        ValueError,
        match=("Analytical joint-behaviour validation failed"),
    ):
        validation.require_valid()


def test_corrupted_envelope_extremum_is_detected() -> None:
    """A false maximum bolt force fails extrema validation."""

    envelope, strength = _benchmark_inputs()

    corrupted_envelope = replace(
        envelope,
        highest_bolt_force_n=(envelope.highest_bolt_force_n + 1.0),
    )

    validation = validate_analytical_joint_behaviour(
        corrupted_envelope,
        strength,
    )

    assert not validation.passed

    assert "envelope_extrema" in validation.failed_check_ids

    assert "strength_envelope_identity" in validation.failed_check_ids


def test_corrupted_section_stress_is_detected() -> None:
    """A false nominal stress fails its force-area identity."""

    envelope, strength = _benchmark_inputs()

    corrupted_strength = replace(
        strength,
        highest_nominal_tensile_stress_mpa=(strength.highest_nominal_tensile_stress_mpa + 1.0),
    )

    validation = validate_analytical_joint_behaviour(
        envelope,
        corrupted_strength,
    )

    assert not validation.passed

    assert "section_stress_identities" in validation.failed_check_ids

"""Tests for complete axial joint behaviour."""

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_behaviour import (
    JointContactRegime,
    calculate_analytical_joint_state,
)
from threadrom.engineering.analytical_joint_input import (
    ExternalLoadMethod,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)


def _benchmark_joint():
    """Load the governed M10 analytical benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def test_preloaded_joint_state_at_zero_external_load() -> None:
    """Preload creates equal bolt tension and member compression."""

    state = calculate_analytical_joint_state(_benchmark_joint())

    assert state.method == "basic_spring_ratio"
    assert state.regime is JointContactRegime.CLAMPED

    assert state.basic_load_fraction == pytest.approx(0.0594321731910)

    assert state.effective_load_fraction == pytest.approx(state.basic_load_fraction)

    assert state.separation_load_n == pytest.approx(5315.9377319584)

    assert state.bolt_force_n == pytest.approx(5000.0)

    assert state.member_compression_force_n == pytest.approx(5000.0)

    assert state.joint_opening_mm == pytest.approx(0.0)

    assert state.external_load_equilibrium_error_n == pytest.approx(
        0.0,
        abs=1.0e-10,
    )


def test_external_load_is_shared_before_separation() -> None:
    """Bolt loading and member unloading satisfy equilibrium."""

    state = calculate_analytical_joint_state(
        _benchmark_joint(),
        external_axial_load_n=1000.0,
    )

    expected_bolt_increment = state.effective_load_fraction * 1000.0

    expected_member_unloading = (1.0 - state.effective_load_fraction) * 1000.0

    assert state.regime is JointContactRegime.CLAMPED

    assert state.bolt_external_increment_n == pytest.approx(expected_bolt_increment)

    assert state.member_unloading_n == pytest.approx(expected_member_unloading)

    assert state.bolt_force_n == pytest.approx(5000.0 + expected_bolt_increment)

    assert state.member_compression_force_n == pytest.approx(5000.0 - expected_member_unloading)

    assert state.external_load_equilibrium_error_n == pytest.approx(
        0.0,
        abs=1.0e-10,
    )


def test_separation_boundary_is_force_continuous() -> None:
    """At separation, the bolt force equals the applied load."""

    base = calculate_analytical_joint_state(_benchmark_joint())

    state = calculate_analytical_joint_state(
        _benchmark_joint(),
        external_axial_load_n=(base.separation_load_n),
    )

    assert state.regime is JointContactRegime.CLAMPED

    assert state.member_compression_force_n == pytest.approx(
        0.0,
        abs=1.0e-10,
    )

    assert state.bolt_force_n == pytest.approx(state.external_axial_load_n)

    assert state.joint_opening_mm == pytest.approx(0.0)


def test_bolt_carries_full_load_after_separation() -> None:
    """Separated members carry no tensile external load."""

    state = calculate_analytical_joint_state(
        _benchmark_joint(),
        external_axial_load_n=6000.0,
    )

    assert state.regime is JointContactRegime.SEPARATED

    assert state.bolt_force_n == pytest.approx(6000.0)

    assert state.member_compression_force_n == pytest.approx(0.0)

    assert state.joint_opening_mm == pytest.approx(
        (6000.0 - state.separation_load_n) / state.bolt_stiffness_n_per_mm
    )

    assert state.external_load_equilibrium_error_n == pytest.approx(
        0.0,
        abs=1.0e-10,
    )


def test_load_introduction_factor_reduces_bolt_fraction() -> None:
    """The governed factor scales the basic bolt load fraction."""

    joint = _benchmark_joint()

    factored_joint = replace(
        joint,
        methods=replace(
            joint.methods,
            external_load=(ExternalLoadMethod.LOAD_INTRODUCTION_FACTOR),
            load_introduction_factor=0.5,
        ),
    )

    state = calculate_analytical_joint_state(
        factored_joint,
        external_axial_load_n=1000.0,
    )

    assert state.effective_load_fraction == pytest.approx(0.5 * state.basic_load_fraction)

    assert state.bolt_external_increment_n == pytest.approx(state.effective_load_fraction * 1000.0)

    assert state.external_load_equilibrium_error_n == pytest.approx(
        0.0,
        abs=1.0e-10,
    )


@pytest.mark.parametrize(
    ("preload_n", "external_load_n", "message"),
    [
        (
            -1.0,
            0.0,
            "Preload",
        ),
        (
            5000.0,
            -1.0,
            "External separating axial load",
        ),
    ],
)
def test_invalid_state_loads_are_rejected(
    preload_n: float,
    external_load_n: float,
    message: str,
) -> None:
    """State overrides retain canonical load validation."""

    with pytest.raises(
        ValueError,
        match=message,
    ):
        calculate_analytical_joint_state(
            _benchmark_joint(),
            preload_n=preload_n,
            external_axial_load_n=(external_load_n),
        )

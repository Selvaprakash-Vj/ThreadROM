"""Tests for pre-solve thermal preload actuator state."""

from __future__ import annotations

import pytest

from threadrom.solver.complete_joint_thermal_preload import (
    ThermalPreloadActuatorState,
    ThermalPreloadState,
    derive_thermal_preload_actuator_state,
    render_bolt_temperature_keywords,
    render_initial_temperature_keywords,
    render_thermal_expansion_keywords,
)


def test_trial_actuator_requires_no_calibration_evidence() -> None:
    state = derive_thermal_preload_actuator_state(
        target_force_n=18_000.0,
        reference_temperature_c=20.0,
        delta_temperature_c=-120.0,
        expansion_coefficient_per_c=1.2e-5,
    )

    assert isinstance(
        state,
        ThermalPreloadActuatorState,
    )
    assert not isinstance(
        state,
        ThermalPreloadState,
    )

    assert state.target_force_n == 18_000.0
    assert state.reference_temperature_c == 20.0
    assert state.delta_temperature_c == -120.0
    assert state.applied_bolt_temperature_c == -100.0
    assert state.expansion_coefficient_per_c == 1.2e-5

    assert not hasattr(
        state,
        "calibration_force_n",
    )
    assert not hasattr(
        state,
        "calibration_delta_temperature_c",
    )


def test_trial_actuator_renders_existing_solver_keywords() -> None:
    state = derive_thermal_preload_actuator_state(
        target_force_n=18_000.0,
        reference_temperature_c=20.0,
        delta_temperature_c=-120.0,
        expansion_coefficient_per_c=1.2e-5,
    )

    expansion = render_thermal_expansion_keywords(
        state=state,
    )
    initial = render_initial_temperature_keywords(
        state=state,
        all_nodes_set_name="ALL_THERMAL_NODES",
    )
    bolt = render_bolt_temperature_keywords(
        state=state,
        bolt_nodes_set_name="BOLT_THERMAL",
    )

    assert expansion[0].startswith(
        "*EXPANSION"
    )
    assert "1.200000000000e-05" in expansion

    assert (
        "ALL_THERMAL_NODES, "
        "2.000000000000e+01"
    ) in initial

    assert (
        "BOLT_THERMAL, "
        "-1.000000000000e+02"
    ) in bolt


@pytest.mark.parametrize(
    "delta_temperature_c",
    (
        0.0,
        1.0,
        float("inf"),
    ),
)
def test_trial_actuator_rejects_non_contraction(
    delta_temperature_c: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="contraction",
    ):
        derive_thermal_preload_actuator_state(
            target_force_n=18_000.0,
            reference_temperature_c=20.0,
            delta_temperature_c=delta_temperature_c,
            expansion_coefficient_per_c=1.2e-5,
        )


def test_certified_state_remains_an_actuator_state() -> None:
    state = ThermalPreloadState(
        target_force_n=20_000.0,
        reference_temperature_c=20.0,
        delta_temperature_c=-243.0,
        applied_bolt_temperature_c=-223.0,
        expansion_coefficient_per_c=1.2e-5,
        calibration_force_n=12_000.0,
        calibration_delta_temperature_c=-145.0,
    )

    assert isinstance(
        state,
        ThermalPreloadActuatorState,
    )
    assert state.calibration_force_n == 12_000.0

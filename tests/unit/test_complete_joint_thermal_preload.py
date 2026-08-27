from pathlib import Path

import pytest

from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
)

from threadrom.solver.complete_joint_thermal_preload import (
    derive_thermal_preload_state,
)


ROOT = Path(__file__).resolve().parents[2]


def test_derive_thermal_preload_state_from_governed_config() -> None:
    preload = load_complete_joint_preload_definition(
        ROOT / "config" / "complete_joint_preload.toml"
    )

    state = derive_thermal_preload_state(preload)

    assert state.target_force_n == pytest.approx(20000.0)

    assert state.reference_temperature_c == pytest.approx(
        20.0
    )

    assert state.delta_temperature_c == pytest.approx(
        -243.2744971
    )

    # Derived — must never be separately hard-coded.
    assert state.applied_bolt_temperature_c == pytest.approx(
        -223.2744971
    )

    assert state.expansion_coefficient_per_c == pytest.approx(
        1.2e-5
    )

    assert state.calibration_force_n == pytest.approx(
        12146.47
    )

    assert state.calibration_delta_temperature_c == pytest.approx(
        -145.0
    )

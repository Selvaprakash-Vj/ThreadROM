import pytest

from threadrom.solver.complete_joint_thermal_preload import (
    ThermalPreloadState,
    render_thermal_preload_keywords,
)


def test_render_thermal_preload_keywords() -> None:
    state = ThermalPreloadState(
        target_force_n=20000.0,
        reference_temperature_c=20.0,
        delta_temperature_c=-250.0,
        applied_bolt_temperature_c=-230.0,
        expansion_coefficient_per_c=1.2e-5,
        calibration_force_n=12146.47,
        calibration_delta_temperature_c=-145.0,
    )

    text = render_thermal_preload_keywords(
        state=state,
        all_nodes_set_name="THERMAL_INITIAL_ALL_NODES",
        bolt_nodes_set_name="BOLT_THERMAL",
        bolt_material_name="BOLT_MATERIAL",
    )

    assert "*EXPANSION, ZERO=20" in text
    assert "1.200000000000e-05" in text

    assert "*INITIAL CONDITIONS, TYPE=TEMPERATURE" in text
    assert "THERMAL_INITIAL_ALL_NODES, 20" in text

    assert "*TEMPERATURE" in text
    assert "BOLT_THERMAL, -230" in text

    assert "*PRE-TENSION SECTION" not in text
    assert "*CLOAD" not in text

    # The renderer must operate on sets, not expanded/manual IDs.
    assert "\n1," not in text
    assert "\n101493," not in text
from pathlib import Path

import pytest

from threadrom.solver.complete_joint_preload import (
    CompleteJointPreloadDefinition,
    load_complete_joint_preload_definition,
)


ROOT = Path(__file__).resolve().parents[2]


def test_load_complete_joint_preload_definition() -> None:
    definition = load_complete_joint_preload_definition(
        ROOT / "config" / "complete_joint_preload.toml"
    )

    assert isinstance(
        definition,
        CompleteJointPreloadDefinition,
    )

    assert definition.preload_id == "TRM-PRELOAD-000001"

    assert definition.target_force_n == pytest.approx(
        20000.0
    )

    assert definition.target_relative_tolerance == pytest.approx(
        0.01
    )

    assert (
        definition.interface_spread_relative_tolerance
        == pytest.approx(0.005)
    )

    assert definition.thermal.enabled is True
    assert (
        definition.thermal.reference_temperature_c
        == pytest.approx(20.0)
    )
    assert (
        definition.thermal.expansion_coefficient_per_c
        == pytest.approx(1.2e-5)
    )
    assert (
        definition.thermal.equivalent_delta_temperature_c
        == pytest.approx(-243.2744971)
    )

    assert definition.model.bolt_component == "bolt"

    assert definition.initial_stress.enabled is True
    assert (
        definition.initial_stress.selection_mode
        == "automatic_free_thread_span_band"
    )

    assert (
        definition.initial_stress.band_start_fraction
        == pytest.approx(0.25)
    )

    assert (
        definition.initial_stress.band_end_fraction
        == pytest.approx(0.75)
    )
    assert (
        definition.initial_stress.stress_magnitude_mode
        == "target_force_over_meshed_area"
    )
    assert (
        definition.initial_stress.stress_direction_mode
        == "derived_bolt_axis"
    )

    assert (
        definition.validation.forbid_native_pretension_section
        is True
    )
    assert (
        definition.validation.forbid_manual_node_ids
        is True
    )
    assert (
        definition.validation.forbid_manual_element_ids
        is True
    )
    assert (
        definition.validation.forbid_contact_adjacent_initial_stress_elements
        is True
    )

from pathlib import Path

from threadrom.solver.complete_joint_pretension import (
    load_complete_joint_pretension_definition,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_load_complete_joint_pretension_definition() -> None:
    definition = load_complete_joint_pretension_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_pretension.toml"
    )

    assert definition.pretension_model_id == "TRM-PTN-000001"
    assert definition.simulation_id == "TRM-SIM-000007"
    assert definition.pretension_mesh_id == "TRM-MSH-000006"
    assert definition.axial_position_mm == 5.0
    assert definition.preload_force_n == 20000.0
    assert definition.normal_axis == "Z"
    assert definition.surface_type == "ELEMENT"
    assert definition.bolt_fragment_count == 2
    assert definition.expected_total_cad_volume_count == 5
    assert definition.group_bolt_fragments_together is True

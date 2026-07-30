"""Tests for complete-joint mesh configuration."""

from __future__ import annotations

from pathlib import Path

from threadrom.geometry.complete_nut import (
    load_complete_nut_definitions,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)
from threadrom.meshing.complete_joint_mesh_definition import (
    load_complete_joint_mesh_definition,
    resolve_complete_joint_mesh_sizes,
)
from threadrom.meshing.mesh_levels import (
    load_mesh_level_policy,
    resolve_mesh_levels,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_complete_joint_medium_mesh_sizes() -> None:
    """The selected bolt and nut refinement levels agree."""

    definition = load_complete_joint_mesh_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_mesh.toml"
    )

    _, bolt_thread = load_threaded_shank_definitions(
        PROJECT_ROOT
    )

    _, nut_thread = load_complete_nut_definitions(
        PROJECT_ROOT
    )

    bolt_policy = load_mesh_level_policy(
        PROJECT_ROOT
        / "config"
        / definition.bolt_mesh_level_policy
    )

    nut_policy = load_mesh_level_policy(
        PROJECT_ROOT
        / "config"
        / definition.nut_mesh_level_policy
    )

    resolved = resolve_complete_joint_mesh_sizes(
        definition,
        resolve_mesh_levels(
            bolt_policy,
            bolt_thread,
        ),
        resolve_mesh_levels(
            nut_policy,
            nut_thread,
        ),
    )

    assert definition.mesh_id == "TRM-MSH-000005"
    assert definition.expected_volume_count == 4
    assert resolved.level_name == "medium"
    assert abs(
        resolved.mesh_size_min_mm - 0.267926609
    ) < 1.0e-9
    assert abs(
        resolved.mesh_size_max_mm - 1.005
    ) < 1.0e-12
    assert abs(
        resolved.bolt_thread_surface_size_mm
        - 0.303650157
    ) < 1.0e-9
    assert abs(
        resolved.nut_thread_surface_size_mm
        - 0.267926609
    ) < 1.0e-9

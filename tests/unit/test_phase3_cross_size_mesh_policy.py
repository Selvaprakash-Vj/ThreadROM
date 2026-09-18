from pathlib import Path

import pytest

from threadrom.meshing.mesh_levels import (
    load_mesh_level_policy,
)


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"


def _level(policy, name: str):
    matches = tuple(
        level
        for level in policy.levels
        if level.name == name
    )

    assert len(matches) == 1

    return matches[0]


def test_cross_size_nut_medium_policy_is_governed_recipe() -> None:
    policy = load_mesh_level_policy(
        CONFIG
        / "nut_mesh_levels_cross_size_sentinel.toml"
    )

    medium = _level(
        policy,
        "medium",
    )

    assert (
        medium.maximum_size_pitch_factor
        == pytest.approx(0.67)
    )
    assert (
        medium.minimum_size_thread_depth_factor
        == pytest.approx(0.22)
    )
    assert (
        medium.thread_surface_size_depth_factor
        == pytest.approx(0.22)
    )


def test_standard_nut_medium_policy_remains_unchanged() -> None:
    standard = load_mesh_level_policy(
        CONFIG
        / "nut_mesh_levels.toml"
    )

    cross_size = load_mesh_level_policy(
        CONFIG
        / "nut_mesh_levels_cross_size_sentinel.toml"
    )

    standard_medium = _level(
        standard,
        "medium",
    )
    cross_size_medium = _level(
        cross_size,
        "medium",
    )

    assert (
        standard_medium.maximum_size_pitch_factor
        == pytest.approx(0.67)
    )
    assert (
        standard_medium.minimum_size_thread_depth_factor
        == pytest.approx(0.33)
    )
    assert (
        standard_medium.thread_surface_size_depth_factor
        == pytest.approx(0.33)
    )

    assert (
        cross_size_medium.maximum_size_pitch_factor
        == standard_medium.maximum_size_pitch_factor
    )

    assert (
        cross_size_medium.minimum_size_thread_depth_factor
        == pytest.approx(0.22)
    )
    assert (
        cross_size_medium.thread_surface_size_depth_factor
        == pytest.approx(0.22)
    )

    assert cross_size.policy_id != standard.policy_id
    assert cross_size.mesh_id != standard.mesh_id
    assert cross_size.geometry_id == standard.geometry_id

"""Tests for parameter-scaled mesh levels."""

from dataclasses import replace
from pathlib import Path

from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)
from threadrom.meshing.mesh_levels import (
    load_mesh_level_policy,
    resolve_mesh_levels,
)


def test_mesh_levels_are_progressively_finer() -> None:
    """Coarse, medium and fine levels resolve monotonically."""

    project_root = Path(__file__).resolve().parents[2]

    _, thread_definition = load_threaded_shank_definitions(project_root)

    policy = load_mesh_level_policy(project_root / "config" / "mesh_levels.toml")

    levels = resolve_mesh_levels(
        policy,
        thread_definition,
    )

    assert [level.name for level in levels] == [
        "coarse",
        "medium",
        "fine",
    ]

    maximum_sizes = [level.mesh_size_max_mm for level in levels]

    minimum_sizes = [level.mesh_size_min_mm for level in levels]

    thread_sizes = [level.thread_surface_size_mm for level in levels]

    assert maximum_sizes == sorted(
        maximum_sizes,
        reverse=True,
    )

    assert minimum_sizes == sorted(
        minimum_sizes,
        reverse=True,
    )

    assert thread_sizes == sorted(
        thread_sizes,
        reverse=True,
    )


def test_mesh_levels_follow_changed_thread_geometry() -> None:
    """Resolved sizes respond to pitch and thread-depth changes."""

    project_root = Path(__file__).resolve().parents[2]

    _, baseline_thread = load_threaded_shank_definitions(project_root)

    policy = load_mesh_level_policy(project_root / "config" / "mesh_levels.toml")

    baseline_levels = resolve_mesh_levels(
        policy,
        baseline_thread,
    )

    alternative_thread = replace(
        baseline_thread,
        nominal_diameter_mm=12.0,
        pitch_mm=1.75,
        minor_diameter_mm=9.9,
    )

    alternative_levels = resolve_mesh_levels(
        policy,
        alternative_thread,
    )

    for baseline, alternative in zip(
        baseline_levels,
        alternative_levels,
        strict=True,
    ):
        assert alternative.mesh_size_max_mm > (baseline.mesh_size_max_mm)

        assert alternative.mesh_size_min_mm > (baseline.mesh_size_min_mm)

        assert alternative.thread_surface_size_mm > (baseline.thread_surface_size_mm)

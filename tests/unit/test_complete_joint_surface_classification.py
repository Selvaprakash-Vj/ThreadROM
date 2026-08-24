"""Tests for complete-joint surface classification."""

from __future__ import annotations

from pathlib import Path

from threadrom.engineering.baseline_assembly import (
    load_baseline_assembly,
)
from threadrom.geometry.complete_nut import (
    load_complete_nut_definitions,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)
from threadrom.meshing.complete_joint_surface_classification import (
    MEMBER_REGION_ORDER,
    classify_complete_joint_step,
    load_complete_joint_surface_definition,
)
from threadrom.meshing.nut_surface_classification import (
    load_nut_surface_classification_definition,
)
from threadrom.meshing.surface_classification import (
    load_surface_classification_definition,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_complete_joint_surface_classification() -> None:
    """All component surfaces receive governed identities."""

    assembly = load_baseline_assembly(
        PROJECT_ROOT
        / "config"
        / "baseline_assembly.toml"
    )

    bolt_blank, _ = load_threaded_shank_definitions(
        PROJECT_ROOT
    )

    nut_blank, _ = load_complete_nut_definitions(
        PROJECT_ROOT
    )

    bolt_definition = (
        load_surface_classification_definition(
            PROJECT_ROOT
            / "config"
            / "surface_classification.toml"
        )
    )

    nut_definition = (
        load_nut_surface_classification_definition(
            PROJECT_ROOT
            / "config"
            / "nut_surface_classification.toml"
        )
    )

    joint_definition = (
        load_complete_joint_surface_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_surface_classification.toml"
        )
    )

    result = classify_complete_joint_step(
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / assembly.assembly_id
        / "geometry"
        / "complete_joint_assembly.step",
        assembly,
        bolt_blank,
        nut_blank,
        bolt_definition,
        nut_definition,
        joint_definition,
    )

    assert len(result.volumes.items()) == 4
    assert len(result.bolt.surfaces) == 33
    assert len(result.nut.surfaces) == 32
    assert len(result.member_surfaces) == 8

    for region in MEMBER_REGION_ORDER:
        assert result.member_count_for(region) == 1

    assert sum(
        surface.region == "transition_surfaces"
        for surface in result.bolt.surfaces
    ) == 0

    assert sum(
        surface.region == "transition_surfaces"
        for surface in result.nut.surfaces
    ) == 0

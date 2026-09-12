"""Tests for complete-joint surface classification."""

from __future__ import annotations

from pathlib import Path

import gmsh  # type: ignore[import-untyped]
import pytest

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
    identify_complete_joint_volumes,
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

def test_identify_complete_joint_volumes_accepts_shorter_bolt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bolt identification must not depend on an absolute 30 mm extent."""

    assembly = load_baseline_assembly(
        PROJECT_ROOT
        / "config"
        / "baseline_assembly.toml"
    )

    joint_definition = (
        load_complete_joint_surface_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_surface_classification.toml"
        )
    )

    volume_entities = (
        (3, 1),
        (3, 2),
        (3, 3),
        (3, 4),
    )

    bounding_boxes = {
        # Valid bolt: head extends below the assembly datum, but the
        # complete axial extent is deliberately below 30 mm.
        1: (-8.0, -8.0, -6.4, 8.0, 8.0, 23.0),
        # Head-side member.
        2: (-15.0, -15.0, 0.0, 15.0, 15.0, 10.0),
        # Nut-side member.
        3: (-15.0, -15.0, 10.0, 15.0, 15.0, 20.0),
        # Nut.
        4: (-8.0, -8.0, 20.0, 8.0, 8.0, 28.0),
    }

    centers = {
        1: (0.0, 0.0, 8.3),
        2: (0.0, 0.0, 5.0),
        3: (0.0, 0.0, 15.0),
        4: (0.0, 0.0, 24.0),
    }

    monkeypatch.setattr(
        gmsh.model,
        "getEntities",
        lambda dimension: (
            volume_entities if dimension == 3 else ()
        ),
    )

    monkeypatch.setattr(
        gmsh.model,
        "getBoundingBox",
        lambda dimension, tag: bounding_boxes[tag],
    )

    monkeypatch.setattr(
        gmsh.model.occ,
        "getCenterOfMass",
        lambda dimension, tag: centers[tag],
    )

    result = identify_complete_joint_volumes(
        assembly,
        joint_definition,
    )

    assert result.bolt_tag == 1
    assert result.head_side_member_tag == 2
    assert result.nut_side_member_tag == 3
    assert result.nut_tag == 4

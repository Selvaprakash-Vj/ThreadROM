from pathlib import Path

import gmsh  # type: ignore[import-untyped]
import pytest

from threadrom.meshing.complete_joint_pretension_fragment import (
    fragment_bolt_for_pretension,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_fragment_bolt_for_pretension() -> None:
    step_path = (
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / "TRM-ASM-000001"
        / "geometry"
        / "complete_joint_assembly.step"
    )

    gmsh.initialize()

    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("pretension-fragment-test")

        gmsh.model.occ.importShapes(
            str(step_path),
            True,
        )
        gmsh.model.occ.synchronize()

        imported_volumes = gmsh.model.getEntities(3)

        bolt_tag = next(
            tag
            for _, tag in imported_volumes
            if (
                gmsh.model.getBoundingBox(3, tag)[2] < 0.0
                and (
                    gmsh.model.getBoundingBox(3, tag)[5]
                    - gmsh.model.getBoundingBox(3, tag)[2]
                )
                > 30.0
            )
        )

        result = fragment_bolt_for_pretension(
            bolt_tag=bolt_tag,
            axial_position_mm=5.0,
        )

        assert len(gmsh.model.getEntities(3)) == 5
        assert len(result.fragment_tags) == 2
        assert result.lower_fragment_tag != result.upper_fragment_tag
        assert result.section_center_z_mm == pytest.approx(5.0, abs=1.0e-9)
        assert result.section_area_mm2 > 0.0

        lower_center_z = gmsh.model.occ.getCenterOfMass(
            3,
            result.lower_fragment_tag,
        )[2]

        upper_center_z = gmsh.model.occ.getCenterOfMass(
            3,
            result.upper_fragment_tag,
        )[2]

        assert lower_center_z < upper_center_z

        adjacent_volumes, _ = gmsh.model.getAdjacencies(
            2,
            result.section_surface_tag,
        )

        assert {
            int(tag)
            for tag in adjacent_volumes
        } == set(result.fragment_tags)

    finally:
        gmsh.finalize()

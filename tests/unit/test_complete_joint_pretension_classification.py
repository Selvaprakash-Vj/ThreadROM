from pathlib import Path

import gmsh  # type: ignore[import-untyped]

from threadrom.engineering.baseline_assembly import (
    load_baseline_assembly,
)
from threadrom.geometry.complete_nut import (
    load_complete_nut_definitions,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)
from threadrom.meshing.complete_joint_pretension_classification import (
    classify_fragmented_complete_joint,
)
from threadrom.meshing.complete_joint_pretension_fragment import (
    fragment_bolt_for_pretension,
)
from threadrom.meshing.complete_joint_surface_classification import (
    identify_complete_joint_volumes,
    load_complete_joint_surface_definition,
)
from threadrom.meshing.nut_surface_classification import (
    load_nut_surface_classification_definition,
)
from threadrom.meshing.surface_classification import (
    load_surface_classification_definition,
)
from threadrom.solver.complete_joint_pretension import (
    load_complete_joint_pretension_definition,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_classify_fragmented_complete_joint() -> None:
    assembly = load_baseline_assembly(
        PROJECT_ROOT / "config" / "baseline_assembly.toml"
    )

    bolt_blank, _ = load_threaded_shank_definitions(
        PROJECT_ROOT
    )

    nut_blank, _ = load_complete_nut_definitions(
        PROJECT_ROOT
    )

    joint_definition = load_complete_joint_surface_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_surface_classification.toml"
    )

    bolt_definition = load_surface_classification_definition(
        PROJECT_ROOT
        / "config"
        / "surface_classification.toml"
    )

    nut_definition = (
        load_nut_surface_classification_definition(
            PROJECT_ROOT
            / "config"
            / "nut_surface_classification.toml"
        )
    )

    pretension_definition = (
        load_complete_joint_pretension_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_pretension.toml"
        )
    )

    step_path = (
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / assembly.assembly_id
        / "geometry"
        / "complete_joint_assembly.step"
    )

    gmsh.initialize()

    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("pretension-classification-test")

        gmsh.model.occ.importShapes(
            str(step_path),
            True,
        )
        gmsh.model.occ.synchronize()

        original_volumes = identify_complete_joint_volumes(
            assembly,
            joint_definition,
        )

        fragment = fragment_bolt_for_pretension(
            bolt_tag=original_volumes.bolt_tag,
            axial_position_mm=(
                pretension_definition.axial_position_mm
            ),
            expected_fragment_count=(
                pretension_definition.bolt_fragment_count
            ),
        )

        result = classify_fragmented_complete_joint(
            assembly=assembly,
            bolt_blank=bolt_blank,
            nut_blank=nut_blank,
            fragment=fragment,
            nut_tag=original_volumes.nut_tag,
            head_side_member_tag=(
                original_volumes.head_side_member_tag
            ),
            nut_side_member_tag=(
                original_volumes.nut_side_member_tag
            ),
            bolt_definition=bolt_definition,
            nut_definition=nut_definition,
            joint_definition=joint_definition,
            pretension_definition=pretension_definition,
        )

        assert len(gmsh.model.getEntities(3)) == 5
        assert result.volumes.total_volume_count == 5
        assert len(result.volumes.bolt_fragment_tags) == 2
        assert result.section_surface_tag == (
            fragment.section_surface_tag
        )

        registrations = {
            registration.physical_name: registration
            for registration in result.physical_groups
        }

        assert (
            registrations[
                pretension_definition.physical_bolt_group_name
            ].entity_count
            == 2
        )

        assert (
            registrations[
                pretension_definition.section_name
            ].entity_count
            == 1
        )

        assert result.section_surface_tag not in {
            surface.tag
            for surface in result.bolt.surfaces
        }

        assert len(result.bolt.physical_groups) > 0
        assert len(result.nut.physical_groups) > 0

    finally:
        gmsh.finalize()

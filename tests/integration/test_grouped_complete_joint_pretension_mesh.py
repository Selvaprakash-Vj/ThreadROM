from pathlib import Path

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
from threadrom.meshing.complete_joint_mesh_definition import (
    load_complete_joint_mesh_definition,
    resolve_complete_joint_mesh_sizes,
)
from threadrom.meshing.complete_joint_surface_classification import (
    load_complete_joint_surface_definition,
)
from threadrom.meshing.grouped_complete_joint_pretension_mesh import (
    generate_grouped_complete_joint_pretension_mesh,
)
from threadrom.meshing.mesh_levels import (
    load_mesh_level_policy,
    resolve_mesh_levels,
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


def test_generate_grouped_complete_joint_pretension_mesh(
    tmp_path: Path,
) -> None:
    assembly = load_baseline_assembly(
        PROJECT_ROOT / "config" / "baseline_assembly.toml"
    )

    bolt_blank, bolt_thread = (
        load_threaded_shank_definitions(PROJECT_ROOT)
    )

    nut_blank, nut_thread = (
        load_complete_nut_definitions(PROJECT_ROOT)
    )

    mesh_definition = load_complete_joint_mesh_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_pretension_mesh.toml"
    )

    pretension_definition = (
        load_complete_joint_pretension_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_pretension.toml"
        )
    )

    bolt_levels = resolve_mesh_levels(
        load_mesh_level_policy(
            PROJECT_ROOT
            / "config"
            / mesh_definition.bolt_mesh_level_policy
        ),
        bolt_thread,
    )

    nut_levels = resolve_mesh_levels(
        load_mesh_level_policy(
            PROJECT_ROOT
            / "config"
            / mesh_definition.nut_mesh_level_policy
        ),
        nut_thread,
    )

    sizes = resolve_complete_joint_mesh_sizes(
        mesh_definition,
        bolt_levels,
        nut_levels,
    )

    joint_definition = (
        load_complete_joint_surface_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_surface_classification.toml"
        )
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

    step_path = (
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / assembly.assembly_id
        / "geometry"
        / "complete_joint_assembly.step"
    )

    msh_path = tmp_path / "pretension_joint.msh"

    result = (
        generate_grouped_complete_joint_pretension_mesh(
            step_path=step_path,
            msh_path=msh_path,
            assembly=assembly,
            bolt_blank=bolt_blank,
            nut_blank=nut_blank,
            mesh_definition=mesh_definition,
            sizes=sizes,
            joint_definition=joint_definition,
            bolt_definition=bolt_definition,
            nut_definition=nut_definition,
            pretension_definition=pretension_definition,
        )
    )

    assert msh_path.exists()
    assert msh_path.stat().st_size > 0

    assert result.meshio_node_count >= (
        mesh_definition.minimum_node_count
    )

    assert result.meshio_tetrahedron_count >= (
        mesh_definition.minimum_tetrahedron_count
    )

    assert result.meshio_triangle_count >= (
        mesh_definition.minimum_boundary_triangle_count
    )

    assert result.section_node_count > 0
    assert (
        result.section_node_count
        == result.shared_fragment_node_count
    )

    assert result.fragment.section_center_z_mm == pytest.approx(
        pretension_definition.axial_position_mm,
        abs=1.0e-9,
    )

    physical_group_names = {
        group.name
        for group in result.physical_groups
    }

    assert pretension_definition.section_name in (
        physical_group_names
    )

    assert (
        pretension_definition.physical_bolt_group_name
        in physical_group_names
    )

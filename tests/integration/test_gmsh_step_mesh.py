"""Integration tests for Gmsh STEP meshability."""

from pathlib import Path

from threadrom.geometry.complete_bolt import (
    build_complete_bolt,
    export_and_reimport_step,
)
from threadrom.geometry.geometry_quality import (
    load_geometry_quality_policy,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)
from threadrom.meshing.gmsh_step import (
    generate_step_tetrahedral_mesh,
    load_gmsh_mesh_definition,
)


def test_baseline_gmsh_mesh_definition_loads() -> None:
    """The controlled baseline mesh definition is valid."""

    project_root = Path(__file__).resolve().parents[2]

    definition = load_gmsh_mesh_definition(project_root / "config" / "baseline_mesh.toml")

    assert definition.mesh_id == "TRM-MSH-000001"
    assert definition.geometry_id == "TRM-GEO-000001"
    assert definition.element_order == 1
    assert not definition.save_all_elements
    assert definition.mesh_size_min_mm > 0.0

    assert definition.mesh_size_min_mm <= definition.mesh_size_max_mm


def test_complete_bolt_step_is_tetrahedron_meshable(
    tmp_path: Path,
) -> None:
    """The complete bolt survives STEP import and 3D meshing."""

    project_root = Path(__file__).resolve().parents[2]

    blank_definition, thread_definition = load_threaded_shank_definitions(project_root)

    quality_policy = load_geometry_quality_policy(project_root / "config" / "geometry_quality.toml")

    mesh_definition = load_gmsh_mesh_definition(project_root / "config" / "baseline_mesh.toml")

    bolt_build = build_complete_bolt(
        blank_definition,
        thread_definition,
        quality_policy,
    )

    step_path = tmp_path / "complete_bolt.step"
    msh_path = tmp_path / "complete_bolt.msh"

    export_and_reimport_step(
        bolt_build.complete_bolt,
        step_path,
    )

    result = generate_step_tetrahedral_mesh(
        step_path,
        msh_path,
        mesh_definition,
    )

    assert result.volume_count == 1
    assert result.cad_volume_mm3 > 0.0

    assert result.gmsh_node_count >= (mesh_definition.minimum_node_count)

    assert result.gmsh_3d_element_count >= (mesh_definition.minimum_tetrahedron_count)

    assert result.gmsh_3d_element_count == result.meshio_tetrahedron_count

    assert result.gmsh_node_count == result.meshio_node_count
    assert result.msh_file_size_bytes > 0

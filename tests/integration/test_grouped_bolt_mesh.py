"""Integration test for grouped bolt-mesh preservation."""

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
    load_gmsh_mesh_definition,
)
from threadrom.meshing.grouped_bolt_mesh import (
    generate_grouped_bolt_mesh,
)
from threadrom.meshing.surface_classification import (
    load_surface_classification_definition,
)


def test_grouped_bolt_mesh_preserves_named_boundaries(
    tmp_path: Path,
) -> None:
    """Meshio recovers every named bolt boundary from the MSH file."""

    project_root = Path(__file__).resolve().parents[2]

    blank_definition, thread_definition = load_threaded_shank_definitions(project_root)

    geometry_policy = load_geometry_quality_policy(
        project_root / "config" / "geometry_quality.toml"
    )

    mesh_definition = load_gmsh_mesh_definition(project_root / "config" / "baseline_mesh.toml")

    classification_definition = load_surface_classification_definition(
        project_root / "config" / "surface_classification.toml"
    )

    bolt_build = build_complete_bolt(
        blank_definition,
        thread_definition,
        geometry_policy,
    )

    step_path = tmp_path / "complete_bolt.step"
    msh_path = tmp_path / "complete_bolt_grouped.msh"

    export_and_reimport_step(
        bolt_build.complete_bolt,
        step_path,
    )

    result = generate_grouped_bolt_mesh(
        step_path,
        msh_path,
        blank_definition,
        mesh_definition,
        classification_definition,
    )

    assert result.gmsh_node_count == result.meshio_node_count

    assert result.gmsh_volume_element_count == result.meshio_tetrahedron_count

    assert result.gmsh_surface_element_count == result.meshio_triangle_count

    assert (
        result.element_count_for(
            mesh_definition.volume_physical_name,
            3,
        )
        == result.meshio_tetrahedron_count
    )

    for group in result.classification.physical_groups:
        assert (
            result.element_count_for(
                group.physical_name,
                2,
            )
            > 0
        )

    assert msh_path.exists()
    assert msh_path.stat().st_size > 0

"""Integration test for grouped bolt-mesh quality."""

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
from threadrom.meshing.tetrahedral_quality import (
    analyze_tetrahedral_mesh_quality,
    load_mesh_quality_definition,
)


def test_grouped_bolt_mesh_passes_quality_safety_gate(
    tmp_path: Path,
) -> None:
    """The grouped bolt mesh contains no degenerate tetrahedra."""

    project_root = Path(__file__).resolve().parents[2]

    blank_definition, thread_definition = load_threaded_shank_definitions(project_root)

    geometry_policy = load_geometry_quality_policy(
        project_root / "config" / "geometry_quality.toml"
    )

    mesh_definition = load_gmsh_mesh_definition(project_root / "config" / "baseline_mesh.toml")

    classification_definition = load_surface_classification_definition(
        project_root / "config" / "surface_classification.toml"
    )

    quality_definition = load_mesh_quality_definition(project_root / "config" / "mesh_quality.toml")

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

    grouped_result = generate_grouped_bolt_mesh(
        step_path,
        msh_path,
        blank_definition,
        mesh_definition,
        classification_definition,
    )

    quality_result = analyze_tetrahedral_mesh_quality(
        msh_path,
        quality_definition,
    )

    assert quality_result.node_count == (grouped_result.meshio_node_count)

    assert quality_result.tetrahedron_count == (grouped_result.meshio_tetrahedron_count)

    assert quality_result.degenerate_count == 0

    assert quality_result.minimum_volume_mm3 > (quality_definition.minimum_tetrahedron_volume_mm3)

    assert quality_result.minimum_mean_ratio >= (quality_definition.minimum_mean_ratio)

    assert quality_result.maximum_edge_ratio <= (quality_definition.maximum_edge_ratio)

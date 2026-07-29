"""Generate the bolt mesh with named engineering boundaries."""

from __future__ import annotations

import json
from pathlib import Path

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


def main() -> None:
    """Generate and verify the grouped bolt mesh."""

    project_root = Path(__file__).resolve().parents[1]

    blank_definition, _ = load_threaded_shank_definitions(project_root)

    mesh_definition = load_gmsh_mesh_definition(project_root / "config" / "baseline_mesh.toml")

    classification_definition = load_surface_classification_definition(
        project_root / "config" / "surface_classification.toml"
    )

    step_path = (
        project_root
        / "simulations"
        / "staging"
        / mesh_definition.geometry_id
        / "geometry"
        / "complete_bolt.step"
    )

    output_directory = project_root / "simulations" / "staging" / mesh_definition.mesh_id / "mesh"

    msh_path = output_directory / "complete_bolt_grouped_first_order.msh"

    result = generate_grouped_bolt_mesh(
        step_path,
        msh_path,
        blank_definition,
        mesh_definition,
        classification_definition,
    )

    metadata_directory = (
        project_root / "simulations" / "staging" / mesh_definition.mesh_id / "metadata"
    )

    metadata_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path = metadata_directory / "grouped_mesh_physical_groups.json"

    manifest = {
        "mesh_id": mesh_definition.mesh_id,
        "geometry_id": mesh_definition.geometry_id,
        "gmsh_node_count": result.gmsh_node_count,
        "gmsh_tetrahedron_count": (result.gmsh_volume_element_count),
        "gmsh_surface_element_count": (result.gmsh_surface_element_count),
        "meshio_node_count": result.meshio_node_count,
        "meshio_tetrahedron_count": (result.meshio_tetrahedron_count),
        "meshio_triangle_count": (result.meshio_triangle_count),
        "physical_groups": [
            {
                "name": summary.name,
                "physical_tag": summary.physical_tag,
                "dimension": summary.dimension,
                "cell_type": summary.cell_type,
                "element_count": summary.element_count,
            }
            for summary in result.physical_groups
        ],
    }

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    physical_rows = "\n".join(
        (
            f"| {summary.name} | {summary.dimension} | "
            f"{summary.cell_type} | {summary.physical_tag} | "
            f"{summary.element_count} |"
        )
        for summary in result.physical_groups
    )

    report = f"""# TRM-MSH-000001 Grouped Mesh Check

## Status

The complete bolt was tetrahedrally meshed with its classified engineering
surfaces preserved as named Gmsh physical groups.

Meshio independently recovered the volume and boundary groups from the
written MSH file.

## Mesh totals

| Quantity | Gmsh | Meshio |
|---|---:|---:|
| Nodes | {result.gmsh_node_count} | {result.meshio_node_count} |
| Tetrahedra | {result.gmsh_volume_element_count} | {result.meshio_tetrahedron_count} |
| Boundary triangles | {result.gmsh_surface_element_count} | {result.meshio_triangle_count} |

## Preserved physical groups

| Physical name | Dimension | Cell type | Physical tag | Element count |
|---|---:|---|---:|---:|
{physical_rows}

## Verification gates

The grouped mesh requires:

- Matching Gmsh and Meshio node counts
- Matching Gmsh and Meshio tetrahedron counts
- Matching Gmsh and Meshio boundary-triangle counts
- A named bolt-volume group containing every tetrahedron
- A non-empty named boundary group for every classified CAD region
- A non-empty MSH output file

## Interpretation

The mesh now contains stable engineering names rather than relying on
temporary CAD entity tags.

These physical names can be translated into CalculiX node sets and
element-face sets for loads, supports and contact definitions.

## Next gate

Measure tetrahedral element quality and establish controlled rejection
criteria before converting the grouped mesh to CalculiX input.
"""

    report_path = project_root / "docs" / "verification" / "TRM-MSH-000001_GROUPED_MESH_CHECK.md"

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    print("Grouped bolt mesh: VERIFIED")
    print(f"Nodes: {result.meshio_node_count}")
    print(f"Tetrahedra: {result.meshio_tetrahedron_count}")
    print(f"Boundary triangles: {result.meshio_triangle_count}")

    for summary in result.physical_groups:
        print(f"{summary.name}: {summary.element_count} {summary.cell_type} elements")

    print(f"MSH file: {msh_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

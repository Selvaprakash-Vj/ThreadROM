"""Generate the complete nut mesh with named boundaries."""

from __future__ import annotations

import json
from pathlib import Path

from threadrom.geometry.nut_blank import (
    load_nut_blank_definition,
)
from threadrom.meshing.gmsh_step import (
    load_gmsh_mesh_definition,
)
from threadrom.meshing.grouped_nut_mesh import (
    generate_grouped_nut_mesh,
)
from threadrom.meshing.nut_surface_classification import (
    load_nut_surface_classification_definition,
)


def main() -> None:
    """Generate and verify the grouped nut mesh."""

    project_root = Path(__file__).resolve().parents[1]

    nut_definition = load_nut_blank_definition(
        project_root / "config" / "nut_geometry.toml",
        project_root / "config" / "baseline_fastener.toml",
        project_root / "config" / "baseline_assembly.toml",
    )

    mesh_definition = load_gmsh_mesh_definition(
        project_root / "config" / "nut_mesh.toml"
    )

    classification_definition = (
        load_nut_surface_classification_definition(
            project_root
            / "config"
            / "nut_surface_classification.toml"
        )
    )

    step_path = (
        project_root
        / "simulations"
        / "staging"
        / mesh_definition.geometry_id
        / "geometry"
        / "complete_nut.step"
    )

    output_directory = (
        project_root
        / "simulations"
        / "staging"
        / mesh_definition.mesh_id
        / "mesh"
    )

    msh_path = (
        output_directory
        / "complete_nut_grouped_first_order.msh"
    )

    result = generate_grouped_nut_mesh(
        step_path,
        msh_path,
        nut_definition,
        mesh_definition,
        classification_definition,
        thread_surface_size_mm=(
            mesh_definition.mesh_size_min_mm
        ),
    )

    metadata_directory = (
        project_root
        / "simulations"
        / "staging"
        / mesh_definition.mesh_id
        / "metadata"
    )

    metadata_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path = (
        metadata_directory
        / "nut_grouped_mesh_physical_groups.json"
    )

    manifest = {
        "mesh_id": mesh_definition.mesh_id,
        "geometry_id": mesh_definition.geometry_id,
        "gmsh_node_count": result.gmsh_node_count,
        "gmsh_tetrahedron_count": (
            result.gmsh_volume_element_count
        ),
        "gmsh_surface_element_count": (
            result.gmsh_surface_element_count
        ),
        "meshio_node_count": result.meshio_node_count,
        "meshio_tetrahedron_count": (
            result.meshio_tetrahedron_count
        ),
        "meshio_triangle_count": (
            result.meshio_triangle_count
        ),
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
            f"| {summary.name} | "
            f"{summary.dimension} | "
            f"{summary.cell_type} | "
            f"{summary.physical_tag} | "
            f"{summary.element_count} |"
        )
        for summary in result.physical_groups
    )

    report = f"""# {mesh_definition.mesh_id} Grouped Nut Mesh Check

## Status

The complete internally threaded nut was tetrahedrally meshed with
its engineering surfaces preserved as named Gmsh physical groups.

Meshio independently recovered all volume and boundary groups from
the written MSH file.

## Mesh totals

| Quantity | Gmsh | Meshio |
|---|---:|---:|
| Nodes | {result.gmsh_node_count} | {result.meshio_node_count} |
| Tetrahedra | {result.gmsh_volume_element_count} | {result.meshio_tetrahedron_count} |
| Boundary triangles | {result.gmsh_surface_element_count} | {result.meshio_triangle_count} |

## Preserved physical groups

| Physical name | Dimension | Cell type | Tag | Elements |
|---|---:|---|---:|---:|
{physical_rows}

## Surface topology

| Region | CAD surface count |
|---|---:|
| Lower bearing | {result.classification.count_for("lower_bearing")} |
| Upper bearing | {result.classification.count_for("upper_bearing")} |
| Outer hex | {result.classification.count_for("outer_hex")} |
| Internal thread | {result.classification.count_for("internal_thread")} |
| Transition surfaces | {result.classification.count_for("transition_surfaces")} |

## Verification gates

The grouped nut mesh requires:

- Matching Gmsh and Meshio node counts
- Matching tetrahedron counts
- Matching boundary-triangle counts
- One NUT volume group containing every tetrahedron
- Non-empty lower and upper bearing groups
- A non-empty outer-hex group
- A non-empty internal-thread group
- A non-empty MSH output file

## Next gate

Measure tetrahedral element quality and establish the controlled
coarse, medium and fine nut-mesh hierarchy.
"""

    report_path = (
        project_root
        / "docs"
        / "verification"
        / f"{mesh_definition.mesh_id}_GROUPED_NUT_MESH_CHECK.md"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print("Grouped nut mesh: VERIFIED")
    print(f"Nodes: {result.meshio_node_count}")
    print(
        f"Tetrahedra: {result.meshio_tetrahedron_count}"
    )
    print(
        f"Boundary triangles: "
        f"{result.meshio_triangle_count}"
    )

    for summary in result.physical_groups:
        print(
            f"{summary.name}: "
            f"{summary.element_count} "
            f"{summary.cell_type} elements"
        )

    print(f"MSH file: {msh_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

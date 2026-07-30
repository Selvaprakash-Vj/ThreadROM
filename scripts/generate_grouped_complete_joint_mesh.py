"""Generate the grouped complete-joint medium mesh."""

from __future__ import annotations

import json
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
from threadrom.meshing.complete_joint_mesh_definition import (
    load_complete_joint_mesh_definition,
    resolve_complete_joint_mesh_sizes,
)
from threadrom.meshing.complete_joint_surface_classification import (
    load_complete_joint_surface_definition,
)
from threadrom.meshing.grouped_complete_joint_mesh import (
    generate_grouped_complete_joint_mesh,
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


def main() -> None:
    """Generate and verify the grouped assembly mesh."""

    project_root = Path(__file__).resolve().parents[1]

    assembly = load_baseline_assembly(
        project_root
        / "config"
        / "baseline_assembly.toml"
    )

    bolt_blank, bolt_thread = (
        load_threaded_shank_definitions(
            project_root
        )
    )

    nut_blank, nut_thread = (
        load_complete_nut_definitions(
            project_root
        )
    )

    mesh_definition = (
        load_complete_joint_mesh_definition(
            project_root
            / "config"
            / "complete_joint_mesh.toml"
        )
    )

    bolt_levels = resolve_mesh_levels(
        load_mesh_level_policy(
            project_root
            / "config"
            / mesh_definition.bolt_mesh_level_policy
        ),
        bolt_thread,
    )

    nut_levels = resolve_mesh_levels(
        load_mesh_level_policy(
            project_root
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

    classification_definition = (
        load_complete_joint_surface_definition(
            project_root
            / "config"
            / "complete_joint_surface_classification.toml"
        )
    )

    bolt_classification_definition = (
        load_surface_classification_definition(
            project_root
            / "config"
            / "surface_classification.toml"
        )
    )

    nut_classification_definition = (
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
        / assembly.assembly_id
        / "geometry"
        / "complete_joint_assembly.step"
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
        / (
            "complete_joint_grouped_"
            f"{sizes.level_name}_first_order.msh"
        )
    )

    result = generate_grouped_complete_joint_mesh(
        step_path,
        msh_path,
        assembly,
        bolt_blank,
        nut_blank,
        mesh_definition,
        sizes,
        classification_definition,
        bolt_classification_definition,
        nut_classification_definition,
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
        / "complete_joint_grouped_mesh.json"
    )

    manifest = {
        "mesh_id": mesh_definition.mesh_id,
        "assembly_id": mesh_definition.assembly_id,
        "geometry_id": mesh_definition.geometry_id,
        "classification_id": (
            mesh_definition.classification_id
        ),
        "selected_level": sizes.level_name,
        "global_minimum_size_mm": (
            sizes.mesh_size_min_mm
        ),
        "global_maximum_size_mm": (
            sizes.mesh_size_max_mm
        ),
        "bolt_thread_surface_size_mm": (
            sizes.bolt_thread_surface_size_mm
        ),
        "nut_thread_surface_size_mm": (
            sizes.nut_thread_surface_size_mm
        ),
        "gmsh_node_count": result.gmsh_node_count,
        "gmsh_tetrahedron_count": (
            result.gmsh_volume_element_count
        ),
        "gmsh_surface_element_count": (
            result.gmsh_surface_element_count
        ),
        "meshio_node_count": (
            result.meshio_node_count
        ),
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
        newline="\n",
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

    report = f"""# {mesh_definition.mesh_id} Grouped Complete-Joint Mesh Check

## Status

The complete four-component threaded joint was tetrahedrally meshed
with the bolt, nut and both clamped-member volumes preserved as named
physical groups.

All classified bolt, nut, bearing, clearance-hole and member-interface
surfaces were preserved in the written MSH file.

Meshio independently recovered the exported groups and element totals.

## Governed refinement

| Quantity | Value |
|---|---:|
| Selected level | {sizes.level_name} |
| Global minimum size | {sizes.mesh_size_min_mm:.9f} mm |
| Global maximum size | {sizes.mesh_size_max_mm:.9f} mm |
| Bolt thread size | {sizes.bolt_thread_surface_size_mm:.9f} mm |
| Nut thread size | {sizes.nut_thread_surface_size_mm:.9f} mm |

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

## Verification gates

- Exactly four named component-volume groups
- Every component volume contains tetrahedral elements
- Named volumes contain all tetrahedra exactly once
- Every classified engineering surface contains triangles
- Matching Gmsh and Meshio node totals
- Matching Gmsh and Meshio tetrahedron totals
- Matching Gmsh and Meshio boundary-triangle totals
- Non-empty MSH output

## Engineering note

The member end faces are currently classified as complete candidate
bearing/interface faces. Load and support subregions will be partitioned
separately before boundary conditions are applied, avoiding overlap
between bearing contact and remote loading definitions.

## Next gate

Measure complete-joint tetrahedral quality and establish acceptance
criteria before CalculiX transfer and contact definition.
"""

    report_path = (
        project_root
        / "docs"
        / "verification"
        / (
            f"{mesh_definition.mesh_id}"
            "_GROUPED_COMPLETE_JOINT_MESH_CHECK.md"
        )
    )

    report_path.write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print("Grouped complete-joint mesh: VERIFIED")
    print(f"Nodes: {result.meshio_node_count}")
    print(
        "Tetrahedra: "
        f"{result.meshio_tetrahedron_count}"
    )
    print(
        "Boundary triangles: "
        f"{result.meshio_triangle_count}"
    )
    print()

    for summary in result.physical_groups:
        print(
            f"{summary.name}: "
            f"{summary.element_count} "
            f"{summary.cell_type} elements"
        )

    print()
    print(f"MSH file: {msh_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

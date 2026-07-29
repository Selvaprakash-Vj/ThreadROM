"""Generate the first Gmsh tetrahedral mesh for TRM-GEO-000001."""

from pathlib import Path

from threadrom.meshing.gmsh_step import (
    generate_step_tetrahedral_mesh,
    load_gmsh_mesh_definition,
)


def main() -> None:
    """Generate and report the baseline bolt meshability gate."""

    project_root = Path(__file__).resolve().parents[1]

    definition = load_gmsh_mesh_definition(project_root / "config" / "baseline_mesh.toml")

    geometry_directory = (
        project_root / "simulations" / "staging" / definition.geometry_id / "geometry"
    )

    mesh_directory = project_root / "simulations" / "staging" / definition.mesh_id / "mesh"

    step_path = geometry_directory / "complete_bolt.step"
    msh_path = mesh_directory / "complete_bolt_first_order.msh"

    result = generate_step_tetrahedral_mesh(
        step_path,
        msh_path,
        definition,
    )

    element_rows = "\n".join(
        (
            f"| {summary.element_type} | {summary.name} | "
            f"{summary.order} | {summary.nodes_per_element} | "
            f"{summary.element_count} |"
        )
        for summary in result.element_summaries
    )

    report = f"""# TRM-MSH-000001 Gmsh Meshability Check

## Status

The complete TRM-GEO-000001 STEP geometry was successfully imported into
Gmsh and converted into a first-order tetrahedral volume mesh.

## Controlled mesh definition

| Quantity | Value |
|---|---:|
| Mesh identifier | {definition.mesh_id} |
| Geometry identifier | {definition.geometry_id} |
| Element order | {definition.element_order} |
| 2D algorithm | {definition.algorithm_2d} |
| 3D algorithm | {definition.algorithm_3d} |
| Minimum mesh size | {definition.mesh_size_min_mm:.6f} mm |
| Maximum mesh size | {definition.mesh_size_max_mm:.6f} mm |
| MSH file version | {definition.msh_file_version:.1f} |
| Binary output | {definition.binary_output} |
| Save all elements | {definition.save_all_elements} |

## Imported CAD topology

| Entity type | Count |
|---|---:|
| Imported top-level entities | {result.imported_top_level_entity_count} |
| Points | {result.point_count} |
| Curves | {result.curve_count} |
| Surfaces | {result.surface_count} |
| Volumes | {result.volume_count} |

## Imported CAD measurements

| Quantity | Value |
|---|---:|
| Gmsh OCC volume | {result.cad_volume_mm3:.6f} mm³ |
| Minimum X | {result.x_min_mm:.6f} mm |
| Maximum X | {result.x_max_mm:.6f} mm |
| Minimum Y | {result.y_min_mm:.6f} mm |
| Maximum Y | {result.y_max_mm:.6f} mm |
| Minimum Z | {result.z_min_mm:.6f} mm |
| Maximum Z | {result.z_max_mm:.6f} mm |

## Generated mesh

| Quantity | Value |
|---|---:|
| Gmsh node count | {result.gmsh_node_count} |
| Gmsh 3D element count | {result.gmsh_3d_element_count} |
| Meshio node count | {result.meshio_node_count} |
| Meshio tetrahedron count | {result.meshio_tetrahedron_count} |
| MSH file size | {result.msh_file_size_bytes} bytes |

## Three-dimensional element types

| Type | Name | Order | Nodes per element | Count |
|---:|---|---:|---:|---:|
{element_rows}

## Acceptance gates

The meshability gate requires:

- Exactly one imported CAD volume
- Positive imported CAD volume
- At least {definition.minimum_node_count} nodes
- At least {definition.minimum_tetrahedron_count} tetrahedral elements
- Matching Gmsh and Meshio node counts
- Matching Gmsh and Meshio tetrahedron counts
- A non-empty Gmsh MSH output file

## Interpretation

This is a meshability proof, not the final analysis mesh.

The present global size controls establish that the detailed helical bolt
geometry can pass through the complete STEP-to-Gmsh volume-meshing pipeline.

Local thread-contact refinement, element-quality limits, convergence studies
and production mesh release criteria remain separate later gates.

## Next gate

Classify the bolt surfaces into controlled engineering regions:

- Bolt-head loading surface
- Under-head bearing surface
- Thread-contact surfaces
- Thread tip/end surface

Those regions will later become solver boundary and contact sets.
"""

    report_path = (
        project_root / "docs" / "verification" / "TRM-MSH-000001_GMSH_MESHABILITY_CHECK.md"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    print("Gmsh STEP meshability: VERIFIED")
    print(f"Imported volumes: {result.volume_count}")
    print(f"CAD surfaces: {result.surface_count}")
    print(f"Gmsh nodes: {result.gmsh_node_count}")
    print(f"Gmsh 3D elements: {result.gmsh_3d_element_count}")
    print(f"Meshio tetrahedra: {result.meshio_tetrahedron_count}")
    print(f"MSH file: {msh_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

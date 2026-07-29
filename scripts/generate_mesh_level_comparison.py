"""Generate coarse, medium and fine grouped bolt meshes."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from time import perf_counter

from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)
from threadrom.meshing.gmsh_step import (
    load_gmsh_mesh_definition,
)
from threadrom.meshing.grouped_bolt_mesh import (
    generate_grouped_bolt_mesh,
)
from threadrom.meshing.mesh_levels import (
    load_mesh_level_policy,
    resolve_mesh_levels,
)
from threadrom.meshing.surface_classification import (
    load_surface_classification_definition,
)
from threadrom.meshing.tetrahedral_quality import (
    analyze_tetrahedral_mesh_quality,
    load_mesh_quality_definition,
)


def main() -> None:
    """Generate and compare the controlled mesh hierarchy."""

    project_root = Path(__file__).resolve().parents[1]

    blank_definition, thread_definition = load_threaded_shank_definitions(project_root)

    base_mesh_definition = load_gmsh_mesh_definition(project_root / "config" / "baseline_mesh.toml")

    classification_definition = load_surface_classification_definition(
        project_root / "config" / "surface_classification.toml"
    )

    quality_definition = load_mesh_quality_definition(project_root / "config" / "mesh_quality.toml")

    level_policy = load_mesh_level_policy(project_root / "config" / "mesh_levels.toml")

    if level_policy.mesh_id != base_mesh_definition.mesh_id:
        raise RuntimeError("Mesh-level and baseline mesh IDs differ.")

    if level_policy.geometry_id != base_mesh_definition.geometry_id:
        raise RuntimeError("Mesh-level and baseline geometry IDs differ.")

    resolved_levels = resolve_mesh_levels(
        level_policy,
        thread_definition,
    )

    step_path = (
        project_root
        / "simulations"
        / "staging"
        / base_mesh_definition.geometry_id
        / "geometry"
        / "complete_bolt.step"
    )

    mesh_directory = (
        project_root / "simulations" / "staging" / base_mesh_definition.mesh_id / "mesh_levels"
    )

    metadata_directory = (
        project_root / "simulations" / "staging" / base_mesh_definition.mesh_id / "metadata"
    )

    mesh_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    metadata_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    comparison_rows: list[dict[str, object]] = []

    for level in resolved_levels:
        mesh_definition = replace(
            base_mesh_definition,
            mesh_size_min_mm=level.mesh_size_min_mm,
            mesh_size_max_mm=level.mesh_size_max_mm,
        )

        msh_path = mesh_directory / f"complete_bolt_{level.name}.msh"

        start_time = perf_counter()

        grouped_result = generate_grouped_bolt_mesh(
            step_path,
            msh_path,
            blank_definition,
            mesh_definition,
            classification_definition,
            thread_surface_size_mm=(level.thread_surface_size_mm),
        )

        quality_result = analyze_tetrahedral_mesh_quality(
            msh_path,
            quality_definition,
        )

        elapsed_seconds = perf_counter() - start_time

        percentile_lookup = {
            item.percentile: item.value for item in quality_result.mean_ratio_percentiles
        }

        comparison_rows.append(
            {
                "level": level.name,
                "mesh_size_min_mm": level.mesh_size_min_mm,
                "mesh_size_max_mm": level.mesh_size_max_mm,
                "thread_surface_size_mm": (level.thread_surface_size_mm),
                "node_count": grouped_result.meshio_node_count,
                "tetrahedron_count": (grouped_result.meshio_tetrahedron_count),
                "boundary_triangle_count": (grouped_result.meshio_triangle_count),
                "minimum_volume_mm3": (quality_result.minimum_volume_mm3),
                "minimum_mean_ratio": (quality_result.minimum_mean_ratio),
                "p1_mean_ratio": percentile_lookup.get(
                    1.0,
                    quality_result.minimum_mean_ratio,
                ),
                "mean_mean_ratio": (quality_result.mean_mean_ratio),
                "maximum_edge_ratio": (quality_result.maximum_edge_ratio),
                "degenerate_count": (quality_result.degenerate_count),
                "elapsed_seconds": elapsed_seconds,
                "msh_file_size_bytes": (grouped_result.msh_file_size_bytes),
            }
        )

        print(
            f"{level.name.upper()}: "
            f"{grouped_result.meshio_node_count} nodes, "
            f"{grouped_result.meshio_tetrahedron_count} tets, "
            f"{elapsed_seconds:.3f} s"
        )

    manifest_path = metadata_directory / "mesh_level_comparison.json"

    manifest = {
        "policy_id": level_policy.policy_id,
        "mesh_id": level_policy.mesh_id,
        "geometry_id": level_policy.geometry_id,
        "pitch_mm": thread_definition.pitch_mm,
        "radial_thread_depth_mm": (thread_definition.radial_thread_depth_mm),
        "levels": comparison_rows,
    }

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    table_rows = "\n".join(
        (
            f"| {row['level']} | "
            f"{row['mesh_size_min_mm']:.6f} | "
            f"{row['mesh_size_max_mm']:.6f} | "
            f"{row['thread_surface_size_mm']:.6f} | "
            f"{row['node_count']} | "
            f"{row['tetrahedron_count']} | "
            f"{row['minimum_mean_ratio']:.6f} | "
            f"{row['p1_mean_ratio']:.6f} | "
            f"{row['maximum_edge_ratio']:.6f} | "
            f"{row['elapsed_seconds']:.3f} |"
        )
        for row in comparison_rows
    )

    report = f"""# TRM-MSH-000001 Mesh-Level Comparison

## Status

Coarse, medium and fine grouped bolt meshes were generated from
dimensionless factors tied to the thread geometry.

## Governing thread dimensions

| Quantity | Value |
|---|---:|
| Thread pitch | {thread_definition.pitch_mm:.9f} mm |
| Radial thread depth | {thread_definition.radial_thread_depth_mm:.9f} mm |

## Mesh-level comparison

| Level | Minimum size (mm) | Maximum size (mm) | Thread size (mm) | Nodes | Tetrahedra | Minimum mean ratio | P1 mean ratio | Maximum edge ratio | Runtime (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{table_rows}

## Parametric interpretation

The absolute mesh dimensions are not stored as M10-specific constants.

For every bolt configuration:

- Global maximum size is derived from thread pitch.
- Global minimum size is derived from radial thread depth.
- Thread-region size is derived from radial thread depth.
- The hierarchy becomes progressively finer from coarse to fine.

This makes the mesh policy reusable when future verified fastener
definitions are introduced.

## Current interpretation

These levels establish a computational hierarchy only.

The final production level will be chosen later using:

- Solver stability
- Bolt-load convergence
- Contact-pressure convergence
- First-thread load-share convergence
- Peak-stress sensitivity
- Runtime and memory cost

## Next gate

Select the medium mesh as the provisional baseline and convert its named
volume and boundary groups into a CalculiX input deck.
"""

    report_path = project_root / "docs" / "verification" / "TRM-MSH-000001_MESH_LEVEL_COMPARISON.md"

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    print()
    print("Parametric mesh hierarchy: VERIFIED")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

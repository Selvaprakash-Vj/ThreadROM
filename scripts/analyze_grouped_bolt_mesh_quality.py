"""Analyze tetrahedral quality of the grouped bolt mesh."""

from __future__ import annotations

import json
from pathlib import Path

from threadrom.meshing.tetrahedral_quality import (
    analyze_tetrahedral_mesh_quality,
    load_mesh_quality_definition,
)


def main() -> None:
    """Generate the controlled tetrahedral-quality report."""

    project_root = Path(__file__).resolve().parents[1]

    definition = load_mesh_quality_definition(project_root / "config" / "mesh_quality.toml")

    msh_path = (
        project_root
        / "simulations"
        / "staging"
        / definition.mesh_id
        / "mesh"
        / "complete_bolt_grouped_first_order.msh"
    )

    result = analyze_tetrahedral_mesh_quality(
        msh_path,
        definition,
    )

    metadata_directory = project_root / "simulations" / "staging" / definition.mesh_id / "metadata"

    metadata_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path = metadata_directory / "tetrahedral_mesh_quality.json"

    manifest = {
        "mesh_id": definition.mesh_id,
        "geometry_id": definition.geometry_id,
        "node_count": result.node_count,
        "tetrahedron_count": result.tetrahedron_count,
        "orientation": {
            "positive": result.positive_orientation_count,
            "negative": result.negative_orientation_count,
            "mixed": result.has_mixed_orientation,
        },
        "degenerate_count": result.degenerate_count,
        "volume_mm3": {
            "minimum": result.minimum_volume_mm3,
            "maximum": result.maximum_volume_mm3,
            "mean": result.mean_volume_mm3,
        },
        "mean_ratio": {
            "minimum": result.minimum_mean_ratio,
            "maximum": result.maximum_mean_ratio,
            "mean": result.mean_mean_ratio,
            "percentiles": [
                {
                    "percentile": item.percentile,
                    "value": item.value,
                }
                for item in result.mean_ratio_percentiles
            ],
            "bands": [
                {
                    "upper_limit": item.upper_limit,
                    "element_count": item.element_count,
                    "element_fraction": item.element_fraction,
                }
                for item in result.mean_ratio_bands
            ],
        },
        "edge_ratio": {
            "minimum": result.minimum_edge_ratio,
            "maximum": result.maximum_edge_ratio,
            "mean": result.mean_edge_ratio,
        },
    }

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    percentile_rows = "\n".join(
        (f"| {item.percentile:.1f} | {item.value:.9f} |") for item in result.mean_ratio_percentiles
    )

    band_rows = "\n".join(
        (
            f"| < {item.upper_limit:.3f} | "
            f"{item.element_count} | "
            f"{100.0 * item.element_fraction:.6f}% |"
        )
        for item in result.mean_ratio_bands
    )

    report = f"""# TRM-MSH-000001 Tetrahedral Quality Check

## Status

Every first-order tetrahedron in the grouped bolt mesh was independently
measured using its nodal coordinates.

## Quality metrics

### Volume

| Quantity | Value |
|---|---:|
| Nodes | {result.node_count} |
| Tetrahedra | {result.tetrahedron_count} |
| Minimum volume | {result.minimum_volume_mm3:.9e} mm? |
| Maximum volume | {result.maximum_volume_mm3:.9e} mm? |
| Mean volume | {result.mean_volume_mm3:.9e} mm? |
| Degenerate tetrahedra | {result.degenerate_count} |

### Orientation

| Orientation | Count |
|---|---:|
| Positive | {result.positive_orientation_count} |
| Negative | {result.negative_orientation_count} |
| Mixed orientation | {result.has_mixed_orientation} |

### Normalized mean ratio

A value of 1.0 represents an equilateral tetrahedron. Values approach zero
as an element becomes degenerate.

| Quantity | Value |
|---|---:|
| Minimum | {result.minimum_mean_ratio:.9f} |
| Maximum | {result.maximum_mean_ratio:.9f} |
| Mean | {result.mean_mean_ratio:.9f} |

| Percentile | Mean ratio |
|---:|---:|
{percentile_rows}

| Quality band | Element count | Fraction |
|---|---:|---:|
{band_rows}

### Edge ratio

The edge ratio is the longest element edge divided by the shortest edge.
The ideal value is 1.0.

| Quantity | Value |
|---|---:|
| Minimum | {result.minimum_edge_ratio:.9f} |
| Maximum | {result.maximum_edge_ratio:.9f} |
| Mean | {result.mean_edge_ratio:.9f} |

## Preliminary safety gates

| Gate | Controlled value |
|---|---:|
| Minimum tetrahedron volume | {definition.minimum_tetrahedron_volume_mm3:.9e} mm? |
| Minimum mean ratio | {definition.minimum_mean_ratio:.9e} |
| Maximum edge ratio | {definition.maximum_edge_ratio:.6f} |
| Mixed orientation permitted | {definition.allow_mixed_orientation} |

These are numerical-safety gates only. They reject zero-volume, degenerate
or catastrophically distorted elements.

Production-quality thresholds will be selected after inspecting this measured
distribution and later validating stress convergence.

## Next gate

Use the measured distribution to define coarse, medium and fine mesh levels,
then establish thread-region refinement and convergence criteria.
"""

    report_path = (
        project_root / "docs" / "verification" / "TRM-MSH-000001_TETRAHEDRAL_QUALITY_CHECK.md"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    print("Tetrahedral mesh quality: VERIFIED")
    print(f"Nodes: {result.node_count}")
    print(f"Tetrahedra: {result.tetrahedron_count}")
    print(f"Degenerate elements: {result.degenerate_count}")
    print(f"Minimum volume: {result.minimum_volume_mm3:.9e} mm^3")
    print(f"Minimum mean ratio: {result.minimum_mean_ratio:.9f}")
    print(f"Mean mean ratio: {result.mean_mean_ratio:.9f}")
    print(f"Maximum edge ratio: {result.maximum_edge_ratio:.9f}")
    print(f"Mixed orientation: {result.has_mixed_orientation}")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

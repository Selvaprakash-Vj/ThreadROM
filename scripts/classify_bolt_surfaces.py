"""Classify the complete bolt surfaces into engineering regions."""

from __future__ import annotations

import json
from pathlib import Path

from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)
from threadrom.meshing.surface_classification import (
    REGION_ORDER,
    classify_step_surfaces,
    load_surface_classification_definition,
)


def main() -> None:
    """Generate the controlled bolt-surface classification record."""

    project_root = Path(__file__).resolve().parents[1]

    blank_definition, _ = load_threaded_shank_definitions(project_root)

    definition = load_surface_classification_definition(
        project_root / "config" / "surface_classification.toml"
    )

    step_path = (
        project_root
        / "simulations"
        / "staging"
        / definition.geometry_id
        / "geometry"
        / "complete_bolt.step"
    )

    result = classify_step_surfaces(
        step_path,
        blank_definition,
        definition,
    )

    metadata_directory = project_root / "simulations" / "staging" / definition.mesh_id / "metadata"

    metadata_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path = metadata_directory / "bolt_surface_classification.json"

    manifest = {
        "mesh_id": definition.mesh_id,
        "geometry_id": definition.geometry_id,
        "plane_tolerance_mm": definition.plane_tolerance_mm,
        "imported_volume_count": result.imported_volume_count,
        "surface_count": result.surface_count,
        "groups": {region: list(result.tags_for(region)) for region in REGION_ORDER},
        "physical_groups": [
            {
                "region": group.region,
                "physical_name": group.physical_name,
                "physical_tag": group.physical_tag,
                "entity_count": group.entity_count,
            }
            for group in result.physical_groups
        ],
        "surfaces": [
            {
                "tag": surface.tag,
                "region": surface.region,
                "area_mm2": surface.area_mm2,
                "center_mm": [
                    surface.center_x_mm,
                    surface.center_y_mm,
                    surface.center_z_mm,
                ],
                "bounds_mm": [
                    surface.x_min_mm,
                    surface.y_min_mm,
                    surface.z_min_mm,
                    surface.x_max_mm,
                    surface.y_max_mm,
                    surface.z_max_mm,
                ],
            }
            for surface in result.surfaces
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

    group_rows = "\n".join(
        (
            f"| {region} | "
            f"{definition.physical_name(region)} | "
            f"{result.count_for(region)} | "
            f"{', '.join(map(str, result.tags_for(region))) or 'None'} |"
        )
        for region in REGION_ORDER
    )

    surface_rows = "\n".join(
        (
            f"| {surface.tag} | {surface.region} | "
            f"{surface.area_mm2:.6f} | "
            f"{surface.center_z_mm:.6f} | "
            f"{surface.z_min_mm:.6f} | "
            f"{surface.z_max_mm:.6f} |"
        )
        for surface in result.surfaces
    )

    report = f"""# TRM-MSH-000001 Bolt Surface Classification

## Status

The complete TRM-GEO-000001 STEP bolt was imported into Gmsh and every
surface was assigned to a controlled engineering region.

## Classification basis

The classifier derives its axial reference planes from the parametric bolt
definition:

| Reference | Position |
|---|---:|
| Head top | {-blank_definition.head_height_mm:.6f} mm |
| Under-head interface | 0.000000 mm |
| Bolt tip | {blank_definition.underhead_length_mm:.6f} mm |
| Classification tolerance | {definition.plane_tolerance_mm:.6f} mm |

No CAD face tag is hard-coded. Surface tags may change after regeneration
without changing the engineering classification logic.

## Classified physical groups

| Region | Physical name | Surface count | Surface tags |
|---|---|---:|---|
{group_rows}

## Surface measurements

| Tag | Region | Area (mm²) | Centre Z (mm) | Minimum Z (mm) | Maximum Z (mm) |
|---:|---|---:|---:|---:|---:|
{surface_rows}

## Verification gates

The classification requires:

- Exactly one imported bolt volume
- Positive area for every surface
- Every surface assigned exactly once
- At least one head-top surface
- At least one under-head bearing surface
- At least six head-side surfaces
- At least one threaded-body surface
- At least one bolt-tip surface
- One Gmsh physical group for every non-empty region

## Interpretation

These regions are topology classifications only.

They do not yet define solver loads or contact behaviour. Later gates will
map them to CalculiX node sets, element-face sets, loads, constraints and
contact definitions.

## Next gate

Integrate these physical groups into the generated tetrahedral MSH file and
verify that Meshio preserves the named surface groups.
"""

    report_path = (
        project_root / "docs" / "verification" / "TRM-MSH-000001_SURFACE_CLASSIFICATION.md"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    print("Bolt surface classification: VERIFIED")
    print(f"Imported volumes: {result.imported_volume_count}")
    print(f"Total surfaces: {result.surface_count}")

    for region in REGION_ORDER:
        print(f"{definition.physical_name(region)}: {result.count_for(region)}")

    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

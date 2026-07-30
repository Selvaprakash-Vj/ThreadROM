"""Classify the complete nut STEP surfaces."""

from pathlib import Path

from threadrom.geometry.nut_blank import (
    load_nut_blank_definition,
)
from threadrom.meshing.nut_surface_classification import (
    REGION_ORDER,
    classify_step_nut_surfaces,
    load_nut_surface_classification_definition,
)


def main() -> None:
    """Classify and print the current nut STEP topology."""

    project_root = Path(__file__).resolve().parents[1]

    nut_definition = load_nut_blank_definition(
        project_root / "config" / "nut_geometry.toml",
        project_root / "config" / "baseline_fastener.toml",
        project_root / "config" / "baseline_assembly.toml",
    )

    definition = load_nut_surface_classification_definition(
        project_root
        / "config"
        / "nut_surface_classification.toml"
    )

    step_path = (
        project_root
        / "simulations"
        / "staging"
        / nut_definition.geometry_id
        / "geometry"
        / "complete_nut.step"
    )

    result = classify_step_nut_surfaces(
        step_path,
        nut_definition,
        definition,
    )

    print("Complete nut surface classification: VERIFIED")
    print(f"Volumes: {result.imported_volume_count}")
    print(f"Surfaces: {result.surface_count}")

    for region in REGION_ORDER:
        print(f"{region}: {result.count_for(region)}")

    print()

    for surface in result.surfaces:
        print(
            f"tag={surface.tag:3d} "
            f"region={surface.region:20s} "
            f"area={surface.area_mm2:12.6f} "
            f"sampled_radius=["
            f"{surface.sampled_radial_min_mm:.6f}, "
            f"{surface.sampled_radial_max_mm:.6f}] "
            f"z=[{surface.z_min_mm:.6f}, "
            f"{surface.z_max_mm:.6f}]"
        )


if __name__ == "__main__":
    main()

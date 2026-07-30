"""Classify all complete-joint engineering surfaces."""

from __future__ import annotations

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
from threadrom.meshing.complete_joint_surface_classification import (
    MEMBER_REGION_ORDER,
    classify_complete_joint_step,
    load_complete_joint_surface_definition,
)
from threadrom.meshing.nut_surface_classification import (
    load_nut_surface_classification_definition,
)
from threadrom.meshing.surface_classification import (
    load_surface_classification_definition,
)


def main() -> None:
    """Classify and verify the complete joint."""

    project_root = Path(__file__).resolve().parents[1]

    assembly = load_baseline_assembly(
        project_root
        / "config"
        / "baseline_assembly.toml"
    )

    bolt_blank, _ = load_threaded_shank_definitions(
        project_root
    )

    nut_blank, _ = load_complete_nut_definitions(
        project_root
    )

    bolt_definition = (
        load_surface_classification_definition(
            project_root
            / "config"
            / "surface_classification.toml"
        )
    )

    nut_definition = (
        load_nut_surface_classification_definition(
            project_root
            / "config"
            / "nut_surface_classification.toml"
        )
    )

    joint_definition = (
        load_complete_joint_surface_definition(
            project_root
            / "config"
            / "complete_joint_surface_classification.toml"
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

    result = classify_complete_joint_step(
        step_path,
        assembly,
        bolt_blank,
        nut_blank,
        bolt_definition,
        nut_definition,
        joint_definition,
    )

    print(
        "Complete joint surface classification: VERIFIED"
    )
    print("Volumes: 4")
    print(
        f"Bolt surfaces: {len(result.bolt.surfaces)}"
    )
    print(
        f"Nut surfaces: {len(result.nut.surfaces)}"
    )
    print(
        "Member surfaces: "
        f"{len(result.member_surfaces)}"
    )
    print()

    for region in MEMBER_REGION_ORDER:
        print(
            f"{region}: "
            f"{result.member_count_for(region)}"
        )

    print()
    print("Member surface tags:")

    for surface in result.member_surfaces:
        print(
            f"tag={surface.tag:3d} "
            f"component={surface.component:17s} "
            f"region={surface.region:29s} "
            f"type={surface.surface_type:8s} "
            f"area={surface.area_mm2:11.6f} "
            f"z={surface.center_z_mm:7.3f}"
        )


if __name__ == "__main__":
    main()

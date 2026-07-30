"""Generate and verify the complete four-solid joint."""

from __future__ import annotations

from pathlib import Path

from threadrom.engineering.baseline_assembly import (
    load_baseline_assembly,
)
from threadrom.geometry.bolt_nut_assembly import (
    build_bolt_nut_assembly,
)
from threadrom.geometry.complete_bolt import (
    build_complete_bolt,
)
from threadrom.geometry.complete_joint_assembly import (
    build_complete_joint_assembly,
    export_and_reimport_complete_joint_assembly,
    load_assembly_geometry_validation_policy,
    measure_complete_joint_assembly,
    validate_complete_joint_assembly,
    validate_complete_joint_step_round_trip,
)
from threadrom.geometry.complete_nut import (
    build_complete_nut,
    load_complete_nut_definitions,
)
from threadrom.geometry.geometry_quality import (
    load_geometry_quality_policy,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)


def main() -> None:
    """Generate and verify the governed complete joint."""

    project_root = Path(__file__).resolve().parents[1]

    assembly_definition = load_baseline_assembly(
        project_root
        / "config"
        / "baseline_assembly.toml"
    )

    validation_policy = (
        load_assembly_geometry_validation_policy(
            project_root
            / "config"
            / "assembly_geometry_validation.toml"
        )
    )

    quality_policy = load_geometry_quality_policy(
        project_root
        / "config"
        / "geometry_quality.toml"
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

    bolt_build = build_complete_bolt(
        bolt_blank,
        bolt_thread,
        quality_policy,
    )

    nut_build = build_complete_nut(
        nut_blank,
        nut_thread,
    )

    bolt_nut = build_bolt_nut_assembly(
        bolt_build.complete_bolt,
        nut_build.complete_nut,
        assembly_definition,
    )

    joint = build_complete_joint_assembly(
        bolt_nut,
        assembly_definition,
    )

    native = measure_complete_joint_assembly(
        joint
    )

    validate_complete_joint_assembly(
        native,
        assembly_definition,
        validation_policy,
    )

    output_directory = (
        project_root
        / "simulations"
        / "staging"
        / assembly_definition.assembly_id
        / "geometry"
    )

    step_path = (
        output_directory
        / "complete_joint_assembly.step"
    )

    _, step = export_and_reimport_complete_joint_assembly(
        joint,
        step_path,
    )

    validate_complete_joint_step_round_trip(
        step,
        quality_policy,
        validation_policy.expected_component_count,
    )

    interference_rows = "\n".join(
        (
            f"| {item.first_component} | "
            f"{item.second_component} | "
            f"{item.intersection_volume_mm3:.12e} |"
        )
        for item in native.interferences
    )

    report = f"""# {assembly_definition.assembly_id} Complete Joint Assembly Check

## Status

The complete bolt, internally threaded nut and two annular
clamped members were constructed as four independent solids.

All governed placement, topology, material-interference and STEP
round-trip gates passed.

## Component topology

| Component | Solid count |
|---|---:|
{chr(10).join(
    f"| {name} | {count} |"
    for name, count in native.component_solid_counts
)}

| Quantity | Value |
|---|---:|
| Complete assembly solids | {native.assembly_solid_count} |
| Maximum pairwise interference | {native.maximum_interference_volume_mm3:.12e} mm^3 |

## Member placement

| Member | Minimum Z | Maximum Z |
|---|---:|---:|
| Head side | {native.head_side_member_z_min_mm:.9f} mm | {native.head_side_member_z_max_mm:.9f} mm |
| Nut side | {native.nut_side_member_z_min_mm:.9f} mm | {native.nut_side_member_z_max_mm:.9f} mm |

## Pairwise material-interference checks

| First component | Second component | Intersection volume (mm^3) |
|---|---|---:|
{interference_rows}

## STEP round-trip

| Quantity | Value |
|---|---:|
| Native solids | {step.native_solid_count} |
| Reimported solids | {step.reimported_solid_count} |
| Native component-volume sum | {step.native_component_volume_mm3:.9f} mm^3 |
| Reimported component-volume sum | {step.reimported_component_volume_mm3:.9f} mm^3 |
| Relative volume error | {step.relative_volume_error:.12e} |
| Maximum bounds error | {step.maximum_bounds_error_mm:.12e} mm |

## Automated parametric gate

Every future generated design case must pass these same checks
before it is permitted to enter meshing, FEM execution or the
surrogate-model dataset.

## Next gate

Classify the complete-joint contact and boundary surfaces:

- Bolt-head bearing surface
- Nut bearing surface
- Upper/lower member interface
- Bolt and nut thread surfaces
- External member loading and support surfaces
"""

    report_path = (
        project_root
        / "docs"
        / "verification"
        / (
            f"{assembly_definition.assembly_id}"
            "_COMPLETE_JOINT_ASSEMBLY_CHECK.md"
        )
    )

    report_path.write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print("Complete joint assembly geometry: VERIFIED")
    print(
        f"Native solids: {step.native_solid_count}"
    )
    print(
        "Reimported solids: "
        f"{step.reimported_solid_count}"
    )
    print(
        "Maximum interference: "
        f"{native.maximum_interference_volume_mm3:.12e} mm^3"
    )
    print(
        "Relative volume error: "
        f"{step.relative_volume_error:.12e}"
    )
    print(
        "Maximum bounds error: "
        f"{step.maximum_bounds_error_mm:.12e} mm"
    )
    print(f"STEP file: {step_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

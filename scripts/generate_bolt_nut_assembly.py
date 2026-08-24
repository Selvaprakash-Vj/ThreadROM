"""Generate and verify the baseline bolt-nut assembly STEP."""

from __future__ import annotations

from pathlib import Path

from threadrom.engineering.baseline_assembly import (
    load_baseline_assembly,
)
from threadrom.geometry.bolt_nut_assembly import (
    build_bolt_nut_assembly,
    export_and_reimport_bolt_nut_assembly,
    measure_bolt_nut_assembly,
    validate_bolt_nut_step_round_trip,
)
from threadrom.geometry.complete_bolt import (
    build_complete_bolt,
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
    """Generate the governed two-solid assembly."""

    project_root = Path(__file__).resolve().parents[1]

    assembly_definition = load_baseline_assembly(
        project_root
        / "config"
        / "baseline_assembly.toml"
    )

    bolt_blank, bolt_thread = (
        load_threaded_shank_definitions(
            project_root
        )
    )

    quality_policy = load_geometry_quality_policy(
        project_root
        / "config"
        / "geometry_quality.toml"
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
        quality_policy,
    )

    assembly_build = build_bolt_nut_assembly(
        bolt_build.complete_bolt,
        nut_build.complete_nut,
        assembly_definition,
        bolt_thread,
        nut_thread,
        quality_policy.thread_boolean_overlap_mm,
    )

    native = measure_bolt_nut_assembly(
        assembly_build
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
        / "bolt_nut_assembly.step"
    )

    _, step = export_and_reimport_bolt_nut_assembly(
        assembly_build,
        step_path,
    )

    validate_bolt_nut_step_round_trip(
        step,
        quality_policy,
    )

    report = f"""# {assembly_definition.assembly_id} Bolt-Nut Assembly Check

## Status

The complete bolt and internally threaded nut were positioned using
the governed parametric thread-pair registration law and exported as a
two-solid STEP assembly.

## Governed placement

| Quantity | Value |
|---|---:|
| Nut translation | {assembly_definition.nut_translation_z_mm:.9f} mm |
| Registration pitch | {assembly_build.registration.pitch_mm:.9f} mm |
| Registration handedness | {assembly_build.registration.handedness} |
| Applied nut rotation | {assembly_build.registration.nut_rotation_deg:.9f} deg |
| Registration basis | canonical rigid screw datum |
| Lower nut bearing plane | {assembly_definition.nut_lower_bearing_z_mm:.9f} mm |
| Upper nut bearing plane | {assembly_definition.nut_upper_bearing_z_mm:.9f} mm |
| Thread protrusion | {assembly_definition.calculated_protrusion_length_mm:.9f} mm |

## Native assembly

| Quantity | Value |
|---|---:|
| Bolt solids | {native.bolt_solid_count} |
| Nut solids | {native.nut_solid_count} |
| Assembly solids | {native.assembly_solid_count} |
| Bolt volume | {native.bolt_volume_mm3:.9f} mm^3 |
| Nut volume | {native.nut_volume_mm3:.9f} mm^3 |
| Component-volume sum | {native.component_volume_sum_mm3:.9f} mm^3 |
| Axial bounds | {native.z_min_mm:.9f} to {native.z_max_mm:.9f} mm |

## STEP round-trip

| Quantity | Value |
|---|---:|
| Native solids | {step.native_solid_count} |
| Reimported solids | {step.reimported_solid_count} |
| Relative volume error | {step.relative_volume_error:.12e} |
| Maximum bounds error | {step.maximum_bounds_error_mm:.12e} mm |

## Acceptance gates

The STEP assembly must preserve:

- Exactly one bolt solid
- Exactly one nut solid
- Exactly two assembly volumes
- Governed parametric thread-pair phase
- STEP volume error within policy
- STEP bounds error within policy

## Next gate

Introduce the two clamped-member solids and verify the complete
four-component joint stack before contact meshing.
"""

    report_path = (
        project_root
        / "docs"
        / "verification"
        / f"{assembly_definition.assembly_id}_BOLT_NUT_ASSEMBLY_CHECK.md"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print("Bolt-nut assembly geometry: VERIFIED")
    print(
        f"Native solids: {step.native_solid_count}"
    )
    print(
        "Reimported solids: "
        f"{step.reimported_solid_count}"
    )
    print(
        "Nut placement: "
        f"Z +{assembly_definition.nut_translation_z_mm:.6f} mm, "
        f"rotation +{assembly_build.registration.nut_rotation_deg:.6f} deg"
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

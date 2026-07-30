"""Generate and verify the complete TRM-GEO-000001 nut."""

from pathlib import Path

import cadquery as cq

from threadrom.geometry.complete_bolt import (
    export_and_reimport_step,
)
from threadrom.geometry.complete_nut import (
    build_complete_nut,
    load_complete_nut_definitions,
    measure_complete_nut,
)


def main() -> None:
    """Generate the complete nut and verify its STEP round trip."""

    project_root = Path(__file__).resolve().parents[1]

    nut_definition, thread_definition = (
        load_complete_nut_definitions(project_root)
    )

    build = build_complete_nut(
        nut_definition,
        thread_definition,
    )

    measurements = measure_complete_nut(build)

    output_directory = (
        project_root
        / "simulations"
        / "staging"
        / nut_definition.geometry_id
        / "geometry"
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    step_path = output_directory / "complete_nut.step"

    imported_shape, step_measurements = (
        export_and_reimport_step(
            build.complete_nut,
            step_path,
        )
    )

    imported_step_copy = (
        output_directory
        / "complete_nut_reimported.step"
    )

    cq.exporters.export(
        imported_shape,
        str(imported_step_copy),
    )

    report = f"""# {nut_definition.geometry_id} Complete Nut Check

## Status

Complete internally threaded nut generated and verified through a STEP
export and re-import round trip.

## Parametric construction

1. Load the governed fastener, assembly and nut definitions.
2. Build the regular hexagonal nut blank.
3. Create the basic internal minor-diameter bore.
4. Sweep the full three-dimensional helical internal-thread cutter.
5. Subtract the cutter from the nut blank.
6. Verify that the result is one valid solid.
7. Export the complete nut to STEP.
8. Re-import the STEP file and compare its volume and bounds.

## Configuration

| Quantity | Value |
|---|---:|
| Geometry identifier | {nut_definition.geometry_id} |
| Assembly identifier | {nut_definition.assembly_id} |
| Component | {nut_definition.component_name} |
| Nominal diameter | {nut_definition.nominal_diameter_mm:.6f} mm |
| Pitch | {nut_definition.pitch_mm:.6f} mm |
| Nut width across flats | {nut_definition.across_flats_mm:.6f} mm |
| Nut width across corners | {nut_definition.across_corners_mm:.6f} mm |
| Nut thickness | {nut_definition.thickness_mm:.6f} mm |
| Basic internal minor diameter | {nut_definition.bore_diameter_mm:.6f} mm |
| Internal-thread radial depth | {thread_definition.radial_thread_depth_mm:.6f} mm |
| Thread handedness | {thread_definition.handedness} |
| Helical sweep turns | {thread_definition.turn_count:.6f} |

## Native CAD measurements

| Quantity | Value |
|---|---:|
| Solid count | {measurements.solid_count} |
| Valid solid | {measurements.is_valid} |
| X bounding length | {measurements.x_length_mm:.6f} mm |
| Y bounding length | {measurements.y_length_mm:.6f} mm |
| Minimum Z | {measurements.z_min_mm:.6f} mm |
| Maximum Z | {measurements.z_max_mm:.6f} mm |
| Plain-bore blank volume | {measurements.blank_volume_mm3:.6f} mm^3 |
| Helical cutter volume | {measurements.cutter_volume_mm3:.6f} mm^3 |
| Removed thread volume | {measurements.removed_thread_volume_mm3:.6f} mm^3 |
| Complete nut volume | {measurements.complete_volume_mm3:.6f} mm^3 |
| Face count | {measurements.face_count} |
| Edge count | {measurements.edge_count} |

## STEP round-trip measurements

| Quantity | Value |
|---|---:|
| STEP file size | {step_measurements.file_size_bytes} bytes |
| Re-imported solid count | {step_measurements.solid_count} |
| Re-imported valid shape | {step_measurements.is_valid} |
| Re-imported volume | {step_measurements.volume_mm3:.6f} mm^3 |
| Relative volume error | {step_measurements.relative_volume_error:.9e} |
| Maximum bounds error | {step_measurements.maximum_bounds_error_mm:.9e} mm |

## Verification gates

The complete nut must:

- Consist of exactly one valid solid
- Preserve the governed nut thickness
- Preserve the external across-flats and across-corners envelope
- Contain a full three-dimensional helical internal thread
- Remove positive material beyond the initial cylindrical bore
- Survive STEP export and re-import
- Preserve volume and bounds through the STEP round trip

## Current limitations

The Phase 1 nut remains an idealized engineering reference.

Not yet included:

- Nut-face chamfers
- Thread lead-in and runout
- Rounded internal-thread root
- Explicit ISO 6H tolerance allowance
- Manufacturing variation
- Surface roughness

## Next gate

Import the complete nut STEP geometry into Gmsh and establish the
nut meshability and topology-classification baseline.
"""

    report_path = (
        project_root
        / "docs"
        / "verification"
        / f"{nut_definition.geometry_id}_COMPLETE_NUT_CHECK.md"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print("Complete parametric nut: GENERATED")
    print(f"Valid solid: {measurements.is_valid}")
    print(f"Solid count: {measurements.solid_count}")
    print(
        "Lateral bounds: "
        f"{measurements.x_length_mm:.6f} x "
        f"{measurements.y_length_mm:.6f} mm"
    )
    print(
        "Z range: "
        f"{measurements.z_min_mm:.6f} to "
        f"{measurements.z_max_mm:.6f} mm"
    )
    print(
        "Complete volume: "
        f"{measurements.complete_volume_mm3:.6f} mm^3"
    )
    print(
        "Removed thread volume: "
        f"{measurements.removed_thread_volume_mm3:.6f} mm^3"
    )
    print(
        "STEP relative volume error: "
        f"{step_measurements.relative_volume_error:.9e}"
    )
    print(
        "STEP maximum bounds error: "
        f"{step_measurements.maximum_bounds_error_mm:.9e} mm"
    )
    print(f"STEP file: {step_path}")
    print(f"Re-imported STEP file: {imported_step_copy}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

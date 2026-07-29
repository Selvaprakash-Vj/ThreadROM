"""Generate and verify the complete TRM-GEO-000001 bolt."""

from pathlib import Path

import cadquery as cq

from threadrom.geometry.complete_bolt import (
    build_complete_bolt,
    expected_hex_across_corners_mm,
    export_and_reimport_step,
    measure_complete_bolt,
)
from threadrom.geometry.geometry_quality import (
    load_geometry_quality_policy,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)


def main() -> None:
    """Generate the complete bolt and STEP round-trip report."""

    project_root = Path(__file__).resolve().parents[1]

    blank_definition, thread_definition = load_threaded_shank_definitions(project_root)

    quality_policy = load_geometry_quality_policy(project_root / "config" / "geometry_quality.toml")

    build = build_complete_bolt(
        blank_definition,
        thread_definition,
        quality_policy,
    )

    measurements = measure_complete_bolt(build)

    output_directory = (
        project_root / "simulations" / "staging" / blank_definition.geometry_id / "geometry"
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    step_path = output_directory / "complete_bolt.step"

    imported_shape, step_measurements = export_and_reimport_step(
        build.complete_bolt,
        step_path,
    )

    imported_step_copy = output_directory / "complete_bolt_reimported.step"

    cq.exporters.export(
        imported_shape,
        str(imported_step_copy),
    )

    expected_across_corners_mm = expected_hex_across_corners_mm(
        blank_definition.head_across_flats_mm
    )

    report = f"""# TRM-GEO-000001 Complete Bolt Check

## Status

Complete development bolt generated and verified through STEP round-trip.

## Parametric construction

1. Load controlled fastener, assembly and geometry definitions.
2. Build a regular hex head from the configured width across flats.
3. Build the verified additive helical threaded shank.
4. Add an internal parametric head-shank fusion bridge.
5. Fuse all components into one valid solid.
6. Export the complete bolt to STEP.
7. Re-import the STEP file and compare volume and bounds.

## Configuration

| Quantity | Value |
|---|---:|
| Geometry identifier | {blank_definition.geometry_id} |
| Nominal diameter | {blank_definition.nominal_diameter_mm:.6f} mm |
| Pitch | {thread_definition.pitch_mm:.6f} mm |
| Under-head length | {blank_definition.underhead_length_mm:.6f} mm |
| Head width across flats | {blank_definition.head_across_flats_mm:.6f} mm |
| Expected width across corners | {expected_across_corners_mm:.6f} mm |
| Head height | {blank_definition.head_height_mm:.6f} mm |
| Handedness | {thread_definition.handedness} |
| Boolean tolerance | {quality_policy.boolean_tolerance_mm:.9f} mm |

## Native CAD measurements

| Quantity | Value |
|---|---:|
| Solid count | {measurements.solid_count} |
| Valid solid | {measurements.is_valid} |
| X bounding length | {measurements.x_length_mm:.6f} mm |
| Y bounding length | {measurements.y_length_mm:.6f} mm |
| Minimum Z | {measurements.z_min_mm:.6f} mm |
| Maximum Z | {measurements.z_max_mm:.6f} mm |
| Head volume | {measurements.head_volume_mm3:.6f} mm³ |
| Threaded-shank volume | {measurements.threaded_shank_volume_mm3:.6f} mm³ |
| Fusion-bridge volume | {measurements.fusion_bridge_volume_mm3:.6f} mm³ |
| Complete-bolt volume | {measurements.complete_volume_mm3:.6f} mm³ |
| Union overlap volume | {measurements.union_overlap_volume_mm3:.6f} mm³ |
| Face count | {measurements.face_count} |
| Edge count | {measurements.edge_count} |

## STEP round-trip measurements

| Quantity | Value |
|---|---:|
| STEP file size | {step_measurements.file_size_bytes} bytes |
| Re-imported solid count | {step_measurements.solid_count} |
| Re-imported valid shape | {step_measurements.is_valid} |
| Re-imported volume | {step_measurements.volume_mm3:.6f} mm³ |
| Relative volume error | {step_measurements.relative_volume_error:.9e} |
| Maximum bounds error | {step_measurements.maximum_bounds_error_mm:.9e} mm |

## Verification gates

The complete bolt must:

- Consist of exactly one valid solid
- Preserve the configured under-head length
- Preserve the configured head height
- Preserve the regular-hex across-flats and across-corners dimensions
- Contain positive head-shank fusion overlap
- Survive STEP export and re-import
- Preserve volume and bounds within the controlled quality policy

## Current limitations

The geometry remains an idealized Phase 1 engineering reference.

Not yet included:

- Tip chamfer
- Under-head fillet
- Thread lead-in and runout
- External tolerance-class allowance
- Rounded thread root
- Manufacturing variation

## Next gate

Import the complete STEP geometry into Gmsh and establish the first
meshability and topology-classification check.
"""

    report_path = project_root / "docs" / "verification" / "TRM-GEO-000001_COMPLETE_BOLT_CHECK.md"

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    print("Complete parametric bolt: GENERATED")
    print(f"Valid solid: {measurements.is_valid}")
    print(f"Solid count: {measurements.solid_count}")
    print(f"Lateral bounds: {measurements.x_length_mm:.6f} x {measurements.y_length_mm:.6f} mm")
    print(f"Z range: {measurements.z_min_mm:.6f} to {measurements.z_max_mm:.6f} mm")
    print(f"Complete volume: {measurements.complete_volume_mm3:.6f} mm^3")
    print(f"STEP relative volume error: {step_measurements.relative_volume_error:.9e}")
    print(f"STEP maximum bounds error: {step_measurements.maximum_bounds_error_mm:.9e} mm")
    print(f"STEP file: {step_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

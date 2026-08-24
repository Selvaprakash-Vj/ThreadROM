"""Generate and verify the additive TRM-GEO-000001 threaded shank."""

from pathlib import Path

import cadquery as cq

from threadrom.geometry.geometry_quality import load_geometry_quality_policy
from threadrom.geometry.threaded_shank import (
    build_threaded_shank,
    load_threaded_shank_definitions,
    measure_threaded_shank,
)


def main() -> None:
    """Generate the threaded shank and its verification record."""

    project_root = Path(__file__).resolve().parents[1]

    blank_definition, thread_definition = (
        load_threaded_shank_definitions(project_root)
    )

    quality_policy = load_geometry_quality_policy(
        project_root / "config" / "geometry_quality.toml"
    )

    build = build_threaded_shank(
        blank_definition,
        thread_definition,
        quality_policy,
    )

    measurements = measure_threaded_shank(
        build,
        thread_definition,
    )

    output_directory = (
        project_root
        / "simulations"
        / "staging"
        / blank_definition.geometry_id
        / "geometry"
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    step_path = output_directory / "threaded_shank.step"

    cq.exporters.export(
        build.threaded_shank,
        str(step_path),
    )

    report = f"""# TRM-GEO-000001 Threaded Shank Check

## Status

Development threaded shank generated using additive construction.

## Construction method

The previous subtractive helical-groove approach was rejected after the
OpenCascade Boolean intersection returned an invalid result approximately
equal to the complete cylindrical blank.

The controlled replacement construction is:

1. Build a continuous minor-diameter core.
2. Sweep a trapezoidal external-thread ridge along a right-hand helix.
3. Introduce controlled radial overlap.
4. Fuse the core and ridge using a fuzzy Boolean tolerance.

## Configuration

| Quantity | Value |
|---|---:|
| Nominal major diameter | {blank_definition.nominal_diameter_mm:.6f} mm |
| Basic minor diameter | {thread_definition.minor_diameter_mm:.9f} mm |
| Threaded length | {thread_definition.thread_length_mm:.6f} mm |
| Pitch | {thread_definition.pitch_mm:.6f} mm |
| Handedness | {thread_definition.handedness} |

## CAD measurements

| Quantity | Value |
|---|---:|
| Solid count | {measurements.solid_count} |
| Valid solid | {measurements.is_valid} |
| X bounding length | {measurements.x_length_mm:.6f} mm |
| Y bounding length | {measurements.y_length_mm:.6f} mm |
| Minimum Z | {measurements.z_min_mm:.6f} mm |
| Maximum Z | {measurements.z_max_mm:.6f} mm |
| Core volume | {measurements.core_volume_mm3:.6f} mm³ |
| Ridge volume | {measurements.ridge_volume_mm3:.6f} mm³ |
| Threaded volume | {measurements.threaded_volume_mm3:.6f} mm³ |
| Fusion overlap volume | {measurements.radial_overlap_volume_mm3:.6f} mm³ |
| Major-cylinder upper-bound volume | {measurements.major_cylinder_volume_mm3:.6f} mm³ |
| Face count | {measurements.face_count} |
| Edge count | {measurements.edge_count} |

## Verification interpretation

The threaded volume must:

- Exceed the minor-core volume
- Remain below the unthreaded major-cylinder volume
- Contain a positive fusion-overlap volume
- Form exactly one valid solid
- Remain within the nominal major diameter
- Span the complete configured axial length

## Current limitations

The threaded shank does not yet include:

- Hexagonal bolt head
- Underhead fillet
- Thread runout
- Tip chamfer
- External tolerance class 6g
- Rounded thread root
- Manufacturing variation

## Next gate

The threaded shank must be fused with the verified hexagonal bolt head and
subsequently pass STEP export and re-import verification.
"""

    report_path = (
        project_root
        / "docs"
        / "verification"
        / "TRM-GEO-000001_THREADED_SHANK_CHECK.md"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    print("Additive threaded shank: GENERATED")
    print(f"Valid solid: {measurements.is_valid}")
    print(f"Solid count: {measurements.solid_count}")
    print(
        "Major bounding size: "
        f"{measurements.x_length_mm:.6f} x "
        f"{measurements.y_length_mm:.6f} mm"
    )
    print(
        "Z range: "
        f"{measurements.z_min_mm:.6f} to "
        f"{measurements.z_max_mm:.6f} mm"
    )
    print(
        "Core volume: "
        f"{measurements.core_volume_mm3:.6f} mm^3"
    )
    print(
        "Ridge volume: "
        f"{measurements.ridge_volume_mm3:.6f} mm^3"
    )
    print(
        "Threaded volume: "
        f"{measurements.threaded_volume_mm3:.6f} mm^3"
    )
    print(
        "Fusion overlap: "
        f"{measurements.radial_overlap_volume_mm3:.6f} mm^3"
    )
    print(f"Faces: {measurements.face_count}")
    print(f"Edges: {measurements.edge_count}")
    print(f"STEP file: {step_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
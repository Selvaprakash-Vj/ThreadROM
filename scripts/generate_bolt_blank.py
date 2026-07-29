"""Generate and verify the TRM-GEO-000001 bolt control blank."""

from pathlib import Path

from threadrom.geometry.bolt_blank import (
    build_bolt_blank,
    load_bolt_blank_definition,
    measure_bolt_blank,
)


def main() -> None:
    """Generate the controlled STEP geometry and verification report."""

    project_root = Path(__file__).resolve().parents[1]

    definition = load_bolt_blank_definition(
        project_root / "config" / "baseline_geometry.toml"
    )

    model = build_bolt_blank(definition)
    measurements = measure_bolt_blank(model)

    output_directory = (
        project_root
        / "simulations"
        / "staging"
        / definition.geometry_id
        / "geometry"
    )

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    step_path = output_directory / "bolt_control_blank.step"

    model.export(
        str(step_path),
        unit="MM",
        outputUnit="MM",
    )

    report = f"""# TRM-GEO-000001 Bolt Control Blank Check

## Status

Development geometry generated and dimensionally checked.

## Configuration

| Quantity | Value |
|---|---:|
| Nominal body diameter | {definition.nominal_diameter_mm:.6f} mm |
| Underhead length | {definition.underhead_length_mm:.6f} mm |
| Head across flats | {definition.head_across_flats_mm:.6f} mm |
| Head across corners | {definition.head_across_corners_mm:.6f} mm |
| Head height | {definition.head_height_mm:.6f} mm |

## CAD measurements

| Quantity | Value |
|---|---:|
| Solid count | {measurements.solid_count} |
| Valid solid | {measurements.is_valid} |
| X bounding length | {measurements.x_length_mm:.6f} mm |
| Y bounding length | {measurements.y_length_mm:.6f} mm |
| Minimum Z | {measurements.z_min_mm:.6f} mm |
| Maximum Z | {measurements.z_max_mm:.6f} mm |
| CAD volume | {measurements.volume_mm3:.6f} mm³ |
| Analytical volume | {definition.analytical_volume_mm3:.6f} mm³ |

## Coordinate interpretation

- Bolt bearing face: Z = 0
- Bolt body extends in positive Z
- Bolt head extends in negative Z
- Bolt axis coincides with the global Z-axis

## Scope

This geometry is an unthreaded control blank.

It does not yet contain:

- External helical thread
- Underhead fillet
- Head chamfer
- Thread runout
- Tip chamfer
- Manufacturing tolerances

The blank must pass dimensional verification before thread construction begins.
"""

    report_path = (
        project_root
        / "docs"
        / "verification"
        / "TRM-GEO-000001_BOLT_BLANK_CHECK.md"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    print("TRM-GEO-000001 bolt blank: GENERATED")
    print(f"Valid solid: {measurements.is_valid}")
    print(f"Solid count: {measurements.solid_count}")
    print(
        "CAD volume: "
        f"{measurements.volume_mm3:.6f} mm^3"
    )
    print(
        "Analytical volume: "
        f"{definition.analytical_volume_mm3:.6f} mm^3"
    )
    print(
        "Z range: "
        f"{measurements.z_min_mm:.6f} to "
        f"{measurements.z_max_mm:.6f} mm"
    )
    print(f"STEP file: {step_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
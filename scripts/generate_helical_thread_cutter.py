"""Generate and verify the external helical thread cutter."""

from pathlib import Path

import cadquery as cq

from threadrom.geometry.helical_thread_cutter import (
    build_helical_thread_cutter,
    load_helical_thread_cutter_definition,
    measure_helical_thread_cutter,
)


def main() -> None:
    """Generate the helical cutter and its verification report."""

    project_root = Path(__file__).resolve().parents[1]

    definition = load_helical_thread_cutter_definition(
        project_root / "config" / "external_thread_geometry.toml",
        project_root / "config" / "baseline_fastener.toml",
    )

    cutter = build_helical_thread_cutter(definition)
    measurements = measure_helical_thread_cutter(cutter)

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

    step_path = output_directory / "external_thread_cutter.step"

    cq.exporters.export(
        cutter,
        str(step_path),
    )

    report = f"""# TRM-GEO-000001 Helical Thread Cutter Check

## Status

Development cutter generated and geometrically checked.

## Configuration

| Quantity | Value |
|---|---:|
| Nominal diameter | {definition.nominal_diameter_mm:.6f} mm |
| Major radius | {definition.major_radius_mm:.9f} mm |
| Minor radius | {definition.minor_radius_mm:.9f} mm |
| Pitch | {definition.pitch_mm:.6f} mm |
| Threaded length | {definition.thread_length_mm:.6f} mm |
| Sweep height | {definition.sweep_height_mm:.6f} mm |
| Helical turns | {definition.turn_count:.6f} |
| Start Z | {definition.start_z_mm:.6f} mm |
| Handedness | {definition.handedness} |
| Radial clearance | {definition.radial_clearance_mm:.6f} mm |

## CAD measurements

| Quantity | Value |
|---|---:|
| Solid count | {measurements.solid_count} |
| Valid solid | {measurements.is_valid} |
| Cutter volume | {measurements.volume_mm3:.6f} mm³ |
| X bounding length | {measurements.x_length_mm:.6f} mm |
| Y bounding length | {measurements.y_length_mm:.6f} mm |
| Minimum Z | {measurements.z_min_mm:.6f} mm |
| Maximum Z | {measurements.z_max_mm:.6f} mm |

## Interpretation

The cutter extends one pitch below and above the final 30 mm threaded region.

This deliberate overshoot allows the future threaded shank to be trimmed
cleanly at Z = 0 mm and Z = 30 mm.

The cutter is not itself a released engineering geometry. It is a controlled
construction artefact used to produce TRM-GEO-000001.

## Next gate

The cutter must be subtracted from an isolated cylindrical shank.

The resulting threaded shank must then pass:

- Single-solid validation
- Major-diameter verification
- Minor-diameter verification
- Axial-length verification
- STEP export and re-import verification
"""

    report_path = (
        project_root
        / "docs"
        / "verification"
        / "TRM-GEO-000001_HELICAL_CUTTER_CHECK.md"
    )

    report_path.write_text(
        report,
        encoding="utf-8",
    )

    print("Helical thread cutter: GENERATED")
    print(f"Valid solid: {measurements.is_valid}")
    print(f"Solid count: {measurements.solid_count}")
    print(f"Handedness: {definition.handedness}")
    print(f"Turns: {definition.turn_count:.6f}")
    print(
        "Z range: "
        f"{measurements.z_min_mm:.6f} to "
        f"{measurements.z_max_mm:.6f} mm"
    )
    print(
        "Cutter volume: "
        f"{measurements.volume_mm3:.6f} mm^3"
    )
    print(f"STEP file: {step_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()
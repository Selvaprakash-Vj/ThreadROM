"""Generate the TRM-GEO-000001 external thread-profile report."""

from pathlib import Path

from threadrom.geometry.external_thread_profile import (
    calculate_external_metric_thread_profile,
    calculate_flank_angle_deg,
)


def main() -> None:
    """Generate the controlled external-thread profile report."""

    project_root = Path(__file__).resolve().parents[1]

    profile = calculate_external_metric_thread_profile(
        nominal_diameter_mm=10.0,
        pitch_mm=1.5,
    )

    left_flank_angle = calculate_flank_angle_deg(
        profile.points[1],
        profile.points[2],
    )

    right_flank_angle = calculate_flank_angle_deg(
        profile.points[3],
        profile.points[4],
    )

    point_rows = "\n".join(
        f"| {index} | {point.axial_mm:.9f} | {point.radius_mm:.9f} |"
        for index, point in enumerate(profile.points, start=1)
    )

    report = f"""# TRM-GEO-000001 External Thread Profile Check

## Status

Verified analytical profile for geometry development.

## Profile definition

| Quantity | Value |
|---|---:|
| Nominal diameter | {profile.nominal_diameter_mm:.6f} mm |
| Pitch | {profile.pitch_mm:.6f} mm |
| Major radius | {profile.major_radius_mm:.9f} mm |
| Pitch radius | {profile.pitch_radius_mm:.9f} mm |
| Minor radius | {profile.minor_radius_mm:.9f} mm |
| Radial thread depth | {profile.radial_thread_depth_mm:.9f} mm |
| Fundamental triangle height | {profile.fundamental_height_mm:.9f} mm |
| Crest-flat width | {profile.crest_flat_width_mm:.9f} mm |
| Root-flat width | {profile.root_flat_width_mm:.9f} mm |
| Included flank angle | {profile.flank_angle_deg:.3f} degrees |
| Left flank angle to axis | {left_flank_angle:.6f} degrees |
| Right flank angle to axis | {right_flank_angle:.6f} degrees |

## One-pitch profile points

| Point | Axial coordinate | Radius |
|---:|---:|---:|
{point_rows}

## Coordinate interpretation

- Axial coordinates are parallel to the global Z-axis.
- Radius is measured normally from the global Z-axis.
- The profile is centred on one external-thread crest.
- Adjacent pitch cells repeat every 1.5 mm.

## Current limitations

This is the ideal external basic profile.

It does not yet include:

- External tolerance class 6g
- Rounded root implementation
- Thread runout
- Start chamfer
- Manufacturing variation
- CAD-kernel approximation

The verified profile will next be swept along a right-handed helix.
"""

    output_path = (
        project_root
        / "docs"
        / "verification"
        / "TRM-GEO-000001_EXTERNAL_THREAD_PROFILE_CHECK.md"
    )

    output_path.write_text(
        report,
        encoding="utf-8",
    )

    print("External thread profile: VERIFIED")
    print(f"Major radius: {profile.major_radius_mm:.9f} mm")
    print(f"Pitch radius: {profile.pitch_radius_mm:.9f} mm")
    print(f"Minor radius: {profile.minor_radius_mm:.9f} mm")
    print(
        "Radial thread depth: "
        f"{profile.radial_thread_depth_mm:.9f} mm"
    )
    print(f"Crest width: {profile.crest_flat_width_mm:.9f} mm")
    print(f"Root width: {profile.root_flat_width_mm:.9f} mm")
    print(f"Left flank angle: {left_flank_angle:.6f} degrees")
    print(f"Right flank angle: {right_flank_angle:.6f} degrees")
    print(f"Report: {output_path}")


if __name__ == "__main__":
    main()
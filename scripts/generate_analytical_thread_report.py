"""Generate the governed analytical thread-mechanics artifacts."""

from __future__ import annotations

from pathlib import Path

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_thread_result import (
    evaluate_analytical_thread,
    render_analytical_thread_report,
)


def main() -> None:
    """Generate JSON and Markdown thread-mechanics results."""

    project_root = Path(__file__).resolve().parents[1]

    config_path = project_root / "config" / "analytical_m10_5kn.toml"

    output_directory = project_root / "docs" / "verification"

    json_path = output_directory / "TRM-ANL-000001_THREAD_MECHANICS.json"

    report_path = output_directory / "TRM-ANL-000001_THREAD_MECHANICS.md"

    joint = load_analytical_joint_input(config_path)
    result = evaluate_analytical_thread(joint)

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path.write_text(
        result.to_json(),
        encoding="utf-8",
        newline="\n",
    )

    report_path.write_text(
        render_analytical_thread_report(result),
        encoding="utf-8",
        newline="\n",
    )

    mechanics = result.mechanics

    print(f"Joint: {result.joint_id}")
    print(f"Pitch diameter: {mechanics.basic_pitch_diameter_mm:.9f} mm")
    print(f"Tensile area: {mechanics.tensile_stress_area_mm2:.9f} mm2")
    print(f"Root area: {mechanics.external_root_area_mm2:.9f} mm2")
    print(f"Engaged pitches: {mechanics.engaged_pitch_count:.9f}")
    print(f"Helix angle: {mechanics.helix_angle_at_pitch_diameter_deg:.9f} deg")
    print(f"JSON: {json_path.relative_to(project_root)}")
    print(f"Report: {report_path.relative_to(project_root)}")


if __name__ == "__main__":
    main()

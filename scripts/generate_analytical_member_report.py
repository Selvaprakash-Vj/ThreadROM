"""Generate governed analytical member-mechanics artifacts."""

from __future__ import annotations

from pathlib import Path

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_member_result import (
    evaluate_analytical_member,
    render_analytical_member_report,
)


def main() -> None:
    """Generate JSON and Markdown member-mechanics results."""

    project_root = Path(__file__).resolve().parents[1]

    config_path = project_root / "config" / "analytical_m10_5kn.toml"

    output_directory = project_root / "docs" / "verification"

    json_path = output_directory / "TRM-ANL-000001_MEMBER_MECHANICS.json"

    report_path = output_directory / "TRM-ANL-000001_MEMBER_MECHANICS.md"

    joint = load_analytical_joint_input(config_path)
    result = evaluate_analytical_member(joint)

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
        render_analytical_member_report(result),
        encoding="utf-8",
        newline="\n",
    )

    mechanics = result.mechanics

    print(f"Joint: {result.joint_id}")
    print(f"Layers: {len(mechanics.layers)}")
    print(f"Member thickness: {mechanics.total_thickness_mm:.9f} mm")
    print(f"Member stiffness: {mechanics.axial_stiffness_n_per_mm:.9f} N/mm")
    print(f"Member shortening: {mechanics.total_shortening_mm:.12e} mm")
    print(f"Maximum compression stress: {mechanics.maximum_compressive_stress_mpa:.9f} MPa")
    print(f"Validation: {'PASS' if result.validation.passed else 'FAIL'}")
    print(f"JSON: {json_path.relative_to(project_root)}")
    print(f"Report: {report_path.relative_to(project_root)}")


if __name__ == "__main__":
    main()

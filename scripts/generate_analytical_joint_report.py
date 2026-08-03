"""Generate governed analytical joint-behaviour artifacts."""

from __future__ import annotations

from pathlib import Path

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_joint_result import (
    evaluate_analytical_joint,
    render_analytical_joint_report,
)


def main() -> None:
    """Generate JSON and Markdown complete-joint results."""

    project_root = Path(__file__).resolve().parents[1]

    config_path = project_root / "config" / "analytical_m10_5kn.toml"

    output_directory = project_root / "docs" / "verification"

    json_path = output_directory / "TRM-ANL-000001_JOINT_BEHAVIOUR.json"

    report_path = output_directory / "TRM-ANL-000001_JOINT_BEHAVIOUR.md"

    joint = load_analytical_joint_input(config_path)

    result = evaluate_analytical_joint(joint)

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
        render_analytical_joint_report(result),
        encoding="utf-8",
        newline="\n",
    )

    envelope = result.envelope
    strength = result.strength

    print(f"Joint: {result.joint_id}")
    print(f"Envelope points: {len(envelope.points)}")
    print(f"Highest bolt force: {envelope.highest_bolt_force_n:.9f} N")
    print(f"Minimum separation margin: {envelope.minimum_separation_margin_n:.9f} N")
    print(f"Maximum opening: {envelope.maximum_joint_opening_mm:.12e} mm")
    print(f"Highest nominal stress: {strength.highest_nominal_tensile_stress_mpa:.9f} MPa")
    print(f"Validation: {'PASS' if result.validation.passed else 'FAIL'}")
    print(f"JSON: {json_path.relative_to(project_root)}")
    print(f"Report: {report_path.relative_to(project_root)}")


if __name__ == "__main__":
    main()

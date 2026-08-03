"""Generate the governed analytical benchmark input summary."""

from __future__ import annotations

from pathlib import Path

from threadrom.engineering.analytical_input_summary import (
    render_analytical_input_summary,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)


def main() -> None:
    """Generate the first governed analytical input summary."""

    project_root = Path(__file__).resolve().parents[1]

    config_path = project_root / "config" / "analytical_m10_5kn.toml"

    output_path = project_root / "docs" / "verification" / "TRM-ANL-000001_INPUT_SUMMARY.md"

    joint = load_analytical_joint_input(config_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        render_analytical_input_summary(joint),
        encoding="utf-8",
        newline="\n",
    )

    print(f"Joint:  {joint.joint_id}")
    print(f"Config: {config_path.relative_to(project_root)}")
    print(f"Report: {output_path.relative_to(project_root)}")
    print(f"Grip:   {joint.grip_length_mm:.6f} mm")
    print(f"Preload: {joint.loading.preload_n:.6f} N")


if __name__ == "__main__":
    main()

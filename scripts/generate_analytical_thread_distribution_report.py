"""Generate governed analytical thread-load distribution artifacts."""

from __future__ import annotations

from pathlib import Path

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_thread_distribution_result import (
    evaluate_analytical_thread_distribution,
    render_analytical_thread_distribution_report,
)


def main() -> None:
    """Generate JSON and Markdown distribution evidence."""

    project_root = Path(__file__).resolve().parents[1]

    config_path = project_root / "config" / "analytical_m10_5kn.toml"

    output_directory = project_root / "docs" / "verification"

    json_path = output_directory / "TRM-ANL-000001_THREAD_LOAD_DISTRIBUTION.json"

    report_path = output_directory / "TRM-ANL-000001_THREAD_LOAD_DISTRIBUTION.md"

    joint = load_analytical_joint_input(config_path)

    result = evaluate_analytical_thread_distribution(joint)

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
        render_analytical_thread_distribution_report(result),
        encoding="utf-8",
        newline="\n",
    )

    distribution = result.distribution

    print(f"Joint: {result.joint_id}")
    print(f"Transferred load: {distribution.total_transferred_load_n:.9f} N")
    print(f"Active turns: {distribution.active_turn_count}")
    print(f"First-turn load: {distribution.first_turn_load_n:.9f} N")
    print(f"First-turn share: {100.0 * distribution.first_turn_load_share:.6f}%")
    print(f"Maximum-loaded turn: {distribution.maximum_loaded_turn_number}")
    print(f"Load-conservation error: {distribution.load_conservation_error_n:.12e} N")
    print(f"Validation: {'PASS' if result.validation.passed else 'FAIL'}")
    print(f"JSON: {json_path.relative_to(project_root)}")
    print(f"Report: {report_path.relative_to(project_root)}")


if __name__ == "__main__":
    main()

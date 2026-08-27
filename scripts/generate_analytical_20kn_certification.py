"""Generate the governed 20 kN analytical certification package."""

from __future__ import annotations

from pathlib import Path

from threadrom.engineering.analytical_bolt_result import (
    evaluate_analytical_bolt,
    render_analytical_bolt_report,
)
from threadrom.engineering.analytical_input_summary import (
    render_analytical_input_summary,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_joint_result import (
    evaluate_analytical_joint,
    render_analytical_joint_report,
)
from threadrom.engineering.analytical_member_result import (
    evaluate_analytical_member,
    render_analytical_member_report,
)
from threadrom.engineering.analytical_thread_distribution_result import (
    evaluate_analytical_thread_distribution,
    render_analytical_thread_distribution_report,
)
from threadrom.engineering.analytical_thread_result import (
    evaluate_analytical_thread,
    render_analytical_thread_report,
)


def _write_result(
    output_directory: Path,
    stem: str,
    result: object,
    markdown: str,
) -> tuple[Path, Path]:
    """Write deterministic JSON and Markdown analytical artifacts."""

    json_path = output_directory / f"{stem}.json"
    report_path = output_directory / f"{stem}.md"

    to_json = result.to_json

    json_path.write_text(
        to_json(),
        encoding="utf-8",
        newline="\n",
    )

    report_path.write_text(
        markdown,
        encoding="utf-8",
        newline="\n",
    )

    return json_path, report_path


def main() -> None:
    """Generate all governed TRM-ANL-000002 certification artifacts."""

    root = Path(__file__).resolve().parents[1]

    config_path = root / "config" / "analytical_m10_20kn.toml"
    output_directory = root / "docs" / "verification"

    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    joint = load_analytical_joint_input(config_path)

    input_summary_path = (
        output_directory / "TRM-ANL-000002_INPUT_SUMMARY.md"
    )

    input_summary_path.write_text(
        render_analytical_input_summary(joint),
        encoding="utf-8",
        newline="\n",
    )

    thread_result = evaluate_analytical_thread(joint)
    bolt_result = evaluate_analytical_bolt(joint)
    member_result = evaluate_analytical_member(joint)
    joint_result = evaluate_analytical_joint(joint)
    distribution_result = evaluate_analytical_thread_distribution(joint)

    artifacts = (
        _write_result(
            output_directory,
            "TRM-ANL-000002_THREAD_MECHANICS",
            thread_result,
            render_analytical_thread_report(thread_result),
        ),
        _write_result(
            output_directory,
            "TRM-ANL-000002_BOLT_MECHANICS",
            bolt_result,
            render_analytical_bolt_report(bolt_result),
        ),
        _write_result(
            output_directory,
            "TRM-ANL-000002_MEMBER_MECHANICS",
            member_result,
            render_analytical_member_report(member_result),
        ),
        _write_result(
            output_directory,
            "TRM-ANL-000002_JOINT_BEHAVIOUR",
            joint_result,
            render_analytical_joint_report(joint_result),
        ),
        _write_result(
            output_directory,
            "TRM-ANL-000002_THREAD_DISTRIBUTION",
            distribution_result,
            render_analytical_thread_distribution_report(
                distribution_result
            ),
        ),
    )

    print("20 kN ANALYTICAL CERTIFICATION PACKAGE: GENERATED")
    print(f"Joint      : {joint.joint_id}")
    print(f"Preload    : {joint.loading.preload_n:.6f} N")
    print(f"Input      : {input_summary_path.relative_to(root)}")

    for json_path, report_path in artifacts:
        print(f"JSON       : {json_path.relative_to(root)}")
        print(f"Report     : {report_path.relative_to(root)}")


if __name__ == "__main__":
    main()

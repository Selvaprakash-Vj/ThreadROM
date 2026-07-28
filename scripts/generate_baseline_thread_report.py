"""Generate the baseline analytical thread-reference report."""

from pathlib import Path

from threadrom.engineering.baseline_reference import (
    load_baseline_thread_reference,
    render_baseline_thread_report,
)


def main() -> None:
    """Generate the controlled Markdown verification record."""

    project_root = Path(__file__).resolve().parents[1]

    config_path = (
        project_root
        / "config"
        / "baseline_fastener.toml"
    )

    output_path = (
        project_root
        / "docs"
        / "verification"
        / "TRM-GEO-000001_BASIC_THREAD_CHECK.md"
    )

    reference = load_baseline_thread_reference(config_path)
    report = render_baseline_thread_report(reference)

    output_path.write_text(
        report,
        encoding="utf-8",
    )

    print("Analytical thread reference: GENERATED")
    print(f"Thread: {reference.designation}")
    print(
        "Tensile stress area: "
        f"{reference.dimensions.tensile_stress_area_mm2:.6f} mm^2"
    )
    print(f"Report: {output_path}")


if __name__ == "__main__":
    main()
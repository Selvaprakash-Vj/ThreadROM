"""Generate the baseline bolt axial-capacity report."""

from pathlib import Path

from threadrom.engineering.baseline_capacity import (
    evaluate_baseline_bolt_capacity,
    render_capacity_report,
)


def main() -> None:
    """Generate and print the baseline capacity-check summary."""

    project_root = Path(__file__).resolve().parents[1]

    check = evaluate_baseline_bolt_capacity(
        project_root / "config" / "baseline_fastener.toml",
        project_root / "config" / "baseline_assembly.toml",
    )

    report = render_capacity_report(check)

    output_path = (
        project_root
        / "docs"
        / "verification"
        / "TRM-SIM-000001_PRELOAD_CAPACITY_CHECK.md"
    )

    output_path.write_text(
        report,
        encoding="utf-8",
    )

    print("Baseline axial-capacity check: COMPLETED")
    print(
        "Preload stress: "
        f"{check.preload_stress_pa / 1.0e6:.3f} MPa"
    )
    print(
        "Conservative combined stress: "
        f"{check.conservative_combined_stress_pa / 1.0e6:.3f} MPa"
    )
    print(
        "Preload proof utilisation: "
        f"{check.preload_proof_utilisation:.4f}"
    )
    print(
        "Combined proof utilisation: "
        f"{check.combined_proof_utilisation:.4f}"
    )
    print(
        "Conservative combined check: "
        f"{'PASS' if check.passes_conservative_combined_check else 'FAIL'}"
    )
    print(f"Report: {output_path}")


if __name__ == "__main__":
    main()
"""Generate the baseline joint-stiffness report."""

from pathlib import Path

from threadrom.engineering.baseline_joint_stiffness import (
    evaluate_baseline_joint_stiffness,
    render_joint_stiffness_report,
)


def main() -> None:
    """Generate the controlled joint-stiffness verification record."""

    project_root = Path(__file__).resolve().parents[1]

    check = evaluate_baseline_joint_stiffness(
        project_root / "config" / "baseline_fastener.toml",
        project_root / "config" / "baseline_assembly.toml",
    )

    report = render_joint_stiffness_report(check)

    output_path = (
        project_root
        / "docs"
        / "verification"
        / "TRM-SIM-000001_JOINT_STIFFNESS_CHECK.md"
    )

    output_path.write_text(
        report,
        encoding="utf-8",
    )

    print("Baseline joint-stiffness check: COMPLETED")
    print(
        "Bolt stiffness: "
        f"{check.bolt_stiffness_n_per_m / 1.0e6:.3f} kN/mm"
    )
    print(
        "Member stiffness: "
        f"{check.member_stiffness_n_per_m / 1.0e6:.3f} kN/mm"
    )
    print(f"Joint constant: {check.joint_constant:.6f}")
    print(
        "Bolt-load increment: "
        f"{check.bolt_load_increment_n:.1f} N"
    )
    print(
        "Remaining clamp load: "
        f"{check.remaining_clamp_load_n:.1f} N"
    )
    print(
        "Estimated separation load: "
        f"{check.separation_load_n:.1f} N"
    )
    print(
        "Proof check: "
        f"{'PASS' if check.passes_proof_check else 'FAIL'}"
    )
    print(
        "Separation check: "
        f"{'PASS' if check.passes_separation_check else 'FAIL'}"
    )
    print(f"Report: {output_path}")


if __name__ == "__main__":
    main()
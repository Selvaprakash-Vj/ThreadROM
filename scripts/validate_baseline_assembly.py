"""Validate the proposed ThreadROM baseline assembly."""

from pathlib import Path

from threadrom.engineering.baseline_assembly import (
    load_baseline_assembly,
)


def main() -> None:
    """Load the baseline assembly and print its consistency summary."""

    project_root = Path(__file__).resolve().parents[1]

    assembly = load_baseline_assembly(
        project_root / "config" / "baseline_assembly.toml"
    )

    print("Baseline assembly validation: PASSED")
    print(f"Assembly identity: {assembly.assembly_id}")
    print(f"Bolt length: {assembly.bolt_length_mm:.3f} mm")
    print(f"Grip length: {assembly.total_grip_length_mm:.3f} mm")
    print(f"Nut thickness: {assembly.nut_thickness_mm:.3f} mm")
    print(f"Thread protrusion: {assembly.protrusion_length_mm:.3f} mm")
    print(f"Engaged threads: {assembly.engaged_thread_count:.3f}")
    print(f"Target preload: {assembly.target_preload_n:.1f} N")
    print(f"External axial load: {assembly.external_axial_load_n:.1f} N")


if __name__ == "__main__":
    main()
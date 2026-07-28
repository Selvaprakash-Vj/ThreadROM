"""Run the ThreadROM CalculiX smoke test."""

from threadrom.solver.calculix import run_smoke_test


def main() -> None:
    """Execute the solver smoke test and print its verification summary."""

    result = run_smoke_test()

    print("CalculiX smoke test: PASSED")
    print(f"Exit code: {result.exit_code}")
    print(
        "Mean loaded displacement: "
        f"{result.mean_loaded_displacement_m:.6e} m"
    )
    print(
        "Mean axial stress: "
        f"{result.mean_axial_stress_pa / 1.0e6:.6f} MPa"
    )
    print(
        "Expected axial stress: "
        f"{result.expected_axial_stress_pa / 1.0e6:.6f} MPa"
    )
    print(
        "Relative stress error: "
        f"{result.relative_stress_error:.6e}"
    )


if __name__ == "__main__":
    main()
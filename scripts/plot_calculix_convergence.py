"""Plot CalculiX nonlinear convergence history."""

from __future__ import annotations

import argparse
from pathlib import Path

from threadrom.postprocessing.calculix_convergence_plot import (
    load_iteration_points,
    write_convergence_figure,
)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Generate a convergence figure from a ThreadROM nonlinear-progress JSON file.")
    )

    parser.add_argument(
        "--input",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    return parser.parse_args()


def main() -> None:
    """Generate the requested convergence figure."""

    arguments = _parse_arguments()

    points = load_iteration_points(arguments.input)

    output_path = write_convergence_figure(
        arguments.input,
        arguments.output,
    )

    latest = points[-1]

    print("CALCULIX CONVERGENCE FIGURE: GENERATED")
    print(f"Iteration records: {len(points)}")
    print(
        "Latest state: "
        f"step {latest.step}, "
        f"increment {latest.increment}, "
        f"attempt {latest.attempt}, "
        f"iteration {latest.iteration}"
    )
    print(f"Latest residual force: {latest.residual_force_percent:.6g}%")
    print(f"Latest displacement correction: {latest.correction_displacement_percent:.6g}%")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()

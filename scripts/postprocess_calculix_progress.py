"""Export CalculiX nonlinear progress as JSON."""

from __future__ import annotations

import argparse
from pathlib import Path

from threadrom.postprocessing.calculix_nonlinear_progress import (
    write_nonlinear_progress_json,
)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Parse CalculiX STA and CVG files into a structured JSON artifact.")
    )

    parser.add_argument(
        "--sta",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--cvg",
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
    """Export the requested nonlinear progress."""

    arguments = _parse_arguments()

    payload = write_nonlinear_progress_json(
        arguments.sta,
        arguments.cvg,
        arguments.output,
    )

    print("CALCULIX NONLINEAR PROGRESS: EXPORTED")
    print(f"Accepted increments: {payload['accepted_increment_count']}")
    print(f"Iteration records: {payload['iteration_record_count']}")
    print(f"Latest accepted increment: {payload['latest_accepted_increment']}")
    print(f"Latest iteration: {payload['latest_iteration']}")
    print(f"Output: {arguments.output}")


if __name__ == "__main__":
    main()

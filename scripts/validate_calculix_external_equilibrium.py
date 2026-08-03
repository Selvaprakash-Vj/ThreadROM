"""Validate preload-only external equilibrium."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from threadrom.postprocessing.calculix_external_equilibrium import (
    write_external_equilibrium_json,
)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate near-zero external support reaction during a preload-only CalculiX analysis."
        )
    )

    parser.add_argument(
        "--progress",
        required=True,
    )

    parser.add_argument(
        "--total-force",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    parser.add_argument(
        "--support-set-name",
        required=True,
    )

    parser.add_argument(
        "--force-absolute-tolerance-n",
        type=float,
        default=1.0e-3,
    )

    parser.add_argument(
        "--time-absolute-tolerance",
        type=float,
        default=1.0e-9,
    )

    return parser.parse_args()


def main() -> None:
    arguments = _parse_arguments()

    payload = write_external_equilibrium_json(
        Path(arguments.progress),
        Path(arguments.total_force),
        Path(arguments.output),
        support_set_name=(arguments.support_set_name),
        force_absolute_tolerance_n=(arguments.force_absolute_tolerance_n),
        time_absolute_tolerance=(arguments.time_absolute_tolerance),
    )

    print(f"CALCULIX EXTERNAL EQUILIBRIUM: {str(payload['overall_status']).upper()}")

    print(f"Accepted increments: {payload['accepted_increment_count']}")

    print(f"Support-force records: {payload['support_force_record_count']}")

    print(f"Passed: {payload['passed_count']}")

    print(f"Failed: {payload['failed_count']}")

    print(f"Pending: {payload['pending_count']}")

    print(f"Output: {Path(arguments.output).resolve()}")


if __name__ == "__main__":
    main()

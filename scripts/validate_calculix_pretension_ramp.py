"""Validate CalculiX pretension results against the load ramp."""

from __future__ import annotations

import argparse
from pathlib import Path

from threadrom.postprocessing.calculix_pretension_validation import (
    write_pretension_validation_json,
)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Validate accepted CalculiX increments against the commanded pretension ramp.")
    )

    parser.add_argument(
        "--progress",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--pretension",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--target-preload-n",
        type=float,
        required=True,
    )

    parser.add_argument(
        "--force-relative-tolerance",
        type=float,
        default=1.0e-6,
    )

    parser.add_argument(
        "--force-absolute-tolerance-n",
        type=float,
        default=1.0e-6,
    )

    parser.add_argument(
        "--time-absolute-tolerance",
        type=float,
        default=1.0e-9,
    )

    return parser.parse_args()


def main() -> None:
    """Run governed pretension-ramp validation."""

    arguments = _parse_arguments()

    payload = write_pretension_validation_json(
        arguments.progress,
        arguments.pretension,
        arguments.output,
        target_preload_n=(arguments.target_preload_n),
        force_relative_tolerance=(arguments.force_relative_tolerance),
        force_absolute_tolerance_n=(arguments.force_absolute_tolerance_n),
        time_absolute_tolerance=(arguments.time_absolute_tolerance),
    )

    print("CALCULIX PRETENSION RAMP: VALIDATED")
    print(f"Overall status: {payload['overall_status']}")
    print(f"Accepted increments: {payload['accepted_increment_count']}")
    print(f"Passed: {payload['passed_count']}")
    print(f"Failed: {payload['failed_count']}")
    print(f"Pending: {payload['pending_count']}")
    print(f"Orphan records: {payload['orphan_record_count']}")
    print(f"Output: {arguments.output}")


if __name__ == "__main__":
    main()

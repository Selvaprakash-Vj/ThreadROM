"""Export CalculiX pretension-reference DAT results."""

from __future__ import annotations

import argparse
from pathlib import Path

from threadrom.postprocessing.calculix_pretension_dat import (
    write_pretension_reference_json,
)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Parse pretension-reference force and displacement results from a CalculiX DAT file."
        )
    )

    parser.add_argument(
        "--dat",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--set-name",
        default="BOLT_PRETENSION_REFERENCE",
    )

    parser.add_argument(
        "--control-component",
        type=int,
        choices=(1, 2, 3),
        default=1,
    )

    return parser.parse_args()


def main() -> None:
    """Export pretension-reference DAT results."""

    arguments = _parse_arguments()

    payload = write_pretension_reference_json(
        arguments.dat,
        arguments.output,
        set_name=arguments.set_name,
        control_component=(arguments.control_component),
    )

    print("CALCULIX PRETENSION DAT: EXPORTED")
    print(f"Records: {payload['record_count']}")
    print(f"Latest record: {payload['latest_record']}")
    print(f"Output: {arguments.output}")


if __name__ == "__main__":
    main()

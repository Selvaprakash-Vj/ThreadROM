"""Extract CalculiX TOTALS=ONLY force histories."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from threadrom.postprocessing.calculix_total_force_dat import (
    write_total_force_json,
)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Extract complete TOTALS=ONLY force records from a CalculiX DAT file.")
    )

    parser.add_argument(
        "--dat",
        required=True,
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    parser.add_argument(
        "--set-name",
        action="append",
        dest="set_names",
    )

    return parser.parse_args()


def main() -> None:
    arguments = _parse_arguments()

    records = write_total_force_json(
        Path(arguments.dat),
        Path(arguments.output),
        set_names=arguments.set_names,
    )

    print("CALCULIX TOTAL-FORCE DAT: PARSED")
    print(f"Records: {len(records)}")
    print(f"Output: {Path(arguments.output).resolve()}")

    if not records:
        print("Latest record: none")
        return

    latest = records[-1]

    print(
        "Latest record: "
        f"set={latest.set_name}, "
        f"step={latest.step}, "
        f"increment={latest.increment}, "
        f"time={latest.time:.12g}"
    )

    print(
        "Latest force: "
        f"({latest.force_x_n:.12e}, "
        f"{latest.force_y_n:.12e}, "
        f"{latest.force_z_n:.12e}) N"
    )


if __name__ == "__main__":
    main()

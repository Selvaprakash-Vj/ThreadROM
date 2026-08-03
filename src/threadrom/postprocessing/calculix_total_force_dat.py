"""Parse total-force histories from CalculiX DAT files."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path

_CALCULIX_NUMBER = (
    r"[+\-]?"
    r"(?:\d+(?:\.\d*)?|\.\d+)"
    r"(?:[EeDd][+\-]?\d+)?"
)

_TOTAL_FORCE_HEADER = re.compile(
    (
        r"total\s+force\s*"
        r"\(\s*fx\s*,\s*fy\s*,\s*fz\s*\)"
        r"\s+for\s+set\s+"
        r"(?P<set_name>\S+)"
        r"\s+and\s+time\s+"
        rf"(?P<time>{_CALCULIX_NUMBER})"
    ),
    re.IGNORECASE,
)

_STEP_HEADER = re.compile(
    r"^\s*STEP\s+(?P<step>\d+)\s*$",
    re.IGNORECASE,
)

_INCREMENT_HEADER = re.compile(
    r"^\s*INCREMENT\s+(?P<increment>\d+)\s*$",
    re.IGNORECASE,
)

_VALUE_PATTERN = re.compile(_CALCULIX_NUMBER)


@dataclass(frozen=True)
class CalculixTotalForceRecord:
    """One complete TOTALS=ONLY force result."""

    step: int | None
    increment: int | None
    set_name: str
    time: float
    force_components_n: tuple[
        float,
        float,
        float,
    ]

    @property
    def force_x_n(self) -> float:
        return self.force_components_n[0]

    @property
    def force_y_n(self) -> float:
        return self.force_components_n[1]

    @property
    def force_z_n(self) -> float:
        return self.force_components_n[2]

    @property
    def maximum_absolute_component_n(self) -> float:
        return max(abs(component) for component in self.force_components_n)


def _parse_number(value: str) -> float:
    """Parse an E- or D-formatted CalculiX number."""

    return float(value.replace("D", "E").replace("d", "e"))


def parse_total_force_records(
    text: str,
    *,
    set_names: Iterable[str] | None = None,
) -> tuple[CalculixTotalForceRecord, ...]:
    """Parse every complete total-force block.

    An incomplete final block is ignored so the parser can safely
    read a DAT file while CalculiX is still appending results.
    """

    requested_names = (
        {set_name.strip().casefold() for set_name in set_names if set_name.strip()}
        if set_names is not None
        else None
    )

    lines = text.splitlines()

    current_step: int | None = None
    current_increment: int | None = None

    records: list[CalculixTotalForceRecord] = []

    for line_index, line in enumerate(lines):
        step_match = _STEP_HEADER.match(line)

        if step_match is not None:
            current_step = int(step_match.group("step"))
            continue

        increment_match = _INCREMENT_HEADER.match(line)

        if increment_match is not None:
            current_increment = int(increment_match.group("increment"))
            continue

        header_match = _TOTAL_FORCE_HEADER.search(line)

        if header_match is None:
            continue

        set_name = header_match.group("set_name")

        if requested_names is not None and set_name.casefold() not in requested_names:
            continue

        force_components: (
            tuple[
                float,
                float,
                float,
            ]
            | None
        ) = None

        for value_line in lines[line_index + 1 : line_index + 8]:
            if (
                _TOTAL_FORCE_HEADER.search(value_line)
                or _STEP_HEADER.match(value_line)
                or _INCREMENT_HEADER.match(value_line)
            ):
                break

            values = _VALUE_PATTERN.findall(value_line)

            if len(values) != 3:
                continue

            force_components = (
                _parse_number(values[0]),
                _parse_number(values[1]),
                _parse_number(values[2]),
            )
            break

        if force_components is None:
            continue

        records.append(
            CalculixTotalForceRecord(
                step=current_step,
                increment=current_increment,
                set_name=set_name,
                time=_parse_number(header_match.group("time")),
                force_components_n=force_components,
            )
        )

    return tuple(records)


def write_total_force_json(
    dat_path: Path,
    output_path: Path,
    *,
    set_names: Iterable[str] | None = None,
) -> tuple[CalculixTotalForceRecord, ...]:
    """Parse a DAT file and write normalized JSON."""

    if not dat_path.is_file() or dat_path.stat().st_size <= 0:
        raise FileNotFoundError(f"Valid CalculiX DAT file not found: {dat_path}")

    requested_names = tuple(set_names) if set_names is not None else None

    records = parse_total_force_records(
        dat_path.read_text(
            encoding="utf-8",
            errors="replace",
        ),
        set_names=requested_names,
    )

    payload = {
        "source_dat": str(dat_path.resolve()),
        "requested_set_names": (list(requested_names) if requested_names is not None else None),
        "record_count": len(records),
        "records": [asdict(record) for record in records],
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            payload,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    return records

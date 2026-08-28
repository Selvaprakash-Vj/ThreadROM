"""CalculiX contact-statistics result parsing."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


_HEADER_PATTERN = re.compile(
    r"^\s*statistics for slave set "
    r"(?P<slave>\S+), master set "
    r"(?P<master>\S+) and time\s+"
    r"(?P<time>[+-]?[0-9.]+(?:E[+-]?\d+)?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class CalculixContactStatisticsRecord:
    """One complete CalculiX contact-statistics block."""

    slave_surface: str
    master_surface: str
    time: float
    total_normal_force_components_n: tuple[float, float, float]
    normal_force_n: float
    shear_force_n: float
    area_mm2: float

    def __post_init__(self) -> None:
        values = (
            self.time,
            *self.total_normal_force_components_n,
            self.normal_force_n,
            self.shear_force_n,
            self.area_mm2,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError(
                "Contact-statistics values must be finite."
            )
        if self.time < 0.0:
            raise ValueError("time cannot be negative.")
        if self.area_mm2 < 0.0:
            raise ValueError("area_mm2 cannot be negative.")
        if self.shear_force_n < 0.0:
            raise ValueError("shear_force_n cannot be negative.")


def _next_nonblank_line(
    lines: list[str],
    start: int,
    end: int,
) -> str | None:
    for index in range(start, end):
        value = lines[index].strip()
        if value:
            return value
    return None


def _parse_numbers(
    line: str,
    *,
    expected_minimum: int,
) -> tuple[float, ...] | None:
    try:
        values = tuple(float(token) for token in line.split())
    except ValueError:
        return None

    if len(values) < expected_minimum:
        return None

    return values


def parse_contact_statistics_records(
    text: str,
) -> tuple[CalculixContactStatisticsRecord, ...]:
    """Parse complete CalculiX contact-statistics blocks.

    An incomplete final block is ignored so this parser can safely
    operate while CalculiX is still appending to the DAT file.
    """

    lines = text.splitlines()

    headers: list[tuple[int, re.Match[str]]] = []
    for index, line in enumerate(lines):
        match = _HEADER_PATTERN.match(line)
        if match is not None:
            headers.append((index, match))

    records: list[CalculixContactStatisticsRecord] = []

    for header_index, (start, match) in enumerate(headers):
        end = (
            headers[header_index + 1][0]
            if header_index + 1 < len(headers)
            else len(lines)
        )

        total_values: tuple[float, ...] | None = None
        area_values: tuple[float, ...] | None = None

        for index in range(start + 1, end):
            normalized = " ".join(
                lines[index].strip().lower().split()
            )

            if normalized.startswith(
                "total normal surface force "
                "(fx,fy,fz)"
            ):
                data_line = _next_nonblank_line(
                    lines,
                    index + 1,
                    end,
                )
                if data_line is not None:
                    total_values = _parse_numbers(
                        data_line,
                        expected_minimum=6,
                    )

            if normalized.startswith(
                "area, normal force "
                "(+ = tension) and shear force"
            ):
                data_line = _next_nonblank_line(
                    lines,
                    index + 1,
                    end,
                )
                if data_line is not None:
                    area_values = _parse_numbers(
                        data_line,
                        expected_minimum=3,
                    )

        if total_values is None or area_values is None:
            continue

        records.append(
            CalculixContactStatisticsRecord(
                slave_surface=match.group("slave"),
                master_surface=match.group("master"),
                time=float(match.group("time")),
                total_normal_force_components_n=(
                    total_values[0],
                    total_values[1],
                    total_values[2],
                ),
                area_mm2=area_values[0],
                normal_force_n=area_values[1],
                shear_force_n=area_values[2],
            )
        )

    return tuple(records)

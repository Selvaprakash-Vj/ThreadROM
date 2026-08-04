"""Targeted displacement extraction from CalculiX FRD files."""

from __future__ import annotations

import math
import re
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

_FRD_FLOAT_PATTERN = re.compile(
    r"[+-]?(?:\d+\.\d+|\d+)(?:E[+-]\d{3})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FrdNodalDisplacement:
    """One nodal displacement record from an FRD dataset."""

    node_id: int
    d1_mm: float
    d2_mm: float
    d3_mm: float


@dataclass(frozen=True)
class FrdDisplacementDataset:
    """One accepted-increment displacement dataset."""

    dataset_sequence: int
    step: int
    increment: int
    time: float
    records: tuple[FrdNodalDisplacement, ...]

    def record_by_node_id(
        self,
        node_id: int,
    ) -> FrdNodalDisplacement:
        """Return one requested nodal record."""

        for record in self.records:
            if record.node_id == node_id:
                return record

        raise KeyError(
            f"Node {node_id} is absent from FRD displacement dataset {self.dataset_sequence}."
        )


def read_targeted_frd_displacement_datasets(
    frd_path: Path,
    target_node_ids: Collection[int],
) -> tuple[FrdDisplacementDataset, ...]:
    """Stream displacement datasets for selected nodes only."""

    requested_node_ids = frozenset(target_node_ids)

    if not requested_node_ids:
        raise ValueError("At least one target FRD node ID is required.")

    if any(node_id <= 0 for node_id in requested_node_ids):
        raise ValueError("FRD target node IDs must be positive.")

    datasets: list[FrdDisplacementDataset] = []

    dataset_sequence: int | None = None
    step: int | None = None
    increment: int | None = None
    dataset_time: float | None = None

    inside_displacement = False
    records: list[FrdNodalDisplacement] = []

    with frd_path.open(
        "r",
        encoding="utf-8",
        errors="replace",
    ) as frd_file:
        for line_number, raw_line in enumerate(
            frd_file,
            start=1,
        ):
            line = raw_line.rstrip("\r\n")

            if line.startswith("    1PSTEP"):
                (
                    dataset_sequence,
                    increment,
                    step,
                ) = _parse_pstep_line(
                    line,
                    line_number=line_number,
                )

                dataset_time = None
                inside_displacement = False
                records = []

                continue

            if line.startswith("  100CL"):
                dataset_time = _parse_result_time(
                    line,
                    line_number=line_number,
                )

                continue

            if line.startswith(" -4") and "DISP" in line:
                if (
                    dataset_sequence is None
                    or step is None
                    or increment is None
                    or dataset_time is None
                ):
                    raise RuntimeError(
                        "FRD displacement header lacks complete "
                        f"dataset metadata at line {line_number}."
                    )

                inside_displacement = True
                records = []

                continue

            if not inside_displacement:
                continue

            if line.startswith(" -3"):
                assert dataset_sequence is not None
                assert step is not None
                assert increment is not None
                assert dataset_time is not None

                datasets.append(
                    FrdDisplacementDataset(
                        dataset_sequence=dataset_sequence,
                        step=step,
                        increment=increment,
                        time=dataset_time,
                        records=tuple(records),
                    )
                )

                inside_displacement = False
                records = []

                continue

            if not line.startswith(" -1"):
                continue

            node_id = _parse_node_id(
                line,
                line_number=line_number,
            )

            if node_id not in requested_node_ids:
                continue

            records.append(
                _parse_displacement_record(
                    line,
                    node_id=node_id,
                    line_number=line_number,
                )
            )

    if inside_displacement:
        raise RuntimeError("FRD file ended before the current displacement dataset terminator.")

    if not datasets:
        raise RuntimeError("No displacement datasets were found in the FRD file.")

    return tuple(datasets)


def _parse_pstep_line(
    line: str,
    *,
    line_number: int,
) -> tuple[int, int, int]:
    """Parse sequence, increment and step from a PSTEP line."""

    fields = line.split()

    if len(fields) < 4 or fields[0] != "1PSTEP":
        raise RuntimeError(f"Malformed FRD PSTEP line {line_number}: {line!r}")

    try:
        dataset_sequence = int(fields[-3])

        increment = int(fields[-2])

        step = int(fields[-1])

    except ValueError as error:
        raise RuntimeError(f"Invalid FRD PSTEP integers at line {line_number}.") from error

    if (
        min(
            dataset_sequence,
            increment,
            step,
        )
        <= 0
    ):
        raise RuntimeError(f"FRD PSTEP identifiers must be positive at line {line_number}.")

    return (
        dataset_sequence,
        increment,
        step,
    )


def _parse_result_time(
    line: str,
    *,
    line_number: int,
) -> float:
    """Parse the fixed-position result time from a 100CL line."""

    if len(line) < 24:
        raise RuntimeError(f"FRD 100CL line {line_number} is too short.")

    raw_time = line[12:24]

    try:
        value = float(raw_time)

    except ValueError as error:
        raise RuntimeError(
            f"Invalid FRD result time at line {line_number}: {raw_time!r}"
        ) from error

    if not math.isfinite(value):
        raise RuntimeError(f"FRD result time must be finite at line {line_number}.")

    return value


def _parse_node_id(
    line: str,
    *,
    line_number: int,
) -> int:
    """Parse the fixed-position node identifier."""

    if len(line) < 13:
        raise RuntimeError(f"FRD nodal line {line_number} is too short.")

    raw_node_id = line[3:13]

    try:
        node_id = int(raw_node_id)

    except ValueError as error:
        raise RuntimeError(f"Invalid FRD node ID at line {line_number}: {raw_node_id!r}") from error

    if node_id <= 0:
        raise RuntimeError(f"FRD node ID must be positive at line {line_number}.")

    return node_id


def _parse_displacement_record(
    line: str,
    *,
    node_id: int,
    line_number: int,
) -> FrdNodalDisplacement:
    """Parse three concatenated FRD displacement components."""

    raw_components = line[13:]

    matches = tuple(_FRD_FLOAT_PATTERN.finditer(raw_components))

    if len(matches) != 3:
        raise RuntimeError(
            "Expected three FRD displacement components at "
            f"line {line_number}; found {len(matches)}."
        )

    reconstructed = "".join(match.group(0) for match in matches)

    if reconstructed != raw_components.strip():
        raise RuntimeError(
            f"Unparsed characters remain in FRD displacement line {line_number}: {raw_components!r}"
        )

    components = tuple(float(match.group(0)) for match in matches)

    if not all(math.isfinite(component) for component in components):
        raise RuntimeError(f"FRD displacement components must be finite at line {line_number}.")

    return FrdNodalDisplacement(
        node_id=node_id,
        d1_mm=components[0],
        d2_mm=components[1],
        d3_mm=components[2],
    )

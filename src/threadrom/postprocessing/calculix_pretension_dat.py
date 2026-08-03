"""Parse pretension-reference results from CalculiX DAT files."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

_FLOAT_TOKEN = (
    r"[+-]?"
    r"(?:\d+(?:\.\d*)?|\.\d+)"
    r"(?:[EeDd][+-]?\d+)?"
)

_STEP_PATTERN = re.compile(
    r"^\s*S\s+T\s+E\s+P\s+(\d+)\s*$",
    re.IGNORECASE,
)

_INCREMENT_PATTERN = re.compile(
    r"^\s*INCREMENT\s+(\d+)\s*$",
    re.IGNORECASE,
)

_HEADER_PATTERN = re.compile(
    rf"^\s*"
    rf"(displacements|forces)"
    rf"\s+\([^)]*\)"
    rf"\s+for set\s+([A-Za-z0-9_]+)"
    rf"\s+and time\s+({_FLOAT_TOKEN})"
    rf"\s*$",
    re.IGNORECASE,
)

_VECTOR_PATTERN = re.compile(
    rf"^\s*"
    rf"(\d+)\s+"
    rf"({_FLOAT_TOKEN})\s+"
    rf"({_FLOAT_TOKEN})\s+"
    rf"({_FLOAT_TOKEN})"
    rf"\s*$"
)


@dataclass(frozen=True)
class PretensionReferenceRecord:
    """One complete pretension-reference DAT result."""

    step: int
    increment: int
    time: float
    set_name: str
    node_id: int
    displacement_components_mm: tuple[
        float,
        float,
        float,
    ]
    force_components_n: tuple[
        float,
        float,
        float,
    ]
    control_component: int
    control_displacement_mm: float
    preload_force_n: float
    force_displacement_ratio_kn_per_mm: float | None


@dataclass(frozen=True)
class _VectorBlock:
    """One displacement or force block parsed from DAT."""

    result_type: str
    step: int
    increment: int
    time: float
    set_name: str
    node_id: int
    components: tuple[
        float,
        float,
        float,
    ]


def _fortran_float(value: str) -> float:
    """Convert a Fortran E- or D-notation number."""

    return float(value.replace("D", "E").replace("d", "e"))


def _next_vector_row(
    lines: list[str],
    start_index: int,
) -> tuple[int, tuple[float, float, float]] | None:
    """Return the next complete node-vector row."""

    for line in lines[start_index:]:
        if line.lstrip().startswith("*"):
            return None

        match = _VECTOR_PATTERN.fullmatch(line)

        if match is None:
            continue

        return (
            int(match.group(1)),
            (
                _fortran_float(match.group(2)),
                _fortran_float(match.group(3)),
                _fortran_float(match.group(4)),
            ),
        )

    return None


def _parse_vector_blocks(
    content: str,
    set_name: str,
) -> tuple[_VectorBlock, ...]:
    """Parse complete vector blocks for the requested set."""

    lines = content.splitlines()

    current_step: int | None = None
    current_increment: int | None = None

    blocks: list[_VectorBlock] = []

    for index, line in enumerate(lines):
        step_match = _STEP_PATTERN.fullmatch(line)

        if step_match is not None:
            current_step = int(step_match.group(1))
            continue

        increment_match = _INCREMENT_PATTERN.fullmatch(line)

        if increment_match is not None:
            current_increment = int(increment_match.group(1))
            continue

        header_match = _HEADER_PATTERN.fullmatch(line)

        if header_match is None:
            continue

        parsed_set_name = header_match.group(2)

        if parsed_set_name.casefold() != set_name.casefold():
            continue

        if current_step is None or current_increment is None:
            continue

        vector_row = _next_vector_row(
            lines,
            index + 1,
        )

        if vector_row is None:
            continue

        node_id, components = vector_row

        blocks.append(
            _VectorBlock(
                result_type=(header_match.group(1).casefold()),
                step=current_step,
                increment=current_increment,
                time=_fortran_float(header_match.group(3)),
                set_name=parsed_set_name,
                node_id=node_id,
                components=components,
            )
        )

    return tuple(blocks)


def parse_pretension_reference_records(
    content: str,
    *,
    set_name: str = "BOLT_PRETENSION_REFERENCE",
    control_component: int = 1,
) -> tuple[PretensionReferenceRecord, ...]:
    """Parse complete force-displacement pretension records."""

    if control_component not in {
        1,
        2,
        3,
    }:
        raise ValueError("Control component must be 1, 2 or 3.")

    component_index = control_component - 1

    blocks = _parse_vector_blocks(
        content,
        set_name,
    )

    key_type = tuple[
        int,
        int,
        float,
        str,
    ]

    displacements: dict[
        key_type,
        _VectorBlock,
    ] = {}

    forces: dict[
        key_type,
        _VectorBlock,
    ] = {}

    for block in blocks:
        key = (
            block.step,
            block.increment,
            block.time,
            block.set_name.casefold(),
        )

        if block.result_type == "displacements":
            displacements[key] = block
        elif block.result_type == "forces":
            forces[key] = block

    common_keys = sorted(set(displacements) & set(forces))

    records: list[PretensionReferenceRecord] = []

    for key in common_keys:
        displacement = displacements[key]
        force = forces[key]

        if displacement.node_id != force.node_id:
            raise ValueError("Pretension displacement and force node IDs do not match.")

        control_displacement = displacement.components[component_index]

        preload_force = force.components[component_index]

        ratio: float | None = None

        if abs(control_displacement) > 1.0e-30:
            ratio = preload_force / control_displacement / 1000.0

        records.append(
            PretensionReferenceRecord(
                step=displacement.step,
                increment=displacement.increment,
                time=displacement.time,
                set_name=displacement.set_name,
                node_id=displacement.node_id,
                displacement_components_mm=(displacement.components),
                force_components_n=(force.components),
                control_component=control_component,
                control_displacement_mm=(control_displacement),
                preload_force_n=preload_force,
                force_displacement_ratio_kn_per_mm=(ratio),
            )
        )

    return tuple(records)


def write_pretension_reference_json(
    dat_path: Path,
    output_path: Path,
    *,
    set_name: str = "BOLT_PRETENSION_REFERENCE",
    control_component: int = 1,
) -> dict[str, object]:
    """Parse a DAT file and write structured JSON."""

    content = dat_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    records = parse_pretension_reference_records(
        content,
        set_name=set_name,
        control_component=control_component,
    )

    payload: dict[str, object] = {
        "schema_version": 1,
        "source_dat": str(dat_path),
        "set_name": set_name,
        "control_component": control_component,
        "record_count": len(records),
        "latest_record": (asdict(records[-1]) if records else None),
        "records": [asdict(record) for record in records],
    }

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    serialized_payload = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    output_path.write_text(
        serialized_payload,
        encoding="utf-8",
        newline="\n",
    )

    normalized_payload: dict[str, object] = json.loads(serialized_payload)

    return normalized_payload

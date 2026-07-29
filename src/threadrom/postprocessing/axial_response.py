"""CalculiX axial-response post-processing."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean, pstdev
from typing import cast


@dataclass(frozen=True)
class AxialCaseDefinition:
    """One controlled axial-response result case."""

    level: str
    simulation_id: str
    dat_relative_path: Path


@dataclass(frozen=True)
class AxialComparisonDefinition:
    """Configuration for comparing axial-response cases."""

    mesh_id: str
    node_set_name: str
    applied_force_n: float
    maximum_global_response_difference_percent: float
    report_relative_path: Path
    cases: tuple[AxialCaseDefinition, ...]


@dataclass(frozen=True)
class NodalDisplacement:
    """One CalculiX nodal displacement result."""

    node_id: int
    vx_mm: float
    vy_mm: float
    vz_mm: float


@dataclass(frozen=True)
class AxialResponseSummary:
    """Global axial-response statistics for one mesh."""

    level: str
    simulation_id: str
    loaded_node_count: int
    mean_vz_mm: float
    minimum_vz_mm: float
    maximum_vz_mm: float
    maximum_absolute_vz_mm: float
    range_vz_mm: float
    standard_deviation_vz_mm: float
    coefficient_of_variation_percent: float
    apparent_stiffness_n_per_mm: float


_NUMBER_PATTERN = re.compile(
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
    r"(?:[EeDd][+-]?\d+)?"
)


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return a required TOML section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(f"Missing or invalid configuration section: {key}")

    return cast(Mapping[str, object], value)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return a required non-empty string."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Missing or invalid string value: {key}")

    return value.strip()


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return a required numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(
        value,
        int | float,
    ):
        raise TypeError(f"Missing or invalid numerical value: {key}")

    return float(value)


def load_axial_comparison_definition(
    config_path: Path,
) -> AxialComparisonDefinition:
    """Load the governed axial-response comparison definition."""

    with config_path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(config_file)

    identity = _section(data, "identity")
    analysis = _section(data, "analysis")
    output = _section(data, "output")

    raw_cases = data.get("cases")

    if not isinstance(raw_cases, list) or len(raw_cases) < 2:
        raise TypeError("At least two axial-response cases are required.")

    cases: list[AxialCaseDefinition] = []

    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise TypeError("Every axial-response case must be a TOML table.")

        case = cast(
            Mapping[str, object],
            raw_case,
        )

        cases.append(
            AxialCaseDefinition(
                level=_string(
                    case,
                    "level",
                ).lower(),
                simulation_id=_string(
                    case,
                    "simulation_id",
                ),
                dat_relative_path=Path(
                    _string(
                        case,
                        "dat_relative_path",
                    )
                ),
            )
        )

    levels = [case.level for case in cases]

    if len(levels) != len(set(levels)):
        raise ValueError("Axial-response case levels must be unique.")

    applied_force_n = _number(
        analysis,
        "applied_force_n",
    )

    if applied_force_n == 0.0:
        raise ValueError("Applied axial force cannot be zero.")

    maximum_global_response_difference_percent = _number(
        analysis,
        "maximum_global_response_difference_percent",
    )

    if maximum_global_response_difference_percent <= 0.0:
        raise ValueError(
            "Maximum global-response difference must be positive."
        )

    return AxialComparisonDefinition(
        mesh_id=_string(
            identity,
            "mesh_id",
        ),
        node_set_name=_string(
            analysis,
            "node_set_name",
        ),
        applied_force_n=applied_force_n,
        maximum_global_response_difference_percent=(
            maximum_global_response_difference_percent
        ),
        report_relative_path=Path(
            _string(
                output,
                "report_relative_path",
            )
        ),
        cases=tuple(cases),
    )


def _calculix_number(value: str) -> float:
    """Parse an E- or D-exponent CalculiX number."""

    return float(value.replace("D", "E").replace("d", "e"))


def read_displacement_block(
    dat_path: Path,
    node_set_name: str,
) -> tuple[NodalDisplacement, ...]:
    """Read one named displacement block from a CalculiX DAT file."""

    if not dat_path.exists() or dat_path.stat().st_size <= 0:
        raise FileNotFoundError(f"Valid CalculiX DAT file not found: {dat_path}")

    lines = dat_path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines()

    header_pattern = re.compile(
        (
            r"displacements\s*"
            r"\(\s*vx\s*,\s*vy\s*,\s*vz\s*\)"
            r"\s+for\s+set\s+" + re.escape(node_set_name) + r"\s+and\s+time"
        ),
        re.IGNORECASE,
    )

    header_index = next(
        (index for index, line in enumerate(lines) if header_pattern.search(line)),
        None,
    )

    if header_index is None:
        raise RuntimeError(
            f"CalculiX displacement output was not found for node set {node_set_name!r}."
        )

    rows: list[NodalDisplacement] = []
    node_ids: set[int] = set()
    data_started = False

    for line in lines[header_index + 1 :]:
        stripped = line.strip()

        if not stripped:
            if data_started:
                break

            continue

        fields = stripped.split()

        if len(fields) != 4:
            if data_started:
                break

            continue

        try:
            node_id = int(fields[0])
            vx_mm = _calculix_number(fields[1])
            vy_mm = _calculix_number(fields[2])
            vz_mm = _calculix_number(fields[3])
        except ValueError:
            if data_started:
                break

            continue

        if node_id in node_ids:
            raise RuntimeError(f"Duplicate displacement result for node {node_id}.")

        node_ids.add(node_id)

        rows.append(
            NodalDisplacement(
                node_id=node_id,
                vx_mm=vx_mm,
                vy_mm=vy_mm,
                vz_mm=vz_mm,
            )
        )

        data_started = True

    if not rows:
        raise RuntimeError(f"No displacement rows found in {dat_path}.")

    return tuple(rows)


def summarize_axial_response(
    case: AxialCaseDefinition,
    dat_path: Path,
    node_set_name: str,
    applied_force_n: float,
) -> AxialResponseSummary:
    """Calculate load-conjugate axial displacement and stiffness."""

    rows = read_displacement_block(
        dat_path,
        node_set_name,
    )

    vz_values = [row.vz_mm for row in rows]

    mean_vz_mm = fmean(vz_values)

    if abs(mean_vz_mm) <= 1.0e-15:
        raise RuntimeError("Mean axial displacement is too small for stiffness calculation.")

    standard_deviation_vz_mm = pstdev(vz_values)

    return AxialResponseSummary(
        level=case.level,
        simulation_id=case.simulation_id,
        loaded_node_count=len(rows),
        mean_vz_mm=mean_vz_mm,
        minimum_vz_mm=min(vz_values),
        maximum_vz_mm=max(vz_values),
        maximum_absolute_vz_mm=max(abs(value) for value in vz_values),
        range_vz_mm=(max(vz_values) - min(vz_values)),
        standard_deviation_vz_mm=(standard_deviation_vz_mm),
        coefficient_of_variation_percent=(standard_deviation_vz_mm / abs(mean_vz_mm) * 100.0),
        apparent_stiffness_n_per_mm=(abs(applied_force_n) / abs(mean_vz_mm)),
    )


def finer_relative_change_percent(
    coarse_value: float,
    finer_value: float,
) -> float:
    """Return signed change relative to the finer result."""

    if finer_value == 0.0:
        raise ValueError("Finer reference value cannot be zero.")

    return (finer_value - coarse_value) / finer_value * 100.0

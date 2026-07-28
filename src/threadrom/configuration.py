"""ThreadROM configuration loading and validation."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class ToolDefinition:
    """Versioned engineering tool definition."""

    backend: str
    version: str


@dataclass(frozen=True)
class CalculixDefinition:
    """CalculiX solver configuration."""

    version: str
    relative_executable: Path
    environment_override: str


@dataclass(frozen=True)
class ThreadROMConfig:
    """Validated ThreadROM project configuration."""

    name: str
    phase: int
    work_package: str
    canonical_length_unit: str
    canonical_force_unit: str
    axial_axis: str
    coordinate_handedness: str
    geometry: ToolDefinition
    mesher: ToolDefinition
    solver: CalculixDefinition


def _mapping(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return a required mapping section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(f"Missing or invalid configuration section: {key}")

    return cast(Mapping[str, object], value)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return a required non-empty string value."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Missing or invalid string value: {key}")

    return value


def _integer(
    data: Mapping[str, object],
    key: str,
) -> int:
    """Return a required integer value."""

    value = data.get(key)

    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"Missing or invalid integer value: {key}")

    return value


def load_project_config(path: Path) -> ThreadROMConfig:
    """Load and validate the ThreadROM TOML configuration."""

    with path.open("rb") as config_file:
        raw_data: dict[str, object] = tomllib.load(config_file)

    project = _mapping(raw_data, "project")
    conventions = _mapping(raw_data, "conventions")
    geometry = _mapping(raw_data, "geometry")
    mesher = _mapping(raw_data, "mesher")
    solver = _mapping(raw_data, "solver")
    calculix = _mapping(solver, "calculix")

    return ThreadROMConfig(
        name=_string(project, "name"),
        phase=_integer(project, "phase"),
        work_package=_string(project, "work_package"),
        canonical_length_unit=_string(
            conventions,
            "canonical_length_unit",
        ),
        canonical_force_unit=_string(
            conventions,
            "canonical_force_unit",
        ),
        axial_axis=_string(conventions, "axial_axis"),
        coordinate_handedness=_string(
            conventions,
            "coordinate_handedness",
        ),
        geometry=ToolDefinition(
            backend=_string(geometry, "backend"),
            version=_string(geometry, "version"),
        ),
        mesher=ToolDefinition(
            backend=_string(mesher, "backend"),
            version=_string(mesher, "version"),
        ),
        solver=CalculixDefinition(
            version=_string(calculix, "version"),
            relative_executable=Path(
                _string(calculix, "relative_executable")
            ),
            environment_override=_string(
                calculix,
                "environment_override",
            ),
        ),
    )


def resolve_calculix_executable(
    config: ThreadROMConfig,
    project_root: Path,
) -> Path:
    """Resolve CalculiX using an environment override or repository path."""

    override = os.environ.get(config.solver.environment_override)

    if override:
        return Path(override)

    return project_root / config.solver.relative_executable
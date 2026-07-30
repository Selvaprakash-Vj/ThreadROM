"""Parameter-scaled mesh levels for threaded geometries."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast


class ThreadGeometryDefinition(Protocol):
    """Thread dimensions required by the mesh-level resolver."""

    @property
    def pitch_mm(self) -> float:
        """Return the axial thread pitch."""

        ...

    @property
    def radial_thread_depth_mm(self) -> float:
        """Return the radial thread depth."""

        ...


@dataclass(frozen=True)
class MeshLevelFactors:
    """Dimensionless factors defining one mesh level."""

    name: str
    maximum_size_pitch_factor: float
    minimum_size_thread_depth_factor: float
    thread_surface_size_depth_factor: float


@dataclass(frozen=True)
class MeshLevelPolicy:
    """Controlled hierarchy of parameter-scaled mesh levels."""

    policy_id: str
    mesh_id: str
    geometry_id: str
    levels: tuple[MeshLevelFactors, ...]


@dataclass(frozen=True)
class ResolvedMeshLevel:
    """Absolute mesh sizes resolved from thread geometry."""

    name: str
    mesh_size_min_mm: float
    mesh_size_max_mm: float
    thread_surface_size_mm: float
    pitch_mm: float
    radial_thread_depth_mm: float


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

    return value


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return a required numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"Missing or invalid numerical value: {key}")

    return float(value)


def _string_tuple(
    data: Mapping[str, object],
    key: str,
) -> tuple[str, ...]:
    """Return a required ordered list of names."""

    value = data.get(key)

    if not isinstance(value, list) or not value:
        raise TypeError(f"Missing or invalid string list: {key}")

    names: list[str] = []

    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise TypeError(f"Invalid string item in list: {key}")

        names.append(item)

    if len(names) != len(set(names)):
        raise ValueError(f"Duplicate names are not permitted in: {key}")

    return tuple(names)


def load_mesh_level_policy(
    config_path: Path,
) -> MeshLevelPolicy:
    """Load and validate the parameter-scaled mesh hierarchy."""

    with config_path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(config_file)

    identity = _section(data, "identity")
    level_sections = _section(data, "levels")

    level_order = _string_tuple(
        identity,
        "level_order",
    )

    levels: list[MeshLevelFactors] = []

    for level_name in level_order:
        level_data = _section(
            level_sections,
            level_name,
        )

        factors = MeshLevelFactors(
            name=level_name,
            maximum_size_pitch_factor=_number(
                level_data,
                "maximum_size_pitch_factor",
            ),
            minimum_size_thread_depth_factor=_number(
                level_data,
                "minimum_size_thread_depth_factor",
            ),
            thread_surface_size_depth_factor=_number(
                level_data,
                "thread_surface_size_depth_factor",
            ),
        )

        factor_values = (
            factors.maximum_size_pitch_factor,
            factors.minimum_size_thread_depth_factor,
            factors.thread_surface_size_depth_factor,
        )

        if any(value <= 0.0 for value in factor_values):
            raise ValueError(f"All factors for level {level_name!r} must be positive.")

        levels.append(factors)

    return MeshLevelPolicy(
        policy_id=_string(identity, "policy_id"),
        mesh_id=_string(identity, "mesh_id"),
        geometry_id=_string(identity, "geometry_id"),
        levels=tuple(levels),
    )


def resolve_mesh_levels(
    policy: MeshLevelPolicy,
    thread_definition: ThreadGeometryDefinition,
) -> tuple[ResolvedMeshLevel, ...]:
    """Resolve dimensionless level factors into millimetres."""

    pitch_mm = thread_definition.pitch_mm
    thread_depth_mm = thread_definition.radial_thread_depth_mm

    if pitch_mm <= 0.0:
        raise ValueError("Thread pitch must be positive.")

    if thread_depth_mm <= 0.0:
        raise ValueError("Radial thread depth must be positive.")

    resolved_levels: list[ResolvedMeshLevel] = []

    for level in policy.levels:
        proposed_minimum_mm = thread_depth_mm * level.minimum_size_thread_depth_factor

        thread_surface_size_mm = thread_depth_mm * level.thread_surface_size_depth_factor

        mesh_size_min_mm = min(
            proposed_minimum_mm,
            thread_surface_size_mm,
        )

        mesh_size_max_mm = pitch_mm * level.maximum_size_pitch_factor

        if mesh_size_min_mm > mesh_size_max_mm:
            raise ValueError(f"Resolved minimum size exceeds maximum for level {level.name!r}.")

        if thread_surface_size_mm > mesh_size_max_mm:
            raise ValueError(f"Resolved thread size exceeds maximum for level {level.name!r}.")

        resolved_levels.append(
            ResolvedMeshLevel(
                name=level.name,
                mesh_size_min_mm=mesh_size_min_mm,
                mesh_size_max_mm=mesh_size_max_mm,
                thread_surface_size_mm=(thread_surface_size_mm),
                pitch_mm=pitch_mm,
                radial_thread_depth_mm=thread_depth_mm,
            )
        )

    maximum_sizes = [level.mesh_size_max_mm for level in resolved_levels]

    minimum_sizes = [level.mesh_size_min_mm for level in resolved_levels]

    thread_sizes = [level.thread_surface_size_mm for level in resolved_levels]

    if maximum_sizes != sorted(
        maximum_sizes,
        reverse=True,
    ):
        raise ValueError("Mesh-level maximum sizes must become progressively finer.")

    if minimum_sizes != sorted(
        minimum_sizes,
        reverse=True,
    ):
        raise ValueError("Mesh-level minimum sizes must become progressively finer.")

    if thread_sizes != sorted(
        thread_sizes,
        reverse=True,
    ):
        raise ValueError("Thread-region sizes must become progressively finer.")

    return tuple(resolved_levels)

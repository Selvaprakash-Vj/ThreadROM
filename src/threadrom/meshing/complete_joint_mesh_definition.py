"""Governed configuration for complete-joint meshing."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from threadrom.meshing.mesh_levels import (
    ResolvedMeshLevel,
)


@dataclass(frozen=True)
class CompleteJointMeshDefinition:
    """Configuration controlling the grouped assembly mesh."""

    mesh_id: str
    assembly_id: str
    geometry_id: str
    classification_id: str
    element_order: int
    algorithm_2d: int
    algorithm_3d: int
    msh_file_version: float
    binary_output: bool
    save_all_elements: bool
    selected_level: str
    bolt_mesh_level_policy: str
    nut_mesh_level_policy: str
    expected_volume_count: int
    minimum_node_count: int
    minimum_tetrahedron_count: int
    minimum_boundary_triangle_count: int


@dataclass(frozen=True)
class ResolvedCompleteJointMeshSizes:
    """Resolved global and component-local joint mesh sizes."""

    level_name: str
    mesh_size_min_mm: float
    mesh_size_max_mm: float
    bolt_thread_surface_size_mm: float
    nut_thread_surface_size_mm: float


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return one required TOML section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(
            f"Missing or invalid configuration section: {key}"
        )

    return cast(Mapping[str, object], value)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return one required non-empty string."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(
            f"Missing or invalid string value: {key}"
        )

    return value


def _integer(
    data: Mapping[str, object],
    key: str,
) -> int:
    """Return one required integer."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"Missing or invalid integer value: {key}"
        )

    return value


def _positive_integer(
    data: Mapping[str, object],
    key: str,
) -> int:
    """Return one required positive integer."""

    value = _integer(data, key)

    if value <= 0:
        raise ValueError(
            f"Integer value must be positive: {key}"
        )

    return value


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return one required numerical value."""

    value = data.get(key)

    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
    ):
        raise TypeError(
            f"Missing or invalid numerical value: {key}"
        )

    return float(value)


def _boolean(
    data: Mapping[str, object],
    key: str,
) -> bool:
    """Return one required Boolean value."""

    value = data.get(key)

    if not isinstance(value, bool):
        raise TypeError(
            f"Missing or invalid Boolean value: {key}"
        )

    return value


def load_complete_joint_mesh_definition(
    path: Path,
) -> CompleteJointMeshDefinition:
    """Load and validate the complete-joint mesh definition."""

    with path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(
            config_file
        )

    identity = _section(data, "identity")
    gmsh = _section(data, "gmsh")
    refinement = _section(data, "refinement")
    verification = _section(data, "verification")

    definition = CompleteJointMeshDefinition(
        mesh_id=_string(identity, "mesh_id"),
        assembly_id=_string(identity, "assembly_id"),
        geometry_id=_string(identity, "geometry_id"),
        classification_id=_string(
            identity,
            "classification_id",
        ),
        element_order=_positive_integer(
            gmsh,
            "element_order",
        ),
        algorithm_2d=_positive_integer(
            gmsh,
            "algorithm_2d",
        ),
        algorithm_3d=_positive_integer(
            gmsh,
            "algorithm_3d",
        ),
        msh_file_version=_number(
            gmsh,
            "msh_file_version",
        ),
        binary_output=_boolean(
            gmsh,
            "binary_output",
        ),
        save_all_elements=_boolean(
            gmsh,
            "save_all_elements",
        ),
        selected_level=_string(
            refinement,
            "selected_level",
        ),
        bolt_mesh_level_policy=_string(
            refinement,
            "bolt_mesh_level_policy",
        ),
        nut_mesh_level_policy=_string(
            refinement,
            "nut_mesh_level_policy",
        ),
        expected_volume_count=_positive_integer(
            verification,
            "expected_volume_count",
        ),
        minimum_node_count=_positive_integer(
            verification,
            "minimum_node_count",
        ),
        minimum_tetrahedron_count=_positive_integer(
            verification,
            "minimum_tetrahedron_count",
        ),
        minimum_boundary_triangle_count=(
            _positive_integer(
                verification,
                "minimum_boundary_triangle_count",
            )
        ),
    )

    if definition.msh_file_version <= 0.0:
        raise ValueError(
            "MSH file version must be positive."
        )

    return definition


def _selected_level(
    levels: tuple[ResolvedMeshLevel, ...],
    selected_name: str,
) -> ResolvedMeshLevel:
    """Return one selected level or raise a controlled error."""

    matches = tuple(
        level
        for level in levels
        if level.name == selected_name
    )

    if len(matches) != 1:
        raise ValueError(
            "Selected mesh level must exist exactly once: "
            f"{selected_name!r}."
        )

    return matches[0]


def resolve_complete_joint_mesh_sizes(
    definition: CompleteJointMeshDefinition,
    bolt_levels: tuple[ResolvedMeshLevel, ...],
    nut_levels: tuple[ResolvedMeshLevel, ...],
    *,
    tolerance_mm: float = 1.0e-12,
) -> ResolvedCompleteJointMeshSizes:
    """Resolve compatible bolt and nut sizes for the joint."""

    if tolerance_mm < 0.0:
        raise ValueError(
            "Mesh-size comparison tolerance cannot be negative."
        )

    bolt_level = _selected_level(
        bolt_levels,
        definition.selected_level,
    )

    nut_level = _selected_level(
        nut_levels,
        definition.selected_level,
    )

    if (
        abs(
            bolt_level.mesh_size_max_mm
            - nut_level.mesh_size_max_mm
        )
        > tolerance_mm
    ):
        raise ValueError(
            "Bolt and nut maximum mesh sizes differ: "
            f"{bolt_level.mesh_size_max_mm} vs "
            f"{nut_level.mesh_size_max_mm}."
        )

    return ResolvedCompleteJointMeshSizes(
        level_name=definition.selected_level,
        mesh_size_min_mm=min(
            bolt_level.mesh_size_min_mm,
            nut_level.mesh_size_min_mm,
        ),
        mesh_size_max_mm=(
            bolt_level.mesh_size_max_mm
        ),
        bolt_thread_surface_size_mm=(
            bolt_level.thread_surface_size_mm
        ),
        nut_thread_surface_size_mm=(
            nut_level.thread_surface_size_mm
        ),
    )

"""Tetrahedral mesh-quality measurement and acceptance gates."""

from __future__ import annotations

import math
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import meshio  # type: ignore[import-untyped]
import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class MeshQualityDefinition:
    """Controlled mesh-quality acceptance and reporting policy."""

    mesh_id: str
    geometry_id: str
    minimum_tetrahedron_volume_mm3: float
    minimum_mean_ratio: float
    maximum_edge_ratio: float
    allow_mixed_orientation: bool
    mean_ratio_percentiles: tuple[float, ...]
    mean_ratio_bands: tuple[float, ...]


@dataclass(frozen=True)
class TetrahedronQualityArrays:
    """Vectorized quality measurements for tetrahedral elements."""

    signed_volumes_mm3: NDArray[np.float64]
    absolute_volumes_mm3: NDArray[np.float64]
    mean_ratios: NDArray[np.float64]
    edge_ratios: NDArray[np.float64]


@dataclass(frozen=True)
class QualityPercentile:
    """One percentile measurement."""

    percentile: float
    value: float


@dataclass(frozen=True)
class QualityBandCount:
    """Number of elements below a controlled quality level."""

    upper_limit: float
    element_count: int
    element_fraction: float


@dataclass(frozen=True)
class TetrahedralMeshQualityResult:
    """Complete tetrahedral mesh-quality summary."""

    node_count: int
    tetrahedron_count: int
    positive_orientation_count: int
    negative_orientation_count: int
    degenerate_count: int
    minimum_volume_mm3: float
    maximum_volume_mm3: float
    mean_volume_mm3: float
    minimum_mean_ratio: float
    maximum_mean_ratio: float
    mean_mean_ratio: float
    minimum_edge_ratio: float
    maximum_edge_ratio: float
    mean_edge_ratio: float
    mean_ratio_percentiles: tuple[QualityPercentile, ...]
    mean_ratio_bands: tuple[QualityBandCount, ...]

    @property
    def has_mixed_orientation(self) -> bool:
        """Return whether both signed orientations are present."""

        return self.positive_orientation_count > 0 and self.negative_orientation_count > 0


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
    """Return a required number."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"Missing or invalid numerical value: {key}")

    return float(value)


def _boolean(
    data: Mapping[str, object],
    key: str,
) -> bool:
    """Return a required Boolean value."""

    value = data.get(key)

    if not isinstance(value, bool):
        raise TypeError(f"Missing or invalid Boolean value: {key}")

    return value


def _number_tuple(
    data: Mapping[str, object],
    key: str,
) -> tuple[float, ...]:
    """Return a required list of numerical values."""

    value = data.get(key)

    if not isinstance(value, list) or not value:
        raise TypeError(f"Missing or invalid numerical list: {key}")

    values: list[float] = []

    for item in value:
        if isinstance(item, bool) or not isinstance(
            item,
            int | float,
        ):
            raise TypeError(f"Invalid numerical item in list: {key}")

        values.append(float(item))

    return tuple(values)


def load_mesh_quality_definition(
    config_path: Path,
) -> MeshQualityDefinition:
    """Load and validate the mesh-quality policy."""

    with config_path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(config_file)

    identity = _section(data, "identity")
    acceptance = _section(data, "acceptance")
    reporting = _section(data, "reporting")

    definition = MeshQualityDefinition(
        mesh_id=_string(identity, "mesh_id"),
        geometry_id=_string(identity, "geometry_id"),
        minimum_tetrahedron_volume_mm3=_number(
            acceptance,
            "minimum_tetrahedron_volume_mm3",
        ),
        minimum_mean_ratio=_number(
            acceptance,
            "minimum_mean_ratio",
        ),
        maximum_edge_ratio=_number(
            acceptance,
            "maximum_edge_ratio",
        ),
        allow_mixed_orientation=_boolean(
            acceptance,
            "allow_mixed_orientation",
        ),
        mean_ratio_percentiles=_number_tuple(
            reporting,
            "mean_ratio_percentiles",
        ),
        mean_ratio_bands=_number_tuple(
            reporting,
            "mean_ratio_bands",
        ),
    )

    if definition.minimum_tetrahedron_volume_mm3 <= 0.0:
        raise ValueError("Minimum tetrahedron volume must be positive.")

    if not 0.0 < definition.minimum_mean_ratio <= 1.0:
        raise ValueError("Minimum mean ratio must lie in (0, 1].")

    if definition.maximum_edge_ratio < 1.0:
        raise ValueError("Maximum edge ratio cannot be below one.")

    if any(not 0.0 <= percentile <= 100.0 for percentile in definition.mean_ratio_percentiles):
        raise ValueError("Quality percentiles must lie between 0 and 100.")

    if any(not 0.0 < band <= 1.0 for band in definition.mean_ratio_bands):
        raise ValueError("Mean-ratio reporting bands must lie in (0, 1].")

    return definition


def calculate_tetrahedron_quality(
    points_mm: NDArray[np.float64],
    tetrahedra: NDArray[np.int64],
) -> TetrahedronQualityArrays:
    """Calculate signed volume, mean ratio and edge ratio."""

    if points_mm.ndim != 2 or points_mm.shape[1] != 3:
        raise ValueError("Node coordinates must have shape (node_count, 3).")

    if tetrahedra.ndim != 2 or tetrahedra.shape[1] != 4:
        raise ValueError("Tetrahedral connectivity must have shape (element_count, 4).")

    element_points = points_mm[tetrahedra]

    point_0 = element_points[:, 0, :]
    point_1 = element_points[:, 1, :]
    point_2 = element_points[:, 2, :]
    point_3 = element_points[:, 3, :]

    signed_volumes = (
        np.einsum(
            "ij,ij->i",
            np.cross(
                point_1 - point_0,
                point_2 - point_0,
            ),
            point_3 - point_0,
        )
        / 6.0
    )

    absolute_volumes = np.abs(signed_volumes)

    edge_vectors = (
        point_1 - point_0,
        point_2 - point_0,
        point_3 - point_0,
        point_2 - point_1,
        point_3 - point_1,
        point_3 - point_2,
    )

    squared_edge_lengths = np.column_stack(
        tuple(
            np.einsum(
                "ij,ij->i",
                edge,
                edge,
            )
            for edge in edge_vectors
        )
    )

    edge_length_sums = np.sum(
        squared_edge_lengths,
        axis=1,
    )

    mean_ratios = np.zeros_like(
        absolute_volumes,
        dtype=np.float64,
    )

    valid_volume_mask = absolute_volumes > np.finfo(np.float64).tiny

    mean_ratios[valid_volume_mask] = (
        12.0
        * np.power(
            3.0 * absolute_volumes[valid_volume_mask],
            2.0 / 3.0,
        )
        / edge_length_sums[valid_volume_mask]
    )

    minimum_squared_edges = np.min(
        squared_edge_lengths,
        axis=1,
    )

    maximum_squared_edges = np.max(
        squared_edge_lengths,
        axis=1,
    )

    edge_ratios = np.full_like(
        absolute_volumes,
        math.inf,
        dtype=np.float64,
    )

    valid_edge_mask = minimum_squared_edges > np.finfo(np.float64).tiny

    edge_ratios[valid_edge_mask] = np.sqrt(
        maximum_squared_edges[valid_edge_mask] / minimum_squared_edges[valid_edge_mask]
    )

    return TetrahedronQualityArrays(
        signed_volumes_mm3=signed_volumes,
        absolute_volumes_mm3=absolute_volumes,
        mean_ratios=mean_ratios,
        edge_ratios=edge_ratios,
    )


def _load_tetrahedral_mesh(
    msh_path: Path,
) -> tuple[
    NDArray[np.float64],
    NDArray[np.int64],
]:
    """Read nodes and first-order tetrahedra from a Meshio file."""

    if not msh_path.exists() or msh_path.stat().st_size <= 0:
        raise FileNotFoundError(f"Valid grouped mesh not found: {msh_path}")

    mesh = meshio.read(msh_path)

    tetrahedral_blocks = [
        np.asarray(
            cell_block.data,
            dtype=np.int64,
        )
        for cell_block in mesh.cells
        if cell_block.type == "tetra"
    ]

    if not tetrahedral_blocks:
        raise RuntimeError("Mesh contains no first-order tetrahedra.")

    tetrahedra = np.vstack(tetrahedral_blocks)

    points = np.asarray(
        mesh.points[:, :3],
        dtype=np.float64,
    )

    return points, tetrahedra


def analyze_tetrahedral_mesh_quality(
    msh_path: Path,
    definition: MeshQualityDefinition,
) -> TetrahedralMeshQualityResult:
    """Analyze and validate the tetrahedral mesh."""

    points, tetrahedra = _load_tetrahedral_mesh(msh_path)

    quality = calculate_tetrahedron_quality(
        points,
        tetrahedra,
    )

    volume_threshold = definition.minimum_tetrahedron_volume_mm3

    degenerate_mask = quality.absolute_volumes_mm3 <= volume_threshold

    percentile_values = np.percentile(
        quality.mean_ratios,
        definition.mean_ratio_percentiles,
    )

    percentiles = tuple(
        QualityPercentile(
            percentile=percentile,
            value=float(value),
        )
        for percentile, value in zip(
            definition.mean_ratio_percentiles,
            percentile_values,
            strict=True,
        )
    )

    tetrahedron_count = len(tetrahedra)

    bands = tuple(
        QualityBandCount(
            upper_limit=band,
            element_count=int(np.count_nonzero(quality.mean_ratios < band)),
            element_fraction=float(
                np.count_nonzero(quality.mean_ratios < band) / tetrahedron_count
            ),
        )
        for band in definition.mean_ratio_bands
    )

    result = TetrahedralMeshQualityResult(
        node_count=len(points),
        tetrahedron_count=tetrahedron_count,
        positive_orientation_count=int(
            np.count_nonzero(quality.signed_volumes_mm3 > volume_threshold)
        ),
        negative_orientation_count=int(
            np.count_nonzero(quality.signed_volumes_mm3 < -volume_threshold)
        ),
        degenerate_count=int(np.count_nonzero(degenerate_mask)),
        minimum_volume_mm3=float(np.min(quality.absolute_volumes_mm3)),
        maximum_volume_mm3=float(np.max(quality.absolute_volumes_mm3)),
        mean_volume_mm3=float(np.mean(quality.absolute_volumes_mm3)),
        minimum_mean_ratio=float(np.min(quality.mean_ratios)),
        maximum_mean_ratio=float(np.max(quality.mean_ratios)),
        mean_mean_ratio=float(np.mean(quality.mean_ratios)),
        minimum_edge_ratio=float(np.min(quality.edge_ratios)),
        maximum_edge_ratio=float(np.max(quality.edge_ratios)),
        mean_edge_ratio=float(np.mean(quality.edge_ratios)),
        mean_ratio_percentiles=percentiles,
        mean_ratio_bands=bands,
    )

    validate_tetrahedral_mesh_quality(
        result,
        definition,
    )

    return result


def validate_tetrahedral_mesh_quality(
    result: TetrahedralMeshQualityResult,
    definition: MeshQualityDefinition,
) -> None:
    """Apply preliminary mesh-safety rejection gates."""

    if result.node_count <= 0:
        raise RuntimeError("Quality analysis found no mesh nodes.")

    if result.tetrahedron_count <= 0:
        raise RuntimeError("Quality analysis found no tetrahedra.")

    if result.degenerate_count > 0:
        raise RuntimeError("Mesh contains degenerate tetrahedra.")

    if result.minimum_volume_mm3 <= definition.minimum_tetrahedron_volume_mm3:
        raise RuntimeError("Minimum tetrahedron volume violates the controlled safety threshold.")

    if result.minimum_mean_ratio < definition.minimum_mean_ratio:
        raise RuntimeError("Minimum mean-ratio quality violates the controlled safety threshold.")

    if result.maximum_edge_ratio > definition.maximum_edge_ratio:
        raise RuntimeError("Maximum edge ratio violates the controlled safety threshold.")

    if result.has_mixed_orientation and not definition.allow_mixed_orientation:
        raise RuntimeError("Mesh contains mixed tetrahedron orientations.")

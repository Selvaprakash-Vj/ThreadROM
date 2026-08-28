"""Semantic mechanics extraction for CalculiX FEM results."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True, slots=True)
class BoltFreeSpanStressRegion:
    """Semantically derived bolt free-span stress region."""

    free_span_start_z_mm: float
    free_span_end_z_mm: float
    band_start_z_mm: float
    band_end_z_mm: float
    selected_element_indices: tuple[int, ...]

    @property
    def free_span_length_mm(self) -> float:
        """Return the physical under-head to engagement-entry span."""

        return (
            self.free_span_end_z_mm
            - self.free_span_start_z_mm
        )


@dataclass(frozen=True, slots=True)
class CompleteJointDeformationState:
    """Certified semantic deformation state of the joint."""

    free_span_start_z_mm: float
    free_span_end_z_mm: float
    free_span_length_mm: float
    head_bearing_mean_uz_mm: float
    nut_bearing_mean_uz_mm: float
    member_shortening_mm: float
    bolt_under_head_mean_uz_mm: float
    bolt_engagement_entry_mean_uz_mm: float
    bolt_geometric_change_mm: float
    bolt_thermal_free_change_mm: float
    bolt_mechanical_extension_mm: float
    engagement_entry_node_count: int


@dataclass(frozen=True, slots=True)
class CompleteJointAxialStressState:
    """Certified semantic axial-stress state of the joint."""

    bolt_region: BoltFreeSpanStressRegion
    bolt: TetrahedralAxialStressSummary
    head_side_member: TetrahedralAxialStressSummary
    nut_side_member: TetrahedralAxialStressSummary


@dataclass(frozen=True, slots=True)
class TetrahedralAxialStressSummary:
    """Axial SZZ statistics over a tetrahedral region."""

    mean_szz_mpa: float
    median_szz_mpa: float
    element_count: int
    total_volume_mm3: float


def derive_bolt_free_span_stress_region(
    *,
    points_mm: NDArray[np.float64],
    bolt_tetrahedra: NDArray[np.int64],
    under_head_triangles: NDArray[np.int64],
    nut_thread_triangles: NDArray[np.int64],
    band_start_fraction: float,
    band_end_fraction: float,
) -> BoltFreeSpanStressRegion:
    """Derive the certified bolt diagnostic band from mesh semantics.

    Phase 2 defines the physical free span from the mean Z of the
    bolt under-head bearing nodes to the minimum Z of the nut
    internal-thread nodes. Bolt tetrahedra are then selected by
    element-centroid Z using the governed fractional band.
    """

    if (
        not np.isfinite(band_start_fraction)
        or not np.isfinite(band_end_fraction)
        or band_start_fraction < 0.0
        or band_end_fraction > 1.0
        or band_start_fraction >= band_end_fraction
    ):
        raise ValueError(
            "Band fractions must satisfy "
            "0 <= start < end <= 1."
        )

    if (
        bolt_tetrahedra.ndim != 2
        or bolt_tetrahedra.shape[1] != 4
        or len(bolt_tetrahedra) == 0
    ):
        raise ValueError(
            "bolt_tetrahedra must have shape (n, 4)."
        )

    for name, triangles in (
        (
            "under_head_triangles",
            under_head_triangles,
        ),
        (
            "nut_thread_triangles",
            nut_thread_triangles,
        ),
    ):
        if (
            triangles.ndim != 2
            or triangles.shape[1] != 3
            or len(triangles) == 0
        ):
            raise ValueError(
                f"{name} must have shape (n, 3)."
            )

    under_head_nodes = np.unique(
        under_head_triangles.reshape(-1)
    )

    nut_thread_nodes = np.unique(
        nut_thread_triangles.reshape(-1)
    )

    free_span_start_z = float(
        np.mean(
            points_mm[
                under_head_nodes,
                2,
            ]
        )
    )

    free_span_end_z = float(
        np.min(
            points_mm[
                nut_thread_nodes,
                2,
            ]
        )
    )

    free_span_length = (
        free_span_end_z
        - free_span_start_z
    )

    if (
        not np.isfinite(free_span_length)
        or free_span_length <= 0.0
    ):
        raise ValueError(
            "Derived bolt free span must be finite and positive."
        )

    band_start_z = (
        free_span_start_z
        + band_start_fraction
        * free_span_length
    )

    band_end_z = (
        free_span_start_z
        + band_end_fraction
        * free_span_length
    )

    centroid_z = points_mm[
        bolt_tetrahedra
    ].mean(
        axis=1
    )[:, 2]

    mask = (
        (centroid_z >= band_start_z)
        & (centroid_z <= band_end_z)
    )

    selected = tuple(
        int(index)
        for index in np.flatnonzero(mask)
    )

    if not selected:
        raise ValueError(
            "Derived bolt stress band contains no tetrahedra."
        )

    return BoltFreeSpanStressRegion(
        free_span_start_z_mm=free_span_start_z,
        free_span_end_z_mm=free_span_end_z,
        band_start_z_mm=band_start_z,
        band_end_z_mm=band_end_z,
        selected_element_indices=selected,
    )


def tetrahedral_volumes_mm3(
    points_mm: NDArray[np.float64],
    tetrahedra: NDArray[np.int64],
) -> NDArray[np.float64]:
    """Return physical volumes for four-node tetrahedra."""

    if tetrahedra.ndim != 2 or tetrahedra.shape[1] != 4:
        raise ValueError(
            "tetrahedra must have shape (n, 4)."
        )

    if len(tetrahedra) == 0:
        raise ValueError(
            "At least one tetrahedron is required."
        )

    xyz = points_mm[
        tetrahedra
    ]

    volumes = (
        np.abs(
            np.einsum(
                "ij,ij->i",
                xyz[:, 0, :] - xyz[:, 3, :],
                np.cross(
                    xyz[:, 1, :] - xyz[:, 3, :],
                    xyz[:, 2, :] - xyz[:, 3, :],
                ),
            )
        )
        / 6.0
    )

    if np.any(
        volumes <= 0.0
    ):
        raise ValueError(
            "Degenerate tetrahedron detected."
        )

    return volumes


def summarize_tetrahedral_szz(
    *,
    points_mm: NDArray[np.float64],
    tetrahedra: NDArray[np.int64],
    nodal_szz_mpa: Mapping[int, float],
) -> TetrahedralAxialStressSummary:
    """Reproduce the certified Phase-2 tetrahedral SZZ metric.

    Each element SZZ is the arithmetic mean of its four nodal SZZ
    values. The reported mean is tetrahedron-volume weighted; the
    reported median is the unweighted median of element SZZ.
    """

    volumes = tetrahedral_volumes_mm3(
        points_mm,
        tetrahedra,
    )

    element_szz = np.asarray(
        [
            np.mean(
                [
                    nodal_szz_mpa[
                        int(node_index)
                    ]
                    for node_index in tetrahedron
                ]
            )
            for tetrahedron in tetrahedra
        ],
        dtype=float,
    )

    if not np.all(
        np.isfinite(element_szz)
    ):
        raise ValueError(
            "Non-finite nodal SZZ value encountered."
        )

    total_volume = float(
        np.sum(volumes)
    )

    mean_szz = float(
        np.sum(
            volumes
            * element_szz
        )
        / total_volume
    )

    median_szz = float(
        np.median(
            element_szz
        )
    )

    return TetrahedralAxialStressSummary(
        mean_szz_mpa=mean_szz,
        median_szz_mpa=median_szz,
        element_count=len(tetrahedra),
        total_volume_mm3=total_volume,
    )

def summarize_complete_joint_axial_state(
    *,
    points_mm: NDArray[np.float64],
    bolt_tetrahedra: NDArray[np.int64],
    head_side_member_tetrahedra: NDArray[np.int64],
    nut_side_member_tetrahedra: NDArray[np.int64],
    under_head_triangles: NDArray[np.int64],
    nut_thread_triangles: NDArray[np.int64],
    band_start_fraction: float,
    band_end_fraction: float,
    nodal_szz_mpa: Mapping[int, float],
) -> CompleteJointAxialStressState:
    """Build the certified axial state from semantic mesh regions.

    The bolt uses the governed free-span diagnostic band.
    Both clamped members use their complete tetrahedral components,
    matching the Phase-2 certification calculation.
    """

    bolt_region = derive_bolt_free_span_stress_region(
        points_mm=points_mm,
        bolt_tetrahedra=bolt_tetrahedra,
        under_head_triangles=under_head_triangles,
        nut_thread_triangles=nut_thread_triangles,
        band_start_fraction=band_start_fraction,
        band_end_fraction=band_end_fraction,
    )

    selected_indices = np.asarray(
        bolt_region.selected_element_indices,
        dtype=np.int64,
    )

    selected_bolt_tetrahedra = bolt_tetrahedra[
        selected_indices
    ]

    bolt_summary = summarize_tetrahedral_szz(
        points_mm=points_mm,
        tetrahedra=selected_bolt_tetrahedra,
        nodal_szz_mpa=nodal_szz_mpa,
    )

    head_summary = summarize_tetrahedral_szz(
        points_mm=points_mm,
        tetrahedra=head_side_member_tetrahedra,
        nodal_szz_mpa=nodal_szz_mpa,
    )

    nut_summary = summarize_tetrahedral_szz(
        points_mm=points_mm,
        tetrahedra=nut_side_member_tetrahedra,
        nodal_szz_mpa=nodal_szz_mpa,
    )

    return CompleteJointAxialStressState(
        bolt_region=bolt_region,
        bolt=bolt_summary,
        head_side_member=head_summary,
        nut_side_member=nut_summary,
    )

def summarize_complete_joint_deformation(
    *,
    points_mm: NDArray[np.float64],
    under_head_triangles: NDArray[np.int64],
    head_member_bearing_triangles: NDArray[np.int64],
    nut_member_bearing_triangles: NDArray[np.int64],
    nut_thread_triangles: NDArray[np.int64],
    bolt_thread_triangles: NDArray[np.int64],
    nodal_uz_mm: Mapping[int, float],
    thermal_expansion_coefficient_per_c: float,
    equivalent_delta_temperature_c: float,
) -> CompleteJointDeformationState:
    """Reproduce the certified Phase-2 joint deformation metrics."""

    for name, triangles in (
        (
            "under_head_triangles",
            under_head_triangles,
        ),
        (
            "head_member_bearing_triangles",
            head_member_bearing_triangles,
        ),
        (
            "nut_member_bearing_triangles",
            nut_member_bearing_triangles,
        ),
        (
            "nut_thread_triangles",
            nut_thread_triangles,
        ),
        (
            "bolt_thread_triangles",
            bolt_thread_triangles,
        ),
    ):
        if (
            triangles.ndim != 2
            or triangles.shape[1] != 3
            or len(triangles) == 0
        ):
            raise ValueError(
                f"{name} must have shape (n, 3)."
            )

    if (
        not np.isfinite(
            thermal_expansion_coefficient_per_c
        )
        or thermal_expansion_coefficient_per_c <= 0.0
    ):
        raise ValueError(
            "Thermal expansion coefficient must be "
            "finite and positive."
        )

    if not np.isfinite(
        equivalent_delta_temperature_c
    ):
        raise ValueError(
            "Equivalent delta temperature must be finite."
        )

    under_head_nodes = np.unique(
        under_head_triangles.reshape(-1)
    )

    head_bearing_nodes = np.unique(
        head_member_bearing_triangles.reshape(-1)
    )

    nut_bearing_nodes = np.unique(
        nut_member_bearing_triangles.reshape(-1)
    )

    nut_thread_nodes = np.unique(
        nut_thread_triangles.reshape(-1)
    )

    bolt_thread_nodes = np.unique(
        bolt_thread_triangles.reshape(-1)
    )

    free_span_start_z = float(
        np.mean(
            points_mm[
                under_head_nodes,
                2,
            ]
        )
    )

    free_span_end_z = float(
        np.min(
            points_mm[
                nut_thread_nodes,
                2,
            ]
        )
    )

    free_span_length = (
        free_span_end_z
        - free_span_start_z
    )

    if (
        not np.isfinite(free_span_length)
        or free_span_length <= 0.0
    ):
        raise ValueError(
            "Derived bolt free span must be finite and positive."
        )

    bolt_thread_z = points_mm[
        bolt_thread_nodes,
        2,
    ]

    entry_mask = np.isclose(
        bolt_thread_z,
        free_span_end_z,
        atol=1.0e-9,
    )

    entry_nodes = bolt_thread_nodes[
        entry_mask
    ]

    if len(entry_nodes) == 0:
        raise ValueError(
            "No bolt thread nodes found on "
            "the engagement-entry plane."
        )

    def mean_uz(
        node_indices: NDArray[np.int64],
    ) -> float:
        values = np.asarray(
            [
                nodal_uz_mm[
                    int(node_index)
                ]
                for node_index in node_indices
            ],
            dtype=float,
        )

        if not np.all(
            np.isfinite(values)
        ):
            raise ValueError(
                "Non-finite nodal UZ value encountered."
            )

        return float(
            np.mean(values)
        )

    head_bearing_uz = mean_uz(
        head_bearing_nodes
    )

    nut_bearing_uz = mean_uz(
        nut_bearing_nodes
    )

    member_shortening = (
        head_bearing_uz
        - nut_bearing_uz
    )

    bolt_under_head_uz = mean_uz(
        under_head_nodes
    )

    bolt_entry_uz = mean_uz(
        entry_nodes
    )

    geometric_bolt_change = (
        bolt_entry_uz
        - bolt_under_head_uz
    )

    thermal_free_change = (
        thermal_expansion_coefficient_per_c
        * equivalent_delta_temperature_c
        * free_span_length
    )

    mechanical_bolt_extension = (
        geometric_bolt_change
        - thermal_free_change
    )

    return CompleteJointDeformationState(
        free_span_start_z_mm=free_span_start_z,
        free_span_end_z_mm=free_span_end_z,
        free_span_length_mm=free_span_length,
        head_bearing_mean_uz_mm=head_bearing_uz,
        nut_bearing_mean_uz_mm=nut_bearing_uz,
        member_shortening_mm=member_shortening,
        bolt_under_head_mean_uz_mm=bolt_under_head_uz,
        bolt_engagement_entry_mean_uz_mm=bolt_entry_uz,
        bolt_geometric_change_mm=geometric_bolt_change,
        bolt_thermal_free_change_mm=thermal_free_change,
        bolt_mechanical_extension_mm=(
            mechanical_bolt_extension
        ),
        engagement_entry_node_count=len(
            entry_nodes
        ),
    )

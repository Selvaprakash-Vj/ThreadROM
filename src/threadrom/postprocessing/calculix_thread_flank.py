"""Semantic thread-flank stress diagnostics for CalculiX results.

This module reproduces the certified Phase-2 solid-STRESS
directionality diagnostic. It is not a native CPRESS/contact-pressure
calculation and must not be interpreted as a strength criterion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


NodalStressComponents = tuple[
    float,
    float,
    float,
    float,
    float,
    float,
]


@dataclass(frozen=True, slots=True)
class ThreadFlankStressSummary:
    """Projected compressive-stress statistics for one flank family."""

    name: str
    triangle_count: int
    area_mm2: float
    mean_compression_mpa: float
    median_compression_mpa: float
    p95_compression_mpa: float
    maximum_compression_mpa: float
    compressed_area_percent: float
    force_proxy_n: float


@dataclass(frozen=True, slots=True)
class ThreadFlankStressState:
    """Semantic engaged-thread flank directionality state."""

    engagement_min_z_mm: float
    engagement_max_z_mm: float
    engaged_triangle_count: int
    low_cluster_center_abs_nz: float
    high_cluster_center_abs_nz: float
    flank_threshold_abs_nz: float
    positive_z_flank: ThreadFlankStressSummary
    negative_z_flank: ThreadFlankStressSummary
    dominant_flank_name: str
    dominance_ratio: float


def summarize_engaged_bolt_thread_flanks(
    *,
    points_mm: NDArray[np.float64],
    bolt_thread_triangles: NDArray[np.int64],
    nut_thread_triangles: NDArray[np.int64],
    nodal_stress_mpa: Mapping[
        int,
        NodalStressComponents,
    ],
) -> ThreadFlankStressState:
    """Reproduce the certified engaged-thread flank diagnostic.

    The nut internal-thread nodes define the physical engagement span.
    Bolt-thread triangles are selected by triangle-centroid Z inside
    that span. Inclined flanks are then identified automatically by
    two-cluster separation of absolute surface-normal Z components.
    """

    for name, triangles in (
        (
            "bolt_thread_triangles",
            bolt_thread_triangles,
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

    nut_thread_nodes = np.unique(
        nut_thread_triangles.reshape(-1)
    )

    nut_thread_xyz = points_mm[
        nut_thread_nodes
    ]

    engagement_min_z = float(
        nut_thread_xyz[:, 2].min()
    )

    engagement_max_z = float(
        nut_thread_xyz[:, 2].max()
    )

    if (
        not np.isfinite(engagement_min_z)
        or not np.isfinite(engagement_max_z)
        or engagement_max_z <= engagement_min_z
    ):
        raise ValueError(
            "Nut thread must define a finite positive "
            "engagement span."
        )

    bolt_xyz_all = points_mm[
        bolt_thread_triangles
    ]

    bolt_centroid_all = bolt_xyz_all.mean(
        axis=1
    )

    engagement_mask = (
        (
            bolt_centroid_all[:, 2]
            >= engagement_min_z
        )
        & (
            bolt_centroid_all[:, 2]
            <= engagement_max_z
        )
    )

    triangles = bolt_thread_triangles[
        engagement_mask
    ]

    if len(triangles) == 0:
        raise ValueError(
            "No bolt-thread triangles found inside "
            "the nut engagement span."
        )

    xyz = points_mm[
        triangles
    ]

    # --------------------------------------------------------
    # Certified Phase-2 surface geometry.
    # --------------------------------------------------------

    edge_1 = (
        xyz[:, 1, :]
        - xyz[:, 0, :]
    )

    edge_2 = (
        xyz[:, 2, :]
        - xyz[:, 0, :]
    )

    cross = np.cross(
        edge_1,
        edge_2,
    )

    double_area = np.linalg.norm(
        cross,
        axis=1,
    )

    if np.any(
        double_area <= 0.0
    ):
        raise ValueError(
            "Degenerate thread triangle detected."
        )

    areas = (
        0.5
        * double_area
    )

    normals = (
        cross
        / double_area[:, None]
    )

    centroids = xyz.mean(
        axis=1
    )

    # Ensure normals point radially outward from the bolt axis.
    # This intentionally reproduces the Phase-2 convention:
    # the radial vector does not need to be normalized because
    # only the sign of the dot product is used.
    radial = centroids.copy()
    radial[:, 2] = 0.0

    radial_magnitude = np.linalg.norm(
        radial,
        axis=1,
    )

    if np.any(
        radial_magnitude <= 0.0
    ):
        raise ValueError(
            "Thread-triangle centroid lies on the bolt axis."
        )

    flip = (
        np.einsum(
            "ij,ij->i",
            normals,
            radial,
        )
        < 0.0
    )

    normals[flip] *= -1.0

    abs_nz = np.abs(
        normals[:, 2]
    )

    # --------------------------------------------------------
    # Certified automatic flank / crest-root classification.
    # --------------------------------------------------------

    low_center = float(
        np.quantile(
            abs_nz,
            0.20,
        )
    )

    high_center = float(
        np.quantile(
            abs_nz,
            0.80,
        )
    )

    for _ in range(100):
        low_distance = np.abs(
            abs_nz - low_center
        )

        high_distance = np.abs(
            abs_nz - high_center
        )

        high_group = (
            high_distance < low_distance
        )

        low_group = ~high_group

        if (
            not np.any(low_group)
            or not np.any(high_group)
        ):
            raise ValueError(
                "Thread-normal clustering did not resolve "
                "two non-empty geometric families."
            )

        new_low = float(
            abs_nz[
                low_group
            ].mean()
        )

        new_high = float(
            abs_nz[
                high_group
            ].mean()
        )

        if (
            abs(
                new_low - low_center
            ) < 1.0e-12
            and abs(
                new_high - high_center
            ) < 1.0e-12
        ):
            break

        low_center = new_low
        high_center = new_high

    if high_center >= low_center:
        flank_mask = high_group
    else:
        flank_mask = low_group

    threshold = (
        0.5
        * (
            low_center
            + high_center
        )
    )

    positive_flank = (
        flank_mask
        & (
            normals[:, 2] > 0.0
        )
    )

    negative_flank = (
        flank_mask
        & (
            normals[:, 2] < 0.0
        )
    )

    if not np.any(
        positive_flank
    ):
        raise ValueError(
            "No +Z-normal flank triangles resolved."
        )

    if not np.any(
        negative_flank
    ):
        raise ValueError(
            "No -Z-normal flank triangles resolved."
        )

    # --------------------------------------------------------
    # Certified triangle-average nodal STRESS projection.
    # CalculiX component order:
    # SXX, SYY, SZZ, SXY, SYZ, SZX.
    # --------------------------------------------------------

    surface_stress = np.empty(
        (
            len(triangles),
            6,
        ),
        dtype=float,
    )

    for triangle_index, triangle in enumerate(
        triangles
    ):
        node_values = []

        for node_index in triangle:
            try:
                values = np.asarray(
                    nodal_stress_mpa[
                        int(node_index)
                    ],
                    dtype=float,
                )
            except KeyError as exc:
                raise ValueError(
                    "Required thread-surface nodal stress "
                    f"is missing for node {int(node_index)}."
                ) from exc

            if values.shape != (6,):
                raise ValueError(
                    "Each nodal stress record must contain "
                    "six CalculiX stress components."
                )

            if not np.all(
                np.isfinite(values)
            ):
                raise ValueError(
                    "Non-finite nodal stress value encountered."
                )

            node_values.append(
                values
            )

        surface_stress[
            triangle_index
        ] = np.mean(
            node_values,
            axis=0,
        )

    tensor = np.zeros(
        (
            len(triangles),
            3,
            3,
        ),
        dtype=float,
    )

    tensor[:, 0, 0] = surface_stress[:, 0]
    tensor[:, 1, 1] = surface_stress[:, 1]
    tensor[:, 2, 2] = surface_stress[:, 2]

    tensor[:, 0, 1] = surface_stress[:, 3]
    tensor[:, 1, 0] = surface_stress[:, 3]

    tensor[:, 1, 2] = surface_stress[:, 4]
    tensor[:, 2, 1] = surface_stress[:, 4]

    tensor[:, 2, 0] = surface_stress[:, 5]
    tensor[:, 0, 2] = surface_stress[:, 5]

    normal_stress = np.einsum(
        "ti,tij,tj->t",
        normals,
        tensor,
        normals,
    )

    # Positive reporting value means compression.
    compression = np.maximum(
        -normal_stress,
        0.0,
    )

    def summarize(
        name: str,
        mask: NDArray[np.bool_],
    ) -> ThreadFlankStressSummary:
        a = areas[
            mask
        ]

        c = compression[
            mask
        ]

        total_area = float(
            np.sum(a)
        )

        mean_compression = float(
            np.sum(
                a * c
            )
            / total_area
        )

        compressed_area_percent = float(
            np.sum(
                a[
                    c > 0.0
                ]
            )
            / total_area
            * 100.0
        )

        # Diagnostic force proxy only.
        # MPa == N/mm?.
        force_proxy_n = float(
            np.sum(
                a * c
            )
        )

        return ThreadFlankStressSummary(
            name=name,
            triangle_count=int(
                mask.sum()
            ),
            area_mm2=total_area,
            mean_compression_mpa=mean_compression,
            median_compression_mpa=float(
                np.median(c)
            ),
            p95_compression_mpa=float(
                np.quantile(
                    c,
                    0.95,
                )
            ),
            maximum_compression_mpa=float(
                np.max(c)
            ),
            compressed_area_percent=(
                compressed_area_percent
            ),
            force_proxy_n=force_proxy_n,
        )

    positive = summarize(
        "+Z-normal flank",
        positive_flank,
    )

    negative = summarize(
        "-Z-normal flank",
        negative_flank,
    )

    if (
        positive.mean_compression_mpa
        >= negative.mean_compression_mpa
    ):
        dominant = positive
        opposite = negative
    else:
        dominant = negative
        opposite = positive

    dominance_ratio = (
        dominant.mean_compression_mpa
        / max(
            opposite.mean_compression_mpa,
            1.0e-12,
        )
    )

    return ThreadFlankStressState(
        engagement_min_z_mm=engagement_min_z,
        engagement_max_z_mm=engagement_max_z,
        engaged_triangle_count=len(
            triangles
        ),
        low_cluster_center_abs_nz=low_center,
        high_cluster_center_abs_nz=high_center,
        flank_threshold_abs_nz=threshold,
        positive_z_flank=positive,
        negative_z_flank=negative,
        dominant_flank_name=dominant.name,
        dominance_ratio=dominance_ratio,
    )

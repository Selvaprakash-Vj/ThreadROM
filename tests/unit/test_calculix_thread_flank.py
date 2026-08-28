"""Tests for semantic thread-flank stress diagnostics."""

import numpy as np
import pytest

from threadrom.postprocessing.calculix_thread_flank import (
    summarize_engaged_bolt_thread_flanks,
)


def _triangle_from_normal(
    *,
    center: tuple[float, float, float],
    normal: tuple[float, float, float],
) -> np.ndarray:
    n = np.asarray(
        normal,
        dtype=float,
    )

    n /= np.linalg.norm(
        n
    )

    e1 = np.asarray(
        [0.0, 1.0, 0.0],
        dtype=float,
    )

    e2 = np.cross(
        n,
        e1,
    )

    return np.asarray(
        [
            np.asarray(center) - 0.2 * e1 - 0.2 * e2,
            np.asarray(center) + 0.2 * e1 - 0.2 * e2,
            np.asarray(center) + 0.4 * e2,
        ],
        dtype=float,
    )


def _synthetic_thread_case(
    *,
    positive_compression_mpa: float = 10.0,
    negative_compression_mpa: float = 100.0,
):
    bolt_geometry = (
        _triangle_from_normal(
            center=(5.0, 0.0, 22.0),
            normal=(0.5, 0.0, 0.866025403784),
        ),
        _triangle_from_normal(
            center=(5.0, 0.0, 24.0),
            normal=(0.5, 0.0, -0.866025403784),
        ),
        _triangle_from_normal(
            center=(5.0, 0.0, 21.0),
            normal=(1.0, 0.0, 0.0),
        ),
        _triangle_from_normal(
            center=(5.0, 0.0, 26.0),
            normal=(1.0, 0.0, 0.0),
        ),
        # Outside the nut engagement span; must be excluded.
        _triangle_from_normal(
            center=(5.0, 0.0, 30.0),
            normal=(0.5, 0.0, 0.866025403784),
        ),
    )

    points = []
    bolt_triangles = []
    nodal_stress = {}

    compressions = (
        positive_compression_mpa,
        negative_compression_mpa,
        5.0,
        5.0,
        999.0,
    )

    for triangle, compression in zip(
        bolt_geometry,
        compressions,
        strict=True,
    ):
        start = len(
            points
        )

        points.extend(
            triangle
        )

        bolt_triangles.append(
            (
                start,
                start + 1,
                start + 2,
            )
        )

        # Isotropic compression makes n.sigma.n = -compression
        # for any triangle normal.
        for node_index in range(
            start,
            start + 3,
        ):
            nodal_stress[node_index] = (
                -compression,
                -compression,
                -compression,
                0.0,
                0.0,
                0.0,
            )

    nut_start = len(
        points
    )

    points.extend(
        [
            [6.0, 0.0, 20.0],
            [6.0, 1.0, 20.0],
            [6.0, 0.0, 28.0],
        ]
    )

    nut_triangles = np.asarray(
        [
            [
                nut_start,
                nut_start + 1,
                nut_start + 2,
            ]
        ],
        dtype=np.int64,
    )

    return (
        np.asarray(
            points,
            dtype=float,
        ),
        np.asarray(
            bolt_triangles,
            dtype=np.int64,
        ),
        nut_triangles,
        nodal_stress,
    )


def test_thread_flank_selection_uses_nut_engagement_span() -> None:
    (
        points,
        bolt_triangles,
        nut_triangles,
        nodal_stress,
    ) = _synthetic_thread_case()

    state = summarize_engaged_bolt_thread_flanks(
        points_mm=points,
        bolt_thread_triangles=bolt_triangles,
        nut_thread_triangles=nut_triangles,
        nodal_stress_mpa=nodal_stress,
    )

    assert state.engagement_min_z_mm == pytest.approx(
        20.0
    )

    assert state.engagement_max_z_mm == pytest.approx(
        28.0
    )

    assert state.engaged_triangle_count == 4


def test_thread_flank_projection_resolves_expected_dominance() -> None:
    (
        points,
        bolt_triangles,
        nut_triangles,
        nodal_stress,
    ) = _synthetic_thread_case(
        positive_compression_mpa=10.0,
        negative_compression_mpa=100.0,
    )

    state = summarize_engaged_bolt_thread_flanks(
        points_mm=points,
        bolt_thread_triangles=bolt_triangles,
        nut_thread_triangles=nut_triangles,
        nodal_stress_mpa=nodal_stress,
    )

    assert (
        state.positive_z_flank.triangle_count
        == 1
    )

    assert (
        state.negative_z_flank.triangle_count
        == 1
    )

    assert (
        state.positive_z_flank.mean_compression_mpa
        == pytest.approx(10.0)
    )

    assert (
        state.negative_z_flank.mean_compression_mpa
        == pytest.approx(100.0)
    )

    assert (
        state.positive_z_flank.compressed_area_percent
        == pytest.approx(100.0)
    )

    assert (
        state.negative_z_flank.compressed_area_percent
        == pytest.approx(100.0)
    )

    assert (
        state.dominant_flank_name
        == "-Z-normal flank"
    )

    assert state.dominance_ratio == pytest.approx(
        10.0
    )


def test_thread_flank_reports_compression_only() -> None:
    (
        points,
        bolt_triangles,
        nut_triangles,
        nodal_stress,
    ) = _synthetic_thread_case(
        positive_compression_mpa=-25.0,
        negative_compression_mpa=50.0,
    )

    state = summarize_engaged_bolt_thread_flanks(
        points_mm=points,
        bolt_thread_triangles=bolt_triangles,
        nut_thread_triangles=nut_triangles,
        nodal_stress_mpa=nodal_stress,
    )

    assert (
        state.positive_z_flank.mean_compression_mpa
        == pytest.approx(0.0)
    )

    assert (
        state.positive_z_flank.compressed_area_percent
        == pytest.approx(0.0)
    )

    assert (
        state.negative_z_flank.mean_compression_mpa
        == pytest.approx(50.0)
    )


def test_thread_flank_requires_both_axial_flank_families() -> None:
    (
        points,
        bolt_triangles,
        nut_triangles,
        nodal_stress,
    ) = _synthetic_thread_case()

    # Convert the only engaged -Z flank to another +Z flank.
    replacement = _triangle_from_normal(
        center=(5.0, 0.0, 24.0),
        normal=(0.5, 0.0, 0.866025403784),
    )

    points[
        bolt_triangles[1]
    ] = replacement

    with pytest.raises(
        ValueError,
        match="-Z-normal flank",
    ):
        summarize_engaged_bolt_thread_flanks(
            points_mm=points,
            bolt_thread_triangles=bolt_triangles,
            nut_thread_triangles=nut_triangles,
            nodal_stress_mpa=nodal_stress,
        )

"""Tests for semantic CalculiX mechanics extraction."""

import numpy as np
import pytest

from threadrom.postprocessing.calculix_semantic_mechanics import (
    derive_bolt_free_span_stress_region,
    summarize_complete_joint_axial_state,
    summarize_complete_joint_deformation,
    summarize_tetrahedral_szz,
    tetrahedral_volumes_mm3,
)


def test_tetrahedral_volumes_returns_physical_volume() -> None:
    points = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )

    tetrahedra = np.asarray(
        [
            [0, 1, 2, 3],
        ],
        dtype=np.int64,
    )

    volumes = tetrahedral_volumes_mm3(
        points,
        tetrahedra,
    )

    assert volumes == pytest.approx(
        [1.0 / 6.0]
    )


def test_szz_summary_uses_element_nodal_mean() -> None:
    points = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )

    tetrahedra = np.asarray(
        [
            [0, 1, 2, 3],
        ],
        dtype=np.int64,
    )

    summary = summarize_tetrahedral_szz(
        points_mm=points,
        tetrahedra=tetrahedra,
        nodal_szz_mpa={
            0: 100.0,
            1: 200.0,
            2: 300.0,
            3: 400.0,
        },
    )

    assert summary.mean_szz_mpa == pytest.approx(
        250.0
    )
    assert summary.median_szz_mpa == pytest.approx(
        250.0
    )
    assert summary.element_count == 1
    assert summary.total_volume_mm3 == pytest.approx(
        1.0 / 6.0
    )


def test_szz_mean_is_volume_weighted_but_median_is_not() -> None:
    points = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [2.0, 0.0, 0.0],
            [0.0, 2.0, 0.0],
            [0.0, 0.0, 2.0],
        ],
        dtype=float,
    )

    tetrahedra = np.asarray(
        [
            [0, 1, 2, 3],
            [0, 4, 5, 6],
        ],
        dtype=np.int64,
    )

    summary = summarize_tetrahedral_szz(
        points_mm=points,
        tetrahedra=tetrahedra,
        nodal_szz_mpa={
            0: 0.0,
            1: 0.0,
            2: 0.0,
            3: 0.0,
            4: 100.0,
            5: 100.0,
            6: 100.0,
        },
    )

    first_element_szz = 0.0
    second_element_szz = 75.0

    first_volume = 1.0 / 6.0
    second_volume = 8.0 / 6.0

    expected_mean = (
        first_volume * first_element_szz
        + second_volume * second_element_szz
    ) / (
        first_volume
        + second_volume
    )

    assert summary.mean_szz_mpa == pytest.approx(
        expected_mean
    )

    assert summary.median_szz_mpa == pytest.approx(
        37.5
    )


def test_szz_summary_rejects_degenerate_tetrahedron() -> None:
    points = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [1.0, 1.0, 0.0],
        ],
        dtype=float,
    )

    tetrahedra = np.asarray(
        [
            [0, 1, 2, 3],
        ],
        dtype=np.int64,
    )

    with pytest.raises(
        ValueError,
        match="Degenerate",
    ):
        summarize_tetrahedral_szz(
            points_mm=points,
            tetrahedra=tetrahedra,
            nodal_szz_mpa={
                0: 1.0,
                1: 1.0,
                2: 1.0,
                3: 1.0,
            },
        )

def _translated_tetrahedron(
    z_offset: float,
) -> np.ndarray:
    return np.asarray(
        [
            [0.0, 0.0, z_offset],
            [1.0, 0.0, z_offset],
            [0.0, 1.0, z_offset],
            [0.0, 0.0, z_offset + 1.0],
        ],
        dtype=float,
    )


def test_bolt_free_span_region_uses_semantic_boundaries() -> None:
    tetra_blocks = tuple(
        _translated_tetrahedron(z)
        for z in (
            2.25,
            7.25,
            12.25,
            17.25,
        )
    )

    tetra_points = np.vstack(
        tetra_blocks
    )

    under_head_start = len(tetra_points)

    extra_points = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 20.0],
            [1.0, 0.0, 20.0],
            [0.0, 1.0, 20.0],
        ],
        dtype=float,
    )

    points = np.vstack(
        (
            tetra_points,
            extra_points,
        )
    )

    tetrahedra = np.asarray(
        [
            [0, 1, 2, 3],
            [4, 5, 6, 7],
            [8, 9, 10, 11],
            [12, 13, 14, 15],
        ],
        dtype=np.int64,
    )

    under_head = np.asarray(
        [
            [
                under_head_start,
                under_head_start + 1,
                under_head_start + 2,
            ],
        ],
        dtype=np.int64,
    )

    nut_thread = np.asarray(
        [
            [
                under_head_start + 3,
                under_head_start + 4,
                under_head_start + 5,
            ],
        ],
        dtype=np.int64,
    )

    region = derive_bolt_free_span_stress_region(
        points_mm=points,
        bolt_tetrahedra=tetrahedra,
        under_head_triangles=under_head,
        nut_thread_triangles=nut_thread,
        band_start_fraction=0.25,
        band_end_fraction=0.75,
    )

    assert region.free_span_start_z_mm == pytest.approx(
        0.0
    )
    assert region.free_span_end_z_mm == pytest.approx(
        20.0
    )
    assert region.free_span_length_mm == pytest.approx(
        20.0
    )
    assert region.band_start_z_mm == pytest.approx(
        5.0
    )
    assert region.band_end_z_mm == pytest.approx(
        15.0
    )

    assert region.selected_element_indices == (
        1,
        2,
    )


def test_bolt_free_span_region_rejects_invalid_fractions() -> None:
    points = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 0.0, 20.0],
            [1.0, 0.0, 20.0],
            [0.0, 1.0, 20.0],
        ],
        dtype=float,
    )

    tetrahedra = np.asarray(
        [
            [0, 1, 2, 3],
        ],
        dtype=np.int64,
    )

    under_head = np.asarray(
        [
            [0, 1, 2],
        ],
        dtype=np.int64,
    )

    nut_thread = np.asarray(
        [
            [4, 5, 6],
        ],
        dtype=np.int64,
    )

    with pytest.raises(
        ValueError,
        match="Band fractions",
    ):
        derive_bolt_free_span_stress_region(
            points_mm=points,
            bolt_tetrahedra=tetrahedra,
            under_head_triangles=under_head,
            nut_thread_triangles=nut_thread,
            band_start_fraction=0.75,
            band_end_fraction=0.25,
        )


def test_bolt_free_span_region_rejects_nonpositive_span() -> None:
    points = np.asarray(
        [
            [0.0, 0.0, 20.0],
            [1.0, 0.0, 20.0],
            [0.0, 1.0, 20.0],
            [0.0, 0.0, 21.0],
            [0.0, 0.0, 10.0],
            [1.0, 0.0, 10.0],
            [0.0, 1.0, 10.0],
        ],
        dtype=float,
    )

    tetrahedra = np.asarray(
        [
            [0, 1, 2, 3],
        ],
        dtype=np.int64,
    )

    under_head = np.asarray(
        [
            [0, 1, 2],
        ],
        dtype=np.int64,
    )

    nut_thread = np.asarray(
        [
            [4, 5, 6],
        ],
        dtype=np.int64,
    )

    with pytest.raises(
        ValueError,
        match="free span",
    ):
        derive_bolt_free_span_stress_region(
            points_mm=points,
            bolt_tetrahedra=tetrahedra,
            under_head_triangles=under_head,
            nut_thread_triangles=nut_thread,
            band_start_fraction=0.25,
            band_end_fraction=0.75,
        )

def test_complete_joint_axial_state_uses_certified_regions() -> None:
    blocks = tuple(
        _translated_tetrahedron(z)
        for z in (
            7.0,
            12.0,
            -5.0,
            25.0,
        )
    )

    component_points = np.vstack(
        blocks
    )

    boundary_start = len(
        component_points
    )

    boundary_points = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 20.0],
            [1.0, 0.0, 20.0],
            [0.0, 1.0, 20.0],
        ],
        dtype=float,
    )

    points = np.vstack(
        (
            component_points,
            boundary_points,
        )
    )

    bolt_tetrahedra = np.asarray(
        [
            [0, 1, 2, 3],
            [4, 5, 6, 7],
        ],
        dtype=np.int64,
    )

    head_tetrahedra = np.asarray(
        [
            [8, 9, 10, 11],
        ],
        dtype=np.int64,
    )

    nut_tetrahedra = np.asarray(
        [
            [12, 13, 14, 15],
        ],
        dtype=np.int64,
    )

    under_head = np.asarray(
        [
            [
                boundary_start,
                boundary_start + 1,
                boundary_start + 2,
            ],
        ],
        dtype=np.int64,
    )

    nut_thread = np.asarray(
        [
            [
                boundary_start + 3,
                boundary_start + 4,
                boundary_start + 5,
            ],
        ],
        dtype=np.int64,
    )

    nodal_szz = {}

    for node in bolt_tetrahedra[0]:
        nodal_szz[int(node)] = 300.0

    for node in bolt_tetrahedra[1]:
        nodal_szz[int(node)] = 340.0

    for node in head_tetrahedra[0]:
        nodal_szz[int(node)] = -33.0

    for node in nut_tetrahedra[0]:
        nodal_szz[int(node)] = -32.0

    state = summarize_complete_joint_axial_state(
        points_mm=points,
        bolt_tetrahedra=bolt_tetrahedra,
        head_side_member_tetrahedra=head_tetrahedra,
        nut_side_member_tetrahedra=nut_tetrahedra,
        under_head_triangles=under_head,
        nut_thread_triangles=nut_thread,
        band_start_fraction=0.25,
        band_end_fraction=0.75,
        nodal_szz_mpa=nodal_szz,
    )

    assert (
        state.bolt_region.selected_element_indices
        == (0, 1)
    )

    assert state.bolt.mean_szz_mpa == pytest.approx(
        320.0
    )
    assert state.bolt.median_szz_mpa == pytest.approx(
        320.0
    )

    assert (
        state.head_side_member.mean_szz_mpa
        == pytest.approx(-33.0)
    )

    assert (
        state.nut_side_member.mean_szz_mpa
        == pytest.approx(-32.0)
    )

    assert state.bolt.element_count == 2
    assert state.head_side_member.element_count == 1
    assert state.nut_side_member.element_count == 1


def test_complete_joint_axial_state_preserves_physical_signs() -> None:
    blocks = tuple(
        _translated_tetrahedron(z)
        for z in (
            10.0,
            -5.0,
            25.0,
        )
    )

    component_points = np.vstack(
        blocks
    )

    boundary_start = len(
        component_points
    )

    points = np.vstack(
        (
            component_points,
            np.asarray(
                [
                    [0.0, 0.0, 0.0],
                    [1.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0],
                    [0.0, 0.0, 20.0],
                    [1.0, 0.0, 20.0],
                    [0.0, 1.0, 20.0],
                ],
                dtype=float,
            ),
        )
    )

    bolt = np.asarray(
        [
            [0, 1, 2, 3],
        ],
        dtype=np.int64,
    )

    head = np.asarray(
        [
            [4, 5, 6, 7],
        ],
        dtype=np.int64,
    )

    nut = np.asarray(
        [
            [8, 9, 10, 11],
        ],
        dtype=np.int64,
    )

    under_head = np.asarray(
        [
            [
                boundary_start,
                boundary_start + 1,
                boundary_start + 2,
            ],
        ],
        dtype=np.int64,
    )

    nut_thread = np.asarray(
        [
            [
                boundary_start + 3,
                boundary_start + 4,
                boundary_start + 5,
            ],
        ],
        dtype=np.int64,
    )

    nodal_szz = {
        **{
            int(node): 100.0
            for node in bolt[0]
        },
        **{
            int(node): -10.0
            for node in head[0]
        },
        **{
            int(node): -20.0
            for node in nut[0]
        },
    }

    state = summarize_complete_joint_axial_state(
        points_mm=points,
        bolt_tetrahedra=bolt,
        head_side_member_tetrahedra=head,
        nut_side_member_tetrahedra=nut,
        under_head_triangles=under_head,
        nut_thread_triangles=nut_thread,
        band_start_fraction=0.25,
        band_end_fraction=0.75,
        nodal_szz_mpa=nodal_szz,
    )

    assert state.bolt.mean_szz_mpa > 0.0
    assert state.head_side_member.mean_szz_mpa < 0.0
    assert state.nut_side_member.mean_szz_mpa < 0.0

def test_complete_joint_deformation_matches_certified_formula() -> None:
    points = np.asarray(
        [
            # Bolt under-head bearing, Z = 0.
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],

            # Head-member bearing, Z = 0.
            [2.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
            [2.0, 1.0, 0.0],

            # Nut-member bearing, Z = 20.
            [2.0, 0.0, 20.0],
            [3.0, 0.0, 20.0],
            [2.0, 1.0, 20.0],

            # Nut internal thread entry, Z = 20.
            [0.0, 0.0, 20.0],
            [1.0, 0.0, 20.0],
            [0.0, 1.0, 20.0],

            # Bolt thread entry, Z = 20.
            [4.0, 0.0, 20.0],
            [5.0, 0.0, 20.0],
            [4.0, 1.0, 20.0],

            # Additional bolt-thread face, Z = 21.
            [4.0, 0.0, 21.0],
            [5.0, 0.0, 21.0],
            [4.0, 1.0, 21.0],
        ],
        dtype=float,
    )

    under_head = np.asarray(
        [[0, 1, 2]],
        dtype=np.int64,
    )

    head_bearing = np.asarray(
        [[3, 4, 5]],
        dtype=np.int64,
    )

    nut_bearing = np.asarray(
        [[6, 7, 8]],
        dtype=np.int64,
    )

    nut_thread = np.asarray(
        [[9, 10, 11]],
        dtype=np.int64,
    )

    bolt_thread = np.asarray(
        [
            [12, 13, 14],
            [15, 16, 17],
        ],
        dtype=np.int64,
    )

    nodal_uz = {
        0: 0.008,
        1: 0.008,
        2: 0.008,

        3: 0.0014,
        4: 0.0014,
        5: 0.0014,

        6: -0.0018,
        7: -0.0018,
        8: -0.0018,

        12: -0.012,
        13: -0.012,
        14: -0.012,

        15: -0.020,
        16: -0.020,
        17: -0.020,
    }

    state = summarize_complete_joint_deformation(
        points_mm=points,
        under_head_triangles=under_head,
        head_member_bearing_triangles=head_bearing,
        nut_member_bearing_triangles=nut_bearing,
        nut_thread_triangles=nut_thread,
        bolt_thread_triangles=bolt_thread,
        nodal_uz_mm=nodal_uz,
        thermal_expansion_coefficient_per_c=1.2e-5,
        equivalent_delta_temperature_c=-250.0,
    )

    assert state.free_span_start_z_mm == pytest.approx(
        0.0
    )

    assert state.free_span_end_z_mm == pytest.approx(
        20.0
    )

    assert state.free_span_length_mm == pytest.approx(
        20.0
    )

    assert state.member_shortening_mm == pytest.approx(
        0.0032
    )

    assert state.bolt_geometric_change_mm == pytest.approx(
        -0.020
    )

    assert state.bolt_thermal_free_change_mm == pytest.approx(
        -0.060
    )

    assert state.bolt_mechanical_extension_mm == pytest.approx(
        0.040
    )

    assert state.engagement_entry_node_count == 3


def test_complete_joint_deformation_uses_entry_plane_only() -> None:
    points = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],

            [2.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
            [2.0, 1.0, 0.0],

            [2.0, 0.0, 20.0],
            [3.0, 0.0, 20.0],
            [2.0, 1.0, 20.0],

            [0.0, 0.0, 20.0],
            [1.0, 0.0, 20.0],
            [0.0, 1.0, 20.0],

            [4.0, 0.0, 20.0],
            [4.0, 0.0, 21.0],
            [4.0, 0.0, 22.0],
        ],
        dtype=float,
    )

    state = summarize_complete_joint_deformation(
        points_mm=points,
        under_head_triangles=np.asarray(
            [[0, 1, 2]],
            dtype=np.int64,
        ),
        head_member_bearing_triangles=np.asarray(
            [[3, 4, 5]],
            dtype=np.int64,
        ),
        nut_member_bearing_triangles=np.asarray(
            [[6, 7, 8]],
            dtype=np.int64,
        ),
        nut_thread_triangles=np.asarray(
            [[9, 10, 11]],
            dtype=np.int64,
        ),
        bolt_thread_triangles=np.asarray(
            [
                [12, 13, 14],
            ],
            dtype=np.int64,
        ),
        nodal_uz_mm={
            0: 0.0,
            1: 0.0,
            2: 0.0,
            3: 0.001,
            4: 0.001,
            5: 0.001,
            6: -0.001,
            7: -0.001,
            8: -0.001,
            12: -0.010,
        },
        thermal_expansion_coefficient_per_c=1.0e-5,
        equivalent_delta_temperature_c=-100.0,
    )

    assert state.engagement_entry_node_count == 1
    assert (
        state.bolt_engagement_entry_mean_uz_mm
        == pytest.approx(-0.010)
    )


def test_complete_joint_deformation_rejects_missing_entry_plane() -> None:
    points = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],

            [2.0, 0.0, 0.0],
            [3.0, 0.0, 0.0],
            [2.0, 1.0, 0.0],

            [2.0, 0.0, 20.0],
            [3.0, 0.0, 20.0],
            [2.0, 1.0, 20.0],

            [0.0, 0.0, 20.0],
            [1.0, 0.0, 20.0],
            [0.0, 1.0, 20.0],

            [4.0, 0.0, 21.0],
            [5.0, 0.0, 21.0],
            [4.0, 1.0, 21.0],
        ],
        dtype=float,
    )

    with pytest.raises(
        ValueError,
        match="engagement-entry",
    ):
        summarize_complete_joint_deformation(
            points_mm=points,
            under_head_triangles=np.asarray(
                [[0, 1, 2]],
                dtype=np.int64,
            ),
            head_member_bearing_triangles=np.asarray(
                [[3, 4, 5]],
                dtype=np.int64,
            ),
            nut_member_bearing_triangles=np.asarray(
                [[6, 7, 8]],
                dtype=np.int64,
            ),
            nut_thread_triangles=np.asarray(
                [[9, 10, 11]],
                dtype=np.int64,
            ),
            bolt_thread_triangles=np.asarray(
                [[12, 13, 14]],
                dtype=np.int64,
            ),
            nodal_uz_mm={},
            thermal_expansion_coefficient_per_c=1.2e-5,
            equivalent_delta_temperature_c=-250.0,
        )

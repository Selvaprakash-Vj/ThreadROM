"""Pretension/contact-surface exclusion regression test."""

from __future__ import annotations

import numpy as np
import pytest

from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixMeshData,
)
from threadrom.solver.complete_joint_physical_pretension import (
    _exclude_boundary_faces_touching_protected_nodes,
    _retain_thread_mating_flank_faces,
)


def test_excludes_contact_faces_touching_pretension_nodes() -> None:
    """Contact facets touching the internal cut are removed."""

    mesh_data = CompleteJointCalculixMeshData(
        points_mm=np.zeros((6, 3), dtype=np.float64),
        component_tetrahedra={},
        boundary_triangles={
            "BOLT_PRETENSION_SECTION": np.asarray(
                [[0, 1, 2]],
                dtype=np.int64,
            ),
            "BOLT_THREAD_SURFACES": np.asarray(
                [
                    [0, 3, 4],
                    [2, 3, 4],
                    [3, 4, 5],
                ],
                dtype=np.int64,
            ),
        },
        boundary_node_sets={
            "BOLT_PRETENSION_SECTION": (1, 2, 3),
            "BOLT_THREAD_SURFACES": (1, 3, 4, 5, 6),
        },
    )

    filtered, removed_count = (
        _exclude_boundary_faces_touching_protected_nodes(
            mesh_data,
            protected_boundary="BOLT_PRETENSION_SECTION",
            filtered_boundary="BOLT_THREAD_SURFACES",
        )
    )

    assert removed_count == 2

    np.testing.assert_array_equal(
        filtered.boundary_triangles["BOLT_THREAD_SURFACES"],
        np.asarray([[3, 4, 5]], dtype=np.int64),
    )

    assert filtered.boundary_node_sets["BOLT_THREAD_SURFACES"] == (
        4,
        5,
        6,
    )

    assert len(
        mesh_data.boundary_triangles["BOLT_THREAD_SURFACES"]
    ) == 3


def test_retains_only_non_cylindrical_thread_contact_faces() -> None:
    """Cylindrical crest/root facets are removed from thread contact."""

    mesh_data = CompleteJointCalculixMeshData(
        points_mm=np.asarray(
            [
                [1.0, -1.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.133974596216, 0.0, 0.5],
                [2.0, -1.0, 0.0],
                [2.0, 1.0, 0.0],
                [2.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        ),
        component_tetrahedra={},
        boundary_triangles={
            "NUT_INTERNAL_THREAD": np.asarray(
                [
                    [0, 1, 2],
                    [3, 4, 5],
                ],
                dtype=np.int64,
            ),
        },
        boundary_node_sets={
            "NUT_INTERNAL_THREAD": (
                1,
                2,
                3,
                4,
                5,
                6,
            ),
        },
    )

    filtered, removed_count = (
        _retain_thread_mating_flank_faces(
            mesh_data,
            filtered_boundary="NUT_INTERNAL_THREAD",
        )
    )

    assert removed_count == 1

    np.testing.assert_array_equal(
        filtered.boundary_triangles[
            "NUT_INTERNAL_THREAD"
        ],
        np.asarray(
            [[0, 1, 2]],
            dtype=np.int64,
        ),
    )

    assert (
        filtered.boundary_node_sets[
            "NUT_INTERNAL_THREAD"
        ]
        == (1, 2, 3)
    )

    assert (
        len(
            mesh_data.boundary_triangles[
                "NUT_INTERNAL_THREAD"
            ]
        )
        == 2
    )

    assert (
        mesh_data.boundary_node_sets[
            "NUT_INTERNAL_THREAD"
        ]
        == (1, 2, 3, 4, 5, 6)
    )


def test_rejects_ambiguous_thread_contact_face_orientation() -> None:
    """Intermediate radial-normal orientations fail closed."""

    mesh_data = CompleteJointCalculixMeshData(
        points_mm=np.asarray(
            [
                [1.0, -1.0, 0.0],
                [1.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        ),
        component_tetrahedra={},
        boundary_triangles={
            "NUT_INTERNAL_THREAD": np.asarray(
                [[0, 1, 2]],
                dtype=np.int64,
            ),
        },
        boundary_node_sets={
            "NUT_INTERNAL_THREAD": (
                1,
                2,
                3,
            ),
        },
    )

    with pytest.raises(
        RuntimeError,
        match="ambiguous radial-normal alignment",
    ):
        _retain_thread_mating_flank_faces(
            mesh_data,
            filtered_boundary="NUT_INTERNAL_THREAD",
        )

import numpy as np

from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixMeshData,
)

from threadrom.solver.complete_joint_continuous_preload import (
    derive_component_calculix_node_ids,
)


def test_derive_component_calculix_node_ids() -> None:
    mesh = CompleteJointCalculixMeshData(
        points_mm=np.zeros((8, 3), dtype=np.float64),
        component_tetrahedra={
            "BOLT": np.asarray(
                [
                    [0, 1, 2, 3],
                    [2, 3, 4, 5],
                ],
                dtype=np.int64,
            ),
            "NUT": np.asarray(
                [
                    [4, 5, 6, 7],
                ],
                dtype=np.int64,
            ),
        },
        boundary_triangles={},
        boundary_node_sets={},
    )

    node_ids = derive_component_calculix_node_ids(
        mesh,
        "BOLT",
    )

    # Meshio connectivity is zero-based.
    # CalculiX node numbering is one-based.
    assert node_ids == (1, 2, 3, 4, 5, 6)


def test_component_node_derivation_includes_wedges() -> None:
    mesh = CompleteJointCalculixMeshData(
        points_mm=np.zeros((10, 3), dtype=np.float64),
        component_tetrahedra={
            "BOLT": np.asarray(
                [[0, 1, 2, 3]],
                dtype=np.int64,
            ),
        },
        boundary_triangles={},
        boundary_node_sets={},
        component_wedges={
            "BOLT": np.asarray(
                [[3, 4, 5, 6, 7, 8]],
                dtype=np.int64,
            ),
        },
    )

    node_ids = derive_component_calculix_node_ids(
        mesh,
        "BOLT",
    )

    assert node_ids == tuple(range(1, 10))
"""Shared helpers for continuous-bolt preload workflows."""

from __future__ import annotations

import numpy as np

from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixMeshData,
)


def derive_component_calculix_node_ids(
    mesh_data: CompleteJointCalculixMeshData,
    component: str,
) -> tuple[int, ...]:
    """Return sorted one-based CalculiX node IDs for one component.

    Connectivity stored in ``CompleteJointCalculixMeshData`` uses
    zero-based Meshio indices. Returned node IDs are converted to the
    one-based numbering written into CalculiX decks.
    """

    try:
        tetrahedra = mesh_data.component_tetrahedra[component]
    except KeyError as error:
        raise ValueError(
            f"Unknown joint component: {component}"
        ) from error

    connectivity_blocks: list[np.ndarray] = []

    if len(tetrahedra) > 0:
        connectivity_blocks.append(
            np.asarray(
                tetrahedra,
                dtype=np.int64,
            ).reshape(-1)
        )

    wedges = mesh_data.component_wedges.get(component)

    if wedges is not None and len(wedges) > 0:
        connectivity_blocks.append(
            np.asarray(
                wedges,
                dtype=np.int64,
            ).reshape(-1)
        )

    if not connectivity_blocks:
        raise ValueError(
            f"Joint component {component} contains no volume elements."
        )

    zero_based_node_ids = np.unique(
        np.concatenate(connectivity_blocks)
    )

    if np.any(zero_based_node_ids < 0):
        raise ValueError(
            f"Joint component {component} contains negative node indices."
        )

    if np.any(zero_based_node_ids >= mesh_data.node_count):
        raise ValueError(
            f"Joint component {component} references nodes "
            "outside the mesh."
        )

    return tuple(
        int(node_id) + 1
        for node_id in zero_based_node_ids.tolist()
    )
def render_calculix_node_set(
    *,
    name: str,
    node_ids: tuple[int, ...],
    values_per_line: int = 16,
) -> str:
    """Render a validated CalculiX node set from one-based node IDs."""

    if not name or not name.strip():
        raise ValueError(
            "Node-set name must be non-empty."
        )

    if not node_ids:
        raise ValueError(
            "Node set must contain at least one node ID."
        )

    if any(node_id <= 0 for node_id in node_ids):
        raise ValueError(
            "CalculiX node IDs must be positive."
        )

    if len(set(node_ids)) != len(node_ids):
        raise ValueError(
            "CalculiX node set contains duplicate node IDs."
        )

    ordered_ids = tuple(sorted(node_ids))

    lines = [
        f"*NSET, NSET={name}",
    ]

    for start in range(
        0,
        len(ordered_ids),
        values_per_line,
    ):
        chunk = ordered_ids[
            start:start + values_per_line
        ]

        lines.append(
            ", ".join(
                str(node_id)
                for node_id in chunk
            )
        )

    return "\n".join(lines) + "\n"
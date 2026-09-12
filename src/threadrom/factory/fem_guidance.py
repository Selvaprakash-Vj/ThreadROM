"""Resolve geometry-relative FEM guidance into dimensional solver policy."""

from __future__ import annotations

import math

from threadrom.factory.fem_profile import (
    FemDistributedGuidancePolicy,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixMeshData,
)
from threadrom.solver.complete_joint_guidance import (
    DistributedGuidancePolicy,
)


def _boundary_node_ids(
    mesh_data: CompleteJointCalculixMeshData,
    name: str,
) -> tuple[int, ...]:
    matches = tuple(
        node_ids
        for boundary_name, node_ids
        in mesh_data.boundary_node_sets.items()
        if boundary_name.casefold() == name.casefold()
    )

    if len(matches) != 1:
        raise KeyError(
            "Could not uniquely resolve guidance boundary "
            f"{name!r}; matches={len(matches)}."
        )

    node_ids = tuple(sorted(set(matches[0])))

    if not node_ids:
        raise ValueError(
            f"Guidance boundary {name!r} contains no nodes."
        )

    return node_ids


def _radial_extent_mm(
    mesh_data: CompleteJointCalculixMeshData,
    node_ids: tuple[int, ...],
) -> tuple[float, float]:
    radii = tuple(
        math.hypot(
            float(mesh_data.points_mm[node_id - 1, 0]),
            float(mesh_data.points_mm[node_id - 1, 1]),
        )
        for node_id in node_ids
    )

    return min(radii), max(radii)


def resolve_fem_distributed_guidance_policy(
    *,
    mesh_data: CompleteJointCalculixMeshData,
    policy: FemDistributedGuidancePolicy,
    nominal_thread_diameter_mm: float,
) -> DistributedGuidancePolicy:
    """Resolve guidance from governed physical and semantic geometry."""

    if (
        not math.isfinite(nominal_thread_diameter_mm)
        or nominal_thread_diameter_mm <= 0.0
    ):
        raise ValueError(
            "Nominal thread diameter must be finite and positive."
        )

    bolt_head_side_nodes = _boundary_node_ids(
        mesh_data,
        "BOLT_HEAD_SIDES",
    )
    nut_outer_hex_nodes = _boundary_node_ids(
        mesh_data,
        "NUT_OUTER_HEX",
    )

    bolt_head_flat_radius_mm, _ = _radial_extent_mm(
        mesh_data,
        bolt_head_side_nodes,
    )
    nut_flat_radius_mm, _ = _radial_extent_mm(
        mesh_data,
        nut_outer_hex_nodes,
    )

    if bolt_head_flat_radius_mm <= 0.0:
        raise ValueError(
            "Bolt-head semantic flat radius must be positive."
        )

    thread_major_radius_mm = (
        0.5 * nominal_thread_diameter_mm
    )

    nut_annulus_width_mm = (
        nut_flat_radius_mm
        - thread_major_radius_mm
    )

    if nut_annulus_width_mm <= 0.0:
        raise ValueError(
            "Nominal thread major radius must lie inside "
            "the nut flat boundary."
        )

    bolt_head_max_radius_mm = (
        bolt_head_flat_radius_mm
        * policy.bolt_head_safe_radius_fraction
    )

    nut_min_radius_mm = (
        thread_major_radius_mm
        + policy.nut_inner_annulus_fraction
        * nut_annulus_width_mm
    )

    nut_max_radius_mm = (
        nut_flat_radius_mm
        - policy.nut_outer_inset_fraction
        * nut_annulus_width_mm
    )

    if not (
        0.0
        < nut_min_radius_mm
        < nut_max_radius_mm
    ):
        raise ValueError(
            "Resolved nut guidance annulus is invalid."
        )

    return DistributedGuidancePolicy(
        translation_sample_node_count=(
            policy.translation_sample_node_count
        ),
        rotation_sample_node_count=(
            policy.rotation_sample_node_count
        ),
        bolt_head_max_radius_mm=(
            bolt_head_max_radius_mm
        ),
        nut_min_radius_mm=nut_min_radius_mm,
        nut_max_radius_mm=nut_max_radius_mm,
    )

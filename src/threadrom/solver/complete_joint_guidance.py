"""Governed distributed rigid-mode guidance for complete-joint FEM."""

from __future__ import annotations

import math
from dataclasses import dataclass

from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixMeshData,
)


BOLT_HEAD_GUIDANCE_SAMPLE = "BOLT_HEAD_GUIDANCE_SAMPLE"
BOLT_HEAD_ROTATION_X_SAMPLE = "BOLT_HEAD_ROTATION_X_SAMPLE"
BOLT_HEAD_ROTATION_Y_SAMPLE = "BOLT_HEAD_ROTATION_Y_SAMPLE"

NUT_TRANSLATION_GUIDANCE_SAMPLE = (
    "NUT_TRANSLATION_GUIDANCE_SAMPLE"
)
NUT_ROTATION_GUIDANCE_SAMPLE = (
    "NUT_ROTATION_GUIDANCE_SAMPLE"
)
NUT_ROTATION_X_SAMPLE = "NUT_ROTATION_X_SAMPLE"
NUT_ROTATION_Y_SAMPLE = "NUT_ROTATION_Y_SAMPLE"
NUT_MEMBER_GUIDANCE_SAMPLE = "NUT_MEMBER_GUIDANCE_SAMPLE"

BOLT_HEAD_GUIDANCE_REFERENCE = (
    "BOLT_HEAD_GUIDANCE_REFERENCE"
)
NUT_TRANSLATION_GUIDANCE_REFERENCE = (
    "NUT_TRANSLATION_GUIDANCE_REFERENCE"
)
NUT_MEMBER_GUIDANCE_REFERENCE = (
    "NUT_MEMBER_GUIDANCE_REFERENCE"
)
NUT_ROTATION_GUIDANCE_REFERENCE = (
    "NUT_ROTATION_GUIDANCE_REFERENCE"
)
BOLT_HEAD_ROTATION_X_REFERENCE = (
    "BOLT_HEAD_ROTATION_X_REFERENCE"
)
BOLT_HEAD_ROTATION_Y_REFERENCE = (
    "BOLT_HEAD_ROTATION_Y_REFERENCE"
)
NUT_ROTATION_X_REFERENCE = "NUT_ROTATION_X_REFERENCE"
NUT_ROTATION_Y_REFERENCE = "NUT_ROTATION_Y_REFERENCE"


@dataclass(frozen=True, slots=True)
class DistributedGuidancePolicy:
    """Explicit governed geometry-independent guidance policy."""

    translation_sample_node_count: int
    rotation_sample_node_count: int
    bolt_head_max_radius_mm: float
    nut_min_radius_mm: float
    nut_max_radius_mm: float

    def __post_init__(self) -> None:
        if self.translation_sample_node_count <= 0:
            raise ValueError(
                "translation_sample_node_count must be positive."
            )

        if self.rotation_sample_node_count <= 0:
            raise ValueError(
                "rotation_sample_node_count must be positive."
            )

        for name, value in (
            (
                "bolt_head_max_radius_mm",
                self.bolt_head_max_radius_mm,
            ),
            ("nut_min_radius_mm", self.nut_min_radius_mm),
            ("nut_max_radius_mm", self.nut_max_radius_mm),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(
                    f"{name} must be finite and positive."
                )

        if self.nut_min_radius_mm >= self.nut_max_radius_mm:
            raise ValueError(
                "nut_min_radius_mm must be smaller than "
                "nut_max_radius_mm."
            )


@dataclass(frozen=True, slots=True)
class DistributedGuidanceDeck:
    """Rendered non-distorting rigid-mode guidance model."""

    lines: tuple[str, ...]
    reference_node_count: int
    sample_node_count: int
    distributing_coupling_count: int
    mean_rotation_mpc_count: int


def _resolve_boundary_node_ids(
    mesh_data: CompleteJointCalculixMeshData,
    requested_name: str,
) -> tuple[int, ...]:
    matches = tuple(
        node_ids
        for name, node_ids in mesh_data.boundary_node_sets.items()
        if name.casefold() == requested_name.casefold()
    )

    if len(matches) != 1:
        raise KeyError(
            "Could not uniquely resolve boundary "
            f"{requested_name!r}; matches={len(matches)}."
        )

    return matches[0]


def _sample_spatially_distributed_node_ids(
    mesh_data: CompleteJointCalculixMeshData,
    node_ids: tuple[int, ...],
    sample_count: int,
) -> tuple[int, ...]:
    """Select deterministic farthest-point samples."""

    unique_node_ids = tuple(sorted(set(node_ids)))

    if sample_count <= 0:
        raise ValueError(
            "Guidance sample count must be positive."
        )

    if sample_count > len(unique_node_ids):
        raise ValueError(
            "Guidance sample count exceeds available nodes."
        )

    coordinates = {
        node_id: (
            float(mesh_data.points_mm[node_id - 1, 0]),
            float(mesh_data.points_mm[node_id - 1, 1]),
            float(mesh_data.points_mm[node_id - 1, 2]),
        )
        for node_id in unique_node_ids
    }

    centroid = tuple(
        sum(
            coordinates[node_id][axis]
            for node_id in unique_node_ids
        )
        / len(unique_node_ids)
        for axis in range(3)
    )

    def squared_distance(
        first: tuple[float, float, float],
        second: tuple[float, float, float],
    ) -> float:
        return sum(
            (first[axis] - second[axis]) ** 2
            for axis in range(3)
        )

    first_node_id = max(
        unique_node_ids,
        key=lambda node_id: (
            squared_distance(
                coordinates[node_id],
                centroid,
            ),
            -node_id,
        ),
    )

    selected = [first_node_id]
    selected_set = {first_node_id}

    minimum_distance = {
        node_id: squared_distance(
            coordinates[node_id],
            coordinates[first_node_id],
        )
        for node_id in unique_node_ids
    }

    while len(selected) < sample_count:
        next_node_id = max(
            (
                node_id
                for node_id in unique_node_ids
                if node_id not in selected_set
            ),
            key=lambda node_id: (
                minimum_distance[node_id],
                -node_id,
            ),
        )

        selected.append(next_node_id)
        selected_set.add(next_node_id)

        for node_id in unique_node_ids:
            if node_id in selected_set:
                continue

            distance = squared_distance(
                coordinates[node_id],
                coordinates[next_node_id],
            )

            minimum_distance[node_id] = min(
                minimum_distance[node_id],
                distance,
            )

    return tuple(selected)


def _filter_node_ids_by_radius(
    mesh_data: CompleteJointCalculixMeshData,
    node_ids: tuple[int, ...],
    *,
    minimum_radius_mm: float,
    maximum_radius_mm: float,
) -> tuple[int, ...]:
    if minimum_radius_mm >= maximum_radius_mm:
        raise ValueError(
            "Minimum guidance radius must be smaller than "
            "maximum guidance radius."
        )

    filtered = tuple(
        node_id
        for node_id in node_ids
        if minimum_radius_mm
        < math.hypot(
            float(mesh_data.points_mm[node_id - 1, 0]),
            float(mesh_data.points_mm[node_id - 1, 1]),
        )
        < maximum_radius_mm
    )

    if not filtered:
        raise ValueError(
            "Guidance radial erosion removed all candidate nodes."
        )

    return filtered


def _format_node_identifier_rows(
    node_ids: tuple[int, ...],
    identifiers_per_row: int = 16,
) -> tuple[str, ...]:
    return tuple(
        ", ".join(
            str(node_id)
            for node_id in node_ids[
                start : start + identifiers_per_row
            ]
        )
        for start in range(
            0,
            len(node_ids),
            identifiers_per_row,
        )
    )


def _format_mean_rotation_mpc(
    node_ids: tuple[int, ...],
    reference_node_id: int,
) -> tuple[str, ...]:
    identifiers = [
        str(node_id)
        for node_id in node_ids
        for _ in range(3)
    ]
    identifiers.append(str(reference_node_id))

    rows: list[str] = []

    first = identifiers[:15]
    remaining = identifiers[15:]

    first_row = "MEANROT, " + ", ".join(first)
    if remaining:
        first_row += ","
    rows.append(first_row)

    while remaining:
        row_identifiers = remaining[:16]
        remaining = remaining[16:]

        row = ", ".join(row_identifiers)
        if remaining:
            row += ","

        rows.append(row)

    return tuple(rows)


def render_distributed_guidance_keywords(
    *,
    mesh_data: CompleteJointCalculixMeshData,
    nut_member_node_ids: tuple[int, ...],
    first_reference_node_id: int,
    first_element_id: int,
    policy: DistributedGuidancePolicy,
) -> DistributedGuidanceDeck:
    """Render deterministic distributed rigid-mode guidance."""

    bolt_head_nodes = _resolve_boundary_node_ids(
        mesh_data,
        "BOLT_HEAD_TOP",
    )
    bolt_head_side_nodes = _resolve_boundary_node_ids(
        mesh_data,
        "BOLT_HEAD_SIDES",
    )

    bolt_head_interior_nodes = tuple(
        sorted(
            set(bolt_head_nodes)
            - set(bolt_head_side_nodes)
        )
    )

    nut_upper_nodes = _resolve_boundary_node_ids(
        mesh_data,
        "NUT_UPPER_BEARING",
    )
    nut_internal_thread_nodes = _resolve_boundary_node_ids(
        mesh_data,
        "NUT_INTERNAL_THREAD",
    )
    nut_outer_hex_nodes = _resolve_boundary_node_ids(
        mesh_data,
        "NUT_OUTER_HEX",
    )

    nut_upper_interior_nodes = tuple(
        sorted(
            set(nut_upper_nodes)
            - set(nut_internal_thread_nodes)
            - set(nut_outer_hex_nodes)
        )
    )

    translation_count = policy.translation_sample_node_count
    rotation_count = policy.rotation_sample_node_count

    required_bolt_nodes = (
        translation_count + 2 * rotation_count
    )
    required_nut_nodes = (
        2 * translation_count + 2 * rotation_count
    )

    bolt_head_safe_nodes = _filter_node_ids_by_radius(
        mesh_data,
        bolt_head_interior_nodes,
        minimum_radius_mm=-1.0e-12,
        maximum_radius_mm=policy.bolt_head_max_radius_mm,
    )

    nut_upper_safe_nodes = _filter_node_ids_by_radius(
        mesh_data,
        nut_upper_interior_nodes,
        minimum_radius_mm=policy.nut_min_radius_mm,
        maximum_radius_mm=policy.nut_max_radius_mm,
    )

    if len(bolt_head_safe_nodes) < required_bolt_nodes:
        raise ValueError(
            "Bolt-head guidance safe zone contains "
            f"{len(bolt_head_safe_nodes)} nodes; "
            f"{required_bolt_nodes} required."
        )

    if len(nut_upper_safe_nodes) < required_nut_nodes:
        raise ValueError(
            "Nut guidance safe zone contains "
            f"{len(nut_upper_safe_nodes)} nodes; "
            f"{required_nut_nodes} required."
        )

    bolt_head_sample = _sample_spatially_distributed_node_ids(
        mesh_data,
        bolt_head_safe_nodes,
        required_bolt_nodes,
    )

    bolt_translation_end = translation_count
    bolt_rotation_x_end = (
        bolt_translation_end + rotation_count
    )

    bolt_translation_sample = (
        bolt_head_sample[:bolt_translation_end]
    )
    bolt_rotation_x_sample = (
        bolt_head_sample[
            bolt_translation_end:bolt_rotation_x_end
        ]
    )
    bolt_rotation_y_sample = (
        bolt_head_sample[bolt_rotation_x_end:]
    )

    nut_upper_sample = _sample_spatially_distributed_node_ids(
        mesh_data,
        nut_upper_safe_nodes,
        required_nut_nodes,
    )

    nut_translation_end = translation_count
    nut_rotation_z_end = (
        nut_translation_end + translation_count
    )
    nut_rotation_x_end = (
        nut_rotation_z_end + rotation_count
    )

    nut_translation_sample = (
        nut_upper_sample[:nut_translation_end]
    )
    nut_rotation_z_sample = (
        nut_upper_sample[
            nut_translation_end:nut_rotation_z_end
        ]
    )
    nut_rotation_x_sample = (
        nut_upper_sample[
            nut_rotation_z_end:nut_rotation_x_end
        ]
    )
    nut_rotation_y_sample = (
        nut_upper_sample[nut_rotation_x_end:]
    )

    nut_member_sample = (
        _sample_spatially_distributed_node_ids(
            mesh_data,
            nut_member_node_ids,
            translation_count,
        )
    )

    sample_sets = (
        (
            BOLT_HEAD_GUIDANCE_SAMPLE,
            bolt_translation_sample,
        ),
        (
            BOLT_HEAD_ROTATION_X_SAMPLE,
            bolt_rotation_x_sample,
        ),
        (
            BOLT_HEAD_ROTATION_Y_SAMPLE,
            bolt_rotation_y_sample,
        ),
        (
            NUT_TRANSLATION_GUIDANCE_SAMPLE,
            nut_translation_sample,
        ),
        (
            NUT_ROTATION_GUIDANCE_SAMPLE,
            nut_rotation_z_sample,
        ),
        (
            NUT_ROTATION_X_SAMPLE,
            nut_rotation_x_sample,
        ),
        (
            NUT_ROTATION_Y_SAMPLE,
            nut_rotation_y_sample,
        ),
        (
            NUT_MEMBER_GUIDANCE_SAMPLE,
            nut_member_sample,
        ),
    )

    all_sample_nodes = tuple(
        node_id
        for _, node_ids in sample_sets
        for node_id in node_ids
    )

    expected_sample_count = (
        4 * (translation_count + rotation_count)
    )

    if len(all_sample_nodes) != expected_sample_count:
        raise RuntimeError(
            "Distributed guidance sampled-node count "
            "does not match policy."
        )

    bolt_surface_samples = (
        bolt_translation_sample
        + bolt_rotation_x_sample
        + bolt_rotation_y_sample
    )
    nut_surface_samples = (
        nut_translation_sample
        + nut_rotation_z_sample
        + nut_rotation_x_sample
        + nut_rotation_y_sample
    )

    if len(set(bolt_surface_samples)) != len(
        bolt_surface_samples
    ):
        raise RuntimeError(
            "Bolt-head guidance samples overlap."
        )

    if len(set(nut_surface_samples)) != len(
        nut_surface_samples
    ):
        raise RuntimeError(
            "Nut guidance samples overlap."
        )

    reference_node_ids = tuple(
        first_reference_node_id + offset
        for offset in range(8)
    )

    (
        bolt_reference_node_id,
        nut_reference_node_id,
        member_reference_node_id,
        nut_rotation_z_reference_node_id,
        bolt_rotation_x_reference_node_id,
        bolt_rotation_y_reference_node_id,
        nut_rotation_x_reference_node_id,
        nut_rotation_y_reference_node_id,
    ) = reference_node_ids

    reference_nodes = (
        (
            BOLT_HEAD_GUIDANCE_REFERENCE,
            bolt_reference_node_id,
            (0.0, 0.0, 0.0),
        ),
        (
            NUT_TRANSLATION_GUIDANCE_REFERENCE,
            nut_reference_node_id,
            (0.0, 0.0, 0.0),
        ),
        (
            NUT_MEMBER_GUIDANCE_REFERENCE,
            member_reference_node_id,
            (0.0, 0.0, 0.0),
        ),
        (
            NUT_ROTATION_GUIDANCE_REFERENCE,
            nut_rotation_z_reference_node_id,
            (0.0, 0.0, 1.0),
        ),
        (
            BOLT_HEAD_ROTATION_X_REFERENCE,
            bolt_rotation_x_reference_node_id,
            (1.0, 0.0, 0.0),
        ),
        (
            BOLT_HEAD_ROTATION_Y_REFERENCE,
            bolt_rotation_y_reference_node_id,
            (0.0, 1.0, 0.0),
        ),
        (
            NUT_ROTATION_X_REFERENCE,
            nut_rotation_x_reference_node_id,
            (1.0, 0.0, 0.0),
        ),
        (
            NUT_ROTATION_Y_REFERENCE,
            nut_rotation_y_reference_node_id,
            (0.0, 1.0, 0.0),
        ),
    )

    coupling_definitions = (
        (
            "BOLT_HEAD_GUIDANCE_COUPLING",
            BOLT_HEAD_GUIDANCE_SAMPLE,
            first_element_id,
            bolt_reference_node_id,
        ),
        (
            "NUT_TRANSLATION_GUIDANCE_COUPLING",
            NUT_TRANSLATION_GUIDANCE_SAMPLE,
            first_element_id + 1,
            nut_reference_node_id,
        ),
        (
            "NUT_MEMBER_GUIDANCE_COUPLING",
            NUT_MEMBER_GUIDANCE_SAMPLE,
            first_element_id + 2,
            member_reference_node_id,
        ),
    )

    rotation_definitions = (
        (
            bolt_rotation_x_sample,
            bolt_rotation_x_reference_node_id,
        ),
        (
            bolt_rotation_y_sample,
            bolt_rotation_y_reference_node_id,
        ),
        (
            nut_rotation_x_sample,
            nut_rotation_x_reference_node_id,
        ),
        (
            nut_rotation_y_sample,
            nut_rotation_y_reference_node_id,
        ),
        (
            nut_rotation_z_sample,
            nut_rotation_z_reference_node_id,
        ),
    )

    lines: list[str] = [
        "** Distributed rigid-mode guidance",
    ]

    for set_name, node_ids in sample_sets:
        lines.extend(
            (
                f"*NSET, NSET={set_name}",
                *_format_node_identifier_rows(
                    tuple(sorted(node_ids))
                ),
            )
        )

    for reference_name, node_id, coordinates in reference_nodes:
        lines.extend(
            (
                f"*NODE, NSET={reference_name}",
                (
                    f"{node_id}, "
                    f"{coordinates[0]:.12e}, "
                    f"{coordinates[1]:.12e}, "
                    f"{coordinates[2]:.12e}"
                ),
            )
        )

    for (
        coupling_name,
        sample_name,
        element_id,
        reference_node_id,
    ) in coupling_definitions:
        lines.extend(
            (
                (
                    "*ELEMENT, TYPE=DCOUP3D, "
                    f"ELSET={coupling_name}"
                ),
                f"{element_id}, {reference_node_id}",
                (
                    "*DISTRIBUTING COUPLING, "
                    f"ELSET={coupling_name}"
                ),
                f"{sample_name}, 1.000000000000e+00",
            )
        )

    for (
        rotation_sample,
        rotation_reference_node_id,
    ) in rotation_definitions:
        lines.extend(
            (
                "*MPC",
                *_format_mean_rotation_mpc(
                    rotation_sample,
                    rotation_reference_node_id,
                ),
            )
        )

    return DistributedGuidanceDeck(
        lines=tuple(lines),
        reference_node_count=len(reference_nodes),
        sample_node_count=len(all_sample_nodes),
        distributing_coupling_count=len(
            coupling_definitions
        ),
        mean_rotation_mpc_count=len(
            rotation_definitions
        ),
    )

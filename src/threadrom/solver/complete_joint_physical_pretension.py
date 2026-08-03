"""Physical nonlinear pretension deck for the complete joint."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from threadrom.solver.complete_joint_boundary_regions import (
    CompleteJointBoundaryRegionDefinition,
    derive_complete_joint_boundary_regions,
    render_complete_joint_boundary_region_nsets,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixDeckSummary,
    CompleteJointCalculixMeshData,
    CompleteJointCalculixTransferDefinition,
    _calculix_surface_name,
    write_complete_joint_calculix_transfer_deck,
)
from threadrom.solver.complete_joint_contact import (
    CompleteJointContactDefinition,
    render_complete_joint_contact_keywords,
)
from threadrom.solver.complete_joint_pretension import (
    CompleteJointPretensionDefinition,
)

PRETENSION_REFERENCE_SET = "BOLT_PRETENSION_REFERENCE"

GUIDANCE_SAMPLE_NODE_COUNT = 48
ROTATION_GUIDANCE_SAMPLE_NODE_COUNT = 28

BOLT_HEAD_GUIDANCE_MAX_RADIUS_MM = 7.5
NUT_GUIDANCE_MIN_RADIUS_MM = 5.5
NUT_GUIDANCE_MAX_RADIUS_MM = 8.0

BOLT_HEAD_GUIDANCE_SAMPLE = "BOLT_HEAD_GUIDANCE_SAMPLE"
BOLT_HEAD_ROTATION_X_SAMPLE = "BOLT_HEAD_ROTATION_X_SAMPLE"
BOLT_HEAD_ROTATION_Y_SAMPLE = "BOLT_HEAD_ROTATION_Y_SAMPLE"

NUT_TRANSLATION_GUIDANCE_SAMPLE = "NUT_TRANSLATION_GUIDANCE_SAMPLE"
NUT_ROTATION_GUIDANCE_SAMPLE = "NUT_ROTATION_GUIDANCE_SAMPLE"
NUT_ROTATION_X_SAMPLE = "NUT_ROTATION_X_SAMPLE"
NUT_ROTATION_Y_SAMPLE = "NUT_ROTATION_Y_SAMPLE"

NUT_MEMBER_GUIDANCE_SAMPLE = "NUT_MEMBER_GUIDANCE_SAMPLE"

BOLT_HEAD_GUIDANCE_REFERENCE = "BOLT_HEAD_GUIDANCE_REFERENCE"
NUT_TRANSLATION_GUIDANCE_REFERENCE = "NUT_TRANSLATION_GUIDANCE_REFERENCE"
NUT_MEMBER_GUIDANCE_REFERENCE = "NUT_MEMBER_GUIDANCE_REFERENCE"
NUT_ROTATION_GUIDANCE_REFERENCE = "NUT_ROTATION_GUIDANCE_REFERENCE"

BOLT_HEAD_ROTATION_X_REFERENCE = "BOLT_HEAD_ROTATION_X_REFERENCE"
BOLT_HEAD_ROTATION_Y_REFERENCE = "BOLT_HEAD_ROTATION_Y_REFERENCE"
NUT_ROTATION_X_REFERENCE = "NUT_ROTATION_X_REFERENCE"
NUT_ROTATION_Y_REFERENCE = "NUT_ROTATION_Y_REFERENCE"


@dataclass(frozen=True)
class CompleteJointPhysicalPretensionDeckSummary:
    """Summary of one physical nonlinear pretension deck."""

    transfer: CompleteJointCalculixDeckSummary
    reference_node_id: int
    boundary_region_count: int
    boundary_region_node_count: int
    contact_pair_count: int
    interaction_count: int
    pretension_section_count: int
    preload_force_n: float
    preload_checkpoint_count: int
    restart_write_count: int
    guidance_reference_node_count: int
    guidance_sample_node_count: int
    distributing_coupling_count: int
    mean_rotation_mpc_count: int
    input_file_size_bytes: int


@dataclass(frozen=True)
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
    """Resolve one transferred boundary node set by name."""

    matches = tuple(
        node_ids
        for name, node_ids in (mesh_data.boundary_node_sets.items())
        if name.casefold() == requested_name.casefold()
    )

    if len(matches) != 1:
        raise KeyError(
            f"Could not uniquely resolve boundary {requested_name!r}; matches={len(matches)}."
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
        raise ValueError("Guidance sample count must be positive.")

    if sample_count > len(unique_node_ids):
        raise ValueError("Guidance sample count exceeds available nodes.")

    coordinates: dict[
        int,
        tuple[float, float, float],
    ] = {
        node_id: (
            float(mesh_data.points_mm[node_id - 1, 0]),
            float(mesh_data.points_mm[node_id - 1, 1]),
            float(mesh_data.points_mm[node_id - 1, 2]),
        )
        for node_id in unique_node_ids
    }

    centroid: tuple[float, float, float] = (
        sum(coordinates[node_id][0] for node_id in unique_node_ids) / len(unique_node_ids),
        sum(coordinates[node_id][1] for node_id in unique_node_ids) / len(unique_node_ids),
        sum(coordinates[node_id][2] for node_id in unique_node_ids) / len(unique_node_ids),
    )

    def squared_distance(
        first: tuple[float, float, float],
        second: tuple[float, float, float],
    ) -> float:
        return sum((first[axis] - second[axis]) ** 2 for axis in range(3))

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
            (node_id for node_id in unique_node_ids if node_id not in selected_set),
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
    """Keep nodes strictly inside one governed radial safe zone."""

    if minimum_radius_mm >= maximum_radius_mm:
        raise ValueError("Minimum guidance radius must be smaller than maximum guidance radius.")

    filtered_node_ids = tuple(
        node_id
        for node_id in node_ids
        if minimum_radius_mm
        < math.hypot(
            float(mesh_data.points_mm[node_id - 1, 0]),
            float(mesh_data.points_mm[node_id - 1, 1]),
        )
        < maximum_radius_mm
    )

    if not filtered_node_ids:
        raise ValueError("Guidance radial erosion removed all candidate nodes.")

    return filtered_node_ids


def _format_node_identifier_rows(
    node_ids: tuple[int, ...],
    identifiers_per_row: int = 16,
) -> tuple[str, ...]:
    """Format deterministic CalculiX node-set rows."""

    return tuple(
        ", ".join(
            str(node_id) for node_id in node_ids[start_index : (start_index + identifiers_per_row)]
        )
        for start_index in range(
            0,
            len(node_ids),
            identifiers_per_row,
        )
    )


def _format_mean_rotation_mpc(
    node_ids: tuple[int, ...],
    reference_node_id: int,
) -> tuple[str, ...]:
    """Render one CalculiX MEANROT MPC definition."""

    identifiers = [str(node_id) for node_id in node_ids for _ in range(3)]

    identifiers.append(str(reference_node_id))

    rows: list[str] = []
    first_row_capacity = 15
    first_identifiers = identifiers[:first_row_capacity]

    remaining = identifiers[first_row_capacity:]

    first_row = "MEANROT, " + ", ".join(first_identifiers)

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


def _render_distributed_guidance_keywords(
    mesh_data: CompleteJointCalculixMeshData,
    nut_member_node_ids: tuple[int, ...],
    first_reference_node_id: int,
    first_element_id: int,
) -> DistributedGuidanceDeck:
    """Render distributed rigid-mode guidance fixtures."""

    bolt_head_nodes = _resolve_boundary_node_ids(
        mesh_data,
        "BOLT_HEAD_TOP",
    )

    bolt_head_side_nodes = _resolve_boundary_node_ids(
        mesh_data,
        "BOLT_HEAD_SIDES",
    )

    bolt_head_interior_nodes = tuple(sorted(set(bolt_head_nodes) - set(bolt_head_side_nodes)))

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
        sorted(set(nut_upper_nodes) - set(nut_internal_thread_nodes) - set(nut_outer_hex_nodes))
    )

    required_bolt_guidance_nodes = (
        GUIDANCE_SAMPLE_NODE_COUNT + 2 * ROTATION_GUIDANCE_SAMPLE_NODE_COUNT
    )

    required_nut_guidance_nodes = (
        2 * GUIDANCE_SAMPLE_NODE_COUNT + 2 * ROTATION_GUIDANCE_SAMPLE_NODE_COUNT
    )

    bolt_head_safe_nodes = _filter_node_ids_by_radius(
        mesh_data,
        bolt_head_interior_nodes,
        minimum_radius_mm=-1.0e-12,
        maximum_radius_mm=(BOLT_HEAD_GUIDANCE_MAX_RADIUS_MM),
    )

    nut_upper_safe_nodes = _filter_node_ids_by_radius(
        mesh_data,
        nut_upper_interior_nodes,
        minimum_radius_mm=NUT_GUIDANCE_MIN_RADIUS_MM,
        maximum_radius_mm=NUT_GUIDANCE_MAX_RADIUS_MM,
    )

    if len(bolt_head_safe_nodes) < required_bolt_guidance_nodes:
        raise ValueError(
            "Bolt-head guidance safe zone contains "
            f"{len(bolt_head_safe_nodes)} nodes; "
            f"{required_bolt_guidance_nodes} required."
        )

    if len(nut_upper_safe_nodes) < required_nut_guidance_nodes:
        raise ValueError(
            "Nut guidance safe zone contains "
            f"{len(nut_upper_safe_nodes)} nodes; "
            f"{required_nut_guidance_nodes} required."
        )

    bolt_head_sample = _sample_spatially_distributed_node_ids(
        mesh_data,
        bolt_head_safe_nodes,
        (GUIDANCE_SAMPLE_NODE_COUNT + 2 * ROTATION_GUIDANCE_SAMPLE_NODE_COUNT),
    )

    bolt_translation_end = GUIDANCE_SAMPLE_NODE_COUNT
    bolt_rotation_x_end = bolt_translation_end + ROTATION_GUIDANCE_SAMPLE_NODE_COUNT

    bolt_translation_sample = bolt_head_sample[:bolt_translation_end]

    bolt_rotation_x_sample = bolt_head_sample[bolt_translation_end:bolt_rotation_x_end]

    bolt_rotation_y_sample = bolt_head_sample[bolt_rotation_x_end:]

    nut_upper_sample = _sample_spatially_distributed_node_ids(
        mesh_data,
        nut_upper_safe_nodes,
        (2 * GUIDANCE_SAMPLE_NODE_COUNT + 2 * ROTATION_GUIDANCE_SAMPLE_NODE_COUNT),
    )

    nut_translation_end = GUIDANCE_SAMPLE_NODE_COUNT

    nut_rotation_z_end = nut_translation_end + GUIDANCE_SAMPLE_NODE_COUNT

    nut_rotation_x_end = nut_rotation_z_end + ROTATION_GUIDANCE_SAMPLE_NODE_COUNT

    nut_translation_sample = nut_upper_sample[:nut_translation_end]

    nut_rotation_z_sample = nut_upper_sample[nut_translation_end:nut_rotation_z_end]

    nut_rotation_x_sample = nut_upper_sample[nut_rotation_z_end:nut_rotation_x_end]

    nut_rotation_y_sample = nut_upper_sample[nut_rotation_x_end:]

    nut_member_sample = _sample_spatially_distributed_node_ids(
        mesh_data,
        nut_member_node_ids,
        GUIDANCE_SAMPLE_NODE_COUNT,
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

    all_sample_nodes = tuple(node_id for _, node_ids in sample_sets for node_id in node_ids)

    if len(all_sample_nodes) != 304:
        raise RuntimeError("Distributed guidance must contain exactly 304 sampled node references.")

    bolt_surface_samples = bolt_translation_sample + bolt_rotation_x_sample + bolt_rotation_y_sample

    nut_surface_samples = (
        nut_translation_sample
        + nut_rotation_z_sample
        + nut_rotation_x_sample
        + nut_rotation_y_sample
    )

    if len(set(bolt_surface_samples)) != len(bolt_surface_samples):
        raise RuntimeError("Bolt-head guidance samples overlap.")

    if len(set(nut_surface_samples)) != len(nut_surface_samples):
        raise RuntimeError("Nut guidance samples overlap.")

    bolt_reference_node_id = first_reference_node_id
    nut_reference_node_id = first_reference_node_id + 1
    member_reference_node_id = first_reference_node_id + 2
    nut_rotation_z_reference_node_id = first_reference_node_id + 3
    bolt_rotation_x_reference_node_id = first_reference_node_id + 4
    bolt_rotation_y_reference_node_id = first_reference_node_id + 5
    nut_rotation_x_reference_node_id = first_reference_node_id + 6
    nut_rotation_y_reference_node_id = first_reference_node_id + 7

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
                *_format_node_identifier_rows(tuple(sorted(node_ids))),
            )
        )

    for (
        reference_name,
        node_id,
        coordinates,
    ) in reference_nodes:
        lines.extend(
            (
                f"*NODE, NSET={reference_name}",
                (f"{node_id}, {coordinates[0]:.12e}, {coordinates[1]:.12e}, {coordinates[2]:.12e}"),
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
                (f"*ELEMENT, TYPE=DCOUP3D, ELSET={coupling_name}"),
                f"{element_id}, {reference_node_id}",
                (f"*DISTRIBUTING COUPLING, ELSET={coupling_name}"),
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
        distributing_coupling_count=len(coupling_definitions),
        mean_rotation_mpc_count=len(rotation_definitions),
    )


def validate_physical_pretension_identities(
    transfer: CompleteJointCalculixTransferDefinition,
    contact: CompleteJointContactDefinition,
    boundary: CompleteJointBoundaryRegionDefinition,
    pretension: CompleteJointPretensionDefinition,
) -> None:
    """Verify identity consistency across the physical model."""

    identity_checks = (
        (
            "simulation",
            transfer.simulation_id,
            contact.simulation_id,
        ),
        (
            "boundary simulation",
            transfer.simulation_id,
            boundary.simulation_id,
        ),
        (
            "pretension simulation",
            transfer.simulation_id,
            pretension.simulation_id,
        ),
        (
            "contact mesh",
            transfer.mesh_id,
            contact.mesh_id,
        ),
        (
            "boundary mesh",
            transfer.mesh_id,
            boundary.mesh_id,
        ),
        (
            "pretension mesh",
            transfer.mesh_id,
            pretension.pretension_mesh_id,
        ),
        (
            "pretension assembly",
            transfer.assembly_id,
            pretension.assembly_id,
        ),
        (
            "pretension geometry",
            transfer.geometry_id,
            pretension.geometry_id,
        ),
        (
            "pretension contact model",
            contact.contact_model_id,
            pretension.contact_model_id,
        ),
        (
            "pretension boundary model",
            boundary.boundary_region_id,
            pretension.boundary_region_id,
        ),
    )

    for label, expected, actual in identity_checks:
        if expected != actual:
            raise ValueError(f"Physical pretension {label} identities differ.")

    if pretension.loading_mode != "FORCE":
        raise ValueError(
            "The baseline physical pretension model requires force-controlled loading."
        )

    if pretension.section_name not in (transfer.required_boundary_groups):
        raise ValueError(
            "The governed pretension section is missing from the transferred boundary groups."
        )


def _render_preload_checkpoint_steps(
    pretension: CompleteJointPretensionDefinition,
    reference_node_id: int,
) -> tuple[str, ...]:
    """Render governed preload steps with restart checkpoints."""

    schedule = pretension.load_schedule
    restart_policy = pretension.restart_policy

    boundary_lines = (
        "*BOUNDARY",
        "HEAD_MEMBER_SUPPORT_BAND, 1, 3, 0.0",
        f"{BOLT_HEAD_GUIDANCE_REFERENCE}, 1, 2, 0.0",
        f"{NUT_TRANSLATION_GUIDANCE_REFERENCE}, 1, 2, 0.0",
        f"{NUT_MEMBER_GUIDANCE_REFERENCE}, 1, 2, 0.0",
        f"{NUT_ROTATION_GUIDANCE_REFERENCE}, 1, 1, 0.0",
        f"{BOLT_HEAD_ROTATION_X_REFERENCE}, 1, 1, 0.0",
        f"{BOLT_HEAD_ROTATION_Y_REFERENCE}, 1, 1, 0.0",
        f"{NUT_ROTATION_X_REFERENCE}, 1, 1, 0.0",
        f"{NUT_ROTATION_Y_REFERENCE}, 1, 1, 0.0",
    )

    output_lines = (
        f"*NODE PRINT, NSET={PRETENSION_REFERENCE_SET}",
        "U",
        "RF",
        "*NODE PRINT, NSET=HEAD_MEMBER_SUPPORT_BAND, TOTALS=ONLY",
        "RF",
        "*NODE FILE",
        "U, RF",
        "*EL FILE",
        "S, E",
    )

    restart_keyword = f"*RESTART,WRITE,FREQUENCY={restart_policy.write_frequency_steps}"

    if restart_policy.overlay_latest:
        restart_keyword += ",OVERLAY"

    lines: list[str] = []

    for checkpoint_index, checkpoint_fraction in enumerate(
        schedule.checkpoint_fractions,
        start=1,
    ):
        target_force_n = pretension.preload_force_n * checkpoint_fraction

        lines.extend(
            (
                (f"** Step {checkpoint_index}: preload checkpoint {checkpoint_fraction:.6f}"),
                (f"*STEP, NLGEOM=YES, INC={schedule.maximum_increments_per_step}"),
                "*STATIC",
                (
                    f"{schedule.initial_time_increment:.12e}, "
                    f"{schedule.step_time:.12e}, "
                    f"{schedule.minimum_time_increment:.12e}, "
                    f"{schedule.maximum_time_increment:.12e}"
                ),
            )
        )

        if checkpoint_index == 1:
            if restart_policy.write_enabled:
                lines.append(restart_keyword)

            lines.extend(boundary_lines)

        lines.extend(
            (
                "*CLOAD",
                (f"{reference_node_id}, 1, {target_force_n:.12e}"),
                *output_lines,
                "*END STEP",
                "",
            )
        )

    return tuple(lines)


def write_complete_joint_physical_pretension_deck(
    mesh_data: CompleteJointCalculixMeshData,
    transfer: CompleteJointCalculixTransferDefinition,
    contact: CompleteJointContactDefinition,
    boundary: CompleteJointBoundaryRegionDefinition,
    pretension: CompleteJointPretensionDefinition,
    input_path: Path,
) -> CompleteJointPhysicalPretensionDeckSummary:
    """Write the first nonlinear complete-joint preload model."""

    validate_physical_pretension_identities(
        transfer,
        contact,
        boundary,
        pretension,
    )

    boundary_regions = derive_complete_joint_boundary_regions(
        mesh_data,
        boundary,
        transfer,
        contact,
    )

    transfer_summary = write_complete_joint_calculix_transfer_deck(
        mesh_data,
        transfer,
        input_path,
        internal_surface_normals={
            pretension.section_name: (
                0.0,
                0.0,
                1.0,
            ),
        },
    )

    boundary_lines = render_complete_joint_boundary_region_nsets(boundary_regions)

    contact_lines = render_complete_joint_contact_keywords(
        contact,
        transfer,
    )

    reference_node_id = mesh_data.node_count + 1

    guidance = _render_distributed_guidance_keywords(
        mesh_data,
        boundary_regions.region("nut_load").node_ids,
        reference_node_id + 1,
        mesh_data.element_count + 1,
    )

    pretension_surface_name = _calculix_surface_name(pretension.section_name)

    text = input_path.read_text(encoding="utf-8")

    text = text.replace(
        (f"{transfer.simulation_id} complete-joint mesh-transfer verification"),
        (f"{transfer.simulation_id} complete-joint physical pretension analysis"),
        1,
    )

    text = text.replace(
        "** Transfer-only deck: no contact or loading",
        ("** Physical deck: nonlinear contact and force-controlled bolt pretension"),
        1,
    )

    smoke_marker = "** Fully constrained zero-load solver-read smoke step"

    if smoke_marker not in text:
        raise RuntimeError("Transfer smoke-step replacement marker was not found.")

    preload_step_lines = _render_preload_checkpoint_steps(
        pretension,
        reference_node_id,
    )

    physical_lines = [
        "** Physical complete-joint pretension model",
        "**",
        *boundary_lines,
        "**",
        *guidance.lines,
        "**",
        f"*NODE, NSET={PRETENSION_REFERENCE_SET}",
        (
            f"{reference_node_id}, "
            f"0.000000000000e+00, "
            f"0.000000000000e+00, "
            f"{pretension.axial_position_mm:.12e}"
        ),
        (f"*PRE-TENSION SECTION, SURFACE={pretension_surface_name}, NODE={reference_node_id}"),
        ("0.000000000000e+00, 0.000000000000e+00, 1.000000000000e+00"),
        "**",
        "** Complete-joint nonlinear contact model",
        *contact_lines,
        "**",
        *preload_step_lines,
    ]

    marker_index = text.index(smoke_marker)

    text = text[:marker_index] + "\n".join(physical_lines)

    input_path.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )

    contact_pair_count = text.count("*CONTACT PAIR,")
    interaction_count = text.count("*SURFACE INTERACTION,")
    pretension_section_count = text.count("*PRE-TENSION SECTION,")
    step_count = text.count("*STEP,")
    restart_write_count = text.count("*RESTART,WRITE")

    if contact_pair_count != contact.expected_contact_pair_count:
        raise RuntimeError("Written contact-pair count does not match the governed expectation.")

    if interaction_count != 1:
        raise RuntimeError("Physical deck must contain exactly one surface interaction.")

    if pretension_section_count != 1:
        raise RuntimeError("Physical deck must contain exactly one pretension-section definition.")

    if step_count != pretension.load_schedule.checkpoint_count:
        raise RuntimeError(
            "Written preload-step count does not match the governed checkpoint count."
        )

    expected_restart_write_count = int(pretension.restart_policy.write_enabled)

    if restart_write_count != expected_restart_write_count:
        raise RuntimeError(
            "Written restart-keyword count does not match the governed restart policy."
        )

    if "ALL_NODES, 1, 3, 0.0" in text:
        raise RuntimeError("The nonphysical all-node constraint remains in the physical deck.")

    boundary_region_node_count = sum(region.node_count for region in boundary_regions.regions)

    return CompleteJointPhysicalPretensionDeckSummary(
        transfer=transfer_summary,
        reference_node_id=reference_node_id,
        boundary_region_count=len(boundary_regions.regions),
        boundary_region_node_count=(boundary_region_node_count),
        contact_pair_count=contact_pair_count,
        interaction_count=interaction_count,
        pretension_section_count=(pretension_section_count),
        preload_force_n=pretension.preload_force_n,
        preload_checkpoint_count=step_count,
        restart_write_count=restart_write_count,
        guidance_reference_node_count=(guidance.reference_node_count),
        guidance_sample_node_count=(guidance.sample_node_count),
        distributing_coupling_count=(guidance.distributing_coupling_count),
        mean_rotation_mpc_count=(guidance.mean_rotation_mpc_count),
        input_file_size_bytes=input_path.stat().st_size,
    )

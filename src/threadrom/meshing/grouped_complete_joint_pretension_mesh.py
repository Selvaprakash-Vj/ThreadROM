"""Generate the grouped five-volume pretension-capable joint mesh."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import gmsh  # type: ignore[import-untyped]

from threadrom.engineering.baseline_assembly import (
    BaselineAssembly,
)
from threadrom.geometry.bolt_blank import BoltBlankDefinition
from threadrom.geometry.nut_blank import NutBlankDefinition
from threadrom.meshing.complete_joint_mesh_definition import (
    CompleteJointMeshDefinition,
    ResolvedCompleteJointMeshSizes,
)
from threadrom.meshing.complete_joint_pretension_classification import (
    CompleteJointPretensionClassificationResult,
    classify_fragmented_complete_joint,
)
from threadrom.meshing.complete_joint_pretension_fragment import (
    CompleteJointPretensionFragmentResult,
    fragment_bolt_for_pretension,
)
from threadrom.meshing.complete_joint_surface_classification import (
    CompleteJointSurfaceClassificationDefinition,
    identify_complete_joint_volumes,
)
from threadrom.meshing.grouped_complete_joint_mesh import (
    JointMeshPhysicalGroupSummary,
    _read_meshio_physical_groups,
    _surface_point_entities,
    configure_complete_joint_gmsh,
)
from threadrom.meshing.nut_surface_classification import (
    INTERNAL_THREAD,
    NutSurfaceClassificationDefinition,
)
from threadrom.meshing.surface_classification import (
    THREAD_SURFACES,
    SurfaceClassificationDefinition,
)
from threadrom.solver.complete_joint_pretension import (
    CompleteJointPretensionDefinition,
    validate_complete_joint_pretension_mesh,
)


@dataclass(frozen=True)
class GroupedCompleteJointPretensionMeshResult:
    """Verified output from the pretension mesh generator."""

    classification: CompleteJointPretensionClassificationResult
    fragment: CompleteJointPretensionFragmentResult
    gmsh_node_count: int
    gmsh_volume_element_count: int
    gmsh_surface_element_count: int
    meshio_node_count: int
    meshio_tetrahedron_count: int
    meshio_triangle_count: int
    section_node_count: int
    shared_fragment_node_count: int
    msh_file_size_bytes: int
    physical_groups: tuple[
        JointMeshPhysicalGroupSummary,
        ...,
    ]


def _verify_shared_section_mesh(
    fragment: CompleteJointPretensionFragmentResult,
    pretension: CompleteJointPretensionDefinition,
) -> tuple[int, int]:
    """Verify that the section mesh is shared by both fragments."""

    section_nodes, section_coordinates, _ = (
        gmsh.model.mesh.getNodes(
            2,
            fragment.section_surface_tag,
            includeBoundary=True,
        )
    )

    lower_nodes, _, _ = gmsh.model.mesh.getNodes(
        3,
        fragment.lower_fragment_tag,
        includeBoundary=True,
    )

    upper_nodes, _, _ = gmsh.model.mesh.getNodes(
        3,
        fragment.upper_fragment_tag,
        includeBoundary=True,
    )

    section_node_set = {
        int(node_tag)
        for node_tag in section_nodes
    }

    shared_fragment_nodes = {
        int(node_tag)
        for node_tag in lower_nodes
    } & {
        int(node_tag)
        for node_tag in upper_nodes
    }

    if not section_node_set:
        raise RuntimeError(
            "Pretension section contains no mesh nodes."
        )

    if (
        pretension.require_shared_section_mesh
        and section_node_set != shared_fragment_nodes
    ):
        raise RuntimeError(
            "Pretension section nodes are not shared exactly "
            "by both bolt fragments."
        )

    z_coordinates = section_coordinates[2::3]

    if len(z_coordinates) != len(section_nodes):
        raise RuntimeError(
            "Pretension section coordinate count is invalid."
        )

    if (
        pretension.require_planar_section
        and any(
            abs(
                float(z_coordinate)
                - pretension.axial_position_mm
            )
            > 1.0e-9
            for z_coordinate in z_coordinates
        )
    ):
        raise RuntimeError(
            "Pretension section mesh is not planar at the "
            "governed axial position."
        )

    return (
        len(section_node_set),
        len(shared_fragment_nodes),
    )


def generate_grouped_complete_joint_pretension_mesh(
    *,
    step_path: Path,
    msh_path: Path,
    assembly: BaselineAssembly,
    bolt_blank: BoltBlankDefinition,
    nut_blank: NutBlankDefinition,
    mesh_definition: CompleteJointMeshDefinition,
    sizes: ResolvedCompleteJointMeshSizes,
    joint_definition: CompleteJointSurfaceClassificationDefinition,
    bolt_definition: SurfaceClassificationDefinition,
    nut_definition: NutSurfaceClassificationDefinition,
    pretension_definition: CompleteJointPretensionDefinition,
) -> GroupedCompleteJointPretensionMeshResult:
    """Generate and verify the fragmented complete-joint mesh."""

    validate_complete_joint_pretension_mesh(
        pretension_definition,
        mesh_definition,
    )

    if mesh_definition.assembly_id != assembly.assembly_id:
        raise ValueError(
            "Pretension mesh and assembly IDs differ."
        )

    if (
        mesh_definition.assembly_id
        != joint_definition.assembly_id
    ):
        raise ValueError(
            "Pretension mesh and classification assembly IDs differ."
        )

    if (
        mesh_definition.geometry_id
        != joint_definition.geometry_id
    ):
        raise ValueError(
            "Pretension mesh and classification geometry IDs differ."
        )

    if sizes.level_name != mesh_definition.selected_level:
        raise ValueError(
            "Resolved and selected mesh levels differ."
        )

    if not step_path.exists() or step_path.stat().st_size <= 0:
        raise FileNotFoundError(
            f"Valid complete-joint STEP not found: {step_path}"
        )

    msh_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    initialized = False
    logger_started = False

    classification_result: (
        CompleteJointPretensionClassificationResult | None
    ) = None

    fragment_result: (
        CompleteJointPretensionFragmentResult | None
    ) = None

    gmsh_node_count = 0
    gmsh_volume_element_count = 0
    gmsh_surface_element_count = 0
    section_node_count = 0
    shared_fragment_node_count = 0

    try:
        gmsh.initialize()
        initialized = True

        gmsh.logger.start()
        logger_started = True

        configure_complete_joint_gmsh(
            mesh_definition,
            sizes,
        )

        gmsh.model.add(
            f"{mesh_definition.mesh_id}-pretension-joint"
        )

        gmsh.model.occ.importShapes(
            str(step_path),
            True,
        )
        gmsh.model.occ.synchronize()

        original_volumes = identify_complete_joint_volumes(
            assembly,
            joint_definition,
        )

        fragment_result = fragment_bolt_for_pretension(
            bolt_tag=original_volumes.bolt_tag,
            axial_position_mm=(
                pretension_definition.axial_position_mm
            ),
            expected_fragment_count=(
                pretension_definition.bolt_fragment_count
            ),
        )

        classification_result = (
            classify_fragmented_complete_joint(
                assembly=assembly,
                bolt_blank=bolt_blank,
                nut_blank=nut_blank,
                fragment=fragment_result,
                nut_tag=original_volumes.nut_tag,
                head_side_member_tag=(
                    original_volumes.head_side_member_tag
                ),
                nut_side_member_tag=(
                    original_volumes.nut_side_member_tag
                ),
                bolt_definition=bolt_definition,
                nut_definition=nut_definition,
                joint_definition=joint_definition,
                pretension_definition=pretension_definition,
            )
        )

        gmsh.model.mesh.setSize(
            gmsh.model.getEntities(0),
            sizes.mesh_size_max_mm,
        )

        bolt_thread_points = _surface_point_entities(
            classification_result.bolt.tags_for(
                THREAD_SURFACES
            )
        )

        nut_thread_points = _surface_point_entities(
            classification_result.nut.tags_for(
                INTERNAL_THREAD
            )
        )

        gmsh.model.mesh.setSize(
            bolt_thread_points,
            sizes.bolt_thread_surface_size_mm,
        )

        gmsh.model.mesh.setSize(
            nut_thread_points,
            sizes.nut_thread_surface_size_mm,
        )

        # CP5 contact-focused flat-interface refinement.
        #
        # The existing point-based thread refinement is retained.
        # A Distance -> Threshold background field additionally
        # refines the full area and near-surface volume around the
        # three nominally flat contact interfaces.
        flat_contact_physical_names = (
            "BOLT_UNDER_HEAD_BEARING",
            "HEAD_MEMBER_HEAD_BEARING",
            "nut_lower_bearing",
            "NUT_MEMBER_NUT_BEARING",
            "HEAD_MEMBER_INTERFACE",
            "NUT_MEMBER_INTERFACE",
        )

        found_flat_contact_names: set[str] = set()
        flat_contact_surface_tags: list[int] = []

        for (
            physical_dimension,
            physical_tag,
        ) in gmsh.model.getPhysicalGroups(2):
            physical_name = gmsh.model.getPhysicalName(
                physical_dimension,
                physical_tag,
            )

            if (
                physical_name
                not in flat_contact_physical_names
            ):
                continue

            found_flat_contact_names.add(
                physical_name
            )

            flat_contact_surface_tags.extend(
                int(surface_tag)
                for surface_tag in (
                    gmsh.model.getEntitiesForPhysicalGroup(
                        physical_dimension,
                        physical_tag,
                    )
                )
            )

        missing_flat_contact_names = sorted(
            set(flat_contact_physical_names)
            - found_flat_contact_names
        )

        if missing_flat_contact_names:
            raise RuntimeError(
                "Missing flat contact physical groups for "
                "contact-focused refinement: "
                + ", ".join(
                    missing_flat_contact_names
                )
            )

        flat_contact_surface_tags = sorted(
            set(flat_contact_surface_tags)
        )

        if not flat_contact_surface_tags:
            raise RuntimeError(
                "Contact-focused refinement resolved no "
                "CAD surfaces."
            )

        contact_surface_size_mm = (
            0.50 * sizes.mesh_size_max_mm
        )

        if contact_surface_size_mm <= 0.0:
            raise RuntimeError(
                "Contact-refinement size must be positive."
            )

        if (
            contact_surface_size_mm
            > sizes.mesh_size_max_mm
        ):
            raise RuntimeError(
                "Contact-refinement size cannot exceed "
                "the global maximum mesh size."
            )

        contact_transition_distance_mm = (
            0.15 * sizes.mesh_size_max_mm
        )

        distance_field = (
            gmsh.model.mesh.field.add(
                "Distance"
            )
        )

        gmsh.model.mesh.field.setNumbers(
            distance_field,
            "SurfacesList",
            flat_contact_surface_tags,
        )

        gmsh.model.mesh.field.setNumber(
            distance_field,
            "Sampling",
            30,
        )

        threshold_field = (
            gmsh.model.mesh.field.add(
                "Threshold"
            )
        )

        gmsh.model.mesh.field.setNumber(
            threshold_field,
            "InField",
            distance_field,
        )

        gmsh.model.mesh.field.setNumber(
            threshold_field,
            "SizeMin",
            contact_surface_size_mm,
        )

        gmsh.model.mesh.field.setNumber(
            threshold_field,
            "SizeMax",
            sizes.mesh_size_max_mm,
        )

        gmsh.model.mesh.field.setNumber(
            threshold_field,
            "DistMin",
            0.0,
        )

        gmsh.model.mesh.field.setNumber(
            threshold_field,
            "DistMax",
            contact_transition_distance_mm,
        )

        gmsh.model.mesh.field.setAsBackgroundMesh(
            threshold_field
        )

        gmsh.model.mesh.generate(3)

        (
            section_node_count,
            shared_fragment_node_count,
        ) = _verify_shared_section_mesh(
            fragment_result,
            pretension_definition,
        )

        node_tags, _, _ = gmsh.model.mesh.getNodes()
        gmsh_node_count = len(node_tags)

        _, volume_tags_by_type, _ = (
            gmsh.model.mesh.getElements(3)
        )

        gmsh_volume_element_count = sum(
            len(tags)
            for tags in volume_tags_by_type
        )

        _, surface_tags_by_type, _ = (
            gmsh.model.mesh.getElements(2)
        )

        gmsh_surface_element_count = sum(
            len(tags)
            for tags in surface_tags_by_type
        )

        gmsh.write(str(msh_path))

    except Exception as error:
        messages: list[str] = []

        if logger_started:
            messages = list(gmsh.logger.get())

        diagnostic_tail = "\n".join(messages[-30:])

        message = (
            "Pretension complete-joint mesh generation failed."
        )

        if diagnostic_tail:
            message += (
                "\nLast Gmsh diagnostic messages:\n"
                + diagnostic_tail
            )

        raise RuntimeError(message) from error

    finally:
        if logger_started:
            gmsh.logger.stop()

        if initialized:
            gmsh.finalize()

    if classification_result is None:
        raise RuntimeError(
            "Pretension classification was not created."
        )

    if fragment_result is None:
        raise RuntimeError(
            "Pretension fragment was not created."
        )

    (
        meshio_node_count,
        meshio_tetrahedron_count,
        meshio_triangle_count,
        physical_groups,
    ) = _read_meshio_physical_groups(msh_path)

    if meshio_node_count > gmsh_node_count:
        raise RuntimeError(
            "Exported node count exceeds the Gmsh model count."
        )

    if (
        gmsh_volume_element_count
        != meshio_tetrahedron_count
    ):
        raise RuntimeError(
            "Exported tetrahedra do not cover all CAD volumes."
        )

    if meshio_triangle_count > gmsh_surface_element_count:
        raise RuntimeError(
            "Exported triangle count exceeds the Gmsh "
            "surface-element count."
        )

    if (
        meshio_node_count
        < mesh_definition.minimum_node_count
    ):
        raise RuntimeError(
            "Pretension mesh node count is below the minimum."
        )

    if (
        meshio_tetrahedron_count
        < mesh_definition.minimum_tetrahedron_count
    ):
        raise RuntimeError(
            "Pretension tetrahedron count is below the minimum."
        )

    if (
        meshio_triangle_count
        < mesh_definition.minimum_boundary_triangle_count
    ):
        raise RuntimeError(
            "Pretension triangle count is below the minimum."
        )

    physical_group_names = {
        summary.name
        for summary in physical_groups
    }

    required_groups = {
        pretension_definition.physical_bolt_group_name,
        pretension_definition.section_name,
    }

    missing_groups = required_groups.difference(
        physical_group_names
    )

    if missing_groups:
        raise RuntimeError(
            "Pretension mesh is missing physical groups: "
            + ", ".join(sorted(missing_groups))
        )

    return GroupedCompleteJointPretensionMeshResult(
        classification=classification_result,
        fragment=fragment_result,
        gmsh_node_count=gmsh_node_count,
        gmsh_volume_element_count=(
            gmsh_volume_element_count
        ),
        gmsh_surface_element_count=(
            gmsh_surface_element_count
        ),
        meshio_node_count=meshio_node_count,
        meshio_tetrahedron_count=(
            meshio_tetrahedron_count
        ),
        meshio_triangle_count=meshio_triangle_count,
        section_node_count=section_node_count,
        shared_fragment_node_count=(
            shared_fragment_node_count
        ),
        msh_file_size_bytes=msh_path.stat().st_size,
        physical_groups=physical_groups,
    )

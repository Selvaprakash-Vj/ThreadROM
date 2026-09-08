"""Generate and verify the grouped complete-joint mesh."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import gmsh  # type: ignore[import-untyped]
import meshio  # type: ignore[import-untyped]

from threadrom.engineering.baseline_assembly import (
    BaselineAssembly,
)
from threadrom.geometry.bolt_blank import (
    BoltBlankDefinition,
)
from threadrom.geometry.nut_blank import (
    NutBlankDefinition,
)
from threadrom.meshing.complete_joint_local_refinement import (
    ResolvedCompleteJointLocalRefinement,
    resolve_complete_joint_local_refinement_surface_tags,
)
from threadrom.meshing.complete_joint_mesh_definition import (
    CompleteJointMeshDefinition,
    ResolvedCompleteJointMeshSizes,
)
from threadrom.meshing.complete_joint_surface_classification import (
    COMPONENT_ORDER,
    MEMBER_REGION_ORDER,
    CompleteJointSurfaceClassificationDefinition,
    CompleteJointSurfaceClassificationResult,
    classify_current_complete_joint,
)
from threadrom.meshing.nut_surface_classification import (
    INTERNAL_THREAD,
    NutSurfaceClassificationDefinition,
)
from threadrom.meshing.surface_classification import (
    THREAD_SURFACES,
    SurfaceClassificationDefinition,
)


@dataclass(frozen=True)
class JointMeshPhysicalGroupSummary:
    """Named physical group recovered from the written MSH."""

    name: str
    physical_tag: int
    dimension: int
    cell_type: str
    element_count: int


@dataclass(frozen=True)
class GroupedCompleteJointMeshResult:
    """Verified complete-joint mesh measurements."""

    classification: (
        CompleteJointSurfaceClassificationResult
    )
    gmsh_node_count: int
    gmsh_volume_element_count: int
    gmsh_surface_element_count: int
    meshio_node_count: int
    meshio_tetrahedron_count: int
    meshio_triangle_count: int
    msh_file_size_bytes: int
    physical_groups: tuple[
        JointMeshPhysicalGroupSummary,
        ...,
    ]

    # Optional governed local-refinement provenance.
    # None/zero means the legacy/base mesh path was used.
    local_refinement_policy_id: str | None = None
    local_refinement_surface_count: int = 0
    local_refinement_size_mm: float | None = None
    local_refinement_transition_distance_mm: float | None = None
    local_refinement_sampling: int | None = None

    def element_count_for(
        self,
        physical_name: str,
        dimension: int,
    ) -> int:
        """Return elements in one named physical group."""

        return sum(
            summary.element_count
            for summary in self.physical_groups
            if (
                summary.name == physical_name
                and summary.dimension == dimension
            )
        )


def configure_complete_joint_gmsh(
    definition: CompleteJointMeshDefinition,
    sizes: ResolvedCompleteJointMeshSizes,
) -> None:
    """Apply governed Gmsh options for the assembly."""

    gmsh.option.setNumber(
        "General.Terminal",
        1,
    )
    gmsh.option.setNumber(
        "Mesh.Algorithm",
        definition.algorithm_2d,
    )
    gmsh.option.setNumber(
        "Mesh.Algorithm3D",
        definition.algorithm_3d,
    )
    gmsh.option.setNumber(
        "Mesh.ElementOrder",
        definition.element_order,
    )
    gmsh.option.setNumber(
        "Mesh.MeshSizeMin",
        sizes.mesh_size_min_mm,
    )
    gmsh.option.setNumber(
        "Mesh.MeshSizeMax",
        sizes.mesh_size_max_mm,
    )
    gmsh.option.setNumber(
        "Mesh.MshFileVersion",
        definition.msh_file_version,
    )
    gmsh.option.setNumber(
        "Mesh.Binary",
        1 if definition.binary_output else 0,
    )
    gmsh.option.setNumber(
        "Mesh.SaveAll",
        1 if definition.save_all_elements else 0,
    )


def _surface_point_entities(
    surface_tags: tuple[int, ...],
) -> list[tuple[int, int]]:
    """Return unique CAD points bounding selected surfaces."""

    if not surface_tags:
        raise RuntimeError(
            "At least one surface is required for refinement."
        )

    boundary_entities = gmsh.model.getBoundary(
        [
            (2, tag)
            for tag in surface_tags
        ],
        combined=False,
        oriented=False,
        recursive=True,
    )

    points = sorted(
        {
            (dimension, tag)
            for dimension, tag in boundary_entities
            if dimension == 0
        }
    )

    if not points:
        raise RuntimeError(
            "No CAD points were found for local refinement."
        )

    return points


def _read_meshio_physical_groups(
    msh_path: Path,
) -> tuple[
    int,
    int,
    int,
    tuple[JointMeshPhysicalGroupSummary, ...],
]:
    """Recover counts and named groups using Meshio."""

    mesh = meshio.read(msh_path)

    physical_data = mesh.cell_data.get("gmsh:physical")

    if physical_data is None:
        raise RuntimeError(
            "Meshio did not recover gmsh:physical data."
        )

    if len(physical_data) != len(mesh.cells):
        raise RuntimeError(
            "Meshio physical data does not align "
            "with the exported cell blocks."
        )

    field_lookup: dict[tuple[int, int], str] = {}

    for name, values in mesh.field_data.items():
        physical_tag = int(values[0])
        dimension = int(values[1])

        field_lookup[
            (physical_tag, dimension)
        ] = name

    counts: dict[tuple[int, int, str], int] = {}

    for cell_block, block_tags in zip(
        mesh.cells,
        physical_data,
        strict=True,
    ):
        if cell_block.type.startswith("tetra"):
            dimension = 3
        elif cell_block.type.startswith("triangle"):
            dimension = 2
        else:
            continue

        for raw_tag in block_tags:
            physical_tag = int(raw_tag)

            key = (
                physical_tag,
                dimension,
                cell_block.type,
            )

            counts[key] = counts.get(key, 0) + 1

    summaries: list[
        JointMeshPhysicalGroupSummary
    ] = []

    for (
        physical_tag,
        dimension,
        cell_type,
    ), element_count in counts.items():
        physical_name = field_lookup.get(
            (physical_tag, dimension)
        )

        if physical_name is None:
            raise RuntimeError(
                "Meshio recovered an unnamed group: "
                f"tag={physical_tag}, "
                f"dimension={dimension}."
            )

        summaries.append(
            JointMeshPhysicalGroupSummary(
                name=physical_name,
                physical_tag=physical_tag,
                dimension=dimension,
                cell_type=cell_type,
                element_count=element_count,
            )
        )

    ordered = tuple(
        sorted(
            summaries,
            key=lambda summary: (
                summary.dimension,
                summary.name,
                summary.cell_type,
            ),
        )
    )

    tetrahedron_count = sum(
        summary.element_count
        for summary in ordered
        if (
            summary.dimension == 3
            and summary.cell_type.startswith("tetra")
        )
    )

    triangle_count = sum(
        summary.element_count
        for summary in ordered
        if (
            summary.dimension == 2
            and summary.cell_type.startswith("triangle")
        )
    )

    return (
        len(mesh.points),
        tetrahedron_count,
        triangle_count,
        ordered,
    )


def validate_grouped_complete_joint_mesh(
    result: GroupedCompleteJointMeshResult,
    mesh_definition: CompleteJointMeshDefinition,
    classification_definition: (
        CompleteJointSurfaceClassificationDefinition
    ),
) -> None:
    """Apply grouped complete-joint mesh gates."""

    if (
        result.gmsh_node_count
        != result.meshio_node_count
    ):
        raise RuntimeError(
            "Gmsh and Meshio report different node counts."
        )

    if (
        result.gmsh_volume_element_count
        != result.meshio_tetrahedron_count
    ):
        raise RuntimeError(
            "Gmsh and Meshio report different "
            "tetrahedron counts."
        )

    if (
        result.gmsh_surface_element_count
        != result.meshio_triangle_count
    ):
        raise RuntimeError(
            "Gmsh and Meshio report different "
            "boundary-triangle counts."
        )

    if (
        result.meshio_node_count
        < mesh_definition.minimum_node_count
    ):
        raise RuntimeError(
            "Complete-joint mesh has too few nodes."
        )

    if (
        result.meshio_tetrahedron_count
        < mesh_definition.minimum_tetrahedron_count
    ):
        raise RuntimeError(
            "Complete-joint mesh has too few tetrahedra."
        )

    if (
        result.meshio_triangle_count
        < mesh_definition.minimum_boundary_triangle_count
    ):
        raise RuntimeError(
            "Complete-joint mesh has too few "
            "boundary triangles."
        )

    if result.msh_file_size_bytes <= 0:
        raise RuntimeError(
            "Complete-joint MSH output is empty."
        )

    volume_element_total = 0

    for component in COMPONENT_ORDER:
        physical_name = (
            classification_definition.volume_name(
                component
            )
        )

        element_count = result.element_count_for(
            physical_name,
            3,
        )

        if element_count <= 0:
            raise RuntimeError(
                "Named joint volume contains no "
                f"tetrahedra: {physical_name}."
            )

        volume_element_total += element_count

    if (
        volume_element_total
        != result.meshio_tetrahedron_count
    ):
        raise RuntimeError(
            "Named joint volume groups do not contain "
            "all tetrahedral elements exactly once."
        )

    expected_surface_names = [
        group.physical_name
        for group in (
            result.classification.bolt.physical_groups
        )
    ]

    expected_surface_names.extend(
        group.physical_name
        for group in (
            result.classification.nut.physical_groups
        )
    )

    expected_surface_names.extend(
        classification_definition.member_surface_name(
            region
        )
        for region in MEMBER_REGION_ORDER
    )

    for physical_name in expected_surface_names:
        if (
            result.element_count_for(
                physical_name,
                2,
            )
            <= 0
        ):
            raise RuntimeError(
                "Named joint surface contains no "
                f"triangles: {physical_name}."
            )



# === GOVERNED COMPLETE-JOINT LOCAL REFINEMENT ===


def _apply_complete_joint_local_refinement(
    *,
    refinement: ResolvedCompleteJointLocalRefinement,
    classification: CompleteJointSurfaceClassificationResult,
    sizes: ResolvedCompleteJointMeshSizes,
) -> int:
    """Apply governed semantic Distance -> Threshold refinement."""

    if refinement.base_mesh_level != sizes.level_name:
        raise ValueError(
            "Local-refinement base mesh level does not match "
            "the resolved complete-joint mesh level."
        )

    if (
        refinement.local_size_mm <= 0.0
        or refinement.local_size_mm
        >= sizes.mesh_size_max_mm
    ):
        raise ValueError(
            "Local-refinement size must be positive and below "
            "the global maximum mesh size."
        )

    if refinement.transition_distance_mm <= 0.0:
        raise ValueError(
            "Local-refinement transition distance must be positive."
        )

    if refinement.distance_sampling <= 0:
        raise ValueError(
            "Local-refinement distance sampling must be positive."
        )

    resolved_surfaces = (
        resolve_complete_joint_local_refinement_surface_tags(
            refinement=refinement,
            classification=classification,
        )
    )

    surface_tags = list(
        resolved_surfaces.all_surface_tags
    )

    if not surface_tags:
        raise RuntimeError(
            "Governed local refinement resolved no CAD surfaces."
        )

    distance_field = gmsh.model.mesh.field.add(
        "Distance"
    )

    gmsh.model.mesh.field.setNumbers(
        distance_field,
        "SurfacesList",
        surface_tags,
    )

    gmsh.model.mesh.field.setNumber(
        distance_field,
        "Sampling",
        refinement.distance_sampling,
    )

    threshold_field = gmsh.model.mesh.field.add(
        "Threshold"
    )

    gmsh.model.mesh.field.setNumber(
        threshold_field,
        "InField",
        distance_field,
    )

    gmsh.model.mesh.field.setNumber(
        threshold_field,
        "SizeMin",
        refinement.local_size_mm,
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
        refinement.transition_distance_mm,
    )

    gmsh.model.mesh.field.setAsBackgroundMesh(
        threshold_field
    )

    return len(surface_tags)


def generate_grouped_complete_joint_mesh(
    step_path: Path,
    msh_path: Path,
    assembly: BaselineAssembly,
    bolt_blank: BoltBlankDefinition,
    nut_blank: NutBlankDefinition,
    mesh_definition: CompleteJointMeshDefinition,
    sizes: ResolvedCompleteJointMeshSizes,
    classification_definition: (
        CompleteJointSurfaceClassificationDefinition
    ),
    bolt_classification_definition: (
        SurfaceClassificationDefinition
    ),
    nut_classification_definition: (
        NutSurfaceClassificationDefinition
    ),
    *,
    local_refinement: (
        ResolvedCompleteJointLocalRefinement | None
    ) = None,
) -> GroupedCompleteJointMeshResult:
    """Generate the four-volume grouped assembly mesh."""

    if mesh_definition.assembly_id != assembly.assembly_id:
        raise ValueError(
            "Joint mesh and assembly IDs differ."
        )

    if (
        mesh_definition.assembly_id
        != classification_definition.assembly_id
    ):
        raise ValueError(
            "Joint mesh and classification assembly "
            "IDs differ."
        )

    if (
        mesh_definition.geometry_id
        != classification_definition.geometry_id
    ):
        raise ValueError(
            "Joint mesh and classification geometry "
            "IDs differ."
        )

    if (
        mesh_definition.classification_id
        != classification_definition.classification_id
    ):
        raise ValueError(
            "Joint mesh and classification IDs differ."
        )

    if (
        mesh_definition.expected_volume_count
        != classification_definition.expected_volume_count
    ):
        raise ValueError(
            "Joint mesh and classification volume "
            "expectations differ."
        )

    if sizes.level_name != mesh_definition.selected_level:
        raise ValueError(
            "Resolved and selected mesh levels differ."
        )

    local_sizes = (
        sizes.bolt_thread_surface_size_mm,
        sizes.nut_thread_surface_size_mm,
    )

    if any(size <= 0.0 for size in local_sizes):
        raise ValueError(
            "Thread refinement sizes must be positive."
        )

    if any(
        size > sizes.mesh_size_max_mm
        for size in local_sizes
    ):
        raise ValueError(
            "Thread refinement cannot exceed "
            "the global maximum size."
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
        CompleteJointSurfaceClassificationResult | None
    ) = None

    gmsh_node_count = 0
    gmsh_volume_element_count = 0
    gmsh_surface_element_count = 0
    local_refinement_surface_count = 0

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
            f"{mesh_definition.mesh_id}-grouped-joint"
        )

        gmsh.model.occ.importShapes(
            str(step_path),
            True,
        )
        gmsh.model.occ.synchronize()

        classification_result = (
            classify_current_complete_joint(
                assembly,
                bolt_blank,
                nut_blank,
                bolt_classification_definition,
                nut_classification_definition,
                classification_definition,
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

        if local_refinement is not None:
            local_refinement_surface_count = (
                _apply_complete_joint_local_refinement(
                    refinement=local_refinement,
                    classification=classification_result,
                    sizes=sizes,
                )
            )

        gmsh.model.mesh.generate(3)

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

        diagnostic_tail = "\n".join(
            messages[-30:]
        )

        message = (
            "Grouped complete-joint mesh generation failed."
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
            "Complete-joint classification was not created."
        )

    (
        meshio_node_count,
        meshio_tetrahedron_count,
        meshio_triangle_count,
        physical_groups,
    ) = _read_meshio_physical_groups(msh_path)

    result = GroupedCompleteJointMeshResult(
        classification=classification_result,
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
        msh_file_size_bytes=msh_path.stat().st_size,
        physical_groups=physical_groups,
        local_refinement_policy_id=(
            None
            if local_refinement is None
            else local_refinement.policy_id
        ),
        local_refinement_surface_count=(
            local_refinement_surface_count
        ),
        local_refinement_size_mm=(
            None
            if local_refinement is None
            else local_refinement.local_size_mm
        ),
        local_refinement_transition_distance_mm=(
            None
            if local_refinement is None
            else local_refinement.transition_distance_mm
        ),
        local_refinement_sampling=(
            None
            if local_refinement is None
            else local_refinement.distance_sampling
        ),
    )

    validate_grouped_complete_joint_mesh(
        result,
        mesh_definition,
        classification_definition,
    )

    return result

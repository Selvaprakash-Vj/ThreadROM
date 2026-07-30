"""Generate a nut mesh containing named engineering boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import gmsh  # type: ignore[import-untyped]
import meshio  # type: ignore[import-untyped]

from threadrom.geometry.nut_blank import NutBlankDefinition
from threadrom.meshing.gmsh_step import (
    GmshMeshDefinition,
    configure_gmsh,
)
from threadrom.meshing.nut_surface_classification import (
    INTERNAL_THREAD,
    NutSurfaceClassificationDefinition,
    NutSurfaceClassificationResult,
    classify_current_model_nut_surfaces,
)


@dataclass(frozen=True)
class NutMeshPhysicalGroupSummary:
    """Named physical group recovered from a nut MSH file."""

    name: str
    physical_tag: int
    dimension: int
    cell_type: str
    element_count: int


@dataclass(frozen=True)
class GroupedNutMeshResult:
    """Verified grouped nut-mesh measurements."""

    classification: NutSurfaceClassificationResult
    gmsh_node_count: int
    gmsh_volume_element_count: int
    gmsh_surface_element_count: int
    meshio_node_count: int
    meshio_tetrahedron_count: int
    meshio_triangle_count: int
    msh_file_size_bytes: int
    physical_groups: tuple[
        NutMeshPhysicalGroupSummary,
        ...,
    ]

    def element_count_for(
        self,
        physical_name: str,
        dimension: int,
    ) -> int:
        """Return the element count for one physical group."""

        return sum(
            summary.element_count
            for summary in self.physical_groups
            if (
                summary.name == physical_name
                and summary.dimension == dimension
            )
        )


def _read_meshio_physical_groups(
    msh_path: Path,
) -> tuple[
    int,
    int,
    int,
    tuple[NutMeshPhysicalGroupSummary, ...],
]:
    """Read nut physical groups independently with Meshio."""

    mesh = meshio.read(msh_path)

    physical_data = mesh.cell_data.get("gmsh:physical")

    if physical_data is None:
        raise RuntimeError(
            "Meshio did not recover gmsh:physical data."
        )

    if len(physical_data) != len(mesh.cells):
        raise RuntimeError(
            "Meshio physical data does not align with cells."
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

    summaries: list[NutMeshPhysicalGroupSummary] = []

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
                "Meshio recovered an unnamed physical group: "
                f"tag={physical_tag}, "
                f"dimension={dimension}."
            )

        summaries.append(
            NutMeshPhysicalGroupSummary(
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


def validate_grouped_nut_mesh(
    result: GroupedNutMeshResult,
    mesh_definition: GmshMeshDefinition,
) -> None:
    """Apply grouped nut-mesh acceptance gates."""

    if result.gmsh_node_count != result.meshio_node_count:
        raise RuntimeError(
            "Gmsh and Meshio report different node counts."
        )

    if (
        result.gmsh_volume_element_count
        != result.meshio_tetrahedron_count
    ):
        raise RuntimeError(
            "Gmsh and Meshio report different tetra counts."
        )

    if (
        result.gmsh_surface_element_count
        != result.meshio_triangle_count
    ):
        raise RuntimeError(
            "Gmsh and Meshio report different triangle counts."
        )

    if result.meshio_tetrahedron_count <= 0:
        raise RuntimeError(
            "Grouped nut mesh contains no tetrahedra."
        )

    if result.meshio_triangle_count <= 0:
        raise RuntimeError(
            "Grouped nut mesh contains no boundary triangles."
        )

    if result.msh_file_size_bytes <= 0:
        raise RuntimeError(
            "Grouped nut MSH output is empty."
        )

    volume_element_count = result.element_count_for(
        mesh_definition.volume_physical_name,
        3,
    )

    if volume_element_count != result.meshio_tetrahedron_count:
        raise RuntimeError(
            "The NUT volume group does not contain "
            "all tetrahedral elements."
        )

    for group in result.classification.physical_groups:
        element_count = result.element_count_for(
            group.physical_name,
            2,
        )

        if element_count <= 0:
            raise RuntimeError(
                "Named nut surface group contains no elements: "
                f"{group.physical_name}."
            )


def generate_grouped_nut_mesh(
    step_path: Path,
    msh_path: Path,
    nut_definition: NutBlankDefinition,
    mesh_definition: GmshMeshDefinition,
    classification_definition: (
        NutSurfaceClassificationDefinition
    ),
    thread_surface_size_mm: float | None = None,
) -> GroupedNutMeshResult:
    """Generate a tetrahedral nut mesh with named boundaries."""

    if (
        mesh_definition.geometry_id
        != classification_definition.geometry_id
    ):
        raise ValueError(
            "Nut mesh and classification geometry IDs differ."
        )

    if (
        mesh_definition.mesh_id
        != classification_definition.mesh_id
    ):
        raise ValueError(
            "Nut mesh and classification mesh IDs differ."
        )

    if not step_path.exists() or step_path.stat().st_size <= 0:
        raise FileNotFoundError(
            f"Valid nut STEP geometry not found: {step_path}"
        )

    msh_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    initialized = False
    logger_started = False

    classification_result: (
        NutSurfaceClassificationResult | None
    ) = None

    gmsh_node_count = 0
    gmsh_volume_element_count = 0
    gmsh_surface_element_count = 0

    try:
        gmsh.initialize()
        initialized = True

        gmsh.logger.start()
        logger_started = True

        configure_gmsh(mesh_definition)

        gmsh.model.add(
            f"{mesh_definition.mesh_id}-grouped-nut"
        )

        gmsh.model.occ.importShapes(
            str(step_path),
            True,
        )
        gmsh.model.occ.synchronize()

        volume_entities = gmsh.model.getEntities(3)

        if len(volume_entities) != 1:
            raise RuntimeError(
                "Grouped nut meshing requires one CAD volume."
            )

        volume_tags = [
            tag
            for _, tag in volume_entities
        ]

        volume_group = gmsh.model.addPhysicalGroup(
            3,
            volume_tags,
        )

        gmsh.model.setPhysicalName(
            3,
            volume_group,
            mesh_definition.volume_physical_name,
        )

        classification_result = (
            classify_current_model_nut_surfaces(
                nut_definition,
                classification_definition,
            )
        )

        all_points = gmsh.model.getEntities(0)

        gmsh.model.mesh.setSize(
            all_points,
            mesh_definition.mesh_size_max_mm,
        )

        if thread_surface_size_mm is not None:
            if thread_surface_size_mm <= 0.0:
                raise ValueError(
                    "Thread mesh size must be positive."
                )

            if (
                thread_surface_size_mm
                > mesh_definition.mesh_size_max_mm
            ):
                raise ValueError(
                    "Thread mesh size cannot exceed "
                    "the global maximum."
                )

            thread_surfaces = [
                (2, tag)
                for tag in classification_result.tags_for(
                    INTERNAL_THREAD
                )
            ]

            thread_boundaries = gmsh.model.getBoundary(
                thread_surfaces,
                combined=False,
                oriented=False,
                recursive=True,
            )

            thread_points = sorted(
                {
                    (dimension, tag)
                    for dimension, tag in thread_boundaries
                    if dimension == 0
                }
            )

            if not thread_points:
                raise RuntimeError(
                    "No internal-thread CAD points were found."
                )

            gmsh.model.mesh.setSize(
                thread_points,
                thread_surface_size_mm,
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
            messages[-20:]
        )

        message = "Grouped nut mesh generation failed."

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
            "Nut classification result was not created."
        )

    (
        meshio_node_count,
        meshio_tetrahedron_count,
        meshio_triangle_count,
        physical_groups,
    ) = _read_meshio_physical_groups(msh_path)

    result = GroupedNutMeshResult(
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
    )

    validate_grouped_nut_mesh(
        result,
        mesh_definition,
    )

    return result

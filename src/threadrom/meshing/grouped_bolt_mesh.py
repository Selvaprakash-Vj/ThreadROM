"""Generate a bolt mesh containing named engineering boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import gmsh  # type: ignore[import-untyped]
import meshio  # type: ignore[import-untyped]

from threadrom.geometry.bolt_blank import BoltBlankDefinition
from threadrom.meshing.gmsh_step import (
    GmshMeshDefinition,
    configure_gmsh,
)
from threadrom.meshing.surface_classification import (
    SurfaceClassificationDefinition,
    SurfaceClassificationResult,
    classify_current_model_surfaces,
)


@dataclass(frozen=True)
class MeshioPhysicalGroupSummary:
    """Named physical group recovered from a Gmsh MSH file."""

    name: str
    physical_tag: int
    dimension: int
    cell_type: str
    element_count: int


@dataclass(frozen=True)
class GroupedBoltMeshResult:
    """Verified grouped bolt-mesh measurements."""

    classification: SurfaceClassificationResult
    gmsh_node_count: int
    gmsh_volume_element_count: int
    gmsh_surface_element_count: int
    meshio_node_count: int
    meshio_tetrahedron_count: int
    meshio_triangle_count: int
    msh_file_size_bytes: int
    physical_groups: tuple[MeshioPhysicalGroupSummary, ...]

    def element_count_for(
        self,
        physical_name: str,
        dimension: int,
    ) -> int:
        """Return the element count for one named physical group."""

        return sum(
            summary.element_count
            for summary in self.physical_groups
            if summary.name == physical_name and summary.dimension == dimension
        )


def _read_meshio_physical_groups(
    msh_path: Path,
) -> tuple[
    int,
    int,
    int,
    tuple[MeshioPhysicalGroupSummary, ...],
]:
    """Read named physical groups independently using Meshio."""

    mesh = meshio.read(msh_path)

    physical_data = mesh.cell_data.get("gmsh:physical")

    if physical_data is None:
        raise RuntimeError("Meshio did not recover gmsh:physical cell data.")

    if len(physical_data) != len(mesh.cells):
        raise RuntimeError("Meshio physical data does not align with cell blocks.")

    field_lookup: dict[tuple[int, int], str] = {}

    for name, values in mesh.field_data.items():
        physical_tag = int(values[0])
        dimension = int(values[1])
        field_lookup[(physical_tag, dimension)] = name

    counts: dict[tuple[int, int, str], int] = {}

    for cell_block, block_physical_tags in zip(
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

        for raw_tag in block_physical_tags:
            physical_tag = int(raw_tag)
            key = (
                physical_tag,
                dimension,
                cell_block.type,
            )
            counts[key] = counts.get(key, 0) + 1

    summaries: list[MeshioPhysicalGroupSummary] = []

    for (
        physical_tag,
        dimension,
        cell_type,
    ), element_count in counts.items():
        physical_name = field_lookup.get((physical_tag, dimension))

        if physical_name is None:
            raise RuntimeError(
                "Meshio recovered an unnamed physical group: "
                f"tag={physical_tag}, dimension={dimension}."
            )

        summaries.append(
            MeshioPhysicalGroupSummary(
                name=physical_name,
                physical_tag=physical_tag,
                dimension=dimension,
                cell_type=cell_type,
                element_count=element_count,
            )
        )

    ordered_summaries = tuple(
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
        for summary in ordered_summaries
        if summary.dimension == 3 and summary.cell_type.startswith("tetra")
    )

    triangle_count = sum(
        summary.element_count
        for summary in ordered_summaries
        if summary.dimension == 2 and summary.cell_type.startswith("triangle")
    )

    return (
        len(mesh.points),
        tetrahedron_count,
        triangle_count,
        ordered_summaries,
    )


def validate_grouped_bolt_mesh(
    result: GroupedBoltMeshResult,
    mesh_definition: GmshMeshDefinition,
) -> None:
    """Apply grouped-mesh acceptance gates."""

    if result.gmsh_node_count != result.meshio_node_count:
        raise RuntimeError("Gmsh and Meshio report different node counts.")

    if result.gmsh_volume_element_count != result.meshio_tetrahedron_count:
        raise RuntimeError("Gmsh and Meshio report different tetrahedron counts.")

    if result.gmsh_surface_element_count != result.meshio_triangle_count:
        raise RuntimeError("Gmsh and Meshio report different surface-element counts.")

    if result.meshio_tetrahedron_count <= 0:
        raise RuntimeError("Grouped mesh contains no tetrahedral elements.")

    if result.meshio_triangle_count <= 0:
        raise RuntimeError("Grouped mesh contains no triangular boundary elements.")

    if result.msh_file_size_bytes <= 0:
        raise RuntimeError("Grouped MSH output file is empty.")

    if (
        result.element_count_for(
            mesh_definition.volume_physical_name,
            3,
        )
        != result.meshio_tetrahedron_count
    ):
        raise RuntimeError("The named bolt-volume group does not contain all tetrahedral elements.")

    for group in result.classification.physical_groups:
        element_count = result.element_count_for(
            group.physical_name,
            2,
        )

        if element_count <= 0:
            raise RuntimeError(
                f"Named surface group contains no exported elements: {group.physical_name}."
            )


def generate_grouped_bolt_mesh(
    step_path: Path,
    msh_path: Path,
    blank_definition: BoltBlankDefinition,
    mesh_definition: GmshMeshDefinition,
    classification_definition: SurfaceClassificationDefinition,
) -> GroupedBoltMeshResult:
    """Generate a tetrahedral mesh with named engineering boundaries."""

    if mesh_definition.geometry_id != (classification_definition.geometry_id):
        raise ValueError("Mesh and surface-classification geometry IDs differ.")

    if mesh_definition.mesh_id != classification_definition.mesh_id:
        raise ValueError("Mesh and surface-classification mesh IDs differ.")

    if not step_path.exists() or step_path.stat().st_size <= 0:
        raise FileNotFoundError(f"Valid STEP geometry not found: {step_path}")

    msh_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    initialized = False
    logger_started = False

    classification_result: SurfaceClassificationResult | None = None
    gmsh_node_count = 0
    gmsh_volume_element_count = 0
    gmsh_surface_element_count = 0

    try:
        gmsh.initialize()
        initialized = True

        gmsh.logger.start()
        logger_started = True

        configure_gmsh(mesh_definition)

        gmsh.model.add(f"{mesh_definition.mesh_id}-grouped")

        gmsh.model.occ.importShapes(
            str(step_path),
            True,
        )

        gmsh.model.occ.synchronize()

        volume_entities = gmsh.model.getEntities(3)

        if len(volume_entities) != 1:
            raise RuntimeError("Grouped bolt meshing requires exactly one CAD volume.")

        volume_tags = [tag for _, tag in volume_entities]

        volume_group = gmsh.model.addPhysicalGroup(
            3,
            volume_tags,
        )

        gmsh.model.setPhysicalName(
            3,
            volume_group,
            mesh_definition.volume_physical_name,
        )

        classification_result = classify_current_model_surfaces(
            blank_definition,
            classification_definition,
        )

        point_entities = gmsh.model.getEntities(0)

        gmsh.model.mesh.setSize(
            point_entities,
            mesh_definition.mesh_size_max_mm,
        )

        gmsh.model.mesh.generate(3)

        node_tags, _, _ = gmsh.model.mesh.getNodes()
        gmsh_node_count = len(node_tags)

        _, volume_element_tags, _ = gmsh.model.mesh.getElements(3)

        gmsh_volume_element_count = sum(len(tags) for tags in volume_element_tags)

        _, surface_element_tags, _ = gmsh.model.mesh.getElements(2)

        gmsh_surface_element_count = sum(len(tags) for tags in surface_element_tags)

        gmsh.write(str(msh_path))

    except Exception as error:
        messages: list[str] = []

        if logger_started:
            messages = list(gmsh.logger.get())

        diagnostic_tail = "\n".join(messages[-20:])

        message = "Grouped Gmsh mesh generation failed."

        if diagnostic_tail:
            message += f"\nLast Gmsh diagnostic messages:\n{diagnostic_tail}"

        raise RuntimeError(message) from error

    finally:
        if logger_started:
            gmsh.logger.stop()

        if initialized:
            gmsh.finalize()

    if classification_result is None:
        raise RuntimeError("Surface classification result was not created.")

    (
        meshio_node_count,
        meshio_tetrahedron_count,
        meshio_triangle_count,
        physical_groups,
    ) = _read_meshio_physical_groups(msh_path)

    result = GroupedBoltMeshResult(
        classification=classification_result,
        gmsh_node_count=gmsh_node_count,
        gmsh_volume_element_count=gmsh_volume_element_count,
        gmsh_surface_element_count=gmsh_surface_element_count,
        meshio_node_count=meshio_node_count,
        meshio_tetrahedron_count=meshio_tetrahedron_count,
        meshio_triangle_count=meshio_triangle_count,
        msh_file_size_bytes=msh_path.stat().st_size,
        physical_groups=physical_groups,
    )

    validate_grouped_bolt_mesh(
        result,
        mesh_definition,
    )

    return result

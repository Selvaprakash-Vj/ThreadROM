"""Gmsh STEP import and tetrahedral meshability verification."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import gmsh  # type: ignore[import-untyped]
import meshio  # type: ignore[import-untyped]


@dataclass(frozen=True)
class GmshMeshDefinition:
    """Controlled Gmsh meshing parameters."""

    mesh_id: str
    geometry_id: str
    element_order: int
    algorithm_2d: int
    algorithm_3d: int
    mesh_size_min_mm: float
    mesh_size_max_mm: float
    msh_file_version: float
    binary_output: bool
    save_all_elements: bool
    volume_physical_name: str
    surface_physical_name: str
    expected_volume_count: int
    minimum_node_count: int
    minimum_tetrahedron_count: int


@dataclass(frozen=True)
class GmshElementSummary:
    """Summary of one generated three-dimensional element type."""

    element_type: int
    name: str
    order: int
    nodes_per_element: int
    element_count: int


@dataclass(frozen=True)
class GmshMeshabilityResult:
    """Verified topology and mesh measurements."""

    imported_top_level_entity_count: int
    point_count: int
    curve_count: int
    surface_count: int
    volume_count: int
    cad_volume_mm3: float
    x_min_mm: float
    x_max_mm: float
    y_min_mm: float
    y_max_mm: float
    z_min_mm: float
    z_max_mm: float
    gmsh_node_count: int
    gmsh_3d_element_count: int
    meshio_node_count: int
    meshio_tetrahedron_count: int
    msh_file_size_bytes: int
    element_summaries: tuple[GmshElementSummary, ...]


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return a required TOML section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(f"Missing or invalid configuration section: {key}")

    return cast(Mapping[str, object], value)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return a required non-empty string."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Missing or invalid string value: {key}")

    return value


def _integer(
    data: Mapping[str, object],
    key: str,
) -> int:
    """Return a required integer value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"Missing or invalid integer value: {key}")

    return value


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return a required numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"Missing or invalid numerical value: {key}")

    return float(value)


def _boolean(
    data: Mapping[str, object],
    key: str,
) -> bool:
    """Return a required Boolean value."""

    value = data.get(key)

    if not isinstance(value, bool):
        raise TypeError(f"Missing or invalid Boolean value: {key}")

    return value


def load_gmsh_mesh_definition(
    config_path: Path,
) -> GmshMeshDefinition:
    """Load and validate the controlled Gmsh mesh definition."""

    with config_path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(config_file)

    identity = _section(data, "identity")
    gmsh_section = _section(data, "gmsh")
    physical_groups = _section(data, "physical_groups")
    verification = _section(data, "verification")

    definition = GmshMeshDefinition(
        mesh_id=_string(identity, "mesh_id"),
        geometry_id=_string(identity, "geometry_id"),
        element_order=_integer(
            gmsh_section,
            "element_order",
        ),
        algorithm_2d=_integer(
            gmsh_section,
            "algorithm_2d",
        ),
        algorithm_3d=_integer(
            gmsh_section,
            "algorithm_3d",
        ),
        mesh_size_min_mm=_number(
            gmsh_section,
            "mesh_size_min_mm",
        ),
        mesh_size_max_mm=_number(
            gmsh_section,
            "mesh_size_max_mm",
        ),
        msh_file_version=_number(
            gmsh_section,
            "msh_file_version",
        ),
        binary_output=_boolean(
            gmsh_section,
            "binary_output",
        ),
        save_all_elements=_boolean(
            gmsh_section,
            "save_all_elements",
        ),
        volume_physical_name=_string(
            physical_groups,
            "volume_name",
        ),
        surface_physical_name=_string(
            physical_groups,
            "surface_name",
        ),
        expected_volume_count=_integer(
            verification,
            "expected_volume_count",
        ),
        minimum_node_count=_integer(
            verification,
            "minimum_node_count",
        ),
        minimum_tetrahedron_count=_integer(
            verification,
            "minimum_tetrahedron_count",
        ),
    )

    if definition.element_order <= 0:
        raise ValueError("Element order must be positive.")

    if definition.mesh_size_min_mm <= 0.0:
        raise ValueError("Minimum mesh size must be positive.")

    if definition.mesh_size_max_mm <= 0.0:
        raise ValueError("Maximum mesh size must be positive.")

    if definition.mesh_size_min_mm > definition.mesh_size_max_mm:
        raise ValueError("Minimum mesh size cannot exceed maximum mesh size.")

    if definition.expected_volume_count <= 0:
        raise ValueError("Expected volume count must be positive.")

    if definition.minimum_node_count <= 0:
        raise ValueError("Minimum node count must be positive.")

    if definition.minimum_tetrahedron_count <= 0:
        raise ValueError("Minimum tetrahedron count must be positive.")

    return definition


def _configure_gmsh(
    definition: GmshMeshDefinition,
) -> None:
    """Apply controlled Gmsh options."""

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
        definition.mesh_size_min_mm,
    )
    gmsh.option.setNumber(
        "Mesh.MeshSizeMax",
        definition.mesh_size_max_mm,
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


def _collect_element_summaries() -> tuple[
    tuple[GmshElementSummary, ...],
    int,
]:
    """Collect all generated three-dimensional element types."""

    (
        element_types,
        element_tags_by_type,
        _,
    ) = gmsh.model.mesh.getElements(3)

    summaries: list[GmshElementSummary] = []
    total_element_count = 0

    for element_type, element_tags in zip(
        element_types,
        element_tags_by_type,
        strict=True,
    ):
        (
            name,
            dimension,
            order,
            nodes_per_element,
            _,
            _,
        ) = gmsh.model.mesh.getElementProperties(int(element_type))

        if int(dimension) != 3:
            continue

        element_count = len(element_tags)
        total_element_count += element_count

        summaries.append(
            GmshElementSummary(
                element_type=int(element_type),
                name=str(name),
                order=int(order),
                nodes_per_element=int(nodes_per_element),
                element_count=element_count,
            )
        )

    return tuple(summaries), total_element_count


def _meshio_counts(
    msh_path: Path,
) -> tuple[int, int]:
    """Independently read the generated mesh with Meshio."""

    mesh = meshio.read(msh_path)

    tetrahedron_count = sum(
        len(cell_block.data) for cell_block in mesh.cells if cell_block.type.startswith("tetra")
    )

    return len(mesh.points), tetrahedron_count


def validate_meshability_result(
    result: GmshMeshabilityResult,
    definition: GmshMeshDefinition,
) -> None:
    """Apply the controlled meshability acceptance gates."""

    if result.volume_count != definition.expected_volume_count:
        raise RuntimeError(
            "Unexpected imported volume count: "
            f"{result.volume_count}; expected "
            f"{definition.expected_volume_count}."
        )

    if result.cad_volume_mm3 <= 0.0:
        raise RuntimeError("Imported STEP geometry has non-positive volume.")

    if result.gmsh_node_count < definition.minimum_node_count:
        raise RuntimeError("Generated node count is below the controlled minimum.")

    if result.gmsh_3d_element_count < definition.minimum_tetrahedron_count:
        raise RuntimeError("Generated 3D element count is below the controlled minimum.")

    if result.meshio_tetrahedron_count < definition.minimum_tetrahedron_count:
        raise RuntimeError("Meshio did not recover enough tetrahedral elements.")

    if result.gmsh_3d_element_count != result.meshio_tetrahedron_count:
        raise RuntimeError("Gmsh and Meshio report different tetrahedron counts.")

    if result.meshio_node_count != result.gmsh_node_count:
        raise RuntimeError("Gmsh and Meshio report different node counts.")

    if result.msh_file_size_bytes <= 0:
        raise RuntimeError("Gmsh mesh output file is empty.")


def generate_step_tetrahedral_mesh(
    step_path: Path,
    msh_path: Path,
    definition: GmshMeshDefinition,
) -> GmshMeshabilityResult:
    """Import STEP geometry and generate a verified tetrahedral mesh."""

    if not step_path.exists():
        raise FileNotFoundError(f"STEP geometry does not exist: {step_path}")

    if step_path.stat().st_size <= 0:
        raise RuntimeError(f"STEP geometry is empty: {step_path}")

    msh_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    initialized = False
    logger_started = False

    try:
        gmsh.initialize()
        initialized = True

        gmsh.logger.start()
        logger_started = True

        _configure_gmsh(definition)

        gmsh.model.add(definition.mesh_id)

        imported_entities = gmsh.model.occ.importShapes(
            str(step_path),
            True,
        )

        gmsh.model.occ.synchronize()

        point_entities = gmsh.model.getEntities(0)
        curve_entities = gmsh.model.getEntities(1)
        surface_entities = gmsh.model.getEntities(2)
        volume_entities = gmsh.model.getEntities(3)

        if len(volume_entities) != definition.expected_volume_count:
            raise RuntimeError(
                f"STEP import produced an unexpected number of volumes: {len(volume_entities)}."
            )

        volume_tags = [tag for _, tag in volume_entities]

        surface_tags = [tag for _, tag in surface_entities]

        volume_group = gmsh.model.addPhysicalGroup(
            3,
            volume_tags,
        )
        gmsh.model.setPhysicalName(
            3,
            volume_group,
            definition.volume_physical_name,
        )

        if surface_tags:
            surface_group = gmsh.model.addPhysicalGroup(
                2,
                surface_tags,
            )
            gmsh.model.setPhysicalName(
                2,
                surface_group,
                definition.surface_physical_name,
            )

        gmsh.model.mesh.setSize(
            point_entities,
            definition.mesh_size_max_mm,
        )

        volume_tag = volume_tags[0]

        cad_volume_mm3 = gmsh.model.occ.getMass(
            3,
            volume_tag,
        )

        (
            x_min_mm,
            y_min_mm,
            z_min_mm,
            x_max_mm,
            y_max_mm,
            z_max_mm,
        ) = gmsh.model.getBoundingBox(
            3,
            volume_tag,
        )

        gmsh.model.mesh.generate(3)

        node_tags, _, _ = gmsh.model.mesh.getNodes()
        gmsh_node_count = len(node_tags)

        (
            element_summaries,
            gmsh_3d_element_count,
        ) = _collect_element_summaries()

        gmsh.write(str(msh_path))

        preliminary_values = (
            len(imported_entities),
            len(point_entities),
            len(curve_entities),
            len(surface_entities),
            len(volume_entities),
            float(cad_volume_mm3),
            float(x_min_mm),
            float(x_max_mm),
            float(y_min_mm),
            float(y_max_mm),
            float(z_min_mm),
            float(z_max_mm),
            gmsh_node_count,
            gmsh_3d_element_count,
            element_summaries,
        )

    except Exception as error:
        messages: list[str] = []

        if logger_started:
            messages = list(gmsh.logger.get())

        diagnostic_tail = "\n".join(messages[-20:])

        message = "Gmsh STEP mesh generation failed."

        if diagnostic_tail:
            message += f"\nLast Gmsh diagnostic messages:\n{diagnostic_tail}"

        raise RuntimeError(message) from error

    finally:
        if logger_started:
            gmsh.logger.stop()

        if initialized:
            gmsh.finalize()

    (
        imported_top_level_entity_count,
        point_count,
        curve_count,
        surface_count,
        volume_count,
        cad_volume_mm3,
        x_min_mm,
        x_max_mm,
        y_min_mm,
        y_max_mm,
        z_min_mm,
        z_max_mm,
        gmsh_node_count,
        gmsh_3d_element_count,
        element_summaries,
    ) = preliminary_values

    meshio_node_count, meshio_tetrahedron_count = _meshio_counts(msh_path)

    result = GmshMeshabilityResult(
        imported_top_level_entity_count=(imported_top_level_entity_count),
        point_count=point_count,
        curve_count=curve_count,
        surface_count=surface_count,
        volume_count=volume_count,
        cad_volume_mm3=cad_volume_mm3,
        x_min_mm=x_min_mm,
        x_max_mm=x_max_mm,
        y_min_mm=y_min_mm,
        y_max_mm=y_max_mm,
        z_min_mm=z_min_mm,
        z_max_mm=z_max_mm,
        gmsh_node_count=gmsh_node_count,
        gmsh_3d_element_count=gmsh_3d_element_count,
        meshio_node_count=meshio_node_count,
        meshio_tetrahedron_count=meshio_tetrahedron_count,
        msh_file_size_bytes=msh_path.stat().st_size,
        element_summaries=element_summaries,
    )

    validate_meshability_result(
        result,
        definition,
    )

    return result

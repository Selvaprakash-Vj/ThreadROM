"""Governed complete-joint CalculiX mesh transfer."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import meshio  # type: ignore[import-untyped]
import numpy as np
from numpy.typing import NDArray

from threadrom.solver.calculix_mesh_transfer import (
    _calculix_name,
    _format_identifier_rows,
)

BOLT = "bolt"
NUT = "nut"
HEAD_SIDE_MEMBER = "head_side_member"
NUT_SIDE_MEMBER = "nut_side_member"

COMPONENT_ORDER = (
    BOLT,
    NUT,
    HEAD_SIDE_MEMBER,
    NUT_SIDE_MEMBER,
)


@dataclass(frozen=True)
class CompleteJointCalculixTransferDefinition:
    """Configuration for four-volume CalculiX transfer."""

    simulation_id: str
    mesh_id: str
    assembly_id: str
    geometry_id: str
    classification_id: str
    mesh_level: str
    source_mesh_name: str
    executable_relative_path: Path
    job_name: str
    timeout_seconds: int
    element_type: str
    smoke_test_fixed_node_set: str
    smoke_test_output_node_group: str
    volume_groups: tuple[tuple[str, str], ...]
    bolt_material_name: str
    nut_material_name: str
    member_material_name: str
    youngs_modulus_mpa: float
    poissons_ratio: float
    expected_volume_group_count: int
    expected_boundary_group_count: int
    minimum_node_count: int
    minimum_element_count: int
    required_boundary_groups: tuple[str, ...]

    def volume_name(
        self,
        component: str,
    ) -> str:
        """Return the configured volume name."""

        lookup = dict(self.volume_groups)

        try:
            return lookup[component]
        except KeyError as error:
            raise ValueError(
                f"Unknown joint component: {component}"
            ) from error


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return one required TOML section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(
            f"Missing or invalid configuration section: {key}"
        )

    return cast(Mapping[str, object], value)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return one required non-empty string."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(
            f"Missing or invalid string value: {key}"
        )

    return value


def _integer(
    data: Mapping[str, object],
    key: str,
) -> int:
    """Return one required positive integer."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            f"Missing or invalid integer value: {key}"
        )

    if value <= 0:
        raise ValueError(
            f"Integer value must be positive: {key}"
        )

    return value


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return one required numerical value."""

    value = data.get(key)

    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
    ):
        raise TypeError(
            f"Missing or invalid numerical value: {key}"
        )

    return float(value)


def _string_tuple(
    data: Mapping[str, object],
    key: str,
) -> tuple[str, ...]:
    """Return one required tuple of non-empty strings."""

    value = data.get(key)

    if not isinstance(value, list):
        raise TypeError(
            f"Missing or invalid string list: {key}"
        )

    result: list[str] = []

    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise TypeError(
                f"Invalid string-list member in: {key}"
            )

        result.append(item)

    if not result:
        raise ValueError(
            f"String list cannot be empty: {key}"
        )

    return tuple(result)


def load_complete_joint_calculix_transfer_definition(
    config_path: Path,
) -> CompleteJointCalculixTransferDefinition:
    """Load and validate the joint transfer configuration."""

    with config_path.open("rb") as config_file:
        data: dict[str, object] = tomllib.load(
            config_file
        )

    identity = _section(data, "identity")
    input_section = _section(data, "input")
    solver = _section(data, "solver")
    smoke_test = _section(data, "smoke_test")
    volumes = _section(data, "volume_groups")
    materials = _section(data, "materials")
    verification = _section(
        data,
        "verification",
    )

    volume_groups = tuple(
        (
            component,
            _string(volumes, component),
        )
        for component in COMPONENT_ORDER
    )

    definition = CompleteJointCalculixTransferDefinition(
        simulation_id=_string(
            identity,
            "simulation_id",
        ),
        mesh_id=_string(
            identity,
            "mesh_id",
        ),
        assembly_id=_string(
            identity,
            "assembly_id",
        ),
        geometry_id=_string(
            identity,
            "geometry_id",
        ),
        classification_id=_string(
            identity,
            "classification_id",
        ),
        mesh_level=_string(
            input_section,
            "mesh_level",
        ).lower(),
        source_mesh_name=_string(
            input_section,
            "source_mesh_name",
        ),
        executable_relative_path=Path(
            _string(
                solver,
                "executable_relative_path",
            )
        ),
        job_name=_string(
            solver,
            "job_name",
        ),
        timeout_seconds=_integer(
            solver,
            "timeout_seconds",
        ),
        element_type=_string(
            solver,
            "element_type",
        ),
        smoke_test_fixed_node_set=_string(
            smoke_test,
            "fixed_node_set",
        ),
        smoke_test_output_node_group=_string(
            smoke_test,
            "output_node_group",
        ),
        volume_groups=volume_groups,
        bolt_material_name=_string(
            materials,
            "bolt",
        ),
        nut_material_name=_string(
            materials,
            "nut",
        ),
        member_material_name=_string(
            materials,
            "members",
        ),
        youngs_modulus_mpa=_number(
            materials,
            "youngs_modulus_mpa",
        ),
        poissons_ratio=_number(
            materials,
            "poissons_ratio",
        ),
        expected_volume_group_count=_integer(
            verification,
            "expected_volume_group_count",
        ),
        expected_boundary_group_count=_integer(
            verification,
            "expected_boundary_group_count",
        ),
        minimum_node_count=_integer(
            verification,
            "minimum_node_count",
        ),
        minimum_element_count=_integer(
            verification,
            "minimum_element_count",
        ),
        required_boundary_groups=_string_tuple(
            verification,
            "required_boundary_groups",
        ),
    )

    if definition.mesh_level not in {
        "coarse",
        "medium",
        "fine",
    }:
        raise ValueError(
            "Mesh level must be coarse, medium or fine."
        )

    if definition.timeout_seconds <= 0:
        raise ValueError(
            "Solver timeout must be positive."
        )

    if definition.element_type != "C3D4":
        raise ValueError(
            "Complete-joint transfer currently requires C3D4."
        )

    if definition.youngs_modulus_mpa <= 0.0:
        raise ValueError(
            "Young's modulus must be positive."
        )

    if not -1.0 < definition.poissons_ratio < 0.5:
        raise ValueError(
            "Poisson's ratio must lie between -1 and 0.5."
        )

    if (
        definition.smoke_test_output_node_group
        not in definition.required_boundary_groups
    ):
        raise ValueError(
            "Smoke-test output group must be one of the "
            "required engineering boundaries."
        )

    volume_names = tuple(
        name
        for _, name in definition.volume_groups
    )

    if len(set(volume_names)) != len(volume_names):
        raise ValueError(
            "Volume physical-group names must be unique."
        )

    if (
        len(volume_names)
        != definition.expected_volume_group_count
    ):
        raise ValueError(
            "Configured volume-group count does not match "
            "the governed expectation."
        )

    if (
        len(definition.required_boundary_groups)
        != definition.expected_boundary_group_count
    ):
        raise ValueError(
            "Required boundary-group count does not match "
            "the governed expectation."
        )

    if len(
        set(definition.required_boundary_groups)
    ) != len(definition.required_boundary_groups):
        raise ValueError(
            "Required boundary-group names must be unique."
        )

    return definition


@dataclass(frozen=True)
class CompleteJointCalculixMeshData:
    """Four component meshes and named engineering boundaries."""

    points_mm: NDArray[np.float64]
    component_tetrahedra: Mapping[
        str,
        NDArray[np.int64],
    ]
    boundary_triangles: Mapping[
        str,
        NDArray[np.int64],
    ]
    boundary_node_sets: Mapping[
        str,
        tuple[int, ...],
    ]

    @property
    def node_count(self) -> int:
        """Return the total number of mesh nodes."""

        return len(self.points_mm)

    @property
    def element_count(self) -> int:
        """Return the total number of tetrahedra."""

        return sum(
            len(tetrahedra)
            for tetrahedra in (
                self.component_tetrahedra.values()
            )
        )

    @property
    def boundary_triangle_count(self) -> int:
        """Return the total number of boundary triangles."""

        return sum(
            len(triangles)
            for triangles in self.boundary_triangles.values()
        )

    def component_element_count(
        self,
        component: str,
    ) -> int:
        """Return tetrahedra belonging to one component."""

        try:
            return len(self.component_tetrahedra[component])
        except KeyError as error:
            raise ValueError(
                f"Unknown joint component: {component}"
            ) from error

    def boundary_triangle_count_for(
        self,
        physical_name: str,
    ) -> int:
        """Return triangles in one engineering boundary."""

        try:
            return len(self.boundary_triangles[physical_name])
        except KeyError as error:
            raise ValueError(
                f"Unknown joint boundary: {physical_name}"
            ) from error


def read_grouped_complete_joint_mesh(
    msh_path: Path,
    definition: CompleteJointCalculixTransferDefinition,
) -> CompleteJointCalculixMeshData:
    """Read all joint volumes and boundaries from Gmsh MSH."""

    if not msh_path.exists() or msh_path.stat().st_size <= 0:
        raise FileNotFoundError(
            f"Valid grouped joint mesh not found: {msh_path}"
        )

    mesh = meshio.read(msh_path)

    physical_data = mesh.cell_data.get("gmsh:physical")

    if physical_data is None:
        raise RuntimeError(
            "Grouped joint mesh contains no gmsh:physical data."
        )

    if len(physical_data) != len(mesh.cells):
        raise RuntimeError(
            "Physical data does not align with mesh cell blocks."
        )

    field_lookup: dict[tuple[int, int], str] = {}

    for name, values in mesh.field_data.items():
        physical_tag = int(values[0])
        dimension = int(values[1])

        field_lookup[
            (physical_tag, dimension)
        ] = name

    volume_lookup = {
        definition.volume_name(component): component
        for component in COMPONENT_ORDER
    }

    required_boundaries = set(
        definition.required_boundary_groups
    )

    component_blocks: dict[
        str,
        list[NDArray[np.int64]],
    ] = {
        component: []
        for component in COMPONENT_ORDER
    }

    boundary_blocks: dict[
        str,
        list[NDArray[np.int64]],
    ] = {
        name: []
        for name in definition.required_boundary_groups
    }

    recovered_tetrahedron_count = 0
    recovered_triangle_count = 0

    for cell_block, block_physical_tags in zip(
        mesh.cells,
        physical_data,
        strict=True,
    ):
        physical_tags = np.asarray(
            block_physical_tags,
            dtype=np.int64,
        )

        if cell_block.type == "tetra":
            connectivity = np.asarray(
                cell_block.data,
                dtype=np.int64,
            )

            if len(connectivity) != len(physical_tags):
                raise RuntimeError(
                    "Tetrahedral connectivity and physical "
                    "tags have different lengths."
                )

            recovered_tetrahedron_count += len(connectivity)

            for physical_tag in np.unique(physical_tags):
                physical_name = field_lookup.get(
                    (int(physical_tag), 3)
                )

                if physical_name is None:
                    raise RuntimeError(
                        "A tetrahedral block belongs to an "
                        "unnamed physical volume."
                    )

                component = volume_lookup.get(physical_name)

                if component is None:
                    raise RuntimeError(
                        "Unexpected tetrahedral volume group: "
                        f"{physical_name}."
                    )

                mask = physical_tags == physical_tag

                component_blocks[component].append(
                    connectivity[mask]
                )

        elif cell_block.type == "triangle":
            connectivity = np.asarray(
                cell_block.data,
                dtype=np.int64,
            )

            if len(connectivity) != len(physical_tags):
                raise RuntimeError(
                    "Triangle connectivity and physical "
                    "tags have different lengths."
                )

            recovered_triangle_count += len(connectivity)

            for physical_tag in np.unique(physical_tags):
                physical_name = field_lookup.get(
                    (int(physical_tag), 2)
                )

                if physical_name is None:
                    raise RuntimeError(
                        "A boundary block belongs to an "
                        "unnamed physical surface."
                    )

                if physical_name not in required_boundaries:
                    raise RuntimeError(
                        "Unexpected boundary physical group: "
                        f"{physical_name}."
                    )

                mask = physical_tags == physical_tag

                boundary_blocks[physical_name].append(
                    connectivity[mask]
                )

    component_tetrahedra: dict[
        str,
        NDArray[np.int64],
    ] = {}

    for component in COMPONENT_ORDER:
        blocks = component_blocks[component]

        if not blocks:
            raise RuntimeError(
                "No tetrahedra recovered for joint component: "
                f"{component}."
            )

        component_tetrahedra[component] = np.vstack(
            blocks
        )

    boundary_triangles: dict[
        str,
        NDArray[np.int64],
    ] = {}

    boundary_node_sets: dict[
        str,
        tuple[int, ...],
    ] = {}

    for physical_name in (
        definition.required_boundary_groups
    ):
        blocks = boundary_blocks[physical_name]

        if not blocks:
            raise RuntimeError(
                "Required joint boundary was not recovered: "
                f"{physical_name}."
            )

        triangles = np.vstack(blocks)

        boundary_triangles[physical_name] = triangles

        boundary_node_sets[physical_name] = tuple(
            int(node_index) + 1
            for node_index in np.unique(triangles)
        )

    points = np.asarray(
        mesh.points[:, :3],
        dtype=np.float64,
    )

    element_count = sum(
        len(tetrahedra)
        for tetrahedra in component_tetrahedra.values()
    )

    boundary_triangle_count = sum(
        len(triangles)
        for triangles in boundary_triangles.values()
    )

    if element_count != recovered_tetrahedron_count:
        raise RuntimeError(
            "Component element total does not match the "
            "recovered tetrahedron total."
        )

    if boundary_triangle_count != recovered_triangle_count:
        raise RuntimeError(
            "Boundary-group total does not match the "
            "recovered triangle total."
        )

    if len(points) < definition.minimum_node_count:
        raise RuntimeError(
            "Transferred node count is below the "
            "controlled minimum."
        )

    if element_count < definition.minimum_element_count:
        raise RuntimeError(
            "Transferred element count is below the "
            "controlled minimum."
        )

    all_tetrahedra = np.vstack(
        tuple(component_tetrahedra.values())
    )

    all_triangles = np.vstack(
        tuple(boundary_triangles.values())
    )

    if np.min(all_tetrahedra) < 0:
        raise RuntimeError(
            "Tetrahedral connectivity contains a "
            "negative node index."
        )

    if np.max(all_tetrahedra) >= len(points):
        raise RuntimeError(
            "Tetrahedral connectivity references a "
            "missing node."
        )

    if np.min(all_triangles) < 0:
        raise RuntimeError(
            "Boundary connectivity contains a "
            "negative node index."
        )

    if np.max(all_triangles) >= len(points):
        raise RuntimeError(
            "Boundary connectivity references a "
            "missing node."
        )

    return CompleteJointCalculixMeshData(
        points_mm=points,
        component_tetrahedra=component_tetrahedra,
        boundary_triangles=boundary_triangles,
        boundary_node_sets=boundary_node_sets,
    )


@dataclass(frozen=True)
class CompleteJointCalculixDeckSummary:
    """Summary of the written four-volume transfer deck."""

    node_count: int
    element_count: int
    volume_element_set_count: int
    boundary_node_set_count: int
    element_surface_count: int
    mapped_element_face_count: int
    smoke_test_fixed_node_count: int
    input_file_size_bytes: int
    component_element_counts: tuple[
        tuple[str, int],
        ...,
    ]


def _calculix_surface_name(
    physical_name: str,
) -> str:
    """Return a distinct CalculiX surface identifier."""

    return _calculix_name(
        f"SURF_{physical_name}"
    )


def write_complete_joint_calculix_transfer_deck(
    mesh_data: CompleteJointCalculixMeshData,
    definition: CompleteJointCalculixTransferDefinition,
    input_path: Path,
    *,
    internal_surface_normals: (
        Mapping[str, tuple[float, float, float]] | None
    ) = None,
) -> CompleteJointCalculixDeckSummary:
    """Write nodes, component ELSETs and boundary NSETs."""

    mapped_boundary_faces = (
        map_complete_joint_boundary_faces(
            mesh_data,
            internal_surface_normals=(
                internal_surface_normals
            ),
        )
    )

    lines = [
        "*HEADING",
        (
            f"{definition.simulation_id} "
            "complete-joint mesh-transfer verification"
        ),
        "**",
        "** Solver working units: mm, N, MPa",
        "** Transfer-only deck: no contact or loading",
        "**",
        "*NODE",
    ]

    for node_id, point in enumerate(
        mesh_data.points_mm,
        start=1,
    ):
        lines.append(
            f"{node_id}, "
            f"{point[0]:.12e}, "
            f"{point[1]:.12e}, "
            f"{point[2]:.12e}"
        )

    next_element_id = 1
    component_counts: list[tuple[str, int]] = []

    for component in COMPONENT_ORDER:
        tetrahedra = mesh_data.component_tetrahedra[
            component
        ]

        element_set_name = _calculix_name(
            definition.volume_name(component)
        )

        lines.append(
            "*ELEMENT, "
            f"TYPE={definition.element_type}, "
            f"ELSET={element_set_name}"
        )

        for connectivity in tetrahedra:
            node_ids = tuple(
                int(node_index) + 1
                for node_index in connectivity
            )

            lines.append(
                f"{next_element_id}, "
                + ", ".join(
                    str(node_id)
                    for node_id in node_ids
                )
            )

            next_element_id += 1

        component_counts.append(
            (component, len(tetrahedra))
        )

    for physical_name in sorted(
        mesh_data.boundary_node_sets
    ):
        calculix_name = _calculix_name(physical_name)

        lines.append(
            f"*NSET, NSET={calculix_name}"
        )

        lines.extend(
            _format_identifier_rows(
                mesh_data.boundary_node_sets[
                    physical_name
                ]
            )
        )

    for physical_name in sorted(
        mapped_boundary_faces
    ):
        lines.append(
            "*SURFACE, TYPE=ELEMENT, "
            f"NAME={_calculix_surface_name(physical_name)}"
        )

        for face in mapped_boundary_faces[
            physical_name
        ]:
            lines.append(
                f"{face.element_id}, {face.face_label}"
            )

    material_definitions = (
        definition.bolt_material_name,
        definition.nut_material_name,
        definition.member_material_name,
    )

    for material_name in material_definitions:
        lines.extend(
            [
                (
                    "*MATERIAL, NAME="
                    f"{_calculix_name(material_name)}"
                ),
                "*ELASTIC",
                (
                    f"{definition.youngs_modulus_mpa:.12e}, "
                    f"{definition.poissons_ratio:.12e}"
                ),
            ]
        )

    section_assignments = (
        (
            BOLT,
            definition.bolt_material_name,
        ),
        (
            NUT,
            definition.nut_material_name,
        ),
        (
            HEAD_SIDE_MEMBER,
            definition.member_material_name,
        ),
        (
            NUT_SIDE_MEMBER,
            definition.member_material_name,
        ),
    )

    for component, material_name in section_assignments:
        lines.append(
            "*SOLID SECTION, "
            f"ELSET={_calculix_name(definition.volume_name(component))}, "
            f"MATERIAL={_calculix_name(material_name)}"
        )

    fixed_node_set = _calculix_name(
        definition.smoke_test_fixed_node_set
    )

    output_node_group = _calculix_name(
        definition.smoke_test_output_node_group
    )

    lines.extend(
        [
            "**",
            "** Fully constrained zero-load solver-read smoke step",
            "** This step is intentionally nonphysical.",
            (
                "*NSET, NSET="
                f"{fixed_node_set}, GENERATE"
            ),
            f"1, {mesh_data.node_count}, 1",
            "*STEP, NLGEOM=NO",
            "*STATIC",
            "1.0, 1.0",
            "*BOUNDARY",
            f"{fixed_node_set}, 1, 3, 0.0",
            (
                "*NODE PRINT, NSET="
                f"{output_node_group}, TOTALS=ONLY"
            ),
            "U",
            (
                "*NODE FILE, NSET="
                f"{output_node_group}"
            ),
            "U",
            "*END STEP",
            "",
        ]
    )

    input_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
        newline="\n",
    )

    written_element_count = next_element_id - 1

    if written_element_count != mesh_data.element_count:
        raise RuntimeError(
            "Written element count does not match "
            "the transferred mesh."
        )

    mapped_element_face_count = sum(
        len(faces)
        for faces in mapped_boundary_faces.values()
    )

    return CompleteJointCalculixDeckSummary(
        node_count=mesh_data.node_count,
        element_count=written_element_count,
        volume_element_set_count=len(COMPONENT_ORDER),
        boundary_node_set_count=len(
            mesh_data.boundary_node_sets
        ),
        element_surface_count=len(
            mapped_boundary_faces
        ),
        mapped_element_face_count=(
            mapped_element_face_count
        ),
        smoke_test_fixed_node_count=(
            mesh_data.node_count
        ),
        input_file_size_bytes=input_path.stat().st_size,
        component_element_counts=tuple(
            component_counts
        ),
    )


@dataclass(frozen=True)
class CalculixElementFace:
    """One CalculiX solid-element face reference."""

    element_id: int
    face_label: str


def _c3d4_faces(
    connectivity: NDArray[np.int64],
) -> tuple[tuple[str, tuple[int, int, int]], ...]:
    """Return CalculiX C3D4 face labels and node indices."""

    if connectivity.shape != (4,):
        raise ValueError(
            "C3D4 connectivity must contain four nodes."
        )

    node_1 = int(connectivity[0])
    node_2 = int(connectivity[1])
    node_3 = int(connectivity[2])
    node_4 = int(connectivity[3])

    return (
        ("S1", (node_1, node_2, node_3)),
        ("S2", (node_1, node_4, node_2)),
        ("S3", (node_2, node_4, node_3)),
        ("S4", (node_3, node_4, node_1)),
    )


def _outward_c3d4_face_normal(
    points_mm: NDArray[np.float64],
    connectivity: NDArray[np.int64],
    face_nodes: tuple[int, int, int],
) -> NDArray[np.float64]:
    """Return the unit outward normal of one C3D4 face."""

    point_1 = points_mm[face_nodes[0]]
    point_2 = points_mm[face_nodes[1]]
    point_3 = points_mm[face_nodes[2]]

    normal = np.cross(
        point_2 - point_1,
        point_3 - point_1,
    )

    magnitude = float(np.linalg.norm(normal))

    if magnitude <= 0.0:
        raise RuntimeError(
            "A C3D4 face has zero geometric area."
        )

    face_node_set = set(face_nodes)

    opposite_nodes = [
        int(node_index)
        for node_index in connectivity
        if int(node_index) not in face_node_set
    ]

    if len(opposite_nodes) != 1:
        raise RuntimeError(
            "Could not identify the opposite C3D4 node."
        )

    face_centroid = (
        point_1 + point_2 + point_3
    ) / 3.0

    opposite_direction = (
        points_mm[opposite_nodes[0]]
        - face_centroid
    )

    if float(np.dot(normal, opposite_direction)) > 0.0:
        normal = -normal

    return np.asarray(
        normal / magnitude,
        dtype=np.float64,
    )


def map_complete_joint_boundary_faces(
    mesh_data: CompleteJointCalculixMeshData,
    *,
    internal_surface_normals: (
        Mapping[str, tuple[float, float, float]] | None
    ) = None,
) -> Mapping[str, tuple[CalculixElementFace, ...]]:
    """Map physical triangles to governed C3D4 faces.

    External triangles must match exactly one tetrahedral face.
    A governed internal triangle must match exactly two faces;
    the face whose outward normal follows the requested direction
    is selected.
    """

    requested_normals = (
        {}
        if internal_surface_normals is None
        else dict(internal_surface_normals)
    )

    unknown_internal_surfaces = set(
        requested_normals
    ).difference(mesh_data.boundary_triangles)

    if unknown_internal_surfaces:
        raise ValueError(
            "Internal-surface directions reference unknown "
            "physical groups: "
            + ", ".join(
                sorted(unknown_internal_surfaces)
            )
        )

    normalized_directions: dict[
        str,
        NDArray[np.float64],
    ] = {}

    for physical_name, direction in (
        requested_normals.items()
    ):
        vector = np.asarray(
            direction,
            dtype=np.float64,
        )

        if vector.shape != (3,):
            raise ValueError(
                "Internal-surface direction must contain "
                f"three components: {physical_name}."
            )

        magnitude = float(np.linalg.norm(vector))

        if magnitude <= 0.0:
            raise ValueError(
                "Internal-surface direction cannot be zero: "
                f"{physical_name}."
            )

        normalized_directions[physical_name] = (
            vector / magnitude
        )

    target_lookup: dict[
        tuple[int, int, int],
        str,
    ] = {}

    for physical_name, triangles in (
        mesh_data.boundary_triangles.items()
    ):
        for triangle in triangles:
            sorted_nodes = sorted(
                int(node_index)
                for node_index in triangle
            )

            if len(sorted_nodes) != 3:
                raise RuntimeError(
                    "Boundary triangle must contain three nodes."
                )

            key = (
                sorted_nodes[0],
                sorted_nodes[1],
                sorted_nodes[2],
            )

            existing_name = target_lookup.get(key)

            if existing_name is not None:
                raise RuntimeError(
                    "One boundary triangle belongs to multiple "
                    "physical groups: "
                    f"{existing_name} and {physical_name}."
                )

            target_lookup[key] = physical_name

    candidate_lookup: dict[
        tuple[int, int, int],
        list[
            tuple[
                CalculixElementFace,
                NDArray[np.float64],
            ]
        ],
    ] = {
        key: []
        for key in target_lookup
    }

    next_element_id = 1

    for component in COMPONENT_ORDER:
        tetrahedra = mesh_data.component_tetrahedra[
            component
        ]

        for local_index, connectivity in enumerate(
            tetrahedra
        ):
            element_id = next_element_id + local_index

            for face_label, face_nodes in _c3d4_faces(
                connectivity
            ):
                sorted_face_nodes = sorted(face_nodes)

                key = (
                    sorted_face_nodes[0],
                    sorted_face_nodes[1],
                    sorted_face_nodes[2],
                )

                if key not in target_lookup:
                    continue

                candidate_lookup[key].append(
                    (
                        CalculixElementFace(
                            element_id=element_id,
                            face_label=face_label,
                        ),
                        _outward_c3d4_face_normal(
                            mesh_data.points_mm,
                            connectivity,
                            face_nodes,
                        ),
                    )
                )

        next_element_id += len(tetrahedra)

    mapped_faces: dict[
        str,
        list[CalculixElementFace],
    ] = {
        physical_name: []
        for physical_name in mesh_data.boundary_triangles
    }

    for key, physical_name in target_lookup.items():
        candidates = candidate_lookup[key]

        requested_direction = (
            normalized_directions.get(physical_name)
        )

        if requested_direction is None:
            if len(candidates) != 1:
                raise RuntimeError(
                    "An external physical boundary triangle "
                    "did not match exactly one tetrahedral face: "
                    f"{physical_name} matched {len(candidates)}."
                )

            selected_face = candidates[0][0]

        else:
            if len(candidates) != 2:
                raise RuntimeError(
                    "A governed internal physical triangle "
                    "did not match exactly two tetrahedral faces: "
                    f"{physical_name} matched {len(candidates)}."
                )

            scored_candidates = sorted(
                (
                    (
                        float(
                            np.dot(
                                normal,
                                requested_direction,
                            )
                        ),
                        face,
                    )
                    for face, normal in candidates
                ),
                key=lambda item: item[0],
                reverse=True,
            )

            best_score, selected_face = (
                scored_candidates[0]
            )
            opposite_score = scored_candidates[1][0]

            tolerance = 1.0e-8

            if best_score < 1.0 - tolerance:
                raise RuntimeError(
                    "No internal tetrahedral face follows the "
                    "governed surface-normal direction: "
                    f"{physical_name}, score={best_score:.12e}."
                )

            if opposite_score > -1.0 + tolerance:
                raise RuntimeError(
                    "Internal-surface face normals are not "
                    "oppositely directed: "
                    f"{physical_name}, "
                    f"score={opposite_score:.12e}."
                )

        mapped_faces[physical_name].append(
            selected_face
        )

    resolved = {
        physical_name: tuple(
            sorted(
                faces,
                key=lambda face: (
                    face.element_id,
                    face.face_label,
                ),
            )
        )
        for physical_name, faces in mapped_faces.items()
    }

    mapped_count = sum(
        len(faces)
        for faces in resolved.values()
    )

    if mapped_count != mesh_data.boundary_triangle_count:
        raise RuntimeError(
            "Mapped C3D4 face total does not match the "
            "physical boundary-triangle total."
        )

    for physical_name, triangles in (
        mesh_data.boundary_triangles.items()
    ):
        if len(resolved[physical_name]) != len(triangles):
            raise RuntimeError(
                "Mapped face count differs from the source "
                f"triangle count for {physical_name}."
            )

    return resolved

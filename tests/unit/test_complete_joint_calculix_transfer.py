"""Tests for complete-joint CalculiX transfer settings."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from threadrom.solver import (
    complete_joint_calculix_transfer as transfer,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    BOLT,
    HEAD_SIDE_MEMBER,
    NUT,
    NUT_SIDE_MEMBER,
    load_complete_joint_calculix_transfer_definition,
    map_complete_joint_boundary_faces,
    read_grouped_complete_joint_mesh,
    write_complete_joint_calculix_transfer_deck,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_meshio_topology_for_calculix_element_types() -> None:
    """Each CalculiX element uses the matching Meshio cells."""

    assert transfer._meshio_topology("C3D4") == (
        "tetra",
        "triangle",
        4,
        3,
    )

    assert transfer._meshio_topology("C3D10") == (
        "tetra10",
        "triangle6",
        10,
        6,
    )


def test_c3d10_face_topology_matches_calculix() -> None:
    """Quadratic tetrahedral faces preserve all six nodes."""

    connectivity = np.arange(
        10,
        dtype=np.int64,
    )

    assert transfer._c3d10_faces(connectivity) == (
        (
            "S1",
            (0, 1, 2, 4, 5, 6),
        ),
        (
            "S2",
            (0, 3, 1, 7, 8, 4),
        ),
        (
            "S3",
            (1, 3, 2, 8, 9, 5),
        ),
        (
            "S4",
            (2, 3, 0, 9, 7, 6),
        ),
    )


def test_map_c3d10_boundary_faces() -> None:
    """Six-node physical facets map to C3D10 faces."""

    points = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.5, 0.0, 0.0),
            (0.5, 0.5, 0.0),
            (0.0, 0.5, 0.0),
            (0.0, 0.0, 0.5),
            (0.5, 0.0, 0.5),
            (0.0, 0.5, 0.5),
        ],
        dtype=np.float64,
    )

    tetrahedron = np.arange(
        10,
        dtype=np.int64,
    ).reshape(1, 10)

    empty = np.empty(
        (0, 10),
        dtype=np.int64,
    )

    mesh_data = transfer.CompleteJointCalculixMeshData(
        points_mm=points,
        component_tetrahedra={
            BOLT: tetrahedron,
            NUT: empty,
            HEAD_SIDE_MEMBER: empty,
            NUT_SIDE_MEMBER: empty,
        },
        boundary_triangles={
            "FACE_1": np.asarray(
                [(0, 1, 2, 4, 5, 6)],
                dtype=np.int64,
            ),
            "FACE_2": np.asarray(
                [(0, 3, 1, 7, 8, 4)],
                dtype=np.int64,
            ),
            "FACE_3": np.asarray(
                [(1, 3, 2, 8, 9, 5)],
                dtype=np.int64,
            ),
            "FACE_4": np.asarray(
                [(2, 3, 0, 9, 7, 6)],
                dtype=np.int64,
            ),
        },
        boundary_node_sets={},
    )

    mapped = map_complete_joint_boundary_faces(mesh_data)

    assert {name: faces[0].face_label for name, faces in mapped.items()} == {
        "FACE_1": "S1",
        "FACE_2": "S2",
        "FACE_3": "S3",
        "FACE_4": "S4",
    }


def test_complete_joint_transfer_definition_accepts_c3d10(
    tmp_path: Path,
) -> None:
    """The governed transfer definition supports C3D10."""

    source_path = PROJECT_ROOT / "config" / "complete_joint_calculix_transfer.toml"

    config_text = source_path.read_text(
        encoding="utf-8",
    ).replace(
        'element_type = "C3D4"',
        'element_type = "C3D10"',
        1,
    )

    config_path = tmp_path / "c3d10_transfer.toml"

    config_path.write_text(
        config_text,
        encoding="utf-8",
    )

    definition = load_complete_joint_calculix_transfer_definition(config_path)

    assert definition.element_type == "C3D10"


def test_complete_joint_transfer_definition() -> None:
    """The governed four-volume definition loads correctly."""

    definition = (
        load_complete_joint_calculix_transfer_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_calculix_transfer.toml"
        )
    )

    assert definition.simulation_id == "TRM-SIM-000004"
    assert definition.mesh_id == "TRM-MSH-000005"
    assert definition.mesh_level == "medium"
    assert definition.element_type == "C3D4"
    assert definition.timeout_seconds == 1800
    assert (
        definition.smoke_test_fixed_node_set
        == "ALL_NODES"
    )
    assert (
        definition.smoke_test_output_node_group
        == "BOLT_HEAD_TOP"
    )

    assert definition.volume_name(BOLT) == "BOLT"
    assert definition.volume_name(NUT) == "NUT"
    assert (
        definition.volume_name(HEAD_SIDE_MEMBER)
        == "HEAD_SIDE_MEMBER"
    )
    assert (
        definition.volume_name(NUT_SIDE_MEMBER)
        == "NUT_SIDE_MEMBER"
    )

    assert definition.expected_volume_group_count == 4
    assert definition.expected_boundary_group_count == 17
    assert len(definition.required_boundary_groups) == 17

    assert definition.youngs_modulus_mpa == 210000.0
    assert definition.poissons_ratio == 0.30



def test_read_grouped_complete_joint_mesh() -> None:
    """All volume and boundary groups survive Meshio transfer."""

    definition = (
        load_complete_joint_calculix_transfer_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_calculix_transfer.toml"
        )
    )

    mesh_data = read_grouped_complete_joint_mesh(
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / definition.mesh_id
        / "mesh"
        / definition.source_mesh_name,
        definition,
    )

    assert mesh_data.node_count == 73360
    assert mesh_data.element_count == 333439
    assert mesh_data.boundary_triangle_count == 76978

    assert mesh_data.component_element_count(BOLT) == 199243
    assert mesh_data.component_element_count(NUT) == 76524

    assert (
        mesh_data.component_element_count(
            HEAD_SIDE_MEMBER
        )
        == 28948
    )

    assert (
        mesh_data.component_element_count(
            NUT_SIDE_MEMBER
        )
        == 28724
    )

    assert len(mesh_data.component_tetrahedra) == 4
    assert len(mesh_data.boundary_triangles) == 17
    assert len(mesh_data.boundary_node_sets) == 17

    for physical_name in (
        definition.required_boundary_groups
    ):
        assert (
            mesh_data.boundary_triangle_count_for(
                physical_name
            )
            > 0
        )

        assert mesh_data.boundary_node_sets[
            physical_name
        ]



def test_write_complete_joint_transfer_deck(
    tmp_path: Path,
) -> None:
    """The transfer deck preserves sets and element totals."""

    definition = (
        load_complete_joint_calculix_transfer_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_calculix_transfer.toml"
        )
    )

    mesh_data = read_grouped_complete_joint_mesh(
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / definition.mesh_id
        / "mesh"
        / definition.source_mesh_name,
        definition,
    )

    input_path = tmp_path / f"{definition.job_name}.inp"

    summary = write_complete_joint_calculix_transfer_deck(
        mesh_data,
        definition,
        input_path,
    )

    assert summary.node_count == 73360
    assert summary.element_count == 333439
    assert summary.volume_element_set_count == 4
    assert summary.boundary_node_set_count == 17
    assert summary.element_surface_count == 17
    assert summary.mapped_element_face_count == 76978
    assert summary.smoke_test_fixed_node_count == 73360
    assert summary.input_file_size_bytes > 0

    text = input_path.read_text(encoding="utf-8")

    assert "*ELEMENT, TYPE=C3D4, ELSET=BOLT" in text
    assert "*ELEMENT, TYPE=C3D4, ELSET=NUT" in text
    assert (
        "*ELEMENT, TYPE=C3D4, "
        "ELSET=HEAD_SIDE_MEMBER"
    ) in text
    assert (
        "*ELEMENT, TYPE=C3D4, "
        "ELSET=NUT_SIDE_MEMBER"
    ) in text

    assert "*NSET, NSET=BOLT_THREAD_SURFACES" in text
    assert "*NSET, NSET=NUT_INTERNAL_THREAD" in text
    assert "*MATERIAL, NAME=BOLT_STEEL" in text
    assert "*MATERIAL, NAME=NUT_STEEL" in text
    assert "*MATERIAL, NAME=MEMBER_STEEL" in text

    assert (
        text.count(
            "*SURFACE, TYPE=ELEMENT, NAME="
        )
        == 17
    )

    assert (
        "*SURFACE, TYPE=ELEMENT, "
        "NAME=SURF_BOLT_THREAD_SURFACES"
    ) in text

    assert (
        "*SURFACE, TYPE=ELEMENT, "
        "NAME=SURF_NUT_INTERNAL_THREAD"
    ) in text

    assert (
        "*SURFACE, TYPE=ELEMENT, "
        "NAME=SURF_HEAD_MEMBER_INTERFACE"
    ) in text

    assert (
        "*NSET, NSET=ALL_NODES, GENERATE"
        in text
    )
    assert "1, 73360, 1" in text
    assert "ALL_NODES, 1, 3, 0.0" in text
    assert "*STEP, NLGEOM=NO" in text
    assert "*END STEP" in text



def test_map_complete_joint_boundary_faces() -> None:
    """Every physical triangle maps to one C3D4 face."""

    definition = (
        load_complete_joint_calculix_transfer_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_calculix_transfer.toml"
        )
    )

    mesh_data = read_grouped_complete_joint_mesh(
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / definition.mesh_id
        / "mesh"
        / definition.source_mesh_name,
        definition,
    )

    mapped = map_complete_joint_boundary_faces(
        mesh_data
    )

    assert len(mapped) == 17

    assert sum(
        len(faces)
        for faces in mapped.values()
    ) == 76978

    for physical_name, triangles in (
        mesh_data.boundary_triangles.items()
    ):
        assert len(mapped[physical_name]) == len(triangles)

        assert {
            face.face_label
            for face in mapped[physical_name]
        }.issubset(
            {"S1", "S2", "S3", "S4"}
        )

        assert all(
            1 <= face.element_id <= 333439
            for face in mapped[physical_name]
        )



def test_map_internal_pretension_section_faces() -> None:
    """The shared section resolves to its governed positive-Z side."""

    definition = (
        load_complete_joint_calculix_transfer_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_pretension_calculix_transfer.toml"
        )
    )

    mesh_data = read_grouped_complete_joint_mesh(
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / definition.mesh_id
        / "mesh"
        / definition.source_mesh_name,
        definition,
    )

    mapped = map_complete_joint_boundary_faces(
        mesh_data,
        internal_surface_normals={
            "BOLT_PRETENSION_SECTION": (
                0.0,
                0.0,
                1.0,
            ),
        },
    )

    assert len(mapped) == 18

    assert (
        len(mapped["BOLT_PRETENSION_SECTION"])
        == 1701
    )

    assert sum(
        len(faces)
        for faces in mapped.values()
    ) == mesh_data.boundary_triangle_count

    assert mesh_data.boundary_triangle_count == 78963

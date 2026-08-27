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

    assert mesh_data.node_count == 101493
    assert mesh_data.element_count == 509115
    assert mesh_data.boundary_triangle_count == 78390

    assert mesh_data.component_element_count(BOLT) == 392486
    assert mesh_data.component_element_count(NUT) == 58757

    assert (
        mesh_data.component_element_count(
            HEAD_SIDE_MEMBER
        )
        == 29037
    )

    assert (
        mesh_data.component_element_count(
            NUT_SIDE_MEMBER
        )
        == 28835
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

    assert summary.node_count == 101493
    assert summary.element_count == 509115
    assert summary.volume_element_set_count == 4
    assert summary.boundary_node_set_count == 17
    assert summary.element_surface_count == 17
    assert summary.mapped_element_face_count == 78390
    assert summary.smoke_test_fixed_node_count == 101493
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
    assert "1, 101493, 1" in text
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
    ) == 78390

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
            1 <= face.element_id <= 509115
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
        == 1746
    )

    assert sum(
        len(faces)
        for faces in mapped.values()
    ) == mesh_data.boundary_triangle_count

    assert mesh_data.boundary_triangle_count == 172640


def test_complete_joint_mesh_data_counts_mixed_c3d4_c3d6_elements() -> None:
    """A component may contain C3D4 bulk plus C3D6 pretension wedges."""

    points = np.zeros(
        (10, 3),
        dtype=np.float64,
    )

    tetrahedron = np.asarray(
        [(0, 1, 2, 3)],
        dtype=np.int64,
    )

    wedge = np.asarray(
        [(0, 1, 2, 4, 5, 6)],
        dtype=np.int64,
    )

    empty_tetrahedra = np.empty(
        (0, 4),
        dtype=np.int64,
    )

    empty_wedges = np.empty(
        (0, 6),
        dtype=np.int64,
    )

    mesh_data = transfer.CompleteJointCalculixMeshData(
        points_mm=points,
        component_tetrahedra={
            BOLT: tetrahedron,
            NUT: empty_tetrahedra,
            HEAD_SIDE_MEMBER: empty_tetrahedra,
            NUT_SIDE_MEMBER: empty_tetrahedra,
        },
        component_wedges={
            BOLT: wedge,
            NUT: empty_wedges,
            HEAD_SIDE_MEMBER: empty_wedges,
            NUT_SIDE_MEMBER: empty_wedges,
        },
        boundary_triangles={},
        boundary_node_sets={},
    )

    assert mesh_data.element_count == 2
    assert mesh_data.component_element_count(BOLT) == 2



def test_read_grouped_complete_joint_mesh_recovers_c3d6_wedges(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Meshio wedge blocks survive beside C3D4 bulk elements."""

    from dataclasses import replace
    from types import SimpleNamespace

    definition = (
        load_complete_joint_calculix_transfer_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_calculix_transfer.toml"
        )
    )

    definition = replace(
        definition,
        minimum_node_count=0,
        minimum_element_count=0,
    )

    points = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 2.0),
            (1.0, 0.0, 2.0),
            (0.0, 1.0, 2.0),
            (2.0, 0.0, 0.0),
        ],
        dtype=np.float64,
    )

    cells = []
    physical = []
    field_data = {}

    next_tag = 1

    # One C3D4 element for every governed component.
    for component in (
        BOLT,
        NUT,
        HEAD_SIDE_MEMBER,
        NUT_SIDE_MEMBER,
    ):
        cells.append(
            SimpleNamespace(
                type="tetra",
                data=np.asarray(
                    [(0, 1, 2, 3)],
                    dtype=np.int64,
                ),
            )
        )

        physical.append(
            np.asarray(
                [next_tag],
                dtype=np.int64,
            )
        )

        field_data[
            definition.volume_name(component)
        ] = np.asarray(
            [next_tag, 3],
            dtype=np.int64,
        )

        next_tag += 1

    # One C3D6 pretension-layer element in the bolt.
    #
    # The wedge belongs to the SAME governed BOLT physical
    # volume as the tetrahedral BOLT block, so it must reuse
    # the existing BOLT physical tag.
    bolt_physical_tag = int(
        field_data[
            definition.volume_name(BOLT)
        ][0]
    )

    cells.append(
        SimpleNamespace(
            type="wedge",
            data=np.asarray(
                [(0, 1, 2, 4, 5, 6)],
                dtype=np.int64,
            ),
        )
    )

    physical.append(
        np.asarray(
            [bolt_physical_tag],
            dtype=np.int64,
        )
    )

    # Preserve every governed boundary group.
    boundary_tags = []

    for physical_name in (
        definition.required_boundary_groups
    ):
        field_data[physical_name] = np.asarray(
            [next_tag, 2],
            dtype=np.int64,
        )

        boundary_tags.append(next_tag)

        next_tag += 1

    cells.append(
        SimpleNamespace(
            type="triangle",
            data=np.asarray(
                [
                    (0, 1, 2)
                    for _ in boundary_tags
                ],
                dtype=np.int64,
            ),
        )
    )

    physical.append(
        np.asarray(
            boundary_tags,
            dtype=np.int64,
        )
    )

    fake_mesh = SimpleNamespace(
        points=points,
        cells=cells,
        cell_data={
            "gmsh:physical": physical,
        },
        field_data=field_data,
    )

    monkeypatch.setattr(
        transfer.meshio,
        "read",
        lambda _: fake_mesh,
    )

    synthetic_path = tmp_path / "synthetic.msh"
    synthetic_path.write_text(
        "synthetic mesh placeholder",
        encoding="utf-8",
    )

    mesh_data = read_grouped_complete_joint_mesh(
        synthetic_path,
        definition,
    )

    assert mesh_data.element_count == 5

    assert (
        mesh_data.component_tetrahedra[BOLT].shape
        == (1, 4)
    )

    assert (
        mesh_data.component_wedges[BOLT].shape
        == (1, 6)
    )

    assert mesh_data.component_element_count(BOLT) == 2


def test_write_complete_joint_transfer_deck_emits_c3d6_wedges(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Mixed bolt meshes emit both C3D4 and C3D6 element blocks."""

    from dataclasses import replace

    definition = (
        load_complete_joint_calculix_transfer_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_calculix_transfer.toml"
        )
    )

    definition = replace(
        definition,
        minimum_node_count=0,
        minimum_element_count=0,
    )

    points = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 2.0),
            (1.0, 0.0, 2.0),
            (0.0, 1.0, 2.0),
        ],
        dtype=np.float64,
    )

    tetrahedron = np.asarray(
        [(0, 1, 2, 3)],
        dtype=np.int64,
    )

    wedge = np.asarray(
        [(0, 1, 2, 4, 5, 6)],
        dtype=np.int64,
    )

    empty_tetrahedra = np.empty(
        (0, 4),
        dtype=np.int64,
    )

    empty_wedges = np.empty(
        (0, 6),
        dtype=np.int64,
    )

    mesh_data = transfer.CompleteJointCalculixMeshData(
        points_mm=points,
        component_tetrahedra={
            BOLT: tetrahedron,
            NUT: empty_tetrahedra,
            HEAD_SIDE_MEMBER: empty_tetrahedra,
            NUT_SIDE_MEMBER: empty_tetrahedra,
        },
        component_wedges={
            BOLT: wedge,
            NUT: empty_wedges,
            HEAD_SIDE_MEMBER: empty_wedges,
            NUT_SIDE_MEMBER: empty_wedges,
        },
        boundary_triangles={},
        boundary_node_sets={},
    )

    # This test is only about volume-element emission.
    monkeypatch.setattr(
        transfer,
        "map_complete_joint_boundary_faces",
        lambda *_args, **_kwargs: {},
    )

    output_path = tmp_path / "mixed.inp"

    transfer.write_complete_joint_calculix_transfer_deck(
        mesh_data,
        definition,
        output_path,
    )

    text = output_path.read_text(
        encoding="utf-8",
    )

    assert "*ELEMENT, TYPE=C3D4, ELSET=BOLT" in text

    assert (
        "*ELEMENT, TYPE=C3D6, "
        "ELSET=BOLT_PRETENSION_LAYER"
        in text
    )



def test_map_complete_joint_boundary_faces_handles_c3d6_wedge_ids() -> None:
    """Boundary mapping preserves IDs for C3D6 wedge faces."""

    points = np.asarray(
        [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, 2.0),
            (1.0, 0.0, 2.0),
            (0.0, 1.0, 2.0),
        ],
        dtype=np.float64,
    )

    tetrahedron = np.asarray(
        [(0, 1, 2, 3)],
        dtype=np.int64,
    )

    wedge = np.asarray(
        [(0, 1, 2, 4, 5, 6)],
        dtype=np.int64,
    )

    empty_tetrahedra = np.empty(
        (0, 4),
        dtype=np.int64,
    )

    empty_wedges = np.empty(
        (0, 6),
        dtype=np.int64,
    )

    mesh_data = transfer.CompleteJointCalculixMeshData(
        points_mm=points,
        component_tetrahedra={
            BOLT: tetrahedron,
            NUT: empty_tetrahedra,
            HEAD_SIDE_MEMBER: empty_tetrahedra,
            NUT_SIDE_MEMBER: empty_tetrahedra,
        },
        component_wedges={
            BOLT: wedge,
            NUT: empty_wedges,
            HEAD_SIDE_MEMBER: empty_wedges,
            NUT_SIDE_MEMBER: empty_wedges,
        },
        boundary_triangles={
            "WEDGE_TOP": np.asarray(
                [(4, 5, 6)],
                dtype=np.int64,
            ),
        },
        boundary_node_sets={},
    )

    mapped = map_complete_joint_boundary_faces(
        mesh_data
    )

    assert mapped["WEDGE_TOP"][0].element_id == 2
    assert mapped["WEDGE_TOP"][0].face_label == "S2"


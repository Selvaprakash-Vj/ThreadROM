"""Tests for complete-joint CalculiX transfer settings."""

from __future__ import annotations

from pathlib import Path

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

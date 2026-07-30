"""Tests for complete-joint contact configuration."""

from __future__ import annotations

from pathlib import Path

from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
)
from threadrom.solver.complete_joint_contact import (
    MEMBER_INTERFACE,
    NUT_BEARING,
    THREAD,
    UNDER_HEAD,
    load_complete_joint_contact_definition,
    render_complete_joint_contact_keywords,
    validate_contact_surfaces_against_transfer,
    write_complete_joint_contact_smoke_deck,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_complete_joint_contact_definition() -> None:
    """The four governed contact pairs load correctly."""

    definition = load_complete_joint_contact_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_contact.toml"
    )

    assert definition.contact_model_id == "TRM-CNT-000001"
    assert definition.simulation_id == "TRM-SIM-000005"
    assert (
        definition.solver_job_name
        == "trm_cnt_000001_contact_smoke"
    )
    assert definition.contact_type == "SURFACE TO SURFACE"
    assert definition.pressure_overclosure == "LINEAR"
    assert (
        definition.normal_stiffness_scale_per_mm
        == 10.0
    )
    assert definition.friction_coefficient == 0.15
    assert (
        definition.friction_stick_slope_ratio
        == 0.01
    )

    assert len(definition.contact_pairs) == 4

    assert (
        definition.pair(THREAD).slave_surface
        == "SURF_NUT_INTERNAL_THREAD"
    )
    assert (
        definition.pair(THREAD).master_surface
        == "SURF_BOLT_THREAD_SURFACES"
    )
    assert (
        definition.pair(UNDER_HEAD).slave_surface
        == "SURF_HEAD_MEMBER_HEAD_BEARING"
    )
    assert (
        definition.pair(NUT_BEARING).master_surface
        == "SURF_NUT_LOWER_BEARING"
    )
    assert (
        definition.pair(MEMBER_INTERFACE).master_surface
        == "SURF_NUT_MEMBER_INTERFACE"
    )


def test_contact_surfaces_exist_in_transfer() -> None:
    """Every contact surface exists in the transferred mesh."""

    contact = load_complete_joint_contact_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_contact.toml"
    )

    transfer = (
        load_complete_joint_calculix_transfer_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_calculix_transfer.toml"
        )
    )

    validate_contact_surfaces_against_transfer(
        contact,
        transfer,
    )



def test_render_complete_joint_contact_keywords() -> None:
    """CalculiX contact keywords use governed physical values."""

    contact = load_complete_joint_contact_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_contact.toml"
    )

    transfer = (
        load_complete_joint_calculix_transfer_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_calculix_transfer.toml"
        )
    )

    lines = render_complete_joint_contact_keywords(
        contact,
        transfer,
    )

    text = "\n".join(lines)

    assert (
        "*SURFACE INTERACTION, NAME=JOINT_CONTACT"
        in text
    )
    assert (
        "*SURFACE BEHAVIOR, "
        "PRESSURE-OVERCLOSURE=LINEAR"
        in text
    )
    assert "2.100000000000e+06" in text
    assert (
        "1.500000000000e-01, "
        "2.100000000000e+04"
        in text
    )
    assert text.count("*CONTACT PAIR,") == 4
    assert "SMALL SLIDING" not in text

    for pair in contact.contact_pairs:
        assert (
            f"{pair.slave_surface}, "
            f"{pair.master_surface}"
        ) in text



def test_write_complete_joint_contact_smoke_deck(
    tmp_path: Path,
) -> None:
    """The smoke deck contains all four contact pairs."""

    contact = load_complete_joint_contact_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_contact.toml"
    )

    transfer = (
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
        / transfer.mesh_id
        / "mesh"
        / transfer.source_mesh_name,
        transfer,
    )

    input_path = (
        tmp_path
        / f"{contact.solver_job_name}.inp"
    )

    summary = write_complete_joint_contact_smoke_deck(
        mesh_data,
        transfer,
        contact,
        input_path,
    )

    assert summary.transfer.node_count == 73360
    assert summary.transfer.element_count == 333439
    assert summary.contact_pair_count == 4
    assert summary.interaction_count == 1
    assert (
        summary.normal_stiffness_n_per_mm3
        == 2100000.0
    )
    assert (
        summary.friction_stick_slope_n_per_mm3
        == 21000.0
    )
    assert summary.input_file_size_bytes > 0

    text = input_path.read_text(encoding="utf-8")

    assert text.count("*CONTACT PAIR,") == 4
    assert text.count("*SURFACE INTERACTION,") == 1

    assert (
        text.index("*SURFACE INTERACTION,")
        < text.index("*STEP,")
    )

    assert (
        "SURF_NUT_INTERNAL_THREAD, "
        "SURF_BOLT_THREAD_SURFACES"
    ) in text

    assert (
        "SURF_HEAD_MEMBER_HEAD_BEARING, "
        "SURF_BOLT_UNDER_HEAD_BEARING"
    ) in text

    assert (
        "SURF_NUT_MEMBER_NUT_BEARING, "
        "SURF_NUT_LOWER_BEARING"
    ) in text

    assert (
        "SURF_HEAD_MEMBER_INTERFACE, "
        "SURF_NUT_MEMBER_INTERFACE"
    ) in text

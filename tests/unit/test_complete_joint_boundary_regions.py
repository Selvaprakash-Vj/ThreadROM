"""Tests for complete-joint mesh-derived boundary regions."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from threadrom.solver.complete_joint_boundary_regions import (
    HEAD_SUPPORT,
    NUT_LOAD,
    derive_complete_joint_boundary_regions,
    load_complete_joint_boundary_region_definition,
    render_complete_joint_boundary_region_nsets,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_complete_joint_boundary_region_definition() -> None:
    """The governed boundary-region configuration loads."""

    definition = (
        load_complete_joint_boundary_region_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_boundary_regions.toml"
        )
    )

    assert definition.boundary_region_id == "TRM-BCR-000001"
    assert definition.simulation_id == "TRM-SIM-000006"
    assert definition.mesh_id == "TRM-MSH-000005"
    assert definition.contact_model_id == "TRM-CNT-000001"
    assert definition.outer_band_inner_radius_mm == 12.0
    assert definition.member_outer_radius_mm == 15.0
    assert definition.coordinate_tolerance_mm == 1.0e-6
    assert len(definition.regions) == 2

    assert (
        definition.region(HEAD_SUPPORT).name
        == "HEAD_MEMBER_SUPPORT_BAND"
    )
    assert (
        definition.region(NUT_LOAD).name
        == "NUT_MEMBER_LOAD_BAND"
    )


def test_derive_complete_joint_boundary_regions() -> None:
    """Both annular regions contain 360 non-contact nodes."""

    boundary_definition = (
        load_complete_joint_boundary_region_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_boundary_regions.toml"
        )
    )

    transfer = (
        load_complete_joint_calculix_transfer_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_calculix_transfer.toml"
        )
    )

    contact = load_complete_joint_contact_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_contact.toml"
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

    result = derive_complete_joint_boundary_regions(
        mesh_data,
        boundary_definition,
        transfer,
        contact,
    )

    head_support = result.region(HEAD_SUPPORT)
    nut_load = result.region(NUT_LOAD)

    assert head_support.node_count == 360
    assert nut_load.node_count == 360

    head_excluded = np.asarray(
        mesh_data.boundary_node_sets[
            head_support.excluded_boundary
        ],
        dtype=np.int64,
    )

    nut_excluded = np.asarray(
        mesh_data.boundary_node_sets[
            nut_load.excluded_boundary
        ],
        dtype=np.int64,
    )

    assert len(
        np.intersect1d(
            np.asarray(head_support.node_ids),
            head_excluded,
        )
    ) == 0

    assert len(
        np.intersect1d(
            np.asarray(nut_load.node_ids),
            nut_excluded,
        )
    ) == 0

    assert set(head_support.node_ids).isdisjoint(
        nut_load.node_ids
    )



def test_render_complete_joint_boundary_region_nsets() -> None:
    """Both derived regions render as valid CalculiX NSET cards."""

    boundary_definition = (
        load_complete_joint_boundary_region_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_boundary_regions.toml"
        )
    )

    transfer = (
        load_complete_joint_calculix_transfer_definition(
            PROJECT_ROOT
            / "config"
            / "complete_joint_calculix_transfer.toml"
        )
    )

    contact = load_complete_joint_contact_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_contact.toml"
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

    result = derive_complete_joint_boundary_regions(
        mesh_data,
        boundary_definition,
        transfer,
        contact,
    )

    lines = render_complete_joint_boundary_region_nsets(
        result
    )

    text = "\n".join(lines)

    assert (
        "*NSET, NSET=HEAD_MEMBER_SUPPORT_BAND"
        in text
    )
    assert (
        "*NSET, NSET=NUT_MEMBER_LOAD_BAND"
        in text
    )
    assert text.count("*NSET, NSET=") == 2

    for region in result.regions:
        for node_id in region.node_ids:
            assert str(node_id) in text

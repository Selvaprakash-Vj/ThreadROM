"""Tests for generic Phase-3 boundary-region policy."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from threadrom.solver.complete_joint_boundary_regions import (
    CompleteJointBoundaryRegionDefinition,
    derive_complete_joint_boundary_regions,
    load_complete_joint_boundary_region_definition,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)


def _certified_definition() -> CompleteJointBoundaryRegionDefinition:
    return load_complete_joint_boundary_region_definition(
        Path("config/complete_joint_boundary_regions.toml")
    )


def test_certified_boundary_definition_preserves_exact_mesh_counts() -> None:
    definition = _certified_definition()

    assert definition.expected_head_support_node_count == 360
    assert definition.expected_nut_load_node_count == 360
    assert definition.require_equal_region_node_counts
    assert definition.outer_band_free_annulus_fraction is None


def test_generic_boundary_definition_can_disable_mesh_specific_counts() -> None:
    certified = _certified_definition()

    generic = replace(
        certified,
        expected_head_support_node_count=None,
        expected_nut_load_node_count=None,
        require_equal_region_node_counts=False,
        outer_band_free_annulus_fraction=0.5,
    )

    assert generic.expected_head_support_node_count is None
    assert generic.expected_nut_load_node_count is None
    assert not generic.require_equal_region_node_counts
    assert generic.outer_band_free_annulus_fraction == 0.5


def test_generic_policy_preserves_topology_safety_gate() -> None:
    certified = _certified_definition()

    generic = replace(
        certified,
        expected_head_support_node_count=None,
        expected_nut_load_node_count=None,
        require_equal_region_node_counts=False,
        outer_band_free_annulus_fraction=0.5,
    )

    assert generic.require_zero_bearing_overlap


def test_generic_outer_half_free_annulus_is_mesh_derived() -> None:
    transfer = load_complete_joint_calculix_transfer_definition(
        Path("config/complete_joint_calculix_transfer.toml")
    )

    contact = load_complete_joint_contact_definition(
        Path("config/complete_joint_contact.toml")
    )

    mesh = read_grouped_complete_joint_mesh(
        Path(
            "simulations/staging/TRM-MSH-000005/mesh/"
            "complete_joint_grouped_medium_first_order.msh"
        ),
        transfer,
    )

    generic = replace(
        _certified_definition(),
        expected_head_support_node_count=None,
        expected_nut_load_node_count=None,
        require_equal_region_node_counts=False,
        outer_band_free_annulus_fraction=0.5,
    )

    result = derive_complete_joint_boundary_regions(
        mesh,
        generic,
        transfer,
        contact,
    )

    head = result.region("head_support")
    nut = result.region("nut_load")

    assert head.node_count > 0
    assert nut.node_count > 0

    # The derived outer-half rule intentionally need not reproduce
    # the certified 12 mm / 360-node mesh-specific selection.
    assert head.node_count == 349
    assert nut.node_count == 349

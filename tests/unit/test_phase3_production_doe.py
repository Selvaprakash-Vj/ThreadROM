"""Focused governance tests for the Phase-3 CP8 Production DOE."""

from __future__ import annotations

from itertools import product
from pathlib import Path

import pytest

from threadrom.case.serialization import case_sha256
from threadrom.factory.pilot_doe import (
    build_phase3_cp7_pilot_doe,
)
from threadrom.factory.production_doe import (
    ProductionDoeCampaign,
    ProductionDoePolicy,
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)


PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)

POLICY_PATH = (
    PROJECT_ROOT
    / "config"
    / "phase3_production_doe.toml"
)


@pytest.fixture(scope="module")
def policy() -> ProductionDoePolicy:
    return load_phase3_production_doe_policy(
        POLICY_PATH
    )


@pytest.fixture(scope="module")
def campaign(
    policy: ProductionDoePolicy,
) -> ProductionDoeCampaign:
    return build_phase3_production_doe(
        policy
    )


def test_policy_loads_frozen_contract(
    policy: ProductionDoePolicy,
) -> None:
    assert (
        policy.policy_id
        == "TRM-PDOE-000001"
    )

    assert policy.status == "frozen"

    assert (
        policy.normalized_dimension_order
        == (
            "target_preload",
            "head_member_thickness",
            "radial_geometry_fraction",
        )
    )

    assert policy.design_rows_total == 24
    assert policy.blind_holdout_rows == 6

    assert policy.preload_min_n == 15_000.0
    assert policy.preload_max_n == 20_000.0


def test_campaign_has_exact_frozen_membership(
    campaign: ProductionDoeCampaign,
) -> None:
    assert len(
        campaign.design_cases
    ) == 24

    assert len(
        campaign.holdout_cases
    ) == 6

    assert len(
        campaign.all_cases
    ) == 30

    assert {
        case.case_id
        for case in campaign.holdout_cases
    } == {
        "H01",
        "H02",
        "H03",
        "H04",
        "H05",
        "H06",
    }

    assert all(
        case.role == "BLIND_HOLDOUT"
        for case in campaign.holdout_cases
    )


def test_generation_is_deterministic(
    policy: ProductionDoePolicy,
    campaign: ProductionDoeCampaign,
) -> None:
    repeated = (
        build_phase3_production_doe(
            policy
        )
    )

    assert (
        repeated.selected_lhs_candidate_index
        == campaign.selected_lhs_candidate_index
    )

    assert (
        repeated.selected_design_minimum_distance
        == campaign.selected_design_minimum_distance
    )

    assert (
        repeated.minimum_design_to_holdout_distance
        == campaign.minimum_design_to_holdout_distance
    )

    first_identity = tuple(
        (
            case.case_id,
            case.role,
            case.normalized_coordinates,
            case.case_hash,
            case.mesh_policy_name,
            case.source_case_id,
        )
        for case in campaign.all_cases
    )

    repeated_identity = tuple(
        (
            case.case_id,
            case.role,
            case.normalized_coordinates,
            case.case_hash,
            case.mesh_policy_name,
            case.source_case_id,
        )
        for case in repeated.all_cases
    )

    assert repeated_identity == first_identity


def test_existing_anchors_exactly_match_cp7_pilot_cases(
    campaign: ProductionDoeCampaign,
) -> None:
    pilot_by_id = {
        item.case_id.value: item
        for item in (
            build_phase3_cp7_pilot_doe().cases
        )
    }

    anchors = tuple(
        case
        for case in campaign.design_cases
        if case.source_case_id is not None
    )

    assert len(anchors) == 4

    assert {
        case.source_case_id
        for case in anchors
    } == {
        "P00_BASELINE_CONTROL",
        "P01_PRELOAD_LOW",
        "P03_ASYMMETRIC_GRIP",
        "P04_RADIAL_GEOMETRY",
    }

    for anchor in anchors:
        pilot = pilot_by_id[
            anchor.source_case_id
        ]

        assert (
            anchor.case_hash
            == case_sha256(
                pilot.case
            )
        )


def test_design_contains_all_eight_declared_cube_corners(
    campaign: ProductionDoeCampaign,
) -> None:
    expected = set(
        product(
            (0.0, 1.0),
            repeat=3,
        )
    )

    observed = {
        case.normalized_coordinates
        for case in campaign.design_cases
        if all(
            coordinate
            in (0.0, 1.0)
            for coordinate
            in case.normalized_coordinates
        )
    }

    assert observed == expected


def test_physical_mapping_matches_frozen_domain(
    campaign: ProductionDoeCampaign,
) -> None:
    by_id = {
        case.case_id: case
        for case in campaign.design_cases
    }

    # D-BND-002 = [0, 0, 1]
    #
    # preload = 15 kN
    # head/nut = 8/12 mm
    # radial endpoint = 36 mm OD / 12 mm hole
    case = by_id["D-BND-002"].case

    head, nut = case.members.layers

    assert (
        case.loading.target_preload_n
        == pytest.approx(
            15_000.0
        )
    )

    assert (
        head.thickness_mm
        == pytest.approx(8.0)
    )

    assert (
        nut.thickness_mm
        == pytest.approx(12.0)
    )

    assert (
        head.thickness_mm
        + nut.thickness_mm
        == pytest.approx(20.0)
    )

    for member in (head, nut):
        assert (
            member.outer_diameter_mm
            == pytest.approx(36.0)
        )

        assert (
            member.clearance_hole_diameter_mm
            == pytest.approx(12.0)
        )


def test_no_generated_case_leaks_into_uncertified_25kn_region(
    campaign: ProductionDoeCampaign,
) -> None:
    for item in campaign.all_cases:
        target = (
            item.case.loading.target_preload_n
        )

        assert 15_000.0 <= target <= 20_000.0

        assert target != 25_000.0


def test_all_case_hashes_and_coordinates_are_unique(
    campaign: ProductionDoeCampaign,
) -> None:
    hashes = tuple(
        case.case_hash
        for case in campaign.all_cases
    )

    coordinates = tuple(
        case.normalized_coordinates
        for case in campaign.all_cases
    )

    assert len(set(hashes)) == len(hashes)

    assert (
        len(set(coordinates))
        == len(coordinates)
    )


def test_holdouts_satisfy_frozen_design_separation(
    policy: ProductionDoePolicy,
    campaign: ProductionDoeCampaign,
) -> None:
    assert (
        campaign.minimum_design_to_holdout_distance
        >= (
            policy.holdout_minimum_distance
            - 1.0e-15
        )
    )

    design_coordinates = {
        case.normalized_coordinates
        for case in campaign.design_cases
    }

    holdout_coordinates = {
        case.normalized_coordinates
        for case in campaign.holdout_cases
    }

    assert (
        design_coordinates.isdisjoint(
            holdout_coordinates
        )
    )


def test_mesh_policy_split_is_governed_by_radial_coordinate(
    campaign: ProductionDoeCampaign,
) -> None:
    for case in campaign.all_cases:
        radial = (
            case.normalized_coordinates[2]
        )

        if radial == 0.0:
            assert (
                case.mesh_policy_name
                == "medium"
            )
        else:
            assert (
                case.mesh_policy_name
                == "medium_plus_v1"
            )

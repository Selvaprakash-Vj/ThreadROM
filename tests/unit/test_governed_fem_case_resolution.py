"""Isolated tests for reusable governed DOE case selection."""

from types import SimpleNamespace

import pytest

from threadrom.factory.governed_fem_case_resolution import (
    resolve_governed_design_case,
)


def make_case(
    case_id,
    *,
    case_hash=None,
    source_case_id=None,
):
    physical_case = object()

    return SimpleNamespace(
        case_id=case_id,
        case_hash=case_hash or "a" * 64,
        source_case_id=source_case_id,
        case=physical_case,
        mesh_policy_name="synthetic_mesh",
    )


def make_campaign(
    *,
    design_cases=(),
    holdout_cases=(),
):
    return SimpleNamespace(
        policy_id="SYNTHETIC-GOVERNED-DOE",
        design_cases=tuple(design_cases),
        holdout_cases=tuple(holdout_cases),
    )


def test_resolves_different_supported_design_case_identifiers():
    first = make_case("SYNTHETIC-M8", case_hash="a" * 64)
    second = make_case("SYNTHETIC-M12", case_hash="b" * 64)

    campaign = make_campaign(
        design_cases=(first, second),
    )

    resolved = resolve_governed_design_case(
        campaign=campaign,
        requested_case_id="SYNTHETIC-M12",
    )

    assert resolved.case_id == second.case_id
    assert resolved.case_hash == second.case_hash
    assert resolved.case_run_id == "trm_fem_" + "b" * 12
    assert resolved.policy_id == campaign.policy_id

    # The original physical case is preserved, not reconstructed.

    assert resolved.production_case is second
    assert resolved.production_case.case is second.case


def test_holdout_is_not_eligible_for_design_execution():
    campaign = make_campaign(
        design_cases=(make_case("DESIGN"),),
        holdout_cases=(make_case("SEALED-HOLDOUT"),),
    )

    with pytest.raises(
        RuntimeError,
        match="not eligible",
    ):
        resolve_governed_design_case(
            campaign=campaign,
            requested_case_id="SEALED-HOLDOUT",
        )


def test_certified_anchor_cannot_be_recalculated():
    campaign = make_campaign(
        design_cases=(
            make_case(
                "CERTIFIED-ANCHOR",
                source_case_id="EXISTING-CERTIFIED-RUN",
            ),
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Certified anchor must be reused",
    ):
        resolve_governed_design_case(
            campaign=campaign,
            requested_case_id="CERTIFIED-ANCHOR",
        )


def test_duplicate_case_identity_is_rejected():
    campaign = make_campaign(
        design_cases=(
            make_case("DUPLICATE"),
            make_case("DUPLICATE"),
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Duplicate case identity",
    ):
        resolve_governed_design_case(
            campaign=campaign,
            requested_case_id="DUPLICATE",
        )


def test_design_holdout_identity_overlap_is_rejected():
    campaign = make_campaign(
        design_cases=(make_case("OVERLAP"),),
        holdout_cases=(make_case("OVERLAP"),),
    )

    with pytest.raises(
        RuntimeError,
        match="identities overlap",
    ):
        resolve_governed_design_case(
            campaign=campaign,
            requested_case_id="OVERLAP",
        )


def test_invalid_hash_is_rejected():
    case = make_case("INVALID-HASH")
    case.case_hash = "not-a-valid-sha256"

    with pytest.raises(
        RuntimeError,
        match="Invalid governed case hash",
    ):
        resolve_governed_design_case(
            campaign=make_campaign(design_cases=(case,)),
            requested_case_id="INVALID-HASH",
        )


def test_unregistered_case_is_rejected():
    campaign = make_campaign(
        design_cases=(make_case("REGISTERED"),),
    )

    with pytest.raises(
        RuntimeError,
        match="absent from the governed design",
    ):
        resolve_governed_design_case(
            campaign=campaign,
            requested_case_id="UNREGISTERED",
        )

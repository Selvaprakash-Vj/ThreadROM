"""Fail-closed tests for the diversified DOE planning budget."""

from copy import deepcopy
import json
from pathlib import Path
import tomllib

import pytest

from threadrom.factory.diversified_doe_planning import (
    preview_diversified_doe_allocation,
)


ROOT = Path(__file__).resolve().parents[1]


def _inputs():
    policy = tomllib.loads(
        (ROOT / "config/phase3_diversified_doe.toml")
        .read_text(encoding="utf-8-sig")
    )
    atlas = json.loads(
        (ROOT / "docs/phase3_fem_atlas/atlas.json")
        .read_text(encoding="utf-8-sig")
    )
    return policy, atlas


def test_six_cohort_budget_is_provisional_and_counts_reuse_as_ceiling():
    policy, atlas = _inputs()
    preview = preview_diversified_doe_allocation(policy, atlas)

    assert len(preview.cohorts) == 6
    assert preview.design_slots == 72
    assert preview.sealed_validation_slots == 18
    assert preview.total_proposed_states == 90
    assert preview.indexed_historical_states == 22
    assert preview.potential_reuse_ceiling == 14
    assert preview.new_state_floor_if_all_reuse_qualifies == 76
    assert preview.new_state_ceiling_without_reuse == 90

    existing = {
        (row.thread_designation, row.member_material_id):
        row.indexed_historical_states
        for row in preview.cohorts
    }
    assert existing[("M8x1.25", "steel_member")] == 1
    assert existing[("M10x1.5", "steel_member")] == 20
    assert existing[("M12x1.75", "steel_member")] == 1
    assert all(
        row.indexed_historical_states == 0
        for row in preview.cohorts
        if row.member_material_id
        == "member_aluminium_en_aw_6082_t6"
    )


@pytest.mark.parametrize(
    "section,key",
    [
        ("governance", "solver_launch_authorized"),
        ("governance", "sealed_holdout_access_authorized"),
        ("design_governance", "candidate_generation_authorized"),
        ("design_governance", "design_size_frozen"),
        ("design_governance", "holdout_allocation_frozen"),
    ],
)
def test_preview_rejects_unexpected_authorization_or_freeze(
    section, key,
):
    policy, atlas = _inputs()
    changed = deepcopy(policy)
    changed[section][key] = True

    with pytest.raises(RuntimeError):
        preview_diversified_doe_allocation(changed, atlas)


def test_preview_rejects_unverified_historical_configuration():
    policy, atlas = _inputs()
    altered = deepcopy(atlas)
    altered["cases"][0]["engineering_inputs"][
        "configuration_status"
    ] = "UNVERIFIED"

    with pytest.raises(RuntimeError):
        preview_diversified_doe_allocation(policy, altered)


def test_preview_rejects_unqualified_material_authorization():
    policy, atlas = _inputs()
    changed = deepcopy(policy)
    changed["candidate_member_material"][
        "solver_launch_authorized"
    ] = True

    with pytest.raises(RuntimeError):
        preview_diversified_doe_allocation(changed, atlas)

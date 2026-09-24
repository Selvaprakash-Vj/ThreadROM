"""Tests for guarded six-cohort DOE design generation."""

from copy import deepcopy
import json
from pathlib import Path
import tomllib

import pytest

from threadrom.case.serialization import case_sha256
from threadrom.factory.diversified_doe_anchor_selection import (
    select_m10_historical_anchors,
)
from threadrom.factory.diversified_doe_design import (
    propose_diversified_design,
)


ROOT = Path(__file__).resolve().parents[1]


def _inputs():
    policy = tomllib.loads(
        (ROOT / "config/phase3_diversified_doe.toml")
        .read_text(encoding="utf-8-sig")
    )
    atlas = (
        ROOT / "docs/phase3_fem_atlas/atlas.json"
    ).read_bytes()
    anchors = select_m10_historical_anchors(policy, atlas)
    return policy, atlas, anchors


def test_actual_policy_blocks_candidate_generation():
    policy, atlas, anchors = _inputs()

    with pytest.raises(
        RuntimeError,
        match="design-generation authorization",
    ):
        propose_diversified_design(
            policy,
            atlas,
            m10_anchor_selection=anchors,
        )


def test_explicit_in_memory_design_permission_yields_72_design_rows():
    policy, atlas, anchors = _inputs()
    trial_policy = deepcopy(policy)

    trial_policy["design_governance"][
        "candidate_generation_authorized"
    ] = True

    rows = propose_diversified_design(
        trial_policy,
        atlas,
        m10_anchor_selection=anchors,
    )

    assert len(rows) == 72
    assert len({row.proposal_id for row in rows}) == 72
    assert len({row.case_hash for row in rows}) == 72

    indexed = [row for row in rows if row.indexed_case_id]
    novel = [row for row in rows if row.product_case]

    assert len(indexed) == 14
    assert len(novel) == 58

    assert {row.indexed_case_id for row in indexed} == (
        set(anchors.selected_case_ids)
        | {"TRM-XFEM-M8-001", "TRM-XFEM-M12-001"}
    )

    assert all(
        row.product_case is None
        and row.evidence_status
        == "EXACT_HISTORICAL_ANCHOR_ADMISSION_PENDING"
        for row in indexed
    )

    assert all(
        case_sha256(row.product_case) == row.case_hash
        and row.evidence_status
        == "NEW_EVIDENCE_REQUIRED_NO_EXECUTION_AUTHORITY"
        for row in novel
    )

    assert all(
        not row.fem_execution_authorized
        and not row.dataset_admission_authorized
        for row in rows
    )

    cohorts = {
        (row.thread_designation, row.member_material_id)
        for row in rows
    }

    assert len(cohorts) == 6
    assert all(
        sum(
            (row.thread_designation, row.member_material_id)
            == cohort
            for row in rows
        ) == 12
        for cohort in cohorts
    )

    historical_hashes = {
        case["case_hash"]
        for case in json.loads(atlas.decode("utf-8-sig"))["cases"]
    }

    assert all(
        row.case_hash not in historical_hashes
        for row in novel
    )


@pytest.mark.parametrize(
    "section,key",
    [
        ("governance", "solver_launch_authorized"),
        ("governance", "geometry_or_mesh_execution_authorized"),
        ("governance", "dataset_admission_authorized"),
        ("governance", "sealed_holdout_access_authorized"),
        ("design_governance", "design_size_frozen"),
        ("design_governance", "holdout_allocation_frozen"),
    ],
)
def test_in_memory_design_preview_stays_fail_closed(section, key):
    policy, atlas, anchors = _inputs()
    trial = deepcopy(policy)

    trial["design_governance"][
        "candidate_generation_authorized"
    ] = True
    trial[section][key] = True

    with pytest.raises(RuntimeError):
        propose_diversified_design(
            trial,
            atlas,
            m10_anchor_selection=anchors,
        )

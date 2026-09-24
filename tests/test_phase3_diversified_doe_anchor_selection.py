"""Tests for design-only historical M10 anchor selection."""

from copy import deepcopy
import json
from pathlib import Path
import tomllib

import pytest

from threadrom.factory.diversified_doe_anchor_selection import (
    MANDATORY_BOUNDARY_IDS,
    select_m10_historical_anchors,
)


ROOT = Path(__file__).resolve().parents[1]


def _inputs():
    policy = tomllib.loads(
        (ROOT / "config/phase3_diversified_doe.toml")
        .read_text(encoding="utf-8-sig")
    )
    atlas_bytes = (
        ROOT / "docs/phase3_fem_atlas/atlas.json"
    ).read_bytes()
    return policy, atlas_bytes


def test_selection_retains_four_boundaries_and_eight_interiors():
    policy, atlas_bytes = _inputs()
    result = select_m10_historical_anchors(policy, atlas_bytes)

    assert len(result.selected_case_ids) == 12
    assert len(set(result.selected_case_hashes)) == 12
    assert len(result.retained_unselected_ids) == 8
    assert MANDATORY_BOUNDARY_IDS.issubset(
        set(result.selected_case_ids)
    )
    assert sum(
        name.startswith("D-INT-")
        for name in result.selected_case_ids
    ) == 8
    assert result.minimum_selected_pairwise_distance > 0.0
    assert result.evidence_admission_authorized is False
    assert result.fem_execution_authorized is False


def test_selection_is_independent_of_atlas_row_order():
    policy, atlas_bytes = _inputs()
    reference = select_m10_historical_anchors(policy, atlas_bytes)

    reversed_atlas = json.loads(atlas_bytes.decode("utf-8-sig"))
    reversed_atlas["cases"].reverse()

    # Reordered bytes must be explicitly repinned for this isolated
    # determinism test. Production operation never relaxes the pin.
    changed_policy = deepcopy(policy)
    import hashlib

    revised_bytes = json.dumps(
        reversed_atlas, sort_keys=True
    ).encode("utf-8")

    changed_policy["provenance"]["baseline_atlas_sha256"] = (
        hashlib.sha256(revised_bytes).hexdigest()
    )

    reordered = select_m10_historical_anchors(
        changed_policy,
        revised_bytes,
    )

    assert reordered == reference


def test_rejects_corrupted_historical_coordinates():
    policy, atlas_bytes = _inputs()
    altered = json.loads(atlas_bytes.decode("utf-8-sig"))

    target = next(
        row for row in altered["cases"]
        if row["case_id"] == "D-INT-001"
    )
    target["engineering_inputs"]["normalized_coordinates"] = [
        1.4, 0.5, 0.5,
    ]

    import hashlib

    altered_bytes = json.dumps(altered).encode("utf-8")
    changed_policy = deepcopy(policy)
    changed_policy["provenance"]["baseline_atlas_sha256"] = (
        hashlib.sha256(altered_bytes).hexdigest()
    )

    with pytest.raises(RuntimeError, match="invalid historical"):
        select_m10_historical_anchors(
            changed_policy,
            altered_bytes,
        )


@pytest.mark.parametrize(
    "section,key",
    [
        ("governance", "solver_launch_authorized"),
        ("governance", "sealed_holdout_access_authorized"),
        ("governance", "dataset_admission_authorized"),
        ("design_governance", "candidate_generation_authorized"),
        ("design_governance", "design_size_frozen"),
        ("design_governance", "holdout_allocation_frozen"),
    ],
)
def test_selection_rejects_unexpected_authorization(section, key):
    policy, atlas_bytes = _inputs()
    changed = deepcopy(policy)
    changed[section][key] = True

    with pytest.raises(RuntimeError, match="fail-closed"):
        select_m10_historical_anchors(changed, atlas_bytes)

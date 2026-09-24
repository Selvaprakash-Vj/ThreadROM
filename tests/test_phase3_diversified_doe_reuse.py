"""Read-only canonical DOE case-hash and atlas-reuse tests."""

from dataclasses import replace
import json
from pathlib import Path
import tomllib

import pytest

from threadrom.case.reference_cases import phase2_certification_case
from threadrom.factory.cross_size_fem_sentinel import (
    build_phase3_cross_size_fem_sentinels,
)
from threadrom.factory.diversified_doe_reuse import (
    preview_case_against_baseline_atlas,
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


def _preview(case, *, policy=None, atlas_bytes=None):
    baseline_policy, baseline_atlas = _inputs()
    return preview_case_against_baseline_atlas(
        case,
        policy=baseline_policy if policy is None else policy,
        atlas_bytes=(
            baseline_atlas if atlas_bytes is None else atlas_bytes
        ),
    )


def test_both_historical_cross_size_sentinels_match_exact_hash():
    sentinels = build_phase3_cross_size_fem_sentinels()
    assert len(sentinels) == 2

    for sentinel in sentinels:
        result = _preview(sentinel.case)

        assert result.indexed_case_id == (
            sentinel.definition.sentinel_id
        )
        assert result.evidence_status == (
            "EXACT_HASH_INDEXED_ADMISSION_PENDING"
        )
        assert result.dataset_admission_status == "NOT_EVALUATED"
        assert result.fem_execution_authorized is False


def test_aluminium_member_candidate_has_no_historical_exact_match():
    baseline = phase2_certification_case()

    candidate = replace(
        baseline,
        members=replace(
            baseline.members,
            layers=tuple(
                replace(
                    layer,
                    material_id="member_aluminium_en_aw_6082_t6",
                )
                for layer in baseline.members.layers
            ),
        ),
    )

    result = _preview(candidate)

    assert result.member_material_id == (
        "member_aluminium_en_aw_6082_t6"
    )
    assert result.indexed_case_id is None
    assert result.evidence_status == (
        "NO_EXACT_HASH_MATCH_NEW_EVIDENCE_REQUIRED"
    )
    assert result.fem_execution_authorized is False


def test_external_load_is_rejected():
    baseline = phase2_certification_case()
    changed = replace(
        baseline,
        loading=replace(
            baseline.loading,
            external_axial_load_n=1000.0,
        ),
    )

    with pytest.raises(RuntimeError, match="external axial load"):
        _preview(changed)


def test_unequal_interface_friction_is_rejected():
    baseline = phase2_certification_case()
    changed = replace(
        baseline,
        interfaces=replace(
            baseline.interfaces,
            thread_friction_coefficient=0.18,
        ),
    )

    with pytest.raises(RuntimeError, match="common friction"):
        _preview(changed)


def test_unequal_member_materials_are_rejected():
    baseline = phase2_certification_case()
    upper, lower = baseline.members.layers

    changed = replace(
        baseline,
        members=replace(
            baseline.members,
            layers=(
                replace(
                    upper,
                    material_id="member_aluminium_en_aw_6082_t6",
                ),
                lower,
            ),
        ),
    )

    with pytest.raises(RuntimeError, match="clamped-member"):
        _preview(changed)


def test_out_of_bounds_preload_is_rejected():
    baseline = phase2_certification_case()
    changed = replace(
        baseline,
        loading=replace(
            baseline.loading,
            target_preload_n=25000.0,
        ),
    )

    with pytest.raises(RuntimeError, match="stress-ratio"):
        _preview(changed)


def test_atlas_hash_drift_is_rejected():
    baseline = phase2_certification_case()
    _, atlas_bytes = _inputs()

    altered = json.loads(atlas_bytes.decode("utf-8"))
    altered["distinct_case_count"] = 999

    with pytest.raises(RuntimeError, match="policy-pinned"):
        _preview(
            baseline,
            atlas_bytes=json.dumps(altered).encode("utf-8"),
        )


def test_unexpected_execution_authorization_is_rejected():
    baseline = phase2_certification_case()
    policy, atlas_bytes = _inputs()

    policy["governance"]["solver_launch_authorized"] = True

    with pytest.raises(RuntimeError, match="authorization"):
        _preview(
            baseline,
            policy=policy,
            atlas_bytes=atlas_bytes,
        )

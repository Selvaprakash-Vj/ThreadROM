"""CP7 certification of the generic FEM result/reuse pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from threadrom.factory.fem_result_extraction import (
    FemResultExtractionPolicy,
    load_fem_result_extraction_policy,
)
from threadrom.factory.fem_solver_semantic_equivalence import (
    canonicalize_calculix_solver_text,
    compare_calculix_solver_decks,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_governed_result_extraction_policy_loads() -> None:
    policy = load_fem_result_extraction_policy(
        PROJECT_ROOT
        / "config"
        / "fem_result_extraction.toml"
    )

    assert (
        policy.policy_id
        == "complete_joint_semantic_results_v1"
    )

    assert (
        policy.bolt_free_span_band_start_fraction
        == pytest.approx(0.25)
    )

    assert (
        policy.bolt_free_span_band_end_fraction
        == pytest.approx(0.75)
    )

    assert policy.bolt_component == "bolt"

    assert (
        policy.head_side_member_component
        == "head_side_member"
    )

    assert (
        policy.nut_side_member_component
        == "nut_side_member"
    )

    assert (
        policy.under_head_surface
        == "BOLT_UNDER_HEAD_BEARING"
    )

    assert (
        policy.bolt_thread_surface
        == "BOLT_THREAD_SURFACES"
    )

    assert (
        policy.nut_thread_surface
        == "nut_internal_thread"
    )


def test_result_extraction_policy_rejects_invalid_band() -> None:
    with pytest.raises(
        ValueError,
        match="0 <= start < end <= 1",
    ):
        FemResultExtractionPolicy(
            policy_id="test",
            bolt_component="bolt",
            head_side_member_component="head",
            nut_side_member_component="nut",
            bolt_free_span_band_start_fraction=0.8,
            bolt_free_span_band_end_fraction=0.2,
            under_head_surface="under",
            head_member_bearing_surface="head-bearing",
            nut_member_bearing_surface="nut-bearing",
            nut_thread_surface="nut-thread",
            bolt_thread_surface="bolt-thread",
        )


def test_solver_semantic_equivalence_ignores_only_governed_aliases(
    tmp_path: Path,
) -> None:
    calibration = tmp_path / "calibration.inp"
    production = tmp_path / "production.inp"

    calibration.write_text(
        """** calibration metadata
*NODE
1, 0., 0., 0.
*NSET, NSET=CASE_BOLT_THERMAL
1
*TEMPERATURE
CASE_BOLT_THERMAL, -2.635629422511E+02
""",
        encoding="utf-8",
    )

    production.write_text(
        """** production metadata
*node
1, 0., 0., 0.
*nset, nset=BOLT_THERMAL
1
*temperature
BOLT_THERMAL, -2.635629422511E+02
""",
        encoding="utf-8",
    )

    result = compare_calculix_solver_decks(
        left_path=calibration,
        right_path=production,
        symbol_aliases={
            "CASE_BOLT_THERMAL": "BOLT_THERMAL",
        },
    )

    assert result.equivalent
    assert (
        result.left_semantic_sha256
        == result.right_semantic_sha256
    )
    assert (
        result.left_line_count
        == result.right_line_count
    )


def test_solver_semantic_equivalence_rejects_physics_change(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left.inp"
    right = tmp_path / "right.inp"

    left.write_text(
        """*STEP, NLGEOM=YES
*STATIC
5.0E-2, 1.0, 1.0E-6, 5.0E-2
*TEMPERATURE
BOLT_THERMAL, -263.5629422511
*END STEP
""",
        encoding="utf-8",
    )

    right.write_text(
        """*STEP, NLGEOM=YES
*STATIC
5.0E-2, 1.0, 1.0E-6, 5.0E-2
*TEMPERATURE
BOLT_THERMAL, -250.0
*END STEP
""",
        encoding="utf-8",
    )

    result = compare_calculix_solver_decks(
        left_path=left,
        right_path=right,
    )

    assert not result.equivalent
    assert (
        result.left_semantic_sha256
        != result.right_semantic_sha256
    )


def test_solver_semantic_canonicalization_drops_comments_and_blanks() -> None:
    result = canonicalize_calculix_solver_text(
        """** comment

*NODE
1, 0., 0., 0.

** another comment
"""
    )

    assert result == (
        "*node",
        "1, 0., 0., 0.",
    )


def test_solver_semantic_equivalence_requires_real_decks(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing.inp"
    existing.write_text(
        "*NODE\n1, 0., 0., 0.\n",
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError):
        compare_calculix_solver_decks(
            left_path=existing,
            right_path=tmp_path / "missing.inp",
        )

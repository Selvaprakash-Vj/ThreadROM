"""Tests for the preliminary baseline joint-stiffness model."""

from pathlib import Path

import pytest

from threadrom.engineering.baseline_joint_stiffness import (
    evaluate_baseline_joint_stiffness,
)


def test_baseline_joint_stiffness_check_passes() -> None:
    """The proposed assembly retains clamp load and remains below proof."""

    project_root = Path(__file__).resolve().parents[2]

    check = evaluate_baseline_joint_stiffness(
        project_root / "config" / "baseline_fastener.toml",
        project_root / "config" / "baseline_assembly.toml",
    )

    assert check.bolt_effective_length_m == pytest.approx(
        0.030,
    )

    assert check.member_compression_area_m2 == pytest.approx(
        0.0006118251693,
    )

    assert check.bolt_stiffness_n_per_m == pytest.approx(
        405927178.313,
    )

    assert check.member_stiffness_n_per_m == pytest.approx(
        6424164277.509,
    )

    assert check.joint_constant == pytest.approx(
        0.05943217319,
    )

    assert check.bolt_load_increment_n == pytest.approx(
        475.4573855,
    )

    assert check.remaining_clamp_load_n == pytest.approx(
        12475.4573855,
    )

    assert check.separation_load_n == pytest.approx(
        21263.7509278,
    )

    assert check.maximum_bolt_stress_pa / 1.0e6 == pytest.approx(
        353.0884586,
    )

    assert check.passes_proof_check
    assert check.passes_separation_check
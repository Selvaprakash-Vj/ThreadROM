"""Tests for the certified Phase-2 FEM result oracle."""

from pathlib import Path

import pytest

from threadrom.factory.fem_result_oracle import (
    load_fem_certified_result_oracle,
)


ROOT = Path(__file__).resolve().parents[2]

ORACLE_PATH = (
    ROOT
    / "config"
    / "phase2_certified_result_oracle.toml"
)


def test_phase2_result_oracle_loads_certified_values() -> None:
    oracle = load_fem_certified_result_oracle(
        ORACLE_PATH
    )

    assert oracle.clamp_force.target_force_n == pytest.approx(
        20_000.0
    )

    assert oracle.clamp_force.mean_force_n == pytest.approx(
        20_063.5
    )

    assert oracle.clamp_force.spread_n == pytest.approx(
        5.780
    )

    assert (
        oracle.clamp_force.thread_normal_force_n
        == pytest.approx(15_318.240)
    )

    assert (
        oracle.axial_stress.bolt_mean_szz_mpa
        == pytest.approx(315.656)
    )

    assert (
        oracle.axial_stress.bolt_median_szz_mpa
        == pytest.approx(335.369)
    )

    assert (
        oracle.axial_stress.head_member_mean_szz_mpa
        == pytest.approx(-33.081)
    )

    assert (
        oracle.axial_stress.nut_member_mean_szz_mpa
        == pytest.approx(-32.952)
    )


def test_phase2_result_oracle_preserves_deformation_reference() -> None:
    oracle = load_fem_certified_result_oracle(
        ORACLE_PATH
    )

    assert (
        oracle.deformation.member_shortening_mm
        == pytest.approx(0.003212695)
    )

    assert (
        oracle.deformation.analytical_member_shortening_mm
        == pytest.approx(0.003113245)
    )

    assert (
        oracle.deformation.bolt_mechanical_extension_mm
        == pytest.approx(0.038321380)
    )

    assert (
        oracle.deformation.member_shortening_ratio
        == pytest.approx(
            0.003212695
            / 0.003113245
        )
    )


def test_phase2_result_oracle_preserves_thread_flank_reference() -> None:
    oracle = load_fem_certified_result_oracle(
        ORACLE_PATH
    )

    flank = oracle.thread_flank

    assert flank.intended_flank_name == "-Z-normal flank"
    assert flank.engaged_triangle_count == 11943
    assert flank.positive_triangle_count == 3949
    assert flank.negative_triangle_count == 3948

    assert (
        flank.positive_mean_compression_mpa
        == pytest.approx(38.443)
    )

    assert (
        flank.negative_mean_compression_mpa
        == pytest.approx(317.140)
    )

    assert flank.dominance_ratio == pytest.approx(
        8.2496
    )


def test_phase2_result_oracle_preserves_numerical_signature() -> None:
    oracle = load_fem_certified_result_oracle(
        ORACLE_PATH
    )

    numerical = oracle.numerical

    assert numerical.accepted_increment_count == 20
    assert numerical.final_step == 1
    assert numerical.final_increment == 20
    assert numerical.final_attempt == 1
    assert numerical.final_iterations == 21
    assert numerical.final_time == pytest.approx(
        1.0
    )


def test_result_oracle_rejects_wrong_member_stress_sign(
    tmp_path: Path,
) -> None:
    text = ORACLE_PATH.read_text(
        encoding="utf-8",
    )

    text = text.replace(
        "head_member_mean_szz_mpa = -33.081",
        "head_member_mean_szz_mpa = 33.081",
    )

    path = (
        tmp_path
        / "bad_oracle.toml"
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="head-member",
    ):
        load_fem_certified_result_oracle(
            path
        )

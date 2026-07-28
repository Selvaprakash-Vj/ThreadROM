"""Tests for the baseline bolt axial-capacity check."""

from pathlib import Path

import pytest

from threadrom.engineering.baseline_capacity import (
    evaluate_baseline_bolt_capacity,
)


def test_baseline_bolt_capacity_check_passes() -> None:
    """The proposed preload and conservative load envelope remain elastic."""

    project_root = Path(__file__).resolve().parents[2]

    check = evaluate_baseline_bolt_capacity(
        project_root / "config" / "baseline_fastener.toml",
        project_root / "config" / "baseline_assembly.toml",
    )

    assert check.tensile_stress_area_mm2 == pytest.approx(
        57.9895969018,
    )

    assert check.preload_stress_pa / 1.0e6 == pytest.approx(
        344.8894469,
    )

    assert (
        check.conservative_combined_stress_pa / 1.0e6
        == pytest.approx(482.8452256)
    )

    assert check.preload_proof_utilisation == pytest.approx(
        0.5946369774,
    )

    assert check.combined_proof_utilisation == pytest.approx(
        0.8324917683,
    )

    assert check.proof_margin_n == pytest.approx(
        5633.966203,
    )

    assert check.passes_preload_proof_check
    assert check.passes_conservative_combined_check
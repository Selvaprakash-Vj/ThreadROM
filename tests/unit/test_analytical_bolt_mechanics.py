"""Tests for parametric analytical bolt mechanics."""

import math
from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_bolt_mechanics import (
    calculate_analytical_bolt_mechanics,
)
from threadrom.engineering.analytical_inputs import (
    BoltAxialSegmentInput,
    BoltSegmentKind,
)
from threadrom.engineering.analytical_joint_input import (
    BoltComplianceMethod,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)


def _benchmark_joint():
    """Load the governed M10 analytical joint."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def test_m10_segmented_bolt_mechanics_match_reference() -> None:
    """The M10 benchmark reproduces the legacy stiffness basis."""

    result = calculate_analytical_bolt_mechanics(_benchmark_joint())

    assert result.method == "segmented"
    assert result.preload_n == pytest.approx(5000.0)

    assert result.effective_length_mm == pytest.approx(30.0)

    assert len(result.segments) == 3

    assert result.tensile_stress_area_mm2 == pytest.approx(57.9895969018)

    assert result.external_root_area_mm2 == pytest.approx(52.2923116585)

    assert result.axial_stiffness_n_per_mm == pytest.approx(405927.1783129)

    assert result.total_elongation_mm == pytest.approx(0.0123174802455)

    assert result.total_strain_energy_n_mm == pytest.approx(30.7937006139)

    assert result.nominal_tensile_stress_mpa == pytest.approx(86.2223617188)

    assert result.root_section_reference_stress_mpa == pytest.approx(95.6163504992)

    assert result.proof_utilisation == pytest.approx(0.1486592443)

    assert result.yield_utilisation == pytest.approx(0.1347224402)

    assert result.ultimate_utilisation == pytest.approx(0.1077779521)


def test_mixed_segment_compliance_is_summed_in_series() -> None:
    """Threaded and unthreaded compliances add in series."""

    joint = _benchmark_joint()

    bolt = replace(
        joint.bolt,
        axial_segments=(
            BoltAxialSegmentInput(
                segment_id="plain_shank",
                kind=BoltSegmentKind.UNTHREADED_SHANK,
                length_mm=10.0,
                diameter_mm=10.0,
            ),
            BoltAxialSegmentInput(
                segment_id="threaded_grip",
                kind=BoltSegmentKind.THREADED,
                length_mm=10.0,
            ),
        ),
    )

    methods = replace(
        joint.methods,
        head_participation_factor=0.0,
        nut_participation_factor=0.0,
    )

    result = calculate_analytical_bolt_mechanics(
        replace(
            joint,
            bolt=bolt,
            methods=methods,
        )
    )

    nominal_area = math.pi / 4.0 * 10.0**2
    tensile_area = result.tensile_stress_area_mm2

    expected_compliance = 10.0 / (210000.0 * nominal_area) + 10.0 / (210000.0 * tensile_area)

    assert result.total_compliance_mm_per_n == pytest.approx(expected_compliance)

    assert result.axial_stiffness_n_per_mm == pytest.approx(1.0 / expected_compliance)

    assert result.segments[0].axial_stress_mpa < result.segments[1].axial_stress_mpa


def test_uniform_method_uses_grip_and_participation_length() -> None:
    """The uniform method retains the legacy effective-length model."""

    joint = _benchmark_joint()

    methods = replace(
        joint.methods,
        bolt_compliance=(BoltComplianceMethod.UNIFORM_TENSILE_AREA),
    )

    result = calculate_analytical_bolt_mechanics(
        replace(
            joint,
            methods=methods,
        )
    )

    assert result.method == "uniform_tensile_area"
    assert len(result.segments) == 1

    assert result.segments[0].segment_id == ("uniform_effective_bolt")

    assert result.effective_length_mm == pytest.approx(30.0)

    assert result.axial_stiffness_n_per_mm == pytest.approx(405927.1783129)


def test_zero_preload_produces_zero_response() -> None:
    """A zero-preload joint retains finite stiffness but no response."""

    joint = _benchmark_joint()

    loading = replace(
        joint.loading,
        preload_n=0.0,
    )

    result = calculate_analytical_bolt_mechanics(
        replace(
            joint,
            loading=loading,
        )
    )

    assert result.axial_stiffness_n_per_mm > 0.0
    assert result.total_elongation_mm == pytest.approx(0.0)
    assert result.total_strain_energy_n_mm == pytest.approx(0.0)
    assert result.nominal_tensile_stress_mpa == pytest.approx(0.0)
    assert result.maximum_segment_stress_mpa == pytest.approx(0.0)

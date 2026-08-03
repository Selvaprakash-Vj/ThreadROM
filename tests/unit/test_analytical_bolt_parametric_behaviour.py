"""Parametric behaviour tests for analytical bolt mechanics."""

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
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)


def _benchmark_joint():
    """Load the governed analytical benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def test_preload_scaling_obeys_linear_elastic_response() -> None:
    """Stress and elongation scale linearly with axial force."""

    joint = _benchmark_joint()

    base = calculate_analytical_bolt_mechanics(joint)

    doubled = calculate_analytical_bolt_mechanics(
        replace(
            joint,
            loading=replace(
                joint.loading,
                preload_n=2.0 * joint.loading.preload_n,
            ),
        )
    )

    assert doubled.total_compliance_mm_per_n == pytest.approx(base.total_compliance_mm_per_n)

    assert doubled.axial_stiffness_n_per_mm == pytest.approx(base.axial_stiffness_n_per_mm)

    assert doubled.total_elongation_mm == pytest.approx(2.0 * base.total_elongation_mm)

    assert doubled.nominal_tensile_stress_mpa == pytest.approx(
        2.0 * base.nominal_tensile_stress_mpa
    )

    assert doubled.root_section_reference_stress_mpa == pytest.approx(
        2.0 * base.root_section_reference_stress_mpa
    )

    assert doubled.total_strain_energy_n_mm == pytest.approx(4.0 * base.total_strain_energy_n_mm)

    assert doubled.proof_utilisation == pytest.approx(2.0 * base.proof_utilisation)


def test_segment_length_scaling_changes_compliance_only() -> None:
    """Doubling all active lengths doubles compliance."""

    joint = _benchmark_joint()

    methods = replace(
        joint.methods,
        head_participation_factor=0.0,
        nut_participation_factor=0.0,
    )

    reference_joint = replace(
        joint,
        methods=methods,
    )

    reference = calculate_analytical_bolt_mechanics(reference_joint)

    scaled_segments = tuple(
        replace(
            segment,
            length_mm=2.0 * segment.length_mm,
        )
        for segment in joint.bolt.axial_segments
    )

    scaled_bolt = replace(
        joint.bolt,
        nominal_length_mm=(2.0 * joint.bolt.nominal_length_mm),
        axial_segments=scaled_segments,
    )

    scaled = calculate_analytical_bolt_mechanics(
        replace(
            reference_joint,
            bolt=scaled_bolt,
        )
    )

    assert scaled.effective_length_mm == pytest.approx(2.0 * reference.effective_length_mm)

    assert scaled.total_compliance_mm_per_n == pytest.approx(
        2.0 * reference.total_compliance_mm_per_n
    )

    assert scaled.axial_stiffness_n_per_mm == pytest.approx(
        0.5 * reference.axial_stiffness_n_per_mm
    )

    assert scaled.total_elongation_mm == pytest.approx(2.0 * reference.total_elongation_mm)

    assert scaled.nominal_tensile_stress_mpa == pytest.approx(reference.nominal_tensile_stress_mpa)

    assert scaled.total_strain_energy_n_mm == pytest.approx(
        2.0 * reference.total_strain_energy_n_mm
    )


def test_custom_area_segment_uses_ea_over_length() -> None:
    """A custom segment follows the elementary axial-bar relation."""

    joint = _benchmark_joint()

    custom_segment = BoltAxialSegmentInput(
        segment_id="custom_gauge_section",
        kind=BoltSegmentKind.CUSTOM_AREA,
        length_mm=25.0,
        area_mm2=100.0,
    )

    bolt = replace(
        joint.bolt,
        axial_segments=(custom_segment,),
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

    expected_stiffness = 210000.0 * 100.0 / 25.0

    expected_stress = joint.loading.preload_n / 100.0

    expected_elongation = joint.loading.preload_n / expected_stiffness

    assert len(result.segments) == 1

    assert result.segments[0].area_mm2 == pytest.approx(100.0)

    assert result.axial_stiffness_n_per_mm == pytest.approx(expected_stiffness)

    assert result.maximum_segment_stress_mpa == pytest.approx(expected_stress)

    assert result.total_elongation_mm == pytest.approx(expected_elongation)


def test_finer_pitch_increases_threaded_bolt_stiffness() -> None:
    """At fixed diameter, finer pitch retains more tensile area."""

    joint = _benchmark_joint()

    coarse = calculate_analytical_bolt_mechanics(joint)

    fine_thread = replace(
        joint.thread,
        pitch_mm=1.0,
    )

    fine = calculate_analytical_bolt_mechanics(
        replace(
            joint,
            thread=fine_thread,
        )
    )

    assert fine.tensile_stress_area_mm2 > coarse.tensile_stress_area_mm2

    assert fine.axial_stiffness_n_per_mm > coarse.axial_stiffness_n_per_mm

    assert fine.nominal_tensile_stress_mpa < coarse.nominal_tensile_stress_mpa

    assert fine.total_elongation_mm < coarse.total_elongation_mm

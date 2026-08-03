"""Tests for analytical joint strength envelopes."""

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_envelope import (
    PreloadCase,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_joint_strength import (
    calculate_analytical_joint_strength,
)


def _benchmark_joint():
    """Load the governed M10 analytical benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def test_governed_preload_strength_matches_bolt_reference() -> None:
    """The zero-external-load envelope reproduces bolt stress."""

    result = calculate_analytical_joint_strength(_benchmark_joint())

    assert result.method == ("linear_axial_section_stress_envelope_v1")

    assert result.joint_id == "TRM-ANL-000001"
    assert result.bolt_id == "TRM-BLT-000001"

    assert result.highest_bolt_force_n == pytest.approx(5000.0)

    assert result.highest_nominal_tensile_stress_mpa == pytest.approx(86.2223617188)

    assert (
        result.highest_root_section_reference_stress_mpa > result.highest_nominal_tensile_stress_mpa
    )

    assert result.cyclic_responses == ()

    assert result.maximum_nominal_stress_amplitude_mpa is None

    assert not result.any_separation
    assert result.maximum_joint_opening_mm == pytest.approx(0.0)


def test_separated_static_state_uses_full_external_load() -> None:
    """After separation the applied load governs bolt stress."""

    joint = _benchmark_joint()

    modified = replace(
        joint,
        loading=replace(
            joint.loading,
            external_axial_load_n=6000.0,
        ),
    )

    result = calculate_analytical_joint_strength(modified)

    assert result.highest_bolt_force_n == pytest.approx(6000.0)

    assert result.highest_nominal_tensile_stress_mpa == pytest.approx(
        6000.0 / result.tensile_stress_area_mm2
    )

    assert result.any_separation
    assert result.maximum_joint_opening_mm > 0.0


def test_maximum_preload_governs_clamped_static_force() -> None:
    """High preload governs bolt force while the joint stays clamped."""

    joint = _benchmark_joint()

    modified = replace(
        joint,
        loading=replace(
            joint.loading,
            external_axial_load_n=1000.0,
            preload_scatter_fraction=0.2,
        ),
    )

    result = calculate_analytical_joint_strength(modified)

    assert result.governing_point_id == ("maximum_preload:static")

    assert result.highest_bolt_force_n > 6000.0


def test_cyclic_stresses_preserve_force_identities() -> None:
    """Cyclic section stresses are force divided by area."""

    joint = _benchmark_joint()

    modified = replace(
        joint,
        loading=replace(
            joint.loading,
            cyclic_minimum_axial_load_n=1000.0,
            cyclic_maximum_axial_load_n=3000.0,
        ),
    )

    result = calculate_analytical_joint_strength(modified)

    nominal = next(
        response
        for response in result.cyclic_responses
        if response.preload_case is PreloadCase.NOMINAL
    )

    assert nominal.nominal_stress_amplitude_mpa == pytest.approx(
        nominal.bolt_force_amplitude_n / result.tensile_stress_area_mm2
    )

    assert nominal.nominal_stress_range_mpa == pytest.approx(
        2.0 * nominal.nominal_stress_amplitude_mpa
    )

    assert nominal.root_reference_stress_amplitude_mpa > nominal.nominal_stress_amplitude_mpa

    assert result.maximum_nominal_stress_amplitude_mpa == pytest.approx(
        max(response.nominal_stress_amplitude_mpa for response in result.cyclic_responses)
    )


def test_cycle_crossing_separation_is_retained() -> None:
    """Strength results retain separation context."""

    joint = _benchmark_joint()

    modified = replace(
        joint,
        loading=replace(
            joint.loading,
            cyclic_minimum_axial_load_n=1000.0,
            cyclic_maximum_axial_load_n=6000.0,
        ),
    )

    result = calculate_analytical_joint_strength(modified)

    nominal = next(
        response
        for response in result.cyclic_responses
        if response.preload_case is PreloadCase.NOMINAL
    )

    assert nominal.separated_during_cycle
    assert nominal.maximum_joint_opening_mm > 0.0
    assert result.any_separation


def test_strength_utilisations_use_nominal_tensile_stress() -> None:
    """Available material strengths produce direct utilisations."""

    joint = _benchmark_joint()

    result = calculate_analytical_joint_strength(joint)

    material = joint.material_by_id(joint.bolt.material_id)

    if material.proof_stress_mpa is not None:
        assert result.proof_utilisation == pytest.approx(
            result.highest_nominal_tensile_stress_mpa / material.proof_stress_mpa
        )

    if material.yield_strength_mpa is not None:
        assert result.yield_utilisation == pytest.approx(
            result.highest_nominal_tensile_stress_mpa / material.yield_strength_mpa
        )

    if material.ultimate_strength_mpa is not None:
        assert result.ultimate_utilisation == pytest.approx(
            result.highest_nominal_tensile_stress_mpa / material.ultimate_strength_mpa
        )


def test_missing_strength_data_produces_none_utilisations() -> None:
    """Unavailable material strengths are not invented."""

    joint = _benchmark_joint()

    materials = tuple(
        replace(
            material,
            proof_stress_mpa=None,
            yield_strength_mpa=None,
            ultimate_strength_mpa=None,
        )
        if material.material_id == joint.bolt.material_id
        else material
        for material in joint.materials
    )

    result = calculate_analytical_joint_strength(
        replace(
            joint,
            materials=materials,
        )
    )

    assert result.proof_utilisation is None
    assert result.yield_utilisation is None
    assert result.ultimate_utilisation is None

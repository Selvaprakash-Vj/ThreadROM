"""Tests for the proposed baseline assembly."""

from pathlib import Path

import pytest

from threadrom.engineering.baseline_assembly import (
    BaselineAssembly,
    load_baseline_assembly,
    validate_baseline_assembly,
)


def test_baseline_assembly_is_consistent() -> None:
    """The proposed assembly passes all consistency rules."""

    project_root = Path(__file__).resolve().parents[2]

    assembly = load_baseline_assembly(
        project_root / "config" / "baseline_assembly.toml"
    )

    assert assembly.assembly_id == "TRM-ASM-000001"
    assert assembly.bolt_length_mm == pytest.approx(30.0)
    assert assembly.total_grip_length_mm == pytest.approx(20.0)
    assert assembly.stack_length_mm == pytest.approx(30.0)
    assert assembly.engaged_thread_count == pytest.approx(
        8.0 / 1.5,
    )
    assert assembly.target_preload_n == pytest.approx(20000.0)
    assert assembly.external_axial_load_n == pytest.approx(8000.0)


def test_inconsistent_bolt_stack_is_rejected() -> None:
    """A bolt length inconsistent with the assembly stack is rejected."""

    invalid = BaselineAssembly(
        assembly_id="TRM-ASM-TEST",
        bolt_length_mm=35.0,
        pitch_mm=1.5,
        upper_member_thickness_mm=10.0,
        lower_member_thickness_mm=10.0,
        total_grip_length_mm=20.0,
        nut_thickness_mm=8.0,
        thread_engagement_length_mm=8.0,
        protrusion_length_mm=2.0,
        clearance_hole_diameter_mm=11.0,
        outer_diameter_mm=30.0,
        target_preload_n=20000.0,
        external_axial_load_n=8000.0,
        friction_coefficient=0.15,
    )

    with pytest.raises(ValueError):
        validate_baseline_assembly(invalid)

def test_baseline_nut_placement_is_phase_aligned() -> None:
    """Nut placement follows the governed right-hand thread phase."""

    project_root = Path(__file__).resolve().parents[2]

    assembly = load_baseline_assembly(
        project_root
        / "config"
        / "baseline_assembly.toml"
    )

    assert assembly.nut_translation_z_mm == 20.0
    assert abs(assembly.nut_rotation_deg - 120.0) < 1.0e-9
    assert assembly.nut_lower_bearing_z_mm == 20.0
    assert assembly.nut_upper_bearing_z_mm == 28.0
    assert assembly.calculated_protrusion_length_mm == 2.0

"""Tests for resolved Phase-3 assembly definitions."""

import pytest

from threadrom.case.resolved import ResolvedAssembly


def _baseline_assembly() -> ResolvedAssembly:
    """Return the resolved certified Phase-2 assembly geometry."""

    return ResolvedAssembly(
        assembly_id="TRM-ASM-P3-BASELINE",
        bolt_length_mm=30.0,
        pitch_mm=1.5,
        upper_member_thickness_mm=10.0,
        lower_member_thickness_mm=10.0,
        total_grip_length_mm=20.0,
        nut_thickness_mm=8.0,
        thread_engagement_length_mm=8.0,
        protrusion_length_mm=2.0,
        clearance_hole_diameter_mm=11.0,
        outer_diameter_mm=30.0,
    )


def test_resolved_assembly_matches_baseline_geometry() -> None:
    """The certified baseline assembly resolves deterministically."""

    assembly = _baseline_assembly()

    assert assembly.total_grip_length_mm == pytest.approx(20.0)
    assert assembly.nut_translation_z_mm == pytest.approx(20.0)
    assert assembly.nut_lower_bearing_z_mm == pytest.approx(20.0)
    assert assembly.nut_upper_bearing_z_mm == pytest.approx(28.0)
    assert assembly.protrusion_length_mm == pytest.approx(2.0)
    assert assembly.calculated_protrusion_length_mm == pytest.approx(2.0)
    assert assembly.engaged_thread_count == pytest.approx(8.0 / 1.5)


def test_total_grip_must_match_member_thickness_sum() -> None:
    """Resolved grip cannot disagree with its member stack."""

    with pytest.raises(ValueError):
        ResolvedAssembly(
            assembly_id="assembly",
            bolt_length_mm=30.0,
            pitch_mm=1.5,
            upper_member_thickness_mm=10.0,
            lower_member_thickness_mm=10.0,
            total_grip_length_mm=19.0,
            nut_thickness_mm=8.0,
            thread_engagement_length_mm=8.0,
            protrusion_length_mm=3.0,
            clearance_hole_diameter_mm=11.0,
            outer_diameter_mm=30.0,
        )


def test_resolved_protrusion_must_match_stack_geometry() -> None:
    """Stored protrusion remains a checked derived quantity."""

    with pytest.raises(ValueError):
        ResolvedAssembly(
            assembly_id="assembly",
            bolt_length_mm=30.0,
            pitch_mm=1.5,
            upper_member_thickness_mm=10.0,
            lower_member_thickness_mm=10.0,
            total_grip_length_mm=20.0,
            nut_thickness_mm=8.0,
            thread_engagement_length_mm=8.0,
            protrusion_length_mm=1.0,
            clearance_hole_diameter_mm=11.0,
            outer_diameter_mm=30.0,
        )


def test_negative_protrusion_is_rejected() -> None:
    """A nut stack cannot extend beyond available bolt length."""

    with pytest.raises(ValueError):
        ResolvedAssembly(
            assembly_id="assembly",
            bolt_length_mm=27.0,
            pitch_mm=1.5,
            upper_member_thickness_mm=10.0,
            lower_member_thickness_mm=10.0,
            total_grip_length_mm=20.0,
            nut_thickness_mm=8.0,
            thread_engagement_length_mm=8.0,
            protrusion_length_mm=-1.0,
            clearance_hole_diameter_mm=11.0,
            outer_diameter_mm=30.0,
        )


def test_flush_bolt_end_is_representable() -> None:
    """Zero protrusion is structurally valid at the resolved-model level."""

    assembly = ResolvedAssembly(
        assembly_id="assembly",
        bolt_length_mm=28.0,
        pitch_mm=1.5,
        upper_member_thickness_mm=10.0,
        lower_member_thickness_mm=10.0,
        total_grip_length_mm=20.0,
        nut_thickness_mm=8.0,
        thread_engagement_length_mm=8.0,
        protrusion_length_mm=0.0,
        clearance_hole_diameter_mm=11.0,
        outer_diameter_mm=30.0,
    )

    assert assembly.calculated_protrusion_length_mm == pytest.approx(0.0)


def test_thread_engagement_cannot_exceed_nut_thickness() -> None:
    """Resolved engagement must remain inside the nut."""

    with pytest.raises(ValueError):
        ResolvedAssembly(
            assembly_id="assembly",
            bolt_length_mm=30.0,
            pitch_mm=1.5,
            upper_member_thickness_mm=10.0,
            lower_member_thickness_mm=10.0,
            total_grip_length_mm=20.0,
            nut_thickness_mm=8.0,
            thread_engagement_length_mm=9.0,
            protrusion_length_mm=2.0,
            clearance_hole_diameter_mm=11.0,
            outer_diameter_mm=30.0,
        )

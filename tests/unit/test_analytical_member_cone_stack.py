"""Tests for opposed layered compression-cone mechanics."""

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_input import (
    MemberCompressionMethod,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_member_cone_stack import (
    CompressionConeSide,
    calculate_layered_compression_cone_mechanics,
)


def _benchmark_joint():
    """Load the governed analytical benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def _cone_joint():
    """Return the benchmark with compression-cone mechanics selected."""

    joint = _benchmark_joint()

    return replace(
        joint,
        methods=replace(
            joint.methods,
            member_compression=(MemberCompressionMethod.COMPRESSION_CONE),
        ),
    )


def test_symmetric_m10_stack_matches_two_frustums() -> None:
    """The benchmark resolves as two equal opposed frustums."""

    result = calculate_layered_compression_cone_mechanics(_cone_joint())

    assert result.method == ("opposed_layered_annular_frustums")

    assert result.half_angle_deg == pytest.approx(30.0)

    assert result.split_plane_from_head_mm == pytest.approx(10.0)

    assert result.head_side_length_mm == pytest.approx(10.0)

    assert result.nut_side_length_mm == pytest.approx(10.0)

    assert len(result.slices) == 2

    assert result.slices[0].side is CompressionConeSide.HEAD
    assert result.slices[1].side is CompressionConeSide.NUT

    assert result.slices[0].compliance_mm_per_n == pytest.approx(2.0065643307363e-7)

    assert result.slices[1].compliance_mm_per_n == pytest.approx(2.0065643307363e-7)

    assert result.total_compliance_mm_per_n == pytest.approx(4.0131286614726e-7)

    assert result.axial_stiffness_n_per_mm == pytest.approx(2491821.4299988)

    assert result.total_shortening_mm == pytest.approx(0.0020065643307363)

    assert result.total_strain_energy_n_mm == pytest.approx(5.0164108268408)

    assert result.maximum_reference_compressive_stress_mpa == pytest.approx(47.1570201754)


def test_midpoint_can_split_one_physical_layer() -> None:
    """The stack midpoint may create partial layer slices."""

    joint = _cone_joint()

    modified_layers = (
        replace(
            joint.member_layers[0],
            thickness_mm=6.0,
        ),
        replace(
            joint.member_layers[1],
            thickness_mm=14.0,
        ),
    )

    result = calculate_layered_compression_cone_mechanics(
        replace(
            joint,
            member_layers=modified_layers,
        )
    )

    assert len(result.slices) == 3

    assert [slice_record.side for slice_record in result.slices] == [
        CompressionConeSide.HEAD,
        CompressionConeSide.HEAD,
        CompressionConeSide.NUT,
    ]

    assert [slice_record.thickness_mm for slice_record in result.slices] == pytest.approx(
        [
            6.0,
            4.0,
            10.0,
        ]
    )

    assert [slice_record.layer_id for slice_record in result.slices] == [
        "head_side_member",
        "nut_side_member",
        "nut_side_member",
    ]

    assert sum(slice_record.thickness_mm for slice_record in result.slices) == pytest.approx(20.0)

    assert result.slices[1].start_effective_outer_diameter_mm == pytest.approx(
        result.slices[0].end_effective_outer_diameter_mm
    )


def test_head_and_nut_bearing_diameters_are_independent() -> None:
    """Different bearing diameters create different cone compliance."""

    joint = _cone_joint()

    modified = replace(
        joint,
        bolt=replace(
            joint.bolt,
            head_bearing_outer_diameter_mm=20.0,
        ),
        nut=replace(
            joint.nut,
            bearing_outer_diameter_mm=16.0,
        ),
    )

    result = calculate_layered_compression_cone_mechanics(modified)

    head_slice = result.slices[0]
    nut_slice = result.slices[1]

    assert head_slice.start_effective_outer_diameter_mm == pytest.approx(20.0)

    assert nut_slice.start_effective_outer_diameter_mm == pytest.approx(16.0)

    assert head_slice.compliance_mm_per_n < nut_slice.compliance_mm_per_n


def test_larger_cone_angle_increases_stack_stiffness() -> None:
    """Faster compression spreading reduces member compliance."""

    joint = _cone_joint()

    base = calculate_layered_compression_cone_mechanics(joint)

    wider = calculate_layered_compression_cone_mechanics(
        replace(
            joint,
            methods=replace(
                joint.methods,
                compression_cone_half_angle_deg=45.0,
            ),
        )
    )

    assert wider.total_compliance_mm_per_n < base.total_compliance_mm_per_n

    assert wider.axial_stiffness_n_per_mm > base.axial_stiffness_n_per_mm

    assert wider.total_shortening_mm < base.total_shortening_mm


def test_cone_assembler_rejects_uniform_method() -> None:
    """The cone assembler cannot be called under another method."""

    with pytest.raises(
        ValueError,
        match="member_compression='compression_cone'",
    ):
        calculate_layered_compression_cone_mechanics(_benchmark_joint())

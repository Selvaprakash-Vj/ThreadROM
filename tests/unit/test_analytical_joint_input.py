"""Tests for the canonical analytical joint input."""

from dataclasses import replace

import pytest

from threadrom.engineering.analytical_inputs import (
    BoltAxialSegmentInput,
    BoltSegmentKind,
    ElasticMaterial,
    LoadingInput,
    MemberLayerInput,
    MetricThreadInput,
)
from threadrom.engineering.analytical_joint_input import (
    AnalyticalJointInput,
    AnalyticalMethodSelection,
    BoltComplianceMethod,
    BoltInput,
    ExternalLoadMethod,
    MemberCompressionMethod,
    NutInput,
    ThreadLoadDistributionMethod,
)


def _m10_benchmark() -> AnalyticalJointInput:
    """Return the first governed parametric benchmark."""

    steel = ElasticMaterial(
        material_id="steel",
        youngs_modulus_mpa=210_000.0,
        poissons_ratio=0.3,
        proof_stress_mpa=580.0,
        yield_strength_mpa=640.0,
        ultimate_strength_mpa=800.0,
    )

    bolt = BoltInput(
        bolt_id="bolt_m10",
        material_id="steel",
        nominal_length_mm=30.0,
        axial_segments=(
            BoltAxialSegmentInput(
                segment_id="grip_thread",
                kind=BoltSegmentKind.THREADED,
                length_mm=20.0,
            ),
        ),
        head_bearing_outer_diameter_mm=16.0,
        head_bearing_inner_diameter_mm=11.0,
    )

    nut = NutInput(
        nut_id="nut_m10",
        material_id="steel",
        thickness_mm=8.0,
        thread_engagement_length_mm=8.0,
        bearing_outer_diameter_mm=16.0,
        bearing_inner_diameter_mm=11.0,
    )

    members = (
        MemberLayerInput(
            layer_id="upper_member",
            thickness_mm=10.0,
            material_id="steel",
            clearance_hole_diameter_mm=11.0,
            outer_diameter_mm=30.0,
        ),
        MemberLayerInput(
            layer_id="lower_member",
            thickness_mm=10.0,
            material_id="steel",
            clearance_hole_diameter_mm=11.0,
            outer_diameter_mm=30.0,
        ),
    )

    methods = AnalyticalMethodSelection(
        bolt_compliance=BoltComplianceMethod.SEGMENTED,
        member_compression=(MemberCompressionMethod.UNIFORM_ANNULAR_CYLINDER),
        external_load=ExternalLoadMethod.BASIC_SPRING_RATIO,
        thread_load_distribution=(ThreadLoadDistributionMethod.DISCRETE_SPRING),
        head_participation_factor=0.5,
        nut_participation_factor=0.5,
    )

    return AnalyticalJointInput(
        joint_id="TRM-ANL-000001",
        thread=MetricThreadInput(
            nominal_diameter_mm=10.0,
            pitch_mm=1.5,
            external_tolerance_class="6g",
            internal_tolerance_class="6H",
        ),
        bolt=bolt,
        nut=nut,
        member_layers=members,
        materials=(steel,),
        loading=LoadingInput(preload_n=5000.0),
        methods=methods,
    )


def test_m10_benchmark_is_represented_parametrically() -> None:
    """The current joint is represented by the general input model."""

    joint = _m10_benchmark()

    assert joint.grip_length_mm == pytest.approx(20.0)
    assert joint.engaged_thread_count == pytest.approx(8.0 / 1.5)
    assert joint.bolt.axial_segment_length_mm == pytest.approx(20.0)
    assert joint.material_by_id("steel").youngs_modulus_mpa == pytest.approx(210_000.0)


def test_duplicate_material_identities_are_rejected() -> None:
    """Material identities must remain unambiguous."""

    joint = _m10_benchmark()

    with pytest.raises(
        ValueError,
        match="Material identities must be unique",
    ):
        replace(
            joint,
            materials=(
                joint.materials[0],
                joint.materials[0],
            ),
        )


def test_unresolved_material_reference_is_rejected() -> None:
    """Every component material reference must resolve."""

    joint = _m10_benchmark()

    with pytest.raises(
        ValueError,
        match="Unresolved material references",
    ):
        replace(
            joint,
            nut=replace(
                joint.nut,
                material_id="missing_material",
            ),
        )


def test_member_hole_must_clear_nominal_thread() -> None:
    """A bolt-nut member hole must exceed nominal thread diameter."""

    joint = _m10_benchmark()

    invalid_layer = replace(
        joint.member_layers[0],
        clearance_hole_diameter_mm=10.0,
    )

    with pytest.raises(
        ValueError,
        match="clearance hole",
    ):
        replace(
            joint,
            member_layers=(
                invalid_layer,
                joint.member_layers[1],
            ),
        )


def test_nut_engagement_cannot_exceed_thickness() -> None:
    """Thread engagement cannot exceed the available nut thickness."""

    joint = _m10_benchmark()

    with pytest.raises(
        ValueError,
        match="must not exceed nut thickness",
    ):
        replace(
            joint,
            nut=replace(
                joint.nut,
                thread_engagement_length_mm=9.0,
            ),
        )


def test_method_assumption_ranges_are_validated() -> None:
    """Dimensionless analytical assumptions have governed ranges."""

    joint = _m10_benchmark()

    with pytest.raises(
        ValueError,
        match="Load-introduction factor",
    ):
        replace(
            joint,
            methods=replace(
                joint.methods,
                load_introduction_factor=1.1,
            ),
        )

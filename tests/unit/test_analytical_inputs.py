"""Tests for canonical analytical-engine input primitives."""

import pytest

from threadrom.engineering.analytical_inputs import (
    BoltAxialSegmentInput,
    BoltSegmentKind,
    ElasticMaterial,
    LoadingInput,
    MemberLayerInput,
    MetricThreadInput,
    ThreadHandedness,
)


def test_parametric_input_primitives_accept_m10_benchmark() -> None:
    """The first M10 benchmark can be represented without hard-coding."""

    steel = ElasticMaterial(
        material_id="steel_8_8",
        youngs_modulus_mpa=210_000.0,
        poissons_ratio=0.3,
        proof_stress_mpa=580.0,
        yield_strength_mpa=640.0,
        ultimate_strength_mpa=800.0,
    )

    thread = MetricThreadInput(
        nominal_diameter_mm=10.0,
        pitch_mm=1.5,
        handedness=ThreadHandedness.RIGHT,
        external_tolerance_class="6g",
        internal_tolerance_class="6H",
    )

    threaded_segment = BoltAxialSegmentInput(
        segment_id="grip_thread",
        kind=BoltSegmentKind.THREADED,
        length_mm=20.0,
    )

    member = MemberLayerInput(
        layer_id="upper_member",
        thickness_mm=10.0,
        material_id=steel.material_id,
        clearance_hole_diameter_mm=11.0,
        outer_diameter_mm=30.0,
    )

    loading = LoadingInput(
        preload_n=5000.0,
        external_axial_load_n=0.0,
    )

    assert thread.nominal_diameter_mm == pytest.approx(10.0)
    assert threaded_segment.length_mm == pytest.approx(20.0)
    assert member.material_id == steel.material_id
    assert loading.preload_n == pytest.approx(5000.0)


@pytest.mark.parametrize(
    ("diameter", "pitch"),
    [
        (0.0, 1.5),
        (-10.0, 1.5),
        (10.0, 0.0),
        (10.0, -1.5),
    ],
)
def test_invalid_metric_thread_inputs_are_rejected(
    diameter: float,
    pitch: float,
) -> None:
    """Non-positive thread dimensions are rejected."""

    with pytest.raises(ValueError):
        MetricThreadInput(
            nominal_diameter_mm=diameter,
            pitch_mm=pitch,
        )


def test_custom_area_segment_requires_area() -> None:
    """Custom-area segments cannot omit their governing area."""

    with pytest.raises(ValueError):
        BoltAxialSegmentInput(
            segment_id="custom",
            kind=BoltSegmentKind.CUSTOM_AREA,
            length_mm=5.0,
        )


def test_cyclic_load_range_must_be_complete_and_ordered() -> None:
    """Cyclic loading requires a complete and ordered load range."""

    with pytest.raises(ValueError):
        LoadingInput(
            preload_n=5000.0,
            cyclic_minimum_axial_load_n=1000.0,
        )

    with pytest.raises(ValueError):
        LoadingInput(
            preload_n=5000.0,
            cyclic_minimum_axial_load_n=2000.0,
            cyclic_maximum_axial_load_n=1000.0,
        )

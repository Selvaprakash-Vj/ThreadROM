"""Cross-size CAD transfer tests for governed M8/M12 candidates."""

from dataclasses import replace
import math

import pytest

from threadrom.case.reference_cases import phase2_certification_case
from threadrom.case.resolver import resolve_case
from threadrom.factory.geometry_adapter import (
    build_geometry_definitions,
)
from threadrom.geometry.complete_bolt import (
    build_complete_bolt,
    measure_complete_bolt,
)
from threadrom.geometry.complete_nut import (
    build_complete_nut,
    measure_complete_nut,
)


def _cross_size_case(
    *,
    designation: str,
    bolt_length_mm: float,
    member_thickness_mm: float,
    member_outer_diameter_mm: float,
    clearance_hole_diameter_mm: float,
):
    """Build one geometrically sensible cross-size case."""

    baseline = phase2_certification_case()
    upper, lower = baseline.members.layers

    return replace(
        baseline,
        fastener=replace(
            baseline.fastener,
            thread_designation=designation,
            bolt_length_mm=bolt_length_mm,
        ),
        members=replace(
            baseline.members,
            layers=(
                replace(
                    upper,
                    thickness_mm=member_thickness_mm,
                    outer_diameter_mm=member_outer_diameter_mm,
                    clearance_hole_diameter_mm=(
                        clearance_hole_diameter_mm
                    ),
                ),
                replace(
                    lower,
                    thickness_mm=member_thickness_mm,
                    outer_diameter_mm=member_outer_diameter_mm,
                    clearance_hole_diameter_mm=(
                        clearance_hole_diameter_mm
                    ),
                ),
            ),
        ),
    )


@pytest.mark.parametrize(
    (
        "designation",
        "nominal_diameter_mm",
        "pitch_mm",
        "bolt_length_mm",
        "head_across_flats_mm",
        "head_height_mm",
        "nut_across_flats_mm",
        "nut_thickness_mm",
        "member_thickness_mm",
        "member_outer_diameter_mm",
        "clearance_hole_diameter_mm",
    ),
    (
        (
            "M8x1.25",
            8.0,
            1.25,
            30.0,
            13.0,
            5.3,
            13.0,
            6.620,
            8.0,
            24.0,
            8.8,
        ),
        (
            "M12x1.75",
            12.0,
            1.75,
            40.0,
            18.0,
            7.5,
            18.0,
            10.585,
            12.0,
            36.0,
            13.2,
        ),
    ),
)
def test_cross_size_complete_components_build_valid_cad(
    designation: str,
    nominal_diameter_mm: float,
    pitch_mm: float,
    bolt_length_mm: float,
    head_across_flats_mm: float,
    head_height_mm: float,
    nut_across_flats_mm: float,
    nut_thickness_mm: float,
    member_thickness_mm: float,
    member_outer_diameter_mm: float,
    clearance_hole_diameter_mm: float,
) -> None:
    case = _cross_size_case(
        designation=designation,
        bolt_length_mm=bolt_length_mm,
        member_thickness_mm=member_thickness_mm,
        member_outer_diameter_mm=member_outer_diameter_mm,
        clearance_hole_diameter_mm=clearance_hole_diameter_mm,
    )

    resolved = resolve_case(case)
    geometry = build_geometry_definitions(resolved)

    # ----------------------------------------------------------
    # Resolved -> CAD-definition transfer
    # ----------------------------------------------------------

    assert geometry.bolt_blank.nominal_diameter_mm == pytest.approx(
        nominal_diameter_mm
    )
    assert geometry.external_thread.pitch_mm == pytest.approx(
        pitch_mm
    )
    assert geometry.bolt_blank.head_across_flats_mm == pytest.approx(
        head_across_flats_mm
    )
    assert geometry.bolt_blank.head_height_mm == pytest.approx(
        head_height_mm
    )

    assert geometry.nut_blank.nominal_diameter_mm == pytest.approx(
        nominal_diameter_mm
    )
    assert geometry.nut_blank.pitch_mm == pytest.approx(
        pitch_mm
    )
    assert geometry.nut_blank.across_flats_mm == pytest.approx(
        nut_across_flats_mm
    )
    assert geometry.nut_blank.thickness_mm == pytest.approx(
        nut_thickness_mm
    )

    assert geometry.external_thread.minor_diameter_mm == pytest.approx(
        resolved.thread_basic_dimensions.basic_external_minor_diameter_mm
    )
    assert geometry.internal_thread.minor_diameter_mm == pytest.approx(
        resolved.thread_basic_dimensions.basic_internal_minor_diameter_mm
    )

    assert geometry.external_thread.thread_length_mm == pytest.approx(
        bolt_length_mm
    )
    assert geometry.internal_thread.thread_length_mm == pytest.approx(
        resolved.assembly.thread_engagement_length_mm
    )

    # ----------------------------------------------------------
    # Actual CAD construction
    # ----------------------------------------------------------

    bolt_build = build_complete_bolt(
        geometry.bolt_blank,
        geometry.external_thread,
        geometry.quality_policy,
        geometry.mating_clearance_mm,
    )

    nut_build = build_complete_nut(
        geometry.nut_blank,
        geometry.internal_thread,
        geometry.quality_policy,
    )

    bolt = measure_complete_bolt(bolt_build)
    nut = measure_complete_nut(nut_build)

    assert bolt.solid_count == 1
    assert bolt.is_valid is True
    assert bolt.complete_volume_mm3 > 0.0
    assert bolt.union_overlap_volume_mm3 > 0.0

    assert nut.solid_count == 1
    assert nut.is_valid is True
    assert nut.complete_volume_mm3 > 0.0
    assert nut.added_thread_material_mm3 > 0.0
    assert nut.removed_thread_volume_mm3 > 0.0
    assert nut.thread_segment_count > 0

    # ----------------------------------------------------------
    # Actual CAD envelope
    # ----------------------------------------------------------

    tolerance = geometry.quality_policy.cad_envelope_tolerance_mm

    assert bolt.z_min_mm == pytest.approx(
        -head_height_mm,
        abs=tolerance,
    )
    assert bolt.z_max_mm == pytest.approx(
        bolt_length_mm,
        abs=tolerance,
    )

    expected_bolt_lateral = sorted(
        (
            head_across_flats_mm,
            head_across_flats_mm
            / math.cos(math.radians(30.0)),
        )
    )
    actual_bolt_lateral = sorted(
        (
            bolt.x_length_mm,
            bolt.y_length_mm,
        )
    )

    assert actual_bolt_lateral[0] == pytest.approx(
        expected_bolt_lateral[0],
        abs=tolerance,
    )
    assert actual_bolt_lateral[1] == pytest.approx(
        expected_bolt_lateral[1],
        abs=tolerance,
    )

    assert nut.z_min_mm == pytest.approx(
        0.0,
        abs=tolerance,
    )
    assert nut.z_max_mm == pytest.approx(
        nut_thickness_mm,
        abs=tolerance,
    )

    expected_nut_lateral = sorted(
        (
            nut_across_flats_mm,
            2.0 * nut_across_flats_mm / math.sqrt(3.0),
        )
    )
    actual_nut_lateral = sorted(
        (
            nut.x_length_mm,
            nut.y_length_mm,
        )
    )

    assert actual_nut_lateral[0] == pytest.approx(
        expected_nut_lateral[0],
        abs=tolerance,
    )
    assert actual_nut_lateral[1] == pytest.approx(
        expected_nut_lateral[1],
        abs=tolerance,
    )


def test_cross_size_geometry_identities_are_distinct() -> None:
    definitions = []

    for args in (
        ("M8x1.25", 30.0, 8.0, 24.0, 8.8),
        ("M12x1.75", 40.0, 12.0, 36.0, 13.2),
    ):
        case = _cross_size_case(
            designation=args[0],
            bolt_length_mm=args[1],
            member_thickness_mm=args[2],
            member_outer_diameter_mm=args[3],
            clearance_hole_diameter_mm=args[4],
        )

        definitions.append(
            build_geometry_definitions(
                resolve_case(case)
            )
        )

    m8, m12 = definitions

    assert (
        m8.bolt_blank.geometry_id
        != m12.bolt_blank.geometry_id
    )
    assert (
        m8.nut_blank.geometry_id
        != m12.nut_blank.geometry_id
    )

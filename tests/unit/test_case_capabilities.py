"""Tests for governed ThreadROM case capability assessment."""

from dataclasses import replace

from threadrom.case import CaseSupportStatus
from threadrom.case.capabilities import assess_case_capability
from threadrom.case.contract import (
    AnalysisSelection,
    FastenerSelection,
    InterfacesSelection,
    LoadingSelection,
    MemberLayerSelection,
    MembersSelection,
    ThreadROMCase,
)
from threadrom.engineering.analytical_inputs import ThreadHandedness


def _baseline_case() -> ThreadROMCase:
    return ThreadROMCase(
        fastener=FastenerSelection(
            bolt_standard="ISO 4017:2022",
            thread_designation="M10x1.5",
            bolt_length_mm=30.0,
            bolt_material_id="fastener_steel",
            bolt_property_class="8.8",
            nut_standard="ISO 4032:2023",
            nut_material_id="fastener_steel",
            nut_property_class="8",
        ),
        members=MembersSelection(
            layers=(
                MemberLayerSelection(
                    layer_id="upper_member",
                    thickness_mm=10.0,
                    material_id="steel_member",
                    outer_diameter_mm=30.0,
                    clearance_hole_diameter_mm=11.0,
                ),
                MemberLayerSelection(
                    layer_id="lower_member",
                    thickness_mm=10.0,
                    material_id="steel_member",
                    outer_diameter_mm=30.0,
                    clearance_hole_diameter_mm=11.0,
                ),
            )
        ),
        interfaces=InterfacesSelection(
            thread_friction_coefficient=0.15,
            head_bearing_friction_coefficient=0.15,
            nut_bearing_friction_coefficient=0.15,
            member_interface_friction_coefficient=0.15,
        ),
        loading=LoadingSelection(
            target_preload_n=20_000.0,
            external_axial_load_n=0.0,
        ),
        analysis=AnalysisSelection(),
    )


def test_baseline_shape_remains_experimental_until_cp4() -> None:
    """CP1 must not self-certify the new factory path."""

    assessment = assess_case_capability(_baseline_case())

    assert assessment.status is CaseSupportStatus.EXPERIMENTAL
    assert any(
        "CP4" in reason
        for reason in assessment.reasons
    )


def test_left_hand_thread_is_experimental() -> None:
    """Representable left-hand threads are not yet certified."""

    case = _baseline_case()
    changed = replace(
        case,
        fastener=replace(
            case.fastener,
            handedness=ThreadHandedness.LEFT,
        ),
    )

    assessment = assess_case_capability(changed)

    assert assessment.status is CaseSupportStatus.EXPERIMENTAL
    assert any(
        "Left-hand" in reason
        for reason in assessment.reasons
    )


def test_nonbaseline_metric_thread_is_experimental() -> None:
    """Other metric-thread designations are not yet factory-certified."""

    case = _baseline_case()
    changed = replace(
        case,
        fastener=replace(
            case.fastener,
            thread_designation="M12x1.75",
        ),
    )

    assessment = assess_case_capability(changed)

    assert assessment.status is CaseSupportStatus.EXPERIMENTAL
    assert any(
        "Non-M10x1.5" in reason
        for reason in assessment.reasons
    )


def test_multistart_thread_is_unsupported() -> None:
    """Known unsupported thread-transfer topology fails capability gating."""

    case = _baseline_case()
    changed = replace(
        case,
        fastener=replace(
            case.fastener,
            starts=2,
        ),
    )

    assessment = assess_case_capability(changed)

    assert assessment.status is CaseSupportStatus.UNSUPPORTED
    assert any(
        "Multi-start" in reason
        for reason in assessment.reasons
    )


def test_unknown_bolt_standard_is_unsupported() -> None:
    """Standards without a governed resolver are rejected."""

    case = _baseline_case()
    changed = replace(
        case,
        fastener=replace(
            case.fastener,
            bolt_standard="CUSTOM",
        ),
    )

    assessment = assess_case_capability(changed)

    assert assessment.status is CaseSupportStatus.UNSUPPORTED


def test_unknown_nut_standard_is_unsupported() -> None:
    """Nut standards without a governed resolver are rejected."""

    case = _baseline_case()
    changed = replace(
        case,
        fastener=replace(
            case.fastener,
            nut_standard="CUSTOM",
        ),
    )

    assessment = assess_case_capability(changed)

    assert assessment.status is CaseSupportStatus.UNSUPPORTED

from __future__ import annotations

from dataclasses import replace

from threadrom.case.preflight import (
    PreflightRuleCode,
    PreflightSeverity,
    PreflightTarget,
)
from threadrom.case.preflight_rules import (
    check_analysis_capability,
    check_bolt_length_feasible,
    check_material_data,
    check_product_topology,
    check_property_class_data,
    check_standard_dimensions,
)
from threadrom.case.reference_cases import phase2_certification_case


def test_certified_reference_topology_has_no_findings() -> None:
    case = phase2_certification_case()

    assert check_product_topology(case) == ()


def test_non_two_layer_topology_is_blocked() -> None:
    case = phase2_certification_case()

    modified = replace(
        case,
        members=replace(
            case.members,
            layers=(case.members.layers[0],),
        ),
    )

    findings = check_product_topology(modified)

    assert len(findings) == 1
    assert findings[0].code is PreflightRuleCode.PRODUCT_TOPOLOGY_SUPPORTED
    assert findings[0].severity is PreflightSeverity.ERROR


def test_mismatched_holes_are_blocked() -> None:
    case = phase2_certification_case()
    upper, lower = case.members.layers

    modified = replace(
        case,
        members=replace(
            case.members,
            layers=(
                upper,
                replace(
                    lower,
                    clearance_hole_diameter_mm=12.0,
                ),
            ),
        ),
    )

    findings = check_product_topology(modified)

    assert len(findings) == 1
    assert "clearance-hole diameters" in findings[0].message


def test_mismatched_outer_diameters_are_blocked() -> None:
    case = phase2_certification_case()
    upper, lower = case.members.layers

    modified = replace(
        case,
        members=replace(
            case.members,
            layers=(
                upper,
                replace(
                    lower,
                    outer_diameter_mm=32.0,
                ),
            ),
        ),
    )

    findings = check_product_topology(modified)

    assert len(findings) == 1
    assert "outer diameters" in findings[0].message


def test_multiple_topology_violations_are_reported_deterministically() -> None:
    case = phase2_certification_case()
    upper, lower = case.members.layers

    modified = replace(
        case,
        members=replace(
            case.members,
            layers=(
                upper,
                replace(
                    lower,
                    clearance_hole_diameter_mm=12.0,
                    outer_diameter_mm=32.0,
                ),
            ),
        ),
    )

    findings = check_product_topology(modified)

    assert len(findings) == 2
    assert "clearance-hole diameters" in findings[0].message
    assert "outer diameters" in findings[1].message



def test_reference_case_passes_static_data_checks() -> None:
    case = phase2_certification_case()

    assert check_standard_dimensions(case) == ()
    assert check_material_data(case) == ()
    assert check_property_class_data(case) == ()
    assert check_bolt_length_feasible(case) == ()


def test_metadata_known_but_dimensionally_unsupported_bolt_is_blocked() -> None:
    case = phase2_certification_case()

    modified = replace(
        case,
        fastener=replace(
            case.fastener,
            bolt_standard="ISO 4014:2022",
        ),
    )

    findings = check_standard_dimensions(modified)

    assert len(findings) == 1
    assert (
        findings[0].code
        is PreflightRuleCode.STANDARD_DIMENSIONS_AVAILABLE
    )
    assert findings[0].severity is PreflightSeverity.ERROR
    assert "ISO 4014:2022" in findings[0].message


def test_unknown_material_is_blocked() -> None:
    case = phase2_certification_case()

    modified = replace(
        case,
        fastener=replace(
            case.fastener,
            bolt_material_id="unknown_material",
        ),
    )

    findings = check_material_data(modified)

    assert len(findings) == 1
    assert findings[0].code is PreflightRuleCode.MATERIAL_DATA_AVAILABLE
    assert findings[0].severity is PreflightSeverity.ERROR
    assert "unknown_material" in findings[0].message


def test_unknown_property_class_is_blocked() -> None:
    case = phase2_certification_case()

    modified = replace(
        case,
        fastener=replace(
            case.fastener,
            bolt_property_class="12.9",
        ),
    )

    findings = check_property_class_data(modified)

    assert len(findings) == 1
    assert (
        findings[0].code
        is PreflightRuleCode.PROPERTY_CLASS_AVAILABLE
    )
    assert findings[0].severity is PreflightSeverity.ERROR
    assert "12.9" in findings[0].message


def test_insufficient_bolt_length_is_blocked() -> None:
    case = phase2_certification_case()

    modified = replace(
        case,
        fastener=replace(
            case.fastener,
            bolt_length_mm=27.0,
        ),
    )

    findings = check_bolt_length_feasible(modified)

    assert len(findings) == 1
    assert findings[0].code is PreflightRuleCode.BOLT_LENGTH_FEASIBLE
    assert findings[0].severity is PreflightSeverity.ERROR
    assert "minimum geometric length is 28 mm" in findings[0].message


def test_bolt_length_check_does_not_duplicate_missing_nut_standard() -> None:
    case = phase2_certification_case()

    modified = replace(
        case,
        fastener=replace(
            case.fastener,
            nut_standard="ISO 4033:2023",
        ),
    )

    standard_findings = check_standard_dimensions(modified)
    length_findings = check_bolt_length_feasible(modified)

    assert len(standard_findings) == 1
    assert length_findings == ()



def test_resolution_target_is_authorized() -> None:
    case = phase2_certification_case()

    assert (
        check_analysis_capability(
            case,
            PreflightTarget.RESOLUTION,
        )
        == ()
    )


def test_reference_analytical_target_is_authorized() -> None:
    case = phase2_certification_case()

    assert (
        check_analysis_capability(
            case,
            PreflightTarget.ANALYTICAL,
        )
        == ()
    )


def test_negative_external_load_blocks_current_analytical_backend() -> None:
    case = phase2_certification_case()

    modified = replace(
        case,
        loading=replace(
            case.loading,
            external_axial_load_n=-1000.0,
        ),
    )

    findings = check_analysis_capability(
        modified,
        PreflightTarget.ANALYTICAL,
    )

    assert len(findings) == 1
    assert (
        findings[0].code
        is PreflightRuleCode.ANALYSIS_CAPABILITY_SUPPORTED
    )
    assert findings[0].severity is PreflightSeverity.ERROR


def test_geometry_target_is_authorized_at_capability_layer() -> None:
    case = phase2_certification_case()

    assert (
        check_analysis_capability(
            case,
            PreflightTarget.GEOMETRY,
        )
        == ()
    )


def test_fem_target_is_blocked_until_cp4() -> None:
    case = phase2_certification_case()

    findings = check_analysis_capability(
        case,
        PreflightTarget.FEM,
    )

    assert len(findings) == 1
    assert (
        findings[0].code
        is PreflightRuleCode.ANALYSIS_CAPABILITY_SUPPORTED
    )
    assert findings[0].severity is PreflightSeverity.ERROR
    assert "CP4" in findings[0].message


def test_rom_target_is_blocked_until_phase4() -> None:
    case = phase2_certification_case()

    findings = check_analysis_capability(
        case,
        PreflightTarget.ROM,
    )

    assert len(findings) == 1
    assert (
        findings[0].code
        is PreflightRuleCode.ANALYSIS_CAPABILITY_SUPPORTED
    )
    assert findings[0].severity is PreflightSeverity.ERROR
    assert "Phase 4" in findings[0].message

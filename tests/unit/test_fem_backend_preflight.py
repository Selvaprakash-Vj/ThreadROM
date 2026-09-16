"""Target-specific preflight tests for current FEM backend restrictions."""

from dataclasses import replace

from threadrom.case.preflight import (
    PreflightDisposition,
    PreflightRuleCode,
    PreflightTarget,
)
from threadrom.case.preflight_engine import preflight_case
from threadrom.case.reference_cases import phase2_certification_case
from threadrom.materials.baseline_catalog import (
    BASELINE_MATERIAL_CATALOG,
)
from threadrom.materials.catalog import MaterialCatalog
from threadrom.materials.models import MaterialFamily


def test_nonuniform_friction_is_representable_but_current_fem_blocks_it() -> None:
    case = phase2_certification_case()

    diversified = replace(
        case,
        interfaces=replace(
            case.interfaces,
            thread_friction_coefficient=0.17,
        ),
    )

    resolution = preflight_case(
        diversified,
        PreflightTarget.RESOLUTION,
    )

    assert resolution.disposition is PreflightDisposition.PASS

    fem = preflight_case(
        diversified,
        PreflightTarget.FEM,
    )

    assert fem.disposition is PreflightDisposition.BLOCKED
    assert any(
        finding.code
        is PreflightRuleCode.FRICTION_ENVELOPE_SUPPORTED
        for finding in fem.blocking_findings
    )


def test_mixed_elastic_materials_are_representable_but_current_fem_blocks_them() -> None:
    case = phase2_certification_case()
    upper, lower = case.members.layers

    aluminium_member = MaterialFamily(
        material_id="test_aluminium_member",
        display_name="Test aluminium member",
        youngs_modulus_mpa=70000.0,
        poissons_ratio=0.33,
        elastic_source_reference="test governed material evidence",
    )

    catalog = MaterialCatalog(
        catalog_id="test-diversified-material-catalog",
        material_families=(
            *BASELINE_MATERIAL_CATALOG.material_families,
            aluminium_member,
        ),
        fastener_property_classes=(
            BASELINE_MATERIAL_CATALOG.fastener_property_classes
        ),
    )

    diversified = replace(
        case,
        members=replace(
            case.members,
            layers=(
                replace(
                    upper,
                    material_id="test_aluminium_member",
                ),
                lower,
            ),
        ),
    )

    resolution = preflight_case(
        diversified,
        PreflightTarget.RESOLUTION,
        material_catalog=catalog,
    )

    assert resolution.disposition is PreflightDisposition.PASS

    fem = preflight_case(
        diversified,
        PreflightTarget.FEM,
        material_catalog=catalog,
    )

    assert fem.disposition is PreflightDisposition.BLOCKED
    assert any(
        finding.code
        is PreflightRuleCode.FEM_ELASTIC_MODEL_SUPPORTED
        for finding in fem.blocking_findings
    )

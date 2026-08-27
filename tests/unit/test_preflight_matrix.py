from __future__ import annotations

from dataclasses import replace

import pytest

from threadrom.case.preflight import (
    PreflightDisposition,
    PreflightRuleCode,
    PreflightTarget,
)
from threadrom.case.preflight_engine import preflight_case
from threadrom.case.reference_cases import phase2_certification_case


@pytest.mark.parametrize(
    ("case_builder", "target", "expected_code"),
    (
        (
            lambda case: replace(
                case,
                fastener=replace(
                    case.fastener,
                    bolt_standard="ISO 4014:2022",
                ),
            ),
            PreflightTarget.RESOLUTION,
            PreflightRuleCode.STANDARD_DIMENSIONS_AVAILABLE,
        ),
        (
            lambda case: replace(
                case,
                fastener=replace(
                    case.fastener,
                    bolt_material_id="unknown_material",
                ),
            ),
            PreflightTarget.RESOLUTION,
            PreflightRuleCode.MATERIAL_DATA_AVAILABLE,
        ),
        (
            lambda case: replace(
                case,
                fastener=replace(
                    case.fastener,
                    bolt_property_class="12.9",
                ),
            ),
            PreflightTarget.RESOLUTION,
            PreflightRuleCode.PROPERTY_CLASS_AVAILABLE,
        ),
        (
            lambda case: replace(
                case,
                members=replace(
                    case.members,
                    layers=(case.members.layers[0],),
                ),
            ),
            PreflightTarget.GEOMETRY,
            PreflightRuleCode.PRODUCT_TOPOLOGY_SUPPORTED,
        ),
        (
            lambda case: replace(
                case,
                fastener=replace(
                    case.fastener,
                    bolt_length_mm=27.0,
                ),
            ),
            PreflightTarget.RESOLUTION,
            PreflightRuleCode.BOLT_LENGTH_FEASIBLE,
        ),
        (
            lambda case: replace(
                case,
                loading=replace(
                    case.loading,
                    external_axial_load_n=-1.0,
                ),
            ),
            PreflightTarget.ANALYTICAL,
            PreflightRuleCode.ANALYSIS_CAPABILITY_SUPPORTED,
        ),
        (
            lambda case: case,
            PreflightTarget.FEM,
            PreflightRuleCode.ANALYSIS_CAPABILITY_SUPPORTED,
        ),
        (
            lambda case: case,
            PreflightTarget.ROM,
            PreflightRuleCode.ANALYSIS_CAPABILITY_SUPPORTED,
        ),
    ),
)
def test_preflight_negative_matrix_blocks_expected_failure(
    case_builder,
    target: PreflightTarget,
    expected_code: PreflightRuleCode,
) -> None:
    case = case_builder(phase2_certification_case())

    report = preflight_case(case, target)

    assert report.disposition is PreflightDisposition.BLOCKED
    assert report.can_proceed is False
    assert expected_code in tuple(
        finding.code
        for finding in report.blocking_findings
    )


@pytest.mark.parametrize(
    "target",
    (
        PreflightTarget.RESOLUTION,
        PreflightTarget.ANALYTICAL,
        PreflightTarget.GEOMETRY,
    ),
)
def test_reference_case_current_authorized_targets_pass(
    target: PreflightTarget,
) -> None:
    report = preflight_case(
        phase2_certification_case(),
        target,
    )

    assert report.disposition is PreflightDisposition.PASS
    assert report.can_proceed is True

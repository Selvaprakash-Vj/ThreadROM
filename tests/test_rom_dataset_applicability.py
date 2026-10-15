from __future__ import annotations

import pytest

from threadrom.factory.rom_dataset_applicability import (
    ApplicabilityDecision,
    evaluate_rom_case_applicability,
)


def simple_domain() -> dict:
    return {
        "schema": "threadrom.rom_supported_domain.v1",
        "record_status": "FINAL",
        "domain_id": "UNIT-DOMAIN",
        "required_engineering_fields": [
            "thread_designation",
            "bolt_material_id",
            "nut_material_id",
            "preload_target_n",
            "head_member_thickness_mm",
        ],
        "constraints": {
            "categorical": {
                "thread_designation": [
                    "M8x1.25",
                    "M10x1.5",
                    "M12x1.75",
                ],
                "bolt_material_id": [
                    "FASTENER_A",
                    "FASTENER_B",
                ],
                "nut_material_id": [
                    "FASTENER_A",
                    "FASTENER_B",
                ],
            },
            "numeric_ranges": {
                "preload_target_n": {
                    "minimum": 15000.0,
                    "maximum": 20000.0,
                },
                "head_member_thickness_mm": {
                    "minimum": 8.0,
                    "maximum": 10.0,
                },
            },
            "equalities": [
                [
                    "bolt_material_id",
                    "nut_material_id",
                ],
            ],
        },
        "governance": {
            "domain_expansion_by_admission_forbidden": True,
        },
    }


def simple_candidate() -> dict:
    return {
        "thread_designation": "M10x1.5",
        "bolt_material_id": "FASTENER_A",
        "nut_material_id": "FASTENER_A",
        "preload_target_n": 17500.0,
        "head_member_thickness_mm": 9.0,
    }


def conditional_domain() -> dict:
    return {
        "schema": "threadrom.rom_supported_domain.v1",
        "record_status": "FINAL",
        "domain_id": "CONDITIONAL",
        "required_engineering_fields": [
            "thread_designation",
            "head_member_thickness_mm",
            "nut_member_thickness_mm",
            "member_outer_diameter_mm",
            "member_clearance_hole_diameter_mm",
            "normalized_coordinates",
        ],
        "constraints": {
            "categorical": {
                "thread_designation": [
                    "M8x1.25",
                    "M10x1.5",
                ],
            },
            "numeric_ranges": {},
            "vector_ranges": {
                "normalized_coordinates": {
                    "components": [
                        {"minimum": 0.0, "maximum": 1.0},
                        {"minimum": 0.0, "maximum": 1.0},
                        {"minimum": 0.0, "maximum": 1.0},
                    ],
                },
            },
            "equalities": [],
            "conditional_profiles": {
                "selector_field": "thread_designation",
                "profiles": {
                    "M8x1.25": {
                        "numeric_ranges": {
                            "head_member_thickness_mm": {
                                "minimum": 6.4,
                                "maximum": 8.0,
                            },
                            "nut_member_thickness_mm": {
                                "minimum": 8.0,
                                "maximum": 9.6,
                            },
                            "member_outer_diameter_mm": {
                                "minimum": 24.0,
                                "maximum": 28.8,
                            },
                            "member_clearance_hole_diameter_mm": {
                                "minimum": 8.8,
                                "maximum": 9.6,
                            },
                        },
                        "sum_constraints": [
                            {
                                "fields": [
                                    "head_member_thickness_mm",
                                    "nut_member_thickness_mm",
                                ],
                                "equals": 16.0,
                            },
                        ],
                        "affine_constraints": [
                            {
                                "dependent": "member_clearance_hole_diameter_mm",
                                "source": "member_outer_diameter_mm",
                                "intercept": 4.8,
                                "slope": 1.0 / 6.0,
                            },
                        ],
                    },
                    "M10x1.5": {
                        "numeric_ranges": {
                            "head_member_thickness_mm": {
                                "minimum": 8.0,
                                "maximum": 10.0,
                            },
                            "nut_member_thickness_mm": {
                                "minimum": 10.0,
                                "maximum": 12.0,
                            },
                            "member_outer_diameter_mm": {
                                "minimum": 30.0,
                                "maximum": 36.0,
                            },
                            "member_clearance_hole_diameter_mm": {
                                "minimum": 11.0,
                                "maximum": 12.0,
                            },
                        },
                        "sum_constraints": [
                            {
                                "fields": [
                                    "head_member_thickness_mm",
                                    "nut_member_thickness_mm",
                                ],
                                "equals": 20.0,
                            },
                        ],
                        "affine_constraints": [
                            {
                                "dependent": "member_clearance_hole_diameter_mm",
                                "source": "member_outer_diameter_mm",
                                "intercept": 6.0,
                                "slope": 1.0 / 6.0,
                            },
                        ],
                    },
                },
            },
        },
        "governance": {
            "domain_expansion_by_admission_forbidden": True,
        },
    }


def conditional_candidate() -> dict:
    return {
        "thread_designation": "M8x1.25",
        "head_member_thickness_mm": 7.2,
        "nut_member_thickness_mm": 8.8,
        "member_outer_diameter_mm": 26.4,
        "member_clearance_hole_diameter_mm": 9.2,
        "normalized_coordinates": [0.5, 0.5, 0.5],
    }


def test_inside_simple_domain_passes() -> None:
    result = evaluate_rom_case_applicability(
        engineering_inputs=simple_candidate(),
        supported_domain=simple_domain(),
    )

    assert result.decision is ApplicabilityDecision.PASS
    assert result.passed is True


def test_outside_simple_numeric_range_rejects() -> None:
    values = simple_candidate()
    values["preload_target_n"] = 20001.0

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=simple_domain(),
    )

    assert result.decision is ApplicabilityDecision.REJECTED


def test_missing_candidate_input_defers() -> None:
    values = simple_candidate()
    del values["head_member_thickness_mm"]

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=simple_domain(),
    )

    assert result.decision is ApplicabilityDecision.DEFERRED


def test_domain_expansion_must_be_forbidden() -> None:
    authority = simple_domain()
    authority["governance"][
        "domain_expansion_by_admission_forbidden"
    ] = False

    with pytest.raises(
        ValueError,
        match="forbid domain expansion",
    ):
        evaluate_rom_case_applicability(
            engineering_inputs=simple_candidate(),
            supported_domain=authority,
        )


def test_conditional_profile_passes() -> None:
    result = evaluate_rom_case_applicability(
        engineering_inputs=conditional_candidate(),
        supported_domain=conditional_domain(),
    )

    assert result.decision is ApplicabilityDecision.PASS


def test_conditional_profile_numeric_bound_rejects() -> None:
    values = conditional_candidate()
    values["member_outer_diameter_mm"] = 29.0

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=conditional_domain(),
    )

    assert result.decision is ApplicabilityDecision.REJECTED


def test_conditional_sum_relation_rejects() -> None:
    values = conditional_candidate()
    values["nut_member_thickness_mm"] = 9.0

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=conditional_domain(),
    )

    assert result.decision is ApplicabilityDecision.REJECTED


def test_conditional_affine_relation_rejects() -> None:
    values = conditional_candidate()
    values["member_clearance_hole_diameter_mm"] = 9.3

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=conditional_domain(),
    )

    assert result.decision is ApplicabilityDecision.REJECTED


def test_vector_component_range_rejects() -> None:
    values = conditional_candidate()
    values["normalized_coordinates"] = [0.5, 1.1, 0.5]

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=conditional_domain(),
    )

    assert result.decision is ApplicabilityDecision.REJECTED


def test_missing_governed_vector_is_derived_from_physical_inputs() -> None:
    authority = conditional_domain()

    authority[
        "constraints"
    ][
        "vector_ranges"
    ][
        "normalized_coordinates"
    ][
        "derived_components"
    ] = [
        {
            "source_field": "head_member_thickness_mm",
            "profile_numeric_range_field": "head_member_thickness_mm",
            "transform": "linear",
        },
        {
            "source_field": "member_outer_diameter_mm",
            "profile_numeric_range_field": "member_outer_diameter_mm",
            "transform": "linear",
        },
        {
            "source_field": "member_clearance_hole_diameter_mm",
            "profile_numeric_range_field": "member_clearance_hole_diameter_mm",
            "transform": "linear",
        },
    ]

    authority[
        "constraints"
    ][
        "vector_ranges"
    ][
        "normalized_coordinates"
    ][
        "derived_absolute_tolerance"
    ] = 1.0e-8

    values = conditional_candidate()

    del values[
        "normalized_coordinates"
    ]

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=authority,
    )

    assert (
        result.decision
        is ApplicabilityDecision.PASS
    )


def test_existing_governed_vector_must_match_physical_derivation() -> None:
    authority = conditional_domain()

    authority[
        "constraints"
    ][
        "vector_ranges"
    ][
        "normalized_coordinates"
    ][
        "derived_components"
    ] = [
        {
            "source_field": "head_member_thickness_mm",
            "profile_numeric_range_field": "head_member_thickness_mm",
            "transform": "linear",
        },
        {
            "source_field": "member_outer_diameter_mm",
            "profile_numeric_range_field": "member_outer_diameter_mm",
            "transform": "linear",
        },
        {
            "source_field": "member_clearance_hole_diameter_mm",
            "profile_numeric_range_field": "member_clearance_hole_diameter_mm",
            "transform": "linear",
        },
    ]

    authority[
        "constraints"
    ][
        "vector_ranges"
    ][
        "normalized_coordinates"
    ][
        "derived_absolute_tolerance"
    ] = 1.0e-8

    values = conditional_candidate()

    # Physical values correspond to [0.5, 0.5, 0.5].
    values[
        "normalized_coordinates"
    ] = [
        0.4,
        0.5,
        0.5,
    ]

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=authority,
    )

    assert (
        result.decision
        is ApplicabilityDecision.REJECTED
    )

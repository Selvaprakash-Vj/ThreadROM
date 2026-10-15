from __future__ import annotations

import json
from pathlib import Path

from threadrom.factory.rom_dataset_applicability import (
    ApplicabilityDecision,
    evaluate_rom_case_applicability,
)


ROOT = Path(__file__).resolve().parents[1]

DOMAIN = (
    ROOT
    / "docs"
    / "phase3_rom_dataset_admission"
    / "member_shortening_v1.supported_domain.json"
)


def load_domain() -> dict:
    return json.loads(
        DOMAIN.read_text(
            encoding="utf-8"
        )
    )


def representative(
    *,
    designation: str,
    member_material: str,
) -> dict:

    domain = load_domain()

    profile = domain[
        "constraints"
    ][
        "conditional_profiles"
    ][
        "profiles"
    ][
        designation
    ]

    ranges = profile[
        "numeric_ranges"
    ]

    head = (
        ranges[
            "head_member_thickness_mm"
        ][
            "minimum"
        ]
        + ranges[
            "head_member_thickness_mm"
        ][
            "maximum"
        ]
    ) / 2.0

    grip = profile[
        "sum_constraints"
    ][0][
        "equals"
    ]

    nut = (
        grip
        - head
    )

    od = (
        ranges[
            "member_outer_diameter_mm"
        ][
            "minimum"
        ]
        + ranges[
            "member_outer_diameter_mm"
        ][
            "maximum"
        ]
    ) / 2.0

    affine = profile[
        "affine_constraints"
    ][0]

    hole = (
        affine[
            "intercept"
        ]
        + affine[
            "slope"
        ]
        * od
    )

    preload = (
        ranges[
            "target_preload_n"
        ][
            "minimum"
        ]
        + ranges[
            "target_preload_n"
        ][
            "maximum"
        ]
    ) / 2.0

    return {
        "thread_designation": designation,
        "bolt_material_id": "fastener_steel",
        "nut_material_id": "fastener_steel",
        "head_member_material_id": member_material,
        "nut_member_material_id": member_material,
        "target_preload_n": preload,
        "head_member_thickness_mm": head,
        "nut_member_thickness_mm": nut,
        "member_outer_diameter_mm": od,
        "member_clearance_hole_diameter_mm": hole,
        "thread_friction_coefficient": 0.15,
        "head_bearing_friction_coefficient": 0.15,
        "nut_bearing_friction_coefficient": 0.15,
        "member_interface_friction_coefficient": 0.15,
        "external_axial_load_n": 0.0,
        "normalized_coordinates": [
            0.5,
            0.5,
            0.5,
        ],
    }


def test_domain_record_is_final_and_nonexpanding() -> None:
    domain = load_domain()

    assert domain[
        "schema"
    ] == "threadrom.rom_supported_domain.v1"

    assert domain[
        "record_status"
    ] == "FINAL"

    assert domain[
        "governance"
    ][
        "domain_expansion_by_admission_forbidden"
    ] is True

    assert domain[
        "governance"
    ][
        "rom_training_authorized"
    ] is False


def test_all_six_size_material_cohorts_have_representative_pass() -> None:
    domain = load_domain()

    for designation in (
        "M8x1.25",
        "M10x1.5",
        "M12x1.75",
    ):
        for member_material in (
            "steel_member",
            "member_aluminium_en_aw_6082_t6",
        ):
            result = evaluate_rom_case_applicability(
                engineering_inputs=representative(
                    designation=designation,
                    member_material=member_material,
                ),
                supported_domain=domain,
            )

            assert (
                result.decision
                is ApplicabilityDecision.PASS
            )


def test_unsupported_thread_rejects() -> None:
    domain = load_domain()

    values = representative(
        designation="M10x1.5",
        member_material="steel_member",
    )

    values[
        "thread_designation"
    ] = "M16x2.0"

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=domain,
    )

    assert (
        result.decision
        is ApplicabilityDecision.REJECTED
    )


def test_unpaired_member_materials_reject() -> None:
    domain = load_domain()

    values = representative(
        designation="M10x1.5",
        member_material="steel_member",
    )

    values[
        "nut_member_material_id"
    ] = "member_aluminium_en_aw_6082_t6"

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=domain,
    )

    assert (
        result.decision
        is ApplicabilityDecision.REJECTED
    )


def test_external_load_expansion_rejects() -> None:
    domain = load_domain()

    values = representative(
        designation="M10x1.5",
        member_material="steel_member",
    )

    values[
        "external_axial_load_n"
    ] = 1.0

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=domain,
    )

    assert (
        result.decision
        is ApplicabilityDecision.REJECTED
    )


def test_real_domain_derives_missing_normalized_coordinates() -> None:
    domain = load_domain()

    values = representative(
        designation="M10x1.5",
        member_material="steel_member",
    )

    del values[
        "normalized_coordinates"
    ]

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=domain,
    )

    assert (
        result.decision
        is ApplicabilityDecision.PASS
    )


def test_real_domain_rejects_inconsistent_existing_normalized_coordinates() -> None:
    domain = load_domain()

    values = representative(
        designation="M10x1.5",
        member_material="steel_member",
    )

    values[
        "normalized_coordinates"
    ] = [
        0.25,
        0.5,
        0.5,
    ]

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=domain,
    )

    assert (
        result.decision
        is ApplicabilityDecision.REJECTED
    )

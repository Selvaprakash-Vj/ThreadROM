from __future__ import annotations

import ast
import hashlib
import json

from pathlib import Path

from threadrom.factory.rom_dataset_applicability import (
    ApplicabilityDecision,
    evaluate_rom_case_applicability,
)


ROOT = Path(__file__).resolve().parents[1]

SCRIPT = (
    ROOT
    / "scripts"
    / "evaluate_phase3_governed_wave_rom_admission_v1.py"
)

DOMAIN = (
    ROOT
    / "docs"
    / "phase3_rom_dataset_admission"
    / "member_shortening_v1.supported_domain.json"
)

EXPECTED_DOMAIN_SHA = (
    "8e299508ddff12f92fce4fcae59a2bf0"
    "34eb91dbffcf0b46db3646a6e0ccfbd6"
)


def test_frozen_supported_domain_identity() -> None:

    actual = hashlib.sha256(
        DOMAIN.read_bytes()
    ).hexdigest()

    assert actual == EXPECTED_DOMAIN_SHA


def test_governed_wave_adapter_has_no_da10_placeholder() -> None:

    source = SCRIPT.read_text(
        encoding="utf-8"
    )

    assert "applicability_passed=None" not in source

    assert (
        "evaluate_rom_case_applicability"
        in source
    )

    assert (
        "EXPECTED_SUPPORTED_DOMAIN_SHA"
        in source
    )

    assert (
        "_member_shortening_applicability"
        in source
    )


def test_post_target_admission_receives_real_da10_variable() -> None:

    tree = ast.parse(
        SCRIPT.read_text(
            encoding="utf-8"
        )
    )

    calls = []

    for node in ast.walk(
        tree
    ):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Name,
        ):
            continue

        if (
            node.func.id
            != "evaluate_member_shortening_post_target_admission"
        ):
            continue

        calls.append(
            node
        )

    assert len(calls) == 1

    keyword = next(
        item
        for item in calls[0].keywords
        if item.arg == "applicability_passed"
    )

    assert isinstance(
        keyword.value,
        ast.Name,
    )

    assert (
        keyword.value.id
        == "applicability_passed"
    )


def test_actual_domain_rejects_external_load_expansion() -> None:

    domain = json.loads(
        DOMAIN.read_text(
            encoding="utf-8"
        )
    )

    profile = domain[
        "constraints"
    ][
        "conditional_profiles"
    ][
        "profiles"
    ][
        "M10x1.5"
    ]

    ranges = profile[
        "numeric_ranges"
    ]

    head = 9.0
    nut = 11.0
    od = 33.0
    hole = 11.5

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

    values = {
        "thread_designation": "M10x1.5",
        "bolt_material_id": "fastener_steel",
        "nut_material_id": "fastener_steel",
        "head_member_material_id": "steel_member",
        "nut_member_material_id": "steel_member",
        "target_preload_n": preload,
        "head_member_thickness_mm": head,
        "nut_member_thickness_mm": nut,
        "member_outer_diameter_mm": od,
        "member_clearance_hole_diameter_mm": hole,
        "thread_friction_coefficient": 0.15,
        "head_bearing_friction_coefficient": 0.15,
        "nut_bearing_friction_coefficient": 0.15,
        "member_interface_friction_coefficient": 0.15,
        "external_axial_load_n": 1.0,
        "normalized_coordinates": [
            0.5,
            0.5,
            0.5,
        ],
    }

    result = evaluate_rom_case_applicability(
        engineering_inputs=values,
        supported_domain=domain,
    )

    assert (
        result.decision
        is ApplicabilityDecision.REJECTED
    )

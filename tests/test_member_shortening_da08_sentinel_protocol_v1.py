from __future__ import annotations

import hashlib
import json

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PROTOCOL = (
    ROOT
    / "docs"
    / "phase3_rom_dataset_admission"
    / "member_shortening_v1.da08_sentinel_protocol.json"
)


def load_protocol() -> dict:
    return json.loads(
        PROTOCOL.read_text(
            encoding="utf-8"
        )
    )


def test_protocol_is_frozen_before_solve() -> None:
    payload = load_protocol()

    assert (
        payload["schema"]
        == "threadrom.rom_da08_sentinel_protocol.v1"
    )

    assert (
        payload["record_status"]
        == "FROZEN_PRE_SOLVE"
    )

    assert (
        payload["disposition"]
        == "SENTINEL_DESIGN_FROZEN_NOT_AUTHORIZED"
    )

    assert payload[
        "governance"
    ][
        "fem_authorized"
    ] is False

    assert payload[
        "governance"
    ][
        "criteria_frozen_before_new_fine_results"
    ] is True


def test_population_is_exactly_frozen() -> None:
    payload = load_protocol()

    population = payload[
        "population"
    ]

    assert (
        population[
            "fem_atlas_cases"
        ]
        == 43
    )

    assert (
        population[
            "da10_applicable_cases"
        ]
        == 35
    )

    assert (
        population[
            "da10_rejected_cases"
        ]
        == 8
    )

    assert (
        population[
            "certification_cohorts"
        ]
        == 11
    )

    assert (
        population[
            "selected_extrema_sentinels"
        ]
        == 19
    )

    assert (
        population[
            "direct_case_reduction_vs_all_eligible"
        ]
        == 16
    )


def test_transfer_governance_fails_closed() -> None:
    payload = load_protocol()

    transfer = payload[
        "future_region_transfer_rule"
    ]

    assert (
        transfer[
            "cross_thread_transfer_forbidden"
        ]
        is True
    )

    assert (
        transfer[
            "cross_material_transfer_forbidden"
        ]
        is True
    )

    assert (
        transfer[
            "cross_mesh_policy_transfer_forbidden"
        ]
        is True
    )

    assert (
        transfer[
            "cross_radial_regime_transfer_forbidden"
        ]
        is True
    )

    assert (
        transfer[
            "extrapolation_forbidden"
        ]
        is True
    )

    assert (
        transfer[
            "automatic_transfer_on_extrema_geometry_alone"
        ]
        is False
    )


def test_every_cohort_has_at_least_one_sentinel() -> None:
    payload = load_protocol()

    cohorts = payload[
        "cohorts"
    ]

    assert len(
        cohorts
    ) == 11

    assert sum(
        len(
            cohort[
                "sentinels"
            ]
        )
        for cohort in cohorts
    ) == 19

    assert all(
        cohort[
            "sentinels"
        ]
        for cohort in cohorts
    )


def test_holdout_and_mesh_preconditions_remain_unresolved() -> None:
    payload = load_protocol()

    assert payload[
        "holdout_governance"
    ][
        "opaque_clearance_required_before_pretraining_execution"
    ] is True

    assert payload[
        "mesh_governance"
    ][
        "actual_mesh_policy_resolution_required_before_authorization"
    ] is True


def test_protocol_sidecar_matches() -> None:
    expected = Path(
        str(PROTOCOL)
        + ".sha256"
    ).read_text(
        encoding="ascii"
    ).strip()

    actual = hashlib.sha256(
        PROTOCOL.read_bytes()
    ).hexdigest()

    assert actual == expected

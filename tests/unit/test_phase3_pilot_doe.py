"""Tests for the governed Phase-3 CP7 Pilot DOE."""

from __future__ import annotations

import pytest

from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_case_preparation import (
    derive_fem_case_preparation,
)
from threadrom.factory.pilot_doe import (
    PilotDoeCapability,
    PilotDoeCaseId,
    build_phase3_cp7_pilot_doe,
)
from threadrom.factory.preload_calibration_seed import (
    derive_analytical_thermal_preload_seed,
)


def test_cp7_pilot_has_exact_governed_case_order() -> None:
    campaign = build_phase3_cp7_pilot_doe()

    assert campaign.campaign_id == "phase3_cp7_pilot_v1"

    assert tuple(
        case.case_id
        for case in campaign.cases
    ) == (
        PilotDoeCaseId.BASELINE_CONTROL,
        PilotDoeCaseId.PRELOAD_LOW,
        PilotDoeCaseId.PRELOAD_HIGH,
        PilotDoeCaseId.ASYMMETRIC_GRIP,
        PilotDoeCaseId.RADIAL_GEOMETRY,
    )


def test_cp7_pilot_cases_have_unique_hashes_and_run_ids() -> None:
    campaign = build_phase3_cp7_pilot_doe()

    hashes = []
    run_ids = []

    for pilot in campaign.cases:
        resolved = resolve_case(
            pilot.case
        )

        preparation = derive_fem_case_preparation(
            resolved
        )

        hashes.append(
            resolved.case_hash
        )
        run_ids.append(
            preparation.identity.run_id
        )

    assert len(set(hashes)) == 5
    assert len(set(run_ids)) == 5


def test_cp7_pilot_preload_cases_are_15_20_25_kn() -> None:
    campaign = build_phase3_cp7_pilot_doe()

    by_id = {
        pilot.case_id: pilot
        for pilot in campaign.cases
    }

    assert (
        by_id[
            PilotDoeCaseId.PRELOAD_LOW
        ].case.loading.target_preload_n
        == 15_000.0
    )

    assert (
        by_id[
            PilotDoeCaseId.BASELINE_CONTROL
        ].case.loading.target_preload_n
        == 20_000.0
    )

    assert (
        by_id[
            PilotDoeCaseId.PRELOAD_HIGH
        ].case.loading.target_preload_n
        == 25_000.0
    )


def test_cp7_preload_seed_scales_linearly_for_fixed_geometry() -> None:
    campaign = build_phase3_cp7_pilot_doe()

    by_id = {
        pilot.case_id: pilot
        for pilot in campaign.cases
    }

    seeds = {
        case_id: derive_analytical_thermal_preload_seed(
            resolve_case(
                by_id[case_id].case
            )
        )
        for case_id in (
            PilotDoeCaseId.PRELOAD_LOW,
            PilotDoeCaseId.BASELINE_CONTROL,
            PilotDoeCaseId.PRELOAD_HIGH,
        )
    }

    baseline_delta = seeds[
        PilotDoeCaseId.BASELINE_CONTROL
    ].predicted_delta_temperature_c

    assert seeds[
        PilotDoeCaseId.PRELOAD_LOW
    ].predicted_delta_temperature_c == pytest.approx(
        0.75 * baseline_delta,
        rel=1.0e-12,
    )

    assert seeds[
        PilotDoeCaseId.PRELOAD_HIGH
    ].predicted_delta_temperature_c == pytest.approx(
        1.25 * baseline_delta,
        rel=1.0e-12,
    )


def test_cp7_asymmetric_case_preserves_total_grip() -> None:
    campaign = build_phase3_cp7_pilot_doe()

    pilot = next(
        case
        for case in campaign.cases
        if (
            case.case_id
            is PilotDoeCaseId.ASYMMETRIC_GRIP
        )
    )

    resolved = resolve_case(
        pilot.case
    )

    assert (
        resolved.assembly.upper_member_thickness_mm
        == 8.0
    )
    assert (
        resolved.assembly.lower_member_thickness_mm
        == 12.0
    )
    assert (
        resolved.assembly.total_grip_length_mm
        == 20.0
    )

    assert (
        pilot.capability
        is PilotDoeCapability.MEMBER_STACK_ASYMMETRY
    )


def test_cp7_radial_case_changes_governed_member_geometry() -> None:
    campaign = build_phase3_cp7_pilot_doe()

    pilot = next(
        case
        for case in campaign.cases
        if (
            case.case_id
            is PilotDoeCaseId.RADIAL_GEOMETRY
        )
    )

    resolved = resolve_case(
        pilot.case
    )

    assert resolved.assembly.outer_diameter_mm == 36.0
    assert (
        resolved.assembly.clearance_hole_diameter_mm
        == 12.0
    )

    seed = derive_analytical_thermal_preload_seed(
        resolved
    )

    assert seed.predicted_delta_temperature_c < 0.0

"""Gate-5 V2 thermal-preload compatibility mechanics tests."""

from __future__ import annotations

import pytest

from threadrom.case.resolver import resolve_case
from threadrom.factory.pilot_doe import (
    PilotDoeCaseId,
    build_phase3_cp7_pilot_doe,
)
from threadrom.factory.preload_calibration_seed import (
    derive_analytical_thermal_preload_seed,
    derive_analytical_thermal_preload_seed_v2,
    derive_thermal_preload_compatibility_mechanics,
)


def _resolved(case_id: PilotDoeCaseId):
    campaign = build_phase3_cp7_pilot_doe()

    item = next(
        item
        for item in campaign.cases
        if item.case_id is case_id
    )

    return resolve_case(item.case)


def test_v2_baseline_separates_thermal_and_mechanical_lengths() -> None:
    resolved = _resolved(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    mechanics = (
        derive_thermal_preload_compatibility_mechanics(
            resolved
        )
    )

    assert mechanics.method == (
        "free_span_plus_distributed_thread_transfer_v2"
    )

    # Certified legacy FEM semantic free span:
    # under-head bearing plane Z=0 to engagement entry Z=20 mm.
    assert mechanics.thermal_actuation_length_mm == pytest.approx(
        20.0,
        abs=1.0e-12,
    )

    assert mechanics.free_span_bolt_length_mm == pytest.approx(
        20.0,
        abs=1.0e-12,
    )

    # Existing governed two-bar/thread-spring model.
    assert (
        mechanics.thread_transfer_equivalent_length_mm
        == pytest.approx(
            3.813845785,
            abs=1.0e-9,
        )
    )

    assert (
        mechanics.free_span_bolt_compliance_mm_per_n
        == pytest.approx(
            1.6423306994062724e-6,
            rel=1.0e-9,
        )
    )

    assert (
        mechanics.thread_transfer_bolt_compliance_mm_per_n
        == pytest.approx(
            3.473009669462709e-7,
            rel=1.0e-9,
        )
    )

    assert mechanics.bolt_compliance_mm_per_n == pytest.approx(
        1.9896316663525434e-6,
        rel=1.0e-9,
    )

    # Independent certified legacy FEM mechanical bolt compliances.
    #
    # No coefficient in the analytical model is fitted to these values.
    # The acceptance bound therefore checks cross-anchor physical
    # agreement rather than exact reproduction of one FEM realization.
    fem_anchor_compliances = (
        1.910004757759e-6,  # A00 baseline
        1.879148390523e-6,  # A01 preload-low
        1.931610448050e-6,  # A02 asymmetric grip
        2.006304035936e-6,  # A03 radial geometry
    )

    relative_errors = tuple(
        abs(
            mechanics.bolt_compliance_mm_per_n
            / fem_value
            - 1.0
        )
        for fem_value in fem_anchor_compliances
    )

    assert max(relative_errors) < 0.06

    mean_absolute_relative_error = (
        sum(relative_errors)
        / len(relative_errors)
    )

    assert mean_absolute_relative_error < 0.04


def test_v1_seed_remains_frozen_while_v2_is_additive() -> None:
    resolved = _resolved(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    legacy = derive_analytical_thermal_preload_seed(
        resolved
    )

    # This protects historical CP8 warm-start provenance.
    assert legacy.predicted_delta_temperature_c == pytest.approx(
        -145.50879555545754,
        rel=1.0e-12,
    )

    assert legacy.effective_bolt_length_mm == pytest.approx(
        30.0,
        abs=1.0e-12,
    )



def test_v2_seed_uses_physical_actuation_span() -> None:
    resolved = _resolved(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    seed = derive_analytical_thermal_preload_seed_v2(
        resolved
    )

    assert seed.method == (
        "physical_free_span_plus_"
        "distributed_thread_transfer_v2"
    )

    assert seed.thermal_actuation_length_mm == pytest.approx(
        20.0,
        abs=1.0e-12,
    )

    assert seed.bolt_compliance_mm_per_n == pytest.approx(
        1.9896316663525434e-6,
        rel=1.0e-9,
    )

    assert seed.predicted_delta_temperature_c == pytest.approx(
        -178.77449477011194,
        rel=1.0e-9,
    )

    # V2 should move toward the accepted legacy FEM preload
    # without embedding the legacy FEM residual in analytical physics.
    legacy_fem_delta_t_c = -243.2744971
    legacy_v1_delta_t_c = -145.50879555545754

    assert abs(
        seed.predicted_delta_temperature_c
        - legacy_fem_delta_t_c
    ) < abs(
        legacy_v1_delta_t_c
        - legacy_fem_delta_t_c
    )

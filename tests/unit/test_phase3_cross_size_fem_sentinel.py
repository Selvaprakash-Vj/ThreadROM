"""Tests for governed M8/M12 FEM certification sentinels."""

import pytest

from threadrom.case.resolver import resolve_case
from threadrom.case.variant_capabilities import (
    PHASE3_FASTENER_VARIANT_CAPABILITIES,
    VariantCapabilityLevel,
)
from threadrom.factory.cross_size_fem_sentinel import (
    build_phase3_cross_size_fem_sentinels,
    reference_nominal_tensile_stress_mpa,
)
from threadrom.factory.fem_case_preparation import (
    derive_fem_case_preparation,
)


def test_cross_size_sentinels_are_exactly_m8_and_m12() -> None:
    sentinels = (
        build_phase3_cross_size_fem_sentinels()
    )

    assert [
        item.definition.thread_designation
        for item in sentinels
    ] == [
        "M8x1.25",
        "M12x1.75",
    ]


def test_cross_size_sentinel_preload_preserves_m10_f_over_as() -> None:
    reference_stress = (
        reference_nominal_tensile_stress_mpa()
    )

    sentinels = (
        build_phase3_cross_size_fem_sentinels()
    )

    for sentinel in sentinels:
        realized_stress = (
            sentinel.target_preload_n
            / sentinel.tensile_stress_area_mm2
        )

        assert realized_stress == pytest.approx(
            reference_stress,
            rel=1.0e-12,
            abs=1.0e-12,
        )


def test_cross_size_sentinel_target_preloads_are_governed() -> None:
    m8, m12 = (
        build_phase3_cross_size_fem_sentinels()
    )

    assert m8.target_preload_n == pytest.approx(
        12625.90024059998,
        rel=1.0e-12,
    )

    assert m12.target_preload_n == pytest.approx(
        29062.639806666983,
        rel=1.0e-12,
    )


def test_cross_size_sentinels_resolve_and_prepare_for_fem() -> None:
    resolved_cases = []

    for sentinel in (
        build_phase3_cross_size_fem_sentinels()
    ):
        resolved = resolve_case(
            sentinel.case
        )

        preparation = (
            derive_fem_case_preparation(
                resolved
            )
        )

        assert (
            resolved.thread_standard.designation
            == sentinel.definition.thread_designation
        )

        assert (
            preparation.physics.target_preload_n
            == pytest.approx(
                sentinel.target_preload_n,
                rel=1.0e-12,
            )
        )

        assert preparation.identity.case_hash
        assert preparation.identity.resolution_hash
        assert preparation.identity.run_id

        resolved_cases.append(
            resolved
        )

    assert (
        resolved_cases[0].case_hash
        != resolved_cases[1].case_hash
    )

    assert (
        resolved_cases[0].resolution_hash
        != resolved_cases[1].resolution_hash
    )


def test_sentinel_definition_does_not_prematurely_upgrade_capability() -> None:
    capabilities = {
        record.key.thread_designation: (
            record.capability
        )
        for record in (
            PHASE3_FASTENER_VARIANT_CAPABILITIES.records
        )
    }

    assert capabilities["M8x1.25"] is (
        VariantCapabilityLevel.DIMENSIONAL_DATA
    )

    assert capabilities["M12x1.75"] is (
        VariantCapabilityLevel.DIMENSIONAL_DATA
    )

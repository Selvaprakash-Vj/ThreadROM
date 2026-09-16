"""Characterize physical invariance to CAD Boolean construction aids."""

from dataclasses import replace

import pytest

from threadrom.case.reference_cases import phase2_certification_case
from threadrom.case.resolver import resolve_case
from threadrom.factory.geometry_adapter import (
    build_geometry_definitions,
)
from threadrom.geometry.complete_bolt import (
    build_complete_bolt,
    measure_complete_bolt,
)
from threadrom.geometry.complete_nut import (
    build_complete_nut,
    measure_complete_nut,
)


BASELINE_OVERLAP_MM = 0.030
BASELINE_BRIDGE_HALF_HEIGHT_MM = 0.020

# Gate-5 geometry certification established that changing the external
# thread Boolean overlap can perturb only the finite non-engaged thread
# termination after the physical-minor-root correction.
#
# Across the certified 0.015...0.060 mm audit range the largest complete
# bolt-volume deviation was approximately 1.274e-4 relative.  Preserve a
# small numerical margin while continuing to require exact envelope parity.
MAX_CERTIFIED_OVERLAP_VOLUME_RELATIVE_CHANGE = 1.5e-4


def _build_with_policy(
    *,
    overlap_mm: float,
    bridge_half_height_mm: float,
):
    resolved = resolve_case(
        phase2_certification_case()
    )

    geometry = build_geometry_definitions(
        resolved
    )

    policy = replace(
        geometry.quality_policy,
        thread_boolean_overlap_mm=overlap_mm,
        fusion_bridge_half_height_mm=(
            bridge_half_height_mm
        ),
    )

    bolt = build_complete_bolt(
        geometry.bolt_blank,
        geometry.external_thread,
        policy,
        geometry.mating_clearance_mm,
    )

    nut = build_complete_nut(
        geometry.nut_blank,
        geometry.internal_thread,
        policy,
    )

    return (
        measure_complete_bolt(bolt),
        measure_complete_nut(nut),
    )


def _assert_finished_envelopes_equal(
    *,
    bolt,
    nut,
    baseline_bolt,
    baseline_nut,
) -> None:
    for actual, baseline in (
        (bolt.x_length_mm, baseline_bolt.x_length_mm),
        (bolt.y_length_mm, baseline_bolt.y_length_mm),
        (bolt.z_min_mm, baseline_bolt.z_min_mm),
        (bolt.z_max_mm, baseline_bolt.z_max_mm),
        (nut.x_length_mm, baseline_nut.x_length_mm),
        (nut.y_length_mm, baseline_nut.y_length_mm),
        (nut.z_min_mm, baseline_nut.z_min_mm),
        (nut.z_max_mm, baseline_nut.z_max_mm),
    ):
        assert actual == pytest.approx(
            baseline,
            abs=1.0e-6,
        )


def _assert_valid_single_solids(
    *,
    bolt,
    nut,
) -> None:
    assert bolt.solid_count == 1
    assert bolt.is_valid is True

    assert nut.solid_count == 1
    assert nut.is_valid is True


@pytest.mark.parametrize(
    "bridge_half_height_mm",
    (
        0.010,
        0.020,
        0.040,
    ),
)
def test_fusion_bridge_is_physically_invariant(
    bridge_half_height_mm: float,
) -> None:
    baseline_bolt, baseline_nut = _build_with_policy(
        overlap_mm=BASELINE_OVERLAP_MM,
        bridge_half_height_mm=(
            BASELINE_BRIDGE_HALF_HEIGHT_MM
        ),
    )

    bolt, nut = _build_with_policy(
        overlap_mm=BASELINE_OVERLAP_MM,
        bridge_half_height_mm=bridge_half_height_mm,
    )

    _assert_finished_envelopes_equal(
        bolt=bolt,
        nut=nut,
        baseline_bolt=baseline_bolt,
        baseline_nut=baseline_nut,
    )

    _assert_valid_single_solids(
        bolt=bolt,
        nut=nut,
    )

    # The fusion bridge remains buried and therefore must not
    # alter either finished physical solid.
    assert bolt.complete_volume_mm3 == pytest.approx(
        baseline_bolt.complete_volume_mm3,
        rel=1.0e-8,
        abs=1.0e-6,
    )

    assert nut.complete_volume_mm3 == pytest.approx(
        baseline_nut.complete_volume_mm3,
        rel=1.0e-8,
        abs=1.0e-6,
    )


@pytest.mark.parametrize(
    "overlap_mm",
    (
        0.015,
        0.030,
        0.060,
    ),
)
def test_thread_boolean_overlap_preserves_envelope_with_bounded_end_effect(
    overlap_mm: float,
) -> None:
    baseline_bolt, baseline_nut = _build_with_policy(
        overlap_mm=BASELINE_OVERLAP_MM,
        bridge_half_height_mm=(
            BASELINE_BRIDGE_HALF_HEIGHT_MM
        ),
    )

    bolt, nut = _build_with_policy(
        overlap_mm=overlap_mm,
        bridge_half_height_mm=(
            BASELINE_BRIDGE_HALF_HEIGHT_MM
        ),
    )

    _assert_finished_envelopes_equal(
        bolt=bolt,
        nut=nut,
        baseline_bolt=baseline_bolt,
        baseline_nut=baseline_nut,
    )

    _assert_valid_single_solids(
        bolt=bolt,
        nut=nut,
    )

    bolt_volume_relative_change = abs(
        bolt.complete_volume_mm3
        / baseline_bolt.complete_volume_mm3
        - 1.0
    )

    assert (
        bolt_volume_relative_change
        <= MAX_CERTIFIED_OVERLAP_VOLUME_RELATIVE_CHANGE
    )

    # The internal-thread/nut realization remained invariant in the
    # governed sensitivity audit; retain the stricter contract here.
    assert nut.complete_volume_mm3 == pytest.approx(
        baseline_nut.complete_volume_mm3,
        rel=1.0e-8,
        abs=1.0e-6,
    )

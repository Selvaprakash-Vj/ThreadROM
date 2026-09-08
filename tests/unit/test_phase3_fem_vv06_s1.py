from __future__ import annotations

from pathlib import Path

import pytest

from threadrom.factory.fem_vv06_s1 import (
    Vv06S1Disposition,
    Vv06S1PointVerdict,
    classify_relative_difference_band,
    derive_overall_disposition,
    derive_relative_difference_band,
    load_vv06_s1_policy,
    require_strictly_increasing,
)


ROOT = Path(__file__).resolve().parents[2]


def test_frozen_policy_loads() -> None:
    policy = load_vv06_s1_policy(
        ROOT / "config" / "fem_vv06_s1.toml"
    )

    assert policy.policy_id == (
        "vv06_s1_matched_preload_screening_v1"
    )

    assert policy.comparison_preload_kn == (
        5.0,
        10.0,
        15.0,
        18.0,
        19.0,
        19.5,
    )

    assert policy.governing_preload_kn == (
        18.0,
        19.0,
        19.5,
    )

    assert (
        policy.response_tolerances
        .member_shortening_relative
        == 0.02
    )

    assert (
        policy.response_tolerances
        .bolt_free_span_mean_szz_relative
        == 0.03
    )

    assert (
        policy.response_tolerances
        .thread_normal_force_relative
        == 0.03
    )

    assert policy.epsilon == 1.0e-12


def test_strictly_increasing_force_history_passes() -> None:
    require_strictly_increasing(
        (1000.0, 2000.0, 3000.0)
    )


@pytest.mark.parametrize(
    "values",
    (
        (1000.0, 1000.0, 2000.0),
        (1000.0, 999.0, 2000.0),
    ),
)
def test_non_monotonic_force_history_fails(
    values: tuple[float, ...],
) -> None:
    with pytest.raises(
        ValueError,
        match="not strictly increasing",
    ):
        require_strictly_increasing(values)


def test_zero_uncertainty_collapses_band() -> None:
    band = derive_relative_difference_band(
        medium_value=100.0,
        fine_value=98.0,
        medium_uncertainty=0.0,
        fine_uncertainty=0.0,
        epsilon=1.0e-12,
    )

    assert band.nominal_relative_difference == pytest.approx(
        0.02
    )

    assert band.lower_relative_difference == pytest.approx(
        0.02
    )

    assert band.upper_relative_difference == pytest.approx(
        0.02
    )


def test_support_requires_upper_bound_inside_tolerance() -> None:
    band = derive_relative_difference_band(
        medium_value=100.0,
        fine_value=99.0,
        medium_uncertainty=0.1,
        fine_uncertainty=0.1,
        epsilon=1.0e-12,
    )

    assert classify_relative_difference_band(
        band=band,
        tolerance=0.02,
    ) is Vv06S1PointVerdict.SUPPORT


def test_reject_requires_lower_bound_outside_tolerance() -> None:
    band = derive_relative_difference_band(
        medium_value=100.0,
        fine_value=95.0,
        medium_uncertainty=0.1,
        fine_uncertainty=0.1,
        epsilon=1.0e-12,
    )

    assert classify_relative_difference_band(
        band=band,
        tolerance=0.02,
    ) is Vv06S1PointVerdict.REJECT


def test_uncertain_band_becomes_indeterminate() -> None:
    band = derive_relative_difference_band(
        medium_value=100.0,
        fine_value=98.0,
        medium_uncertainty=1.0,
        fine_uncertainty=1.0,
        epsilon=1.0e-12,
    )

    assert classify_relative_difference_band(
        band=band,
        tolerance=0.02,
    ) is Vv06S1PointVerdict.INDETERMINATE


def test_overall_reject_has_highest_precedence() -> None:
    assert derive_overall_disposition(
        (
            Vv06S1PointVerdict.SUPPORT,
            Vv06S1PointVerdict.INDETERMINATE,
            Vv06S1PointVerdict.REJECT,
        )
    ) is Vv06S1Disposition.REJECTS_MEDIUM_FOR_P04


def test_overall_indeterminate_precedes_support() -> None:
    assert derive_overall_disposition(
        (
            Vv06S1PointVerdict.SUPPORT,
            Vv06S1PointVerdict.INDETERMINATE,
            Vv06S1PointVerdict.SUPPORT,
        )
    ) is Vv06S1Disposition.INDETERMINATE


def test_overall_support_requires_unanimous_support() -> None:
    assert derive_overall_disposition(
        (
            Vv06S1PointVerdict.SUPPORT,
            Vv06S1PointVerdict.SUPPORT,
            Vv06S1PointVerdict.SUPPORT,
        )
    ) is Vv06S1Disposition.SUPPORTS_CONFIRMATION



def _point(
    *,
    force_n: float,
    response: float,
    increment: int,
) -> object:
    from threadrom.factory.fem_vv06_s1 import (
        Vv06S1HistoryPoint,
    )

    return Vv06S1HistoryPoint(
        force_n=force_n,
        response_value=response,
        dataset_sequence=increment,
        step=1,
        increment=increment,
        time=0.05 * increment,
    )


def test_direct_state_is_preserved_without_interpolation() -> None:
    from threadrom.factory.fem_vv06_s1 import (
        Vv06S1InterpolationKind,
        interpolate_response_at_force,
    )

    points = (
        _point(
            force_n=1000.0,
            response=1.0,
            increment=1,
        ),
        _point(
            force_n=2000.0,
            response=2.0,
            increment=2,
        ),
        _point(
            force_n=3000.0,
            response=3.0,
            increment=3,
        ),
    )

    estimate = interpolate_response_at_force(
        points=points,
        target_force_n=2000.0,
    )

    assert estimate.kind is Vv06S1InterpolationKind.DIRECT
    assert estimate.value == pytest.approx(2.0)
    assert estimate.uncertainty == pytest.approx(0.0)
    assert estimate.lower_increment == 2
    assert estimate.upper_increment == 2
    assert estimate.quadratic_value is None


def test_linear_interpolation_preserves_bracket_provenance() -> None:
    from threadrom.factory.fem_vv06_s1 import (
        Vv06S1InterpolationKind,
        interpolate_response_at_force,
    )

    points = (
        _point(
            force_n=1000.0,
            response=10.0,
            increment=1,
        ),
        _point(
            force_n=2000.0,
            response=20.0,
            increment=2,
        ),
        _point(
            force_n=3000.0,
            response=30.0,
            increment=3,
        ),
    )

    estimate = interpolate_response_at_force(
        points=points,
        target_force_n=1500.0,
    )

    assert (
        estimate.kind
        is Vv06S1InterpolationKind.INTERPOLATED
    )

    assert estimate.linear_value == pytest.approx(15.0)
    assert estimate.value == pytest.approx(15.0)

    assert estimate.lower_increment == 1
    assert estimate.upper_increment == 2

    assert estimate.lower_force_n == pytest.approx(1000.0)
    assert estimate.upper_force_n == pytest.approx(2000.0)

    assert estimate.interpolation_fraction == pytest.approx(0.5)


def test_quadratic_cross_check_derives_uncertainty() -> None:
    from threadrom.factory.fem_vv06_s1 import (
        interpolate_response_at_force,
    )

    # Exact quadratic response Q = x^2 with x expressed in kN.
    points = (
        _point(
            force_n=1000.0,
            response=1.0,
            increment=1,
        ),
        _point(
            force_n=2000.0,
            response=4.0,
            increment=2,
        ),
        _point(
            force_n=3000.0,
            response=9.0,
            increment=3,
        ),
    )

    estimate = interpolate_response_at_force(
        points=points,
        target_force_n=1500.0,
    )

    assert estimate.linear_value == pytest.approx(2.5)
    assert estimate.quadratic_value == pytest.approx(2.25)
    assert estimate.uncertainty == pytest.approx(0.25)

    assert estimate.quadratic_increments == (
        1,
        2,
        3,
    )


def test_two_point_history_uses_full_span_fallback_uncertainty() -> None:
    from threadrom.factory.fem_vv06_s1 import (
        interpolate_response_at_force,
    )

    points = (
        _point(
            force_n=1000.0,
            response=10.0,
            increment=1,
        ),
        _point(
            force_n=2000.0,
            response=14.0,
            increment=2,
        ),
    )

    estimate = interpolate_response_at_force(
        points=points,
        target_force_n=1500.0,
    )

    assert estimate.linear_value == pytest.approx(12.0)
    assert estimate.quadratic_value is None

    # Frozen fallback:
    # U_Q = |Q_upper - Q_lower|
    assert estimate.uncertainty == pytest.approx(4.0)


def test_extrapolation_is_refused() -> None:
    from threadrom.factory.fem_vv06_s1 import (
        interpolate_response_at_force,
    )

    points = (
        _point(
            force_n=1000.0,
            response=1.0,
            increment=1,
        ),
        _point(
            force_n=2000.0,
            response=2.0,
            increment=2,
        ),
        _point(
            force_n=3000.0,
            response=3.0,
            increment=3,
        ),
    )

    with pytest.raises(
        ValueError,
        match="outside the solved clamp-force history",
    ):
        interpolate_response_at_force(
            points=points,
            target_force_n=3500.0,
        )


def test_non_monotonic_history_is_not_silently_sorted() -> None:
    from threadrom.factory.fem_vv06_s1 import (
        interpolate_response_at_force,
    )

    points = (
        _point(
            force_n=1000.0,
            response=1.0,
            increment=1,
        ),
        _point(
            force_n=2100.0,
            response=2.0,
            increment=2,
        ),
        _point(
            force_n=2050.0,
            response=3.0,
            increment=3,
        ),
    )

    with pytest.raises(
        ValueError,
        match="not strictly increasing",
    ):
        interpolate_response_at_force(
            points=points,
            target_force_n=1500.0,
        )


def test_explicit_extrapolation_request_is_still_refused() -> None:
    from threadrom.factory.fem_vv06_s1 import (
        interpolate_response_at_force,
    )

    points = (
        _point(
            force_n=1000.0,
            response=1.0,
            increment=1,
        ),
        _point(
            force_n=2000.0,
            response=2.0,
            increment=2,
        ),
    )

    with pytest.raises(
        ValueError,
        match="extrapolation is prohibited",
    ):
        interpolate_response_at_force(
            points=points,
            target_force_n=1500.0,
            allow_extrapolation=True,
        )



def test_clamp_force_history_preserves_certified_force_semantics() -> None:
    from dataclasses import dataclass

    from threadrom.factory.fem_preload_calibration_measurement import (
        extract_clamp_force_history_from_records,
    )
    from threadrom.postprocessing.calculix_contact_statistics import (
        CalculixContactStatisticsRecord,
    )

    @dataclass(frozen=True)
    class Pair:
        name: str
        slave_surface: str
        master_surface: str

    pairs = (
        Pair("under_head", "UH_S", "UH_M"),
        Pair("nut_bearing", "NB_S", "NB_M"),
        Pair("member_interface", "MI_S", "MI_M"),
        Pair("thread", "TH_S", "TH_M"),
    )

    def record(
        slave: str,
        master: str,
        time: float,
        force: float,
    ) -> CalculixContactStatisticsRecord:
        return CalculixContactStatisticsRecord(
            slave_surface=slave,
            master_surface=master,
            time=time,
            total_normal_force_components_n=(0.0, 0.0, force),
            normal_force_n=force,
            shear_force_n=0.0,
            area_mm2=1.0,
        )

    records = (
        record("UH_S", "UH_M", 0.05, -1000.0),
        record("NB_S", "NB_M", 0.05, -1010.0),
        record("MI_S", "MI_M", 0.05, -1020.0),
        record("TH_S", "TH_M", 0.05, -800.0),

        record("UH_S", "UH_M", 0.10, -2000.0),
        record("NB_S", "NB_M", 0.10, -2010.0),
        record("MI_S", "MI_M", 0.10, -2020.0),
        record("TH_S", "TH_M", 0.10, -1600.0),
    )

    history = extract_clamp_force_history_from_records(
        records=records,
        contact_pairs=pairs,
    )

    assert len(history) == 2

    assert history[0].time == pytest.approx(0.05)
    assert history[1].time == pytest.approx(0.10)

    # abs(normal_force_n) is the certified physical-force convention.
    assert (
        history[0].measurement.under_head_force_n
        == pytest.approx(1000.0)
    )
    assert (
        history[0].measurement.nut_bearing_force_n
        == pytest.approx(1010.0)
    )
    assert (
        history[0].measurement.member_interface_force_n
        == pytest.approx(1020.0)
    )
    assert history[0].thread_normal_force_n == pytest.approx(800.0)

    assert (
        history[1].measurement.under_head_force_n
        == pytest.approx(2000.0)
    )
    assert history[1].thread_normal_force_n == pytest.approx(1600.0)


def test_clamp_force_history_keeps_only_fully_synchronized_times() -> None:
    from dataclasses import dataclass

    from threadrom.factory.fem_preload_calibration_measurement import (
        extract_clamp_force_history_from_records,
    )
    from threadrom.postprocessing.calculix_contact_statistics import (
        CalculixContactStatisticsRecord,
    )

    @dataclass(frozen=True)
    class Pair:
        name: str
        slave_surface: str
        master_surface: str

    pairs = (
        Pair("under_head", "UH_S", "UH_M"),
        Pair("nut_bearing", "NB_S", "NB_M"),
        Pair("member_interface", "MI_S", "MI_M"),
        Pair("thread", "TH_S", "TH_M"),
    )

    def record(
        slave: str,
        master: str,
        time: float,
        force: float,
    ) -> CalculixContactStatisticsRecord:
        return CalculixContactStatisticsRecord(
            slave_surface=slave,
            master_surface=master,
            time=time,
            total_normal_force_components_n=(0.0, 0.0, force),
            normal_force_n=force,
            shear_force_n=0.0,
            area_mm2=1.0,
        )

    records = (
        # 0.05 is deliberately missing thread evidence.
        record("UH_S", "UH_M", 0.05, -1000.0),
        record("NB_S", "NB_M", 0.05, -1000.0),
        record("MI_S", "MI_M", 0.05, -1000.0),

        # 0.10 is complete.
        record("UH_S", "UH_M", 0.10, -2000.0),
        record("NB_S", "NB_M", 0.10, -2000.0),
        record("MI_S", "MI_M", 0.10, -2000.0),
        record("TH_S", "TH_M", 0.10, -1600.0),
    )

    history = extract_clamp_force_history_from_records(
        records=records,
        contact_pairs=pairs,
    )

    assert len(history) == 1
    assert history[0].time == pytest.approx(0.10)


def test_clamp_force_history_uses_last_complete_record_at_same_time() -> None:
    from dataclasses import dataclass

    from threadrom.factory.fem_preload_calibration_measurement import (
        extract_clamp_force_history_from_records,
    )
    from threadrom.postprocessing.calculix_contact_statistics import (
        CalculixContactStatisticsRecord,
    )

    @dataclass(frozen=True)
    class Pair:
        name: str
        slave_surface: str
        master_surface: str

    pairs = (
        Pair("under_head", "UH_S", "UH_M"),
        Pair("nut_bearing", "NB_S", "NB_M"),
        Pair("member_interface", "MI_S", "MI_M"),
        Pair("thread", "TH_S", "TH_M"),
    )

    def record(
        slave: str,
        master: str,
        time: float,
        force: float,
    ) -> CalculixContactStatisticsRecord:
        return CalculixContactStatisticsRecord(
            slave_surface=slave,
            master_surface=master,
            time=time,
            total_normal_force_components_n=(0.0, 0.0, force),
            normal_force_n=force,
            shear_force_n=0.0,
            area_mm2=1.0,
        )

    records = (
        record("UH_S", "UH_M", 0.10, -1900.0),
        record("NB_S", "NB_M", 0.10, -2000.0),
        record("MI_S", "MI_M", 0.10, -2010.0),
        record("TH_S", "TH_M", 0.10, -1600.0),

        # Repeated authoritative under-head statistics at same time.
        record("UH_S", "UH_M", 0.10, -2050.0),
    )

    history = extract_clamp_force_history_from_records(
        records=records,
        contact_pairs=pairs,
    )

    assert len(history) == 1
    assert (
        history[0].measurement.under_head_force_n
        == pytest.approx(2050.0)
    )


def test_clamp_force_history_rejects_missing_required_pair_definition() -> None:
    from dataclasses import dataclass

    from threadrom.factory.fem_preload_calibration_measurement import (
        extract_clamp_force_history_from_records,
    )
    from threadrom.postprocessing.calculix_contact_statistics import (
        CalculixContactStatisticsRecord,
    )

    @dataclass(frozen=True)
    class Pair:
        name: str
        slave_surface: str
        master_surface: str

    incomplete_pairs = (
        Pair("under_head", "UH_S", "UH_M"),
        Pair("nut_bearing", "NB_S", "NB_M"),
        Pair("member_interface", "MI_S", "MI_M"),
        # thread deliberately absent
    )

    records = (
        CalculixContactStatisticsRecord(
            slave_surface="UH_S",
            master_surface="UH_M",
            time=0.1,
            total_normal_force_components_n=(0.0, 0.0, -1000.0),
            normal_force_n=-1000.0,
            shear_force_n=0.0,
            area_mm2=1.0,
        ),
    )

    with pytest.raises(
        ValueError,
        match="missing required pairs",
    ):
        extract_clamp_force_history_from_records(
            records=records,
            contact_pairs=incomplete_pairs,
        )

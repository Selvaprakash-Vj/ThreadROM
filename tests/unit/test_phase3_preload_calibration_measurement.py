from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)
from threadrom.postprocessing.calculix_contact_statistics import (
    CalculixContactStatisticsRecord,
)


def _pairs():
    return (
        SimpleNamespace(
            name="thread",
            slave_surface="SLAVE_THREAD",
            master_surface="MASTER_THREAD",
        ),
        SimpleNamespace(
            name="under_head",
            slave_surface="SLAVE_HEAD",
            master_surface="MASTER_HEAD",
        ),
        SimpleNamespace(
            name="nut_bearing",
            slave_surface="SLAVE_NUT",
            master_surface="MASTER_NUT",
        ),
        SimpleNamespace(
            name="member_interface",
            slave_surface="SLAVE_MEMBER",
            master_surface="MASTER_MEMBER",
        ),
    )


def _record(
    *,
    slave: str,
    master: str,
    time: float,
    normal_force_n: float,
) -> CalculixContactStatisticsRecord:
    return CalculixContactStatisticsRecord(
        slave_surface=slave,
        master_surface=master,
        time=time,
        total_normal_force_components_n=(0.0, 0.0, 0.0),
        normal_force_n=normal_force_n,
        shear_force_n=0.0,
        area_mm2=1.0,
    )


def test_extracts_final_synchronized_force_magnitudes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dat_path = tmp_path / "trial.dat"
    dat_path.write_text("placeholder", encoding="utf-8")

    records = (
        _record(
            slave="SLAVE_HEAD",
            master="MASTER_HEAD",
            time=0.5,
            normal_force_n=-10_000.0,
        ),
        _record(
            slave="SLAVE_NUT",
            master="MASTER_NUT",
            time=0.5,
            normal_force_n=-10_010.0,
        ),
        _record(
            slave="SLAVE_MEMBER",
            master="MASTER_MEMBER",
            time=0.5,
            normal_force_n=-10_005.0,
        ),
        _record(
            slave="SLAVE_THREAD",
            master="MASTER_THREAD",
            time=0.5,
            normal_force_n=-7_500.0,
        ),
        _record(
            slave="SLAVE_HEAD",
            master="MASTER_HEAD",
            time=1.0,
            normal_force_n=-20_060.270,
        ),
        _record(
            slave="SLAVE_NUT",
            master="MASTER_NUT",
            time=1.0,
            normal_force_n=-20_066.050,
        ),
        _record(
            slave="SLAVE_MEMBER",
            master="MASTER_MEMBER",
            time=1.0,
            normal_force_n=-20_064.180,
        ),
        _record(
            slave="SLAVE_THREAD",
            master="MASTER_THREAD",
            time=1.0,
            normal_force_n=-15_318.240,
        ),
    )

    monkeypatch.setattr(
        "threadrom.factory."
        "fem_preload_calibration_measurement."
        "parse_contact_statistics_records",
        lambda text: records,
    )

    result = extract_clamp_force_measurement_from_dat(
        dat_path=dat_path,
        contact_pairs=_pairs(),
    )

    assert result.time == pytest.approx(1.0)
    assert result.measurement.under_head_force_n == pytest.approx(
        20_060.270
    )
    assert result.measurement.nut_bearing_force_n == pytest.approx(
        20_066.050
    )
    assert result.measurement.member_interface_force_n == pytest.approx(
        20_064.180
    )
    assert result.measurement.mean_force_n == pytest.approx(
        20_063.5
    )
    assert result.thread_normal_force_n == pytest.approx(
        15_318.240
    )


def test_requires_case_contact_topology(
    tmp_path: Path,
) -> None:
    dat_path = tmp_path / "trial.dat"
    dat_path.write_text("placeholder", encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="missing required pairs",
    ):
        extract_clamp_force_measurement_from_dat(
            dat_path=dat_path,
            contact_pairs=_pairs()[:-1],
        )


def test_requires_synchronized_contact_result_time(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dat_path = tmp_path / "trial.dat"
    dat_path.write_text("placeholder", encoding="utf-8")

    records = (
        _record(
            slave="SLAVE_HEAD",
            master="MASTER_HEAD",
            time=1.0,
            normal_force_n=-20_000.0,
        ),
        _record(
            slave="SLAVE_NUT",
            master="MASTER_NUT",
            time=2.0,
            normal_force_n=-20_000.0,
        ),
        _record(
            slave="SLAVE_MEMBER",
            master="MASTER_MEMBER",
            time=3.0,
            normal_force_n=-20_000.0,
        ),
        _record(
            slave="SLAVE_THREAD",
            master="MASTER_THREAD",
            time=4.0,
            normal_force_n=-15_000.0,
        ),
    )

    monkeypatch.setattr(
        "threadrom.factory."
        "fem_preload_calibration_measurement."
        "parse_contact_statistics_records",
        lambda text: records,
    )

    with pytest.raises(
        RuntimeError,
        match="no synchronized result time",
    ):
        extract_clamp_force_measurement_from_dat(
            dat_path=dat_path,
            contact_pairs=_pairs(),
        )

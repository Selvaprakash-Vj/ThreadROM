"""Tests for CalculiX axial-response post-processing."""

from pathlib import Path

import pytest

from threadrom.postprocessing.axial_response import (
    AxialCaseDefinition,
    finer_relative_change_percent,
    read_displacement_block,
    summarize_axial_response,
)


def _write_dat(path: Path) -> None:
    """Write a representative CalculiX displacement block."""

    path.write_text(
        (
            " displacements (vx,vy,vz) for set BOLT_HEAD_TOP "
            "and time  0.1000000E+01\n"
            "\n"
            " 10  1.000000E-05 -2.000000E-05 "
            "-2.000000E-03\n"
            " 20 -1.000000E-05  2.000000E-05 "
            "-4.000000E-03\n"
            "\n"
        ),
        encoding="utf-8",
        newline="\n",
    )


def test_displacement_block_matches_calculix_format(
    tmp_path: Path,
) -> None:
    """The parser reads the observed CalculiX DAT structure."""

    dat_path = tmp_path / "case.dat"
    _write_dat(dat_path)

    rows = read_displacement_block(
        dat_path,
        "BOLT_HEAD_TOP",
    )

    assert len(rows) == 2
    assert rows[0].node_id == 10
    assert rows[0].vz_mm == pytest.approx(-0.002)
    assert rows[1].node_id == 20
    assert rows[1].vz_mm == pytest.approx(-0.004)


def test_axial_summary_uses_mean_loaded_displacement(
    tmp_path: Path,
) -> None:
    """Apparent stiffness uses the mean loaded-node displacement."""

    dat_path = tmp_path / "case.dat"
    _write_dat(dat_path)

    case = AxialCaseDefinition(
        level="test",
        simulation_id="TRM-SIM-TEST",
        dat_relative_path=Path("case.dat"),
    )

    summary = summarize_axial_response(
        case=case,
        dat_path=dat_path,
        node_set_name="BOLT_HEAD_TOP",
        applied_force_n=-1000.0,
    )

    assert summary.loaded_node_count == 2
    assert summary.mean_vz_mm == pytest.approx(-0.003)
    assert summary.range_vz_mm == pytest.approx(0.002)
    assert summary.standard_deviation_vz_mm == pytest.approx(0.001)

    assert summary.apparent_stiffness_n_per_mm == pytest.approx(333333.3333333333)


def test_relative_change_uses_finer_reference() -> None:
    """Mesh change is normalized using the finer result."""

    result = finer_relative_change_percent(
        coarse_value=2.841180307692e-3,
        finer_value=2.857074770393e-3,
    )

    assert result == pytest.approx(
        0.556319,
        abs=1.0e-6,
    )

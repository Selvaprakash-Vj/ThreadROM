"""Tests for CalculiX total-force DAT parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from threadrom.postprocessing.calculix_total_force_dat import (
    parse_total_force_records,
    write_total_force_json,
)


def test_parse_total_force_history_live_safe() -> None:
    text = """
 STEP 1
 INCREMENT 1

 total force (fx,fy,fz) for set SUPPORT and time 0.5

     1.0D-08 -2.0E-08 3.0E-08

 INCREMENT 2

 total force (fx,fy,fz) for set SUPPORT and time 1.0

     4.0E-08 5.0E-08 -6.0E-08

 total force (fx,fy,fz) for set GUIDE and time 1.0

     7.0E-08 8.0E-08 9.0E-08

 INCREMENT 3

 total force (fx,fy,fz) for set SUPPORT and time 1.5
"""

    records = parse_total_force_records(text)

    assert len(records) == 3

    first = records[0]

    assert first.step == 1
    assert first.increment == 1
    assert first.set_name == "SUPPORT"
    assert first.time == pytest.approx(0.5)
    assert first.force_x_n == pytest.approx(1.0e-8)
    assert first.force_y_n == pytest.approx(-2.0e-8)
    assert first.force_z_n == pytest.approx(3.0e-8)

    assert records[-1].set_name == "GUIDE"
    assert records[-1].increment == 2


def test_parse_total_force_set_filter() -> None:
    text = """
 INCREMENT 1

 total force (fx,fy,fz) for set SUPPORT and time 0.5

     1.0 2.0 3.0

 total force (fx,fy,fz) for set GUIDE and time 0.5

     4.0 5.0 6.0
"""

    records = parse_total_force_records(
        text,
        set_names=("support",),
    )

    assert len(records) == 1
    assert records[0].set_name == "SUPPORT"
    assert records[0].force_z_n == pytest.approx(3.0)


def test_write_total_force_json(
    tmp_path: Path,
) -> None:
    dat_path = tmp_path / "solver.dat"
    output_path = tmp_path / "total_force.json"

    dat_path.write_text(
        """
 INCREMENT 2

 total force (fx,fy,fz) for set SUPPORT and time 0.1

     6.0E-08 4.0E-08 -3.0E-11
""",
        encoding="utf-8",
        newline="\n",
    )

    records = write_total_force_json(
        dat_path,
        output_path,
        set_names=("SUPPORT",),
    )

    assert len(records) == 1

    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["record_count"] == 1
    assert payload["records"][0]["increment"] == 2

    assert payload["records"][0]["force_components_n"] == pytest.approx([6.0e-8, 4.0e-8, -3.0e-11])

"""Tests for CalculiX pretension DAT parsing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from threadrom.postprocessing.calculix_pretension_dat import (
    parse_pretension_reference_records,
    write_pretension_reference_json,
)


def test_parse_single_pretension_record() -> None:
    """One complete DAT increment is extracted."""

    content = """
                        S T E P       1

                                INCREMENT     1

 displacements (vx,vy,vz) for set BOLT_PRETENSION_REFERENCE and time  0.5000000E-01

    259268  1.512816E-05  0.000000E+00  0.000000E+00

 forces (fx,fy,fz) for set BOLT_PRETENSION_REFERENCE and time  0.5000000E-01

    259268  2.500000E+02  0.000000E+00  0.000000E+00
"""

    records = parse_pretension_reference_records(content)

    assert len(records) == 1

    record = records[0]

    assert record.step == 1
    assert record.increment == 1
    assert record.time == 0.05
    assert record.node_id == 259268
    assert record.control_displacement_mm == pytest.approx(1.512816e-5)
    assert record.preload_force_n == 250.0
    assert record.force_displacement_ratio_kn_per_mm == pytest.approx(16525.475665)


def test_incomplete_live_block_is_ignored() -> None:
    """A partially written live result is not emitted."""

    content = """
 S T E P 1
 INCREMENT 2
 displacements (vx,vy,vz) for set BOLT_PRETENSION_REFERENCE and time 0.1
 259268 2.0E-05 0.0 0.0
 forces (fx,fy,fz) for set BOLT_PRETENSION_REFERENCE and time 0.1
"""

    records = parse_pretension_reference_records(content)

    assert records == ()


def test_mismatched_nodes_are_rejected() -> None:
    """Force and displacement nodes must agree."""

    content = """
 S T E P 1
 INCREMENT 1
 displacements (vx,vy,vz) for set BOLT_PRETENSION_REFERENCE and time 0.1
 10 1.0E-05 0.0 0.0
 forces (fx,fy,fz) for set BOLT_PRETENSION_REFERENCE and time 0.1
 11 100.0 0.0 0.0
"""

    with pytest.raises(
        ValueError,
        match="node IDs do not match",
    ):
        parse_pretension_reference_records(content)


def test_write_pretension_json(
    tmp_path: Path,
) -> None:
    """Parsed pretension records are written as JSON."""

    dat_path = tmp_path / "job.dat"
    output_path = tmp_path / "results" / "pretension.json"

    dat_path.write_text(
        """
 S T E P 1
 INCREMENT 1
 displacements (vx,vy,vz) for set BOLT_PRETENSION_REFERENCE and time 0.1
 42 2.0D-05 0.0 0.0
 forces (fx,fy,fz) for set BOLT_PRETENSION_REFERENCE and time 0.1
 42 5.0D+02 0.0 0.0
""",
        encoding="utf-8",
    )

    payload = write_pretension_reference_json(
        dat_path,
        output_path,
    )

    saved = json.loads(output_path.read_text(encoding="utf-8"))

    assert payload["record_count"] == 1
    assert saved == payload
    assert saved["latest_record"]["preload_force_n"] == 500.0

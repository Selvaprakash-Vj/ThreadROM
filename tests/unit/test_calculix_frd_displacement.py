"""Tests for targeted CalculiX FRD displacement extraction."""

from pathlib import Path

import pytest

from threadrom.postprocessing.calculix_frd_displacement import (
    read_targeted_frd_displacement_datasets,
    read_targeted_frd_force_datasets,
)


def _frd_content() -> str:
    """Return a minimal two-increment FRD displacement file."""

    return """    1PSTEP                         1           1           1
  100CL  1015.00000E-002           3                     0    1           1
 -4  DISP        4    1
 -5  D1          1    2    1    0
 -5  D2          1    2    2    0
 -5  D3          1    2    3    0
 -1         1-6.70965E-0031.46947E-0027.15685E-003
 -1         21.00000E-003-2.00000E-0033.00000E-003
 -1         34.00000E-0035.00000E-003-6.00000E-003
 -3
    1PSTEP                         6           2           1
  100CL  1011.00000E-001           3                     0    2           1
 -4  DISP        4    1
 -5  D1          1    2    1    0
 -5  D2          1    2    2    0
 -5  D3          1    2    3    0
 -1         1-1.19505E-0022.68491E-0021.44571E-002
 -1         22.00000E-003-4.00000E-0036.00000E-003
 -1         38.00000E-0031.00000E-002-1.20000E-002
 -3
"""


def test_reads_only_requested_nodes(
    tmp_path: Path,
) -> None:
    """The streaming parser retains only selected nodes."""

    frd_path = tmp_path / "result.frd"

    frd_path.write_text(
        _frd_content(),
        encoding="utf-8",
    )

    datasets = read_targeted_frd_displacement_datasets(
        frd_path,
        target_node_ids={
            1,
            3,
        },
    )

    assert len(datasets) == 2

    first = datasets[0]

    assert first.dataset_sequence == 1
    assert first.step == 1
    assert first.increment == 1
    assert first.time == pytest.approx(0.05)

    assert [record.node_id for record in first.records] == [
        1,
        3,
    ]

    node_1 = first.record_by_node_id(1)

    assert node_1.d1_mm == pytest.approx(-6.70965e-3)

    assert node_1.d2_mm == pytest.approx(1.46947e-2)

    assert node_1.d3_mm == pytest.approx(7.15685e-3)


def test_reads_increment_metadata(
    tmp_path: Path,
) -> None:
    """PSTEP and 100CL metadata are preserved."""

    frd_path = tmp_path / "result.frd"

    frd_path.write_text(
        _frd_content(),
        encoding="utf-8",
    )

    datasets = read_targeted_frd_displacement_datasets(
        frd_path,
        target_node_ids={
            2,
        },
    )

    second = datasets[1]

    assert second.dataset_sequence == 6
    assert second.step == 1
    assert second.increment == 2
    assert second.time == pytest.approx(0.1)

    record = second.record_by_node_id(2)

    assert record.d3_mm == pytest.approx(6.0e-3)


def test_missing_requested_node_raises_on_lookup(
    tmp_path: Path,
) -> None:
    """Missing records fail clearly at target lookup."""

    frd_path = tmp_path / "result.frd"

    frd_path.write_text(
        _frd_content(),
        encoding="utf-8",
    )

    dataset = read_targeted_frd_displacement_datasets(
        frd_path,
        target_node_ids={
            2,
            99,
        },
    )[0]

    with pytest.raises(
        KeyError,
        match="Node 99 is absent",
    ):
        dataset.record_by_node_id(99)


def test_empty_target_set_is_rejected(
    tmp_path: Path,
) -> None:
    """Targeted extraction cannot silently read every FRD node."""

    frd_path = tmp_path / "result.frd"

    frd_path.write_text(
        _frd_content(),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="At least one target",
    ):
        read_targeted_frd_displacement_datasets(
            frd_path,
            target_node_ids=set(),
        )


def test_malformed_component_record_is_rejected(
    tmp_path: Path,
) -> None:
    """Incomplete displacement lines are not accepted."""

    malformed = _frd_content().replace(
        "-6.70965E-0031.46947E-0027.15685E-003",
        "-6.70965E-0031.46947E-002",
        1,
    )

    frd_path = tmp_path / "result.frd"

    frd_path.write_text(
        malformed,
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="Expected three",
    ):
        read_targeted_frd_displacement_datasets(
            frd_path,
            target_node_ids={
                1,
            },
        )



def test_reads_targeted_force_records(
    tmp_path: Path,
) -> None:
    """Targeted FRD force extraction preserves nodal F1/F2/F3."""

    content = """    1PSTEP                         4           1           1
  100CL  101 1.000000000           3                     0    1           1
 -4  FORC        4    1
 -5  F1          1    2    1    0
 -5  F2          1    2    2    0
 -5  F3          1    2    3    0
 -5  ALL         1    2    0    0    1ALL
 -1    1533841.25000E+000-2.50000E+0003.75000E-001
 -1    153385-4.00000E-0015.00000E-001-6.00000E-001
 -3
"""

    frd_path = tmp_path / "force_result.frd"

    frd_path.write_text(
        content,
        encoding="utf-8",
    )

    datasets = read_targeted_frd_force_datasets(
        frd_path,
        target_node_ids={
            153384,
        },
    )

    assert len(datasets) == 1

    dataset = datasets[0]

    assert dataset.dataset_sequence == 4
    assert dataset.step == 1
    assert dataset.increment == 1
    assert dataset.time == pytest.approx(1.0)

    record = dataset.record_by_node_id(153384)

    assert record.f1_n == pytest.approx(1.25)
    assert record.f2_n == pytest.approx(-2.5)
    assert record.f3_n == pytest.approx(0.375)

"""Tests for geometry-aware complete-joint bearing-gap extraction."""

from pathlib import Path

import pytest

from threadrom.postprocessing.complete_joint_bearing_gap import (
    BOLT_UNDER_HEAD_SET,
    HEAD_MEMBER_BEARING_SET,
    NUT_LOWER_BEARING_SET,
    NUT_MEMBER_BEARING_SET,
    extract_complete_joint_bearing_gap_datasets,
    read_calculix_node_sets,
)


def _inp_content() -> str:
    """Return four explicit bearing-interface node sets."""

    return """*HEADING
Synthetic complete-joint bearing-gap case
*NSET, NSET=BOLT_UNDER_HEAD_BEARING
1, 2
*NSET, NSET=HEAD_MEMBER_HEAD_BEARING
3, 4
*NSET, NSET=NUT_LOWER_BEARING
5, 6
*NSET, NSET=NUT_MEMBER_NUT_BEARING
7, 8
*STEP
*STATIC
0.05, 1.0
*END STEP
"""


def _frd_content() -> str:
    """Return two accepted displacement datasets."""

    return """    1PSTEP                         1           1           1
  100CL  1015.00000E-002           3                     0    1           1
 -4  DISP        4    1
 -5  D1          1    2    1    0
 -5  D2          1    2    2    0
 -5  D3          1    2    3    0
 -1         10.00000E+0000.00000E+000-2.00000E-003
 -1         20.00000E+0000.00000E+000-4.00000E-003
 -1         30.00000E+0000.00000E+0000.00000E+000
 -1         40.00000E+0000.00000E+0002.00000E-003
 -1         50.00000E+0000.00000E+0005.00000E-003
 -1         60.00000E+0000.00000E+0007.00000E-003
 -1         70.00000E+0000.00000E+0001.00000E-003
 -1         80.00000E+0000.00000E+0003.00000E-003
 -3
    1PSTEP                         2           2           1
  100CL  1011.00000E-001           3                     0    2           1
 -4  DISP        4    1
 -5  D1          1    2    1    0
 -5  D2          1    2    2    0
 -5  D3          1    2    3    0
 -1         10.00000E+0000.00000E+0003.00000E-003
 -1         20.00000E+0000.00000E+0005.00000E-003
 -1         30.00000E+0000.00000E+0001.00000E-003
 -1         40.00000E+0000.00000E+0001.00000E-003
 -1         50.00000E+0000.00000E+000-2.00000E-003
 -1         60.00000E+0000.00000E+000-4.00000E-003
 -1         70.00000E+0000.00000E+0001.00000E-003
 -1         80.00000E+0000.00000E+0001.00000E-003
 -3
"""


def _write_case(
    tmp_path: Path,
) -> tuple[Path, Path]:
    """Write the synthetic CalculiX deck and FRD result."""

    inp_path = tmp_path / "joint.inp"
    frd_path = tmp_path / "joint.frd"

    inp_path.write_text(
        _inp_content(),
        encoding="utf-8",
    )

    frd_path.write_text(
        _frd_content(),
        encoding="utf-8",
    )

    return inp_path, frd_path


def test_reads_required_explicit_node_sets(
    tmp_path: Path,
) -> None:
    """Explicit node-set membership and ordering are preserved."""

    inp_path, _ = _write_case(tmp_path)

    node_sets = read_calculix_node_sets(
        inp_path,
        {
            BOLT_UNDER_HEAD_SET,
            HEAD_MEMBER_BEARING_SET,
            NUT_LOWER_BEARING_SET,
            NUT_MEMBER_BEARING_SET,
        },
    )

    assert node_sets[BOLT_UNDER_HEAD_SET] == (1, 2)
    assert node_sets[HEAD_MEMBER_BEARING_SET] == (3, 4)
    assert node_sets[NUT_LOWER_BEARING_SET] == (5, 6)
    assert node_sets[NUT_MEMBER_BEARING_SET] == (7, 8)


def test_extracts_geometry_aware_gap_for_each_increment(
    tmp_path: Path,
) -> None:
    """Positive gaps indicate opening and negative gaps compression."""

    inp_path, frd_path = _write_case(tmp_path)

    datasets = extract_complete_joint_bearing_gap_datasets(
        inp_path=inp_path,
        frd_path=frd_path,
    )

    assert len(datasets) == 2

    opening = datasets[0]

    assert opening.step == 1
    assert opening.increment == 1
    assert opening.time == pytest.approx(0.05)

    assert opening.bolt_under_head_mean_d3_mm == pytest.approx(-3.0e-3)
    assert opening.head_member_bearing_mean_d3_mm == pytest.approx(1.0e-3)
    assert opening.nut_lower_bearing_mean_d3_mm == pytest.approx(6.0e-3)
    assert opening.nut_member_bearing_mean_d3_mm == pytest.approx(2.0e-3)

    assert opening.under_head_signed_gap_change_mm == pytest.approx(4.0e-3)
    assert opening.nut_bearing_signed_gap_change_mm == pytest.approx(4.0e-3)

    compression = datasets[1]

    assert compression.step == 1
    assert compression.increment == 2
    assert compression.time == pytest.approx(0.1)

    assert compression.under_head_signed_gap_change_mm == pytest.approx(-3.0e-3)
    assert compression.nut_bearing_signed_gap_change_mm == pytest.approx(-4.0e-3)


def test_missing_required_node_set_is_rejected(
    tmp_path: Path,
) -> None:
    """All four physical bearing node sets are mandatory."""

    inp_path = tmp_path / "missing.inp"

    inp_path.write_text(
        _inp_content().replace(
            """*NSET, NSET=NUT_MEMBER_NUT_BEARING
7, 8
""",
            "",
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="NUT_MEMBER_NUT_BEARING",
    ):
        read_calculix_node_sets(
            inp_path,
            {
                NUT_MEMBER_BEARING_SET,
            },
        )


def test_generated_node_set_is_rejected(
    tmp_path: Path,
) -> None:
    """Generated node sets cannot be silently misinterpreted."""

    inp_path = tmp_path / "generated.inp"

    inp_path.write_text(
        """*NSET, NSET=TARGET, GENERATE
1, 9, 1
""",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="Generated CalculiX node sets are unsupported",
    ):
        read_calculix_node_sets(
            inp_path,
            {
                "TARGET",
            },
        )

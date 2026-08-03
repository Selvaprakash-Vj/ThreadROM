"""Tests for governed CalculiX pretension restarts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from threadrom.solver.complete_joint_pretension_restart import (
    find_last_completed_checkpoint,
    parse_calculix_sta_records,
    prepare_pretension_restart_bundle,
)


def _full_checkpoint_deck(
    checkpoint_count: int,
) -> str:
    lines = ["** Synthetic governed deck"]

    for checkpoint in range(
        1,
        checkpoint_count + 1,
    ):
        lines.extend(
            (
                (f"** Step {checkpoint}: preload checkpoint {checkpoint / checkpoint_count:.6f}"),
                "*STEP, NLGEOM=YES, INC=100",
                "*STATIC",
                ("1.000000000000e+00, 1.000000000000e+00, 1.000000000000e-06, 1.000000000000e+00"),
            )
        )

        if checkpoint == 1:
            lines.append("*RESTART,WRITE,FREQUENCY=1,OVERLAY")

        lines.extend(
            (
                "*CLOAD",
                f"100, 1, {checkpoint * 250.0}",
                "*END STEP",
                "",
            )
        )

    return "\n".join(lines)


def test_find_last_completed_checkpoint() -> None:
    records = parse_calculix_sta_records(
        """
SUMMARY OF JOB INFORMATION
  STEP INC ATT ITRS TOT TIME STEP TIME INC TIME
     1   1   1   4   0.5   0.5   0.5
     1   2   1   6   1.0   1.0   0.5
     2   1   1U  3   1.0   0.0   1.0
     2   1   2   5   2.0   1.0   1.0
     3   1   1U  4   2.0   0.0   1.0
"""
    )

    assert len(records) == 5

    assert (
        find_last_completed_checkpoint(
            records,
            checkpoint_count=4,
            configured_step_time=1.0,
        )
        == 2
    )


def test_prepare_pretension_restart_bundle(
    tmp_path: Path,
) -> None:
    original_input_path = tmp_path / "source.inp"
    sta_path = tmp_path / "source.sta"
    restart_output_path = tmp_path / "source.rout"
    output_directory = tmp_path / "restart_bundle"

    original_input_path.write_text(
        _full_checkpoint_deck(4),
        encoding="utf-8",
        newline="\n",
    )

    sta_path.write_text(
        """
SUMMARY OF JOB INFORMATION
     1  1  1  4  1.0  1.0  1.0
     2  1  1  5  2.0  1.0  1.0
     3  1  1U 4  2.0  0.0  1.0
""",
        encoding="utf-8",
        newline="\n",
    )

    restart_bytes = b"synthetic-calculix-restart"

    restart_output_path.write_bytes(restart_bytes)

    summary = prepare_pretension_restart_bundle(
        original_input_path=original_input_path,
        sta_path=sta_path,
        restart_output_path=restart_output_path,
        output_directory=output_directory,
        continuation_job_name="resume_s02",
        checkpoint_count=4,
        configured_step_time=1.0,
        restart_write_frequency_steps=1,
        overlay_latest=True,
    )

    assert summary.completed_checkpoint == 2
    assert summary.next_checkpoint == 3
    assert summary.remaining_checkpoint_count == 2

    continuation_text = summary.continuation_input_path.read_text(encoding="utf-8")

    assert continuation_text.startswith("*RESTART,READ\n")

    assert "** Step 1:" not in continuation_text
    assert "** Step 2:" not in continuation_text
    assert "** Step 3:" in continuation_text
    assert "** Step 4:" in continuation_text

    assert continuation_text.count("*RESTART,WRITE,FREQUENCY=1,OVERLAY") == 1

    assert summary.restart_input_path.read_bytes() == restart_bytes

    manifest = json.loads(summary.manifest_path.read_text(encoding="utf-8"))

    assert manifest["completed_checkpoint"] == 2
    assert manifest["next_checkpoint"] == 3
    assert manifest["bundle"]["restart_input_sha256"] == manifest["source"]["restart_output_sha256"]


def test_restart_bundle_refuses_overwrite(
    tmp_path: Path,
) -> None:
    original_input_path = tmp_path / "source.inp"
    sta_path = tmp_path / "source.sta"
    restart_output_path = tmp_path / "source.rout"
    output_directory = tmp_path / "existing"

    original_input_path.write_text(
        _full_checkpoint_deck(2),
        encoding="utf-8",
    )

    sta_path.write_text(
        "1 1 1 4 1.0 1.0 1.0\n",
        encoding="utf-8",
    )

    restart_output_path.write_bytes(b"restart")
    output_directory.mkdir()

    with pytest.raises(
        FileExistsError,
        match="already exists",
    ):
        prepare_pretension_restart_bundle(
            original_input_path=original_input_path,
            sta_path=sta_path,
            restart_output_path=restart_output_path,
            output_directory=output_directory,
            continuation_job_name="resume_s01",
            checkpoint_count=2,
            configured_step_time=1.0,
            restart_write_frequency_steps=1,
            overlay_latest=True,
        )

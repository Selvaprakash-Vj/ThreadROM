"""Tests for fail-safe stale FEM process adjudication."""

from threadrom.factory.windows_process_adjudication import (
    FemProcessStatus,
    WindowsProcessSnapshot,
    adjudicate_process_snapshots,
)


def test_live_executor_blocks_recovery() -> None:
    result = adjudicate_process_snapshots(
        snapshots=(
            WindowsProcessSnapshot(
                process_id=100,
                parent_process_id=1,
                executable_path=r"C:\Python\python.exe",
                command_line=(
                    "python "
                    "D:\\ThreadROM\\scripts\\"
                    "run_phase3_production_doe_calibration_trial_case.py "
                    "--case-id D-INT-001 --trial-index 1"
                ),
            ),
        ),
        run_id="trm_fem_abc_cal_01",
        case_id="D-INT-001",
    )

    assert result.status is FemProcessStatus.LIVE_MATCH
    assert result.matching_process_ids == (100,)


def test_live_matching_ccx_blocks_recovery() -> None:
    result = adjudicate_process_snapshots(
        snapshots=(
            WindowsProcessSnapshot(
                process_id=200,
                parent_process_id=100,
                executable_path=r"D:\ThreadROM\bin\ccx.exe",
                command_line=(
                    "D:\\ThreadROM\\bin\\ccx.exe "
                    "-i trm_fem_abc_cal_01"
                ),
            ),
        ),
        run_id="trm_fem_abc_cal_01",
        case_id="D-INT-001",
    )

    assert result.status is FemProcessStatus.LIVE_MATCH
    assert result.matching_process_ids == (200,)


def test_unrelated_processes_do_not_block_recovery() -> None:
    result = adjudicate_process_snapshots(
        snapshots=(
            WindowsProcessSnapshot(
                process_id=300,
                parent_process_id=1,
                executable_path=r"D:\ThreadROM\bin\ccx.exe",
                command_line=(
                    "D:\\ThreadROM\\bin\\ccx.exe "
                    "-i completely_different_job"
                ),
            ),
        ),
        run_id="trm_fem_abc_cal_01",
        case_id="D-INT-001",
    )

    assert result.status is FemProcessStatus.NO_MATCH
    assert result.matching_process_ids == ()

"""Prepare a governed CalculiX pretension restart bundle."""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "src"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from threadrom.solver.complete_joint_pretension import (
    load_complete_joint_pretension_definition,
)
from threadrom.solver.complete_joint_pretension_restart import (
    find_last_completed_checkpoint,
    parse_calculix_sta_records,
    prepare_pretension_restart_bundle,
)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Prepare a non-destructive CalculiX pretension continuation bundle.")
    )

    parser.add_argument(
        "--pretension-config",
        required=True,
    )

    parser.add_argument(
        "--working-directory",
        required=True,
    )

    parser.add_argument(
        "--job-name",
        required=True,
    )

    parser.add_argument(
        "--output-directory",
    )

    parser.add_argument(
        "--continuation-job-name",
    )

    return parser.parse_args()


def main() -> None:
    arguments = _parse_arguments()

    pretension = load_complete_joint_pretension_definition(
        PROJECT_ROOT / "config" / arguments.pretension_config
    )

    if not pretension.restart_policy.write_enabled:
        raise ValueError("The governed restart-write policy is disabled.")

    working_directory = Path(arguments.working_directory).resolve()

    original_input_path = working_directory / f"{arguments.job_name}.inp"

    sta_path = working_directory / f"{arguments.job_name}.sta"

    restart_output_path = working_directory / f"{arguments.job_name}.rout"

    records = parse_calculix_sta_records(
        sta_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    )

    completed_checkpoint = find_last_completed_checkpoint(
        records,
        checkpoint_count=(pretension.load_schedule.checkpoint_count),
        configured_step_time=(pretension.load_schedule.step_time),
    )

    continuation_job_name = arguments.continuation_job_name or (
        f"{arguments.job_name}_resume_s{completed_checkpoint:02d}"
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    output_directory = (
        Path(arguments.output_directory).resolve()
        if arguments.output_directory
        else (working_directory / "restart_bundles" / (f"{continuation_job_name}_{timestamp}"))
    )

    summary = prepare_pretension_restart_bundle(
        original_input_path=original_input_path,
        sta_path=sta_path,
        restart_output_path=restart_output_path,
        output_directory=output_directory,
        continuation_job_name=(continuation_job_name),
        checkpoint_count=(pretension.load_schedule.checkpoint_count),
        configured_step_time=(pretension.load_schedule.step_time),
        restart_write_frequency_steps=(pretension.restart_policy.write_frequency_steps),
        overlay_latest=(pretension.restart_policy.overlay_latest),
    )

    print("PRETENSION RESTART BUNDLE: VERIFIED")
    print(f"Completed checkpoint: {summary.completed_checkpoint}")
    print(f"Next checkpoint: {summary.next_checkpoint}")
    print(f"Remaining checkpoints: {summary.remaining_checkpoint_count}")
    print(f"Continuation job: {summary.continuation_job_name}")
    print(f"Restart size: {summary.restart_size_bytes} bytes")
    print(f"Restart SHA256: {summary.restart_sha256}")
    print(f"Bundle directory: {summary.output_directory}")
    print(f"Continuation input: {summary.continuation_input_path}")
    print(f"Restart input: {summary.restart_input_path}")
    print(f"Manifest: {summary.manifest_path}")


if __name__ == "__main__":
    main()

"""Run the governed complete-joint A0-A3 and A0T settling diagnostics."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from threadrom.solver.complete_joint_boundary_regions import (
    load_complete_joint_boundary_region_definition,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)
from threadrom.solver.complete_joint_pretension import (
    load_complete_joint_pretension_definition,
)
from threadrom.solver.complete_joint_settling_diagnostic import (
    settling_diagnostic_case,
    write_complete_joint_settling_diagnostic_deck,
)

DEFAULT_TRANSFER_CONFIG = "complete_joint_pretension_calculix_transfer_c3d4_coarse_diagnostic.toml"
DEFAULT_CONTACT_CONFIG = "complete_joint_pretension_contact_c3d4_coarse_diagnostic.toml"
DEFAULT_BOUNDARY_CONFIG = "complete_joint_pretension_boundary_regions_c3d4_coarse_diagnostic.toml"
DEFAULT_PRETENSION_CONFIG = "complete_joint_pretension_c3d4_coarse_diagnostic.toml"

CASE_IDS = ("A0", "A0T", "A1", "A2", "A3")

OUTPUT_SUFFIXES = (
    ".12d",
    ".cvg",
    ".dat",
    ".eig",
    ".frd",
    ".sta",
)


def _parse_arguments() -> argparse.Namespace:
    """Parse governed diagnostic-run arguments."""

    parser = argparse.ArgumentParser(
        description=("Run the governed complete-joint A0-A3 and A0T settling diagnostics.")
    )

    parser.add_argument(
        "--transfer-config",
        default=DEFAULT_TRANSFER_CONFIG,
    )
    parser.add_argument(
        "--contact-config",
        default=DEFAULT_CONTACT_CONFIG,
    )
    parser.add_argument(
        "--boundary-config",
        default=DEFAULT_BOUNDARY_CONFIG,
    )
    parser.add_argument(
        "--pretension-config",
        default=DEFAULT_PRETENSION_CONFIG,
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        type=str.upper,
        choices=CASE_IDS,
        default=list(CASE_IDS),
        help="Diagnostic cases to generate or run.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=1800,
        help=("Maximum runtime for each case. Use 0 to disable the timeout."),
    )
    parser.add_argument(
        "--stiffness-threads",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--equation-solver-threads",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--results-threads",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--write-only",
        action="store_true",
        help="Generate and verify decks without launching CalculiX.",
    )

    return parser.parse_args()


def _validate_runtime_controls(
    arguments: argparse.Namespace,
) -> tuple[int | None, int, dict[str, int]]:
    """Validate timeout and thread counts."""

    if arguments.timeout_seconds < 0:
        raise ValueError("Timeout must be zero or a positive number.")

    logical_cpu_count = os.cpu_count() or 1

    thread_counts = {
        "stiffness": arguments.stiffness_threads,
        "equation_solver": (arguments.equation_solver_threads),
        "results": arguments.results_threads,
    }

    for stage, thread_count in thread_counts.items():
        if thread_count < 1:
            raise ValueError(f"{stage} thread count must be positive.")

        if thread_count > logical_cpu_count:
            raise ValueError(
                f"{stage} thread count {thread_count} "
                f"exceeds the detected logical CPU count "
                f"{logical_cpu_count}."
            )

    timeout_seconds = None if arguments.timeout_seconds == 0 else arguments.timeout_seconds

    return (
        timeout_seconds,
        logical_cpu_count,
        thread_counts,
    )


def _solver_environment(
    logical_cpu_count: int,
    thread_counts: dict[str, int],
) -> dict[str, str]:
    """Build the governed CalculiX environment."""

    maximum_requested_threads = max(thread_counts.values())

    environment = os.environ.copy()

    environment.update(
        {
            "OMP_NUM_THREADS": str(maximum_requested_threads),
            "CCX_NPROC_STIFFNESS": str(thread_counts["stiffness"]),
            "CCX_NPROC_EQUATION_SOLVER": str(thread_counts["equation_solver"]),
            "CCX_NPROC_RESULTS": str(thread_counts["results"]),
            "NUMBER_OF_CPUS": str(logical_cpu_count),
        }
    )

    return environment


def _remove_stale_outputs(
    working_directory: Path,
    job_name: str,
) -> None:
    """Remove stale solver-result files for one case."""

    for suffix in OUTPUT_SUFFIXES:
        stale_path = working_directory / f"{job_name}{suffix}"

        if stale_path.exists():
            stale_path.unlink()


def _write_manifest(
    path: Path,
    manifest: dict[str, object],
) -> None:
    """Write one deterministic JSON run manifest."""

    path.write_text(
        json.dumps(
            manifest,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    """Generate and optionally run selected A0-A3 and A0T cases."""

    arguments = _parse_arguments()

    project_root = Path(__file__).resolve().parents[1]
    config_directory = project_root / "config"

    transfer = load_complete_joint_calculix_transfer_definition(
        config_directory / arguments.transfer_config
    )

    contact = load_complete_joint_contact_definition(config_directory / arguments.contact_config)

    boundary = load_complete_joint_boundary_region_definition(
        config_directory / arguments.boundary_config
    )

    pretension = load_complete_joint_pretension_definition(
        config_directory / arguments.pretension_config
    )

    source_mesh_path = (
        project_root
        / "simulations"
        / "staging"
        / transfer.mesh_id
        / "mesh"
        / transfer.source_mesh_name
    )

    mesh_data = read_grouped_complete_joint_mesh(
        source_mesh_path,
        transfer,
    )

    timeout_seconds, logical_cpu_count, thread_counts = _validate_runtime_controls(arguments)

    executable_path = project_root / transfer.executable_relative_path

    if not arguments.write_only and not executable_path.exists():
        raise FileNotFoundError(f"CalculiX executable not found: {executable_path}")

    solver_environment = _solver_environment(
        logical_cpu_count,
        thread_counts,
    )

    working_root = (
        project_root
        / "simulations"
        / "staging"
        / transfer.simulation_id
        / "settling_diagnostics"
        / transfer.mesh_level
    )

    print("COMPLETE-JOINT SETTLING DIAGNOSTICS")
    print(f"Simulation:       {transfer.simulation_id}")
    print(f"Mesh:             {transfer.mesh_id}")
    print(f"Element type:     {transfer.element_type}")
    print(f"Nodes:            {mesh_data.node_count}")
    print(f"Elements:         {mesh_data.element_count}")
    print("Selected cases:   " + ", ".join(arguments.cases))
    print("Mode:             " + ("write-only" if arguments.write_only else "solver run"))

    if not arguments.write_only:
        print("CalculiX runtime controls:")
        print(
            "  Timeout per case: "
            + ("disabled" if timeout_seconds is None else f"{timeout_seconds} seconds")
        )
        print(f"  Stiffness threads: {thread_counts['stiffness']}")
        print(f"  Equation-solver threads: {thread_counts['equation_solver']}")
        print(f"  Results threads: {thread_counts['results']}")
        print(f"  Detected logical CPUs: {logical_cpu_count}")

    for case_id in arguments.cases:
        case = settling_diagnostic_case(case_id)

        case_directory = working_root / case.case_id.lower()

        case_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        job_name = (
            transfer.simulation_id.lower().replace(
                "-",
                "_",
            )
            + f"_{transfer.element_type.lower()}"
            + f"_{case.case_id.lower()}"
            + "_settling"
        )

        input_path = case_directory / f"{job_name}.inp"

        summary = write_complete_joint_settling_diagnostic_deck(
            mesh_data,
            transfer,
            contact,
            boundary,
            pretension,
            case,
            input_path,
        )

        print()
        print(f"CASE {case.case_id}: DECK VERIFIED")
        print(f"  Pretension section: {summary.pretension_section_count}")
        print(f"  Reference force:    {summary.applied_reference_force_n:+.3f} N")
        print(f"  Contact pairs:      {summary.contact_pair_count}")
        print(
            "  Excluded pairs:     "
            + (
                ", ".join(summary.excluded_contact_pair_names)
                if summary.excluded_contact_pair_names
                else "none"
            )
        )
        print(f"  Guidance samples:   {summary.guidance_sample_node_count}")
        print(f"  Excluded faces:     {summary.excluded_thread_contact_face_count}")
        print(f"  Input deck:         {input_path}")

        if arguments.write_only:
            continue

        _remove_stale_outputs(
            case_directory,
            job_name,
        )

        stdout_path = case_directory / f"{job_name}.solver.stdout.log"

        stderr_path = case_directory / f"{job_name}.solver.stderr.log"

        manifest_path = case_directory / f"{job_name}.run.json"

        started_at = time.perf_counter()
        return_code: int | None = None
        timed_out = False

        try:
            with (
                stdout_path.open(
                    "w",
                    encoding="utf-8",
                    newline="\n",
                ) as stdout_stream,
                stderr_path.open(
                    "w",
                    encoding="utf-8",
                    newline="\n",
                ) as stderr_stream,
            ):
                completed = subprocess.run(
                    [
                        str(executable_path),
                        "-i",
                        job_name,
                    ],
                    cwd=case_directory,
                    stdout=stdout_stream,
                    stderr=stderr_stream,
                    timeout=timeout_seconds,
                    env=solver_environment,
                    check=False,
                    text=True,
                )

            return_code = completed.returncode

        except subprocess.TimeoutExpired:
            timed_out = True

        elapsed_seconds = time.perf_counter() - started_at

        manifest: dict[str, object] = {
            "diagnostic_id": "TRM-DIAG-000002",
            "simulation_id": transfer.simulation_id,
            "mesh_id": transfer.mesh_id,
            "element_type": transfer.element_type,
            "case_id": case.case_id,
            "pretension_section_count": (summary.pretension_section_count),
            "applied_reference_force_n": (summary.applied_reference_force_n),
            "contact_pair_count": (summary.contact_pair_count),
            "excluded_contact_pair_names": list(summary.excluded_contact_pair_names),
            "guidance_sample_node_count": (summary.guidance_sample_node_count),
            "excluded_thread_contact_face_count": (summary.excluded_thread_contact_face_count),
            "timeout_seconds": (arguments.timeout_seconds),
            "timeout_enabled": (timeout_seconds is not None),
            "timed_out": timed_out,
            "elapsed_seconds": elapsed_seconds,
            "threading": {
                "stiffness_threads": (thread_counts["stiffness"]),
                "equation_solver_threads": (thread_counts["equation_solver"]),
                "results_threads": (thread_counts["results"]),
                "omp_num_threads": max(thread_counts.values()),
                "detected_logical_cpus": (logical_cpu_count),
            },
            "return_code": return_code,
            "input_path": str(input_path),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
        }

        _write_manifest(
            manifest_path,
            manifest,
        )

        print(f"  Elapsed:            {elapsed_seconds:.3f} s")
        print(f"  Timed out:          {timed_out}")
        print(f"  Return code:        {return_code}")
        print(f"  Run manifest:       {manifest_path}")

        if timed_out:
            raise RuntimeError(f"CalculiX settling diagnostic {case.case_id} timed out.")

        if return_code != 0:
            raise RuntimeError(f"CalculiX settling diagnostic {case.case_id} failed.")


if __name__ == "__main__":
    main()

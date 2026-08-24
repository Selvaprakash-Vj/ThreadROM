"""Run a governed nonlinear complete-joint pretension analysis."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
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
from threadrom.solver.complete_joint_physical_pretension import (
    GUIDANCE_SAMPLE_NODE_COUNT,
    ROTATION_GUIDANCE_SAMPLE_NODE_COUNT,
    write_complete_joint_physical_pretension_deck,
)
from threadrom.solver.complete_joint_pretension import (
    load_complete_joint_pretension_definition,
)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Run a governed nonlinear complete-joint physical pretension analysis.")
    )

    parser.add_argument(
        "--transfer-config",
        required=True,
    )
    parser.add_argument(
        "--contact-config",
        required=True,
    )
    parser.add_argument(
        "--boundary-config",
        required=True,
    )
    parser.add_argument(
        "--pretension-config",
        required=True,
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=0,
        help=("Maximum solver runtime in seconds. Use 0 to disable the timeout."),
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
        "--translation-guidance-samples",
        type=int,
        default=GUIDANCE_SAMPLE_NODE_COUNT,
    )
    parser.add_argument(
        "--rotation-guidance-samples",
        type=int,
        default=ROTATION_GUIDANCE_SAMPLE_NODE_COUNT,
    )
    parser.add_argument(
        "--write-only",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    arguments = _parse_arguments()

    project_root = Path(__file__).resolve().parents[1]
    config_dir = project_root / "config"

    transfer = load_complete_joint_calculix_transfer_definition(
        config_dir / arguments.transfer_config
    )

    contact = load_complete_joint_contact_definition(config_dir / arguments.contact_config)

    boundary = load_complete_joint_boundary_region_definition(
        config_dir / arguments.boundary_config
    )

    pretension = load_complete_joint_pretension_definition(config_dir / arguments.pretension_config)

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

    load_label = round(pretension.preload_force_n)

    job_name = (
        transfer.simulation_id.lower().replace("-", "_")
        + f"_{transfer.element_type.lower()}"
        + f"_{load_label}n_pretension"
    )

    working_directory = (
        project_root
        / "simulations"
        / "staging"
        / transfer.simulation_id
        / "physical_pretension"
        / transfer.mesh_level
    )

    working_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path = working_directory / f"{job_name}.inp"

    summary = write_complete_joint_physical_pretension_deck(
        mesh_data,
        transfer,
        contact,
        boundary,
        pretension,
        input_path,
        translation_sample_node_count=(
            arguments.translation_guidance_samples
        ),
        rotation_sample_node_count=(
            arguments.rotation_guidance_samples
        ),
    )

    print("PHYSICAL PRETENSION DECK: VERIFIED")
    print(f"Simulation: {transfer.simulation_id}")
    print(f"Element type: {transfer.element_type}")
    print(f"Nodes: {mesh_data.node_count}")
    print(f"Elements: {mesh_data.element_count}")
    print(f"Preload: {summary.preload_force_n:.3f} N")
    print(f"Boundary-region nodes: {summary.boundary_region_node_count}")
    print(f"Contact pairs: {summary.contact_pair_count}")
    print(f"Guidance samples: {summary.guidance_sample_node_count}")
    print(f"Input deck: {input_path}")

    if arguments.write_only:
        return

    executable_path = project_root / transfer.executable_relative_path

    if not executable_path.exists():
        raise FileNotFoundError(f"CalculiX executable not found: {executable_path}")

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

    timeout_seconds: int | None = (
        None if arguments.timeout_seconds == 0 else arguments.timeout_seconds
    )

    maximum_requested_threads = max(thread_counts.values())

    solver_environment = os.environ.copy()

    solver_environment.update(
        {
            "OMP_NUM_THREADS": str(maximum_requested_threads),
            "CCX_NPROC_STIFFNESS": str(arguments.stiffness_threads),
            "CCX_NPROC_EQUATION_SOLVER": str(arguments.equation_solver_threads),
            "CCX_NPROC_RESULTS": str(arguments.results_threads),
            "NUMBER_OF_CPUS": str(logical_cpu_count),
        }
    )

    print("CalculiX runtime controls:")
    print("  Timeout: " + ("disabled" if timeout_seconds is None else f"{timeout_seconds} seconds"))
    print(f"  Stiffness threads: {arguments.stiffness_threads}")
    print(f"  Equation-solver threads: {arguments.equation_solver_threads}")
    print(f"  Results threads: {arguments.results_threads}")
    print(f"  Detected logical CPUs: {logical_cpu_count}")

    output_suffixes = (
        ".12d",
        ".cvg",
        ".dat",
        ".eig",
        ".frd",
        ".sta",
    )

    for suffix in output_suffixes:
        stale_path = working_directory / f"{job_name}{suffix}"

        if stale_path.exists():
            stale_path.unlink()

    solver_stdout_path = working_directory / f"{job_name}.solver.stdout.log"

    solver_stderr_path = working_directory / f"{job_name}.solver.stderr.log"

    with (
        solver_stdout_path.open(
            "w",
            encoding="utf-8",
            newline="\n",
        ) as stdout_stream,
        solver_stderr_path.open(
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
            cwd=working_directory,
            stdout=stdout_stream,
            stderr=stderr_stream,
            timeout=timeout_seconds,
            env=solver_environment,
            check=False,
            text=True,
        )

    manifest_path = working_directory / f"{job_name}.run.json"

    manifest = {
        "simulation_id": transfer.simulation_id,
        "mesh_id": transfer.mesh_id,
        "element_type": transfer.element_type,
        "preload_force_n": pretension.preload_force_n,
        "timeout_seconds": arguments.timeout_seconds,
        "timeout_enabled": timeout_seconds is not None,
        "threading": {
            "stiffness_threads": (arguments.stiffness_threads),
            "equation_solver_threads": (arguments.equation_solver_threads),
            "results_threads": (arguments.results_threads),
            "omp_num_threads": (maximum_requested_threads),
            "detected_logical_cpus": (logical_cpu_count),
        },
        "return_code": completed.returncode,
        "input_path": str(input_path),
        "stdout_path": str(solver_stdout_path),
        "stderr_path": str(solver_stderr_path),
    }

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"CalculiX return code: {completed.returncode}")
    print(f"Run manifest: {manifest_path}")

    if completed.returncode != 0:
        raise RuntimeError("CalculiX nonlinear pretension run failed.")


if __name__ == "__main__":
    main()

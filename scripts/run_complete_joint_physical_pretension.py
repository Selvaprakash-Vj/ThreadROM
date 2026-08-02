"""Run a governed nonlinear complete-joint pretension analysis."""

from __future__ import annotations

import argparse
import json
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
        default=43200,
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
            timeout=arguments.timeout_seconds,
            check=False,
            text=True,
        )

    manifest_path = working_directory / f"{job_name}.run.json"

    manifest = {
        "simulation_id": transfer.simulation_id,
        "mesh_id": transfer.mesh_id,
        "element_type": transfer.element_type,
        "preload_force_n": pretension.preload_force_n,
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

"""Run the complete-joint CalculiX transfer smoke test."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
    write_complete_joint_calculix_transfer_deck,
)


def _parse_arguments() -> argparse.Namespace:
    """Parse governed transfer-runner arguments."""

    parser = argparse.ArgumentParser(
        description=("Run a governed complete-joint CalculiX transfer smoke test.")
    )

    parser.add_argument(
        "--transfer-config",
        default="complete_joint_calculix_transfer.toml",
        help=(
            "Transfer configuration filename inside config/. "
            "Defaults to the verified C3D4 transfer."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """Generate, execute and verify the transfer-only deck."""

    arguments = _parse_arguments()
    project_root = Path(__file__).resolve().parents[1]

    definition = load_complete_joint_calculix_transfer_definition(
        project_root / "config" / arguments.transfer_config
    )

    source_mesh_path = (
        project_root
        / "simulations"
        / "staging"
        / definition.mesh_id
        / "mesh"
        / definition.source_mesh_name
    )

    mesh_data = read_grouped_complete_joint_mesh(
        source_mesh_path,
        definition,
    )

    working_directory = (
        project_root
        / "simulations"
        / "staging"
        / definition.simulation_id
        / "mesh_transfer"
        / definition.mesh_level
    )

    input_path = working_directory / f"{definition.job_name}.inp"

    internal_surface_normals = (
        {
            "BOLT_PRETENSION_SECTION": (
                0.0,
                0.0,
                1.0,
            ),
        }
        if "BOLT_PRETENSION_SECTION" in definition.required_boundary_groups
        else None
    )

    deck_summary = write_complete_joint_calculix_transfer_deck(
        mesh_data,
        definition,
        input_path,
        internal_surface_normals=(internal_surface_normals),
    )

    executable_path = project_root / definition.executable_relative_path

    if not executable_path.exists():
        raise FileNotFoundError(f"CalculiX executable not found: {executable_path}")

    for suffix in (
        ".12d",
        ".cvg",
        ".dat",
        ".eig",
        ".frd",
        ".sta",
    ):
        stale_output = working_directory / (definition.job_name + suffix)

        if stale_output.exists():
            stale_output.unlink()

    completed = subprocess.run(
        [
            str(executable_path),
            "-i",
            definition.job_name,
        ],
        cwd=working_directory,
        capture_output=True,
        text=True,
        timeout=definition.timeout_seconds,
        check=False,
    )

    stdout_path = working_directory / (definition.job_name + ".stdout.log")
    stderr_path = working_directory / (definition.job_name + ".stderr.log")

    stdout_path.write_text(
        completed.stdout,
        encoding="utf-8",
        errors="replace",
        newline="\n",
    )

    stderr_path.write_text(
        completed.stderr,
        encoding="utf-8",
        errors="replace",
        newline="\n",
    )

    dat_path = working_directory / (definition.job_name + ".dat")
    frd_path = working_directory / (definition.job_name + ".frd")
    sta_path = working_directory / (definition.job_name + ".sta")

    diagnostics = completed.stdout + "\n" + completed.stderr

    if dat_path.exists():
        diagnostics += "\n" + dat_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

    if completed.returncode != 0:
        raise RuntimeError("CalculiX returned a nonzero exit code.\n" + diagnostics[-4000:])

    if "*ERROR" in diagnostics.upper():
        raise RuntimeError("CalculiX reported an input or solver error.\n" + diagnostics[-4000:])

    required_outputs = (
        dat_path,
        frd_path,
        sta_path,
    )

    missing_outputs = tuple(
        path for path in required_outputs if (not path.exists() or path.stat().st_size <= 0)
    )

    if missing_outputs:
        raise RuntimeError(
            "CalculiX did not create required outputs: "
            + ", ".join(str(path) for path in missing_outputs)
        )

    expected_zero_dof_warning = "no degrees of freedom in the model" in diagnostics.lower()

    if not expected_zero_dof_warning:
        raise RuntimeError(
            "The fully constrained smoke model did not produce the expected zero-DOF diagnostic."
        )

    metadata_directory = (
        project_root / "simulations" / "staging" / definition.simulation_id / "metadata"
    )

    metadata_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path = metadata_directory / "complete_joint_calculix_transfer.json"

    manifest = {
        "simulation_id": definition.simulation_id,
        "mesh_id": definition.mesh_id,
        "assembly_id": definition.assembly_id,
        "geometry_id": definition.geometry_id,
        "classification_id": (definition.classification_id),
        "mesh_level": definition.mesh_level,
        "solver": {
            "return_code": completed.returncode,
            "expected_zero_dof_warning": (expected_zero_dof_warning),
        },
        "transfer": {
            "node_count": deck_summary.node_count,
            "element_count": (deck_summary.element_count),
            "volume_element_set_count": (deck_summary.volume_element_set_count),
            "boundary_node_set_count": (deck_summary.boundary_node_set_count),
            "element_surface_count": (deck_summary.element_surface_count),
            "mapped_element_face_count": (deck_summary.mapped_element_face_count),
            "fixed_node_count": (deck_summary.smoke_test_fixed_node_count),
            "input_file_size_bytes": (deck_summary.input_file_size_bytes),
        },
        "outputs": {
            "dat_size_bytes": dat_path.stat().st_size,
            "frd_size_bytes": frd_path.stat().st_size,
            "sta_size_bytes": sta_path.stat().st_size,
        },
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

    component_rows = "\n".join(
        (f"| {component} | {element_count} |")
        for component, element_count in (deck_summary.component_element_counts)
    )

    report = f"""# {definition.simulation_id} Complete-Joint CalculiX Transfer Check

## Status

The grouped four-component threaded-joint mesh was transferred into
a CalculiX {definition.element_type} input deck and processed successfully by CalculiX 2.23.

This is a transfer-only solver-read smoke test. It is not a physical
threaded-joint simulation.

## Transfer summary

| Quantity | Value |
|---|---:|
| Mesh level | {definition.mesh_level} |
| Nodes | {deck_summary.node_count} |
| {definition.element_type} elements | {deck_summary.element_count} |
| Component ELSETs | {deck_summary.volume_element_set_count} |
| Engineering NSETs | {deck_summary.boundary_node_set_count} |
| Engineering element surfaces | {deck_summary.element_surface_count} |
| Mapped {definition.element_type} boundary faces | {deck_summary.mapped_element_face_count} |
| Fully constrained smoke-test nodes | {deck_summary.smoke_test_fixed_node_count} |
| Input file size | {deck_summary.input_file_size_bytes} bytes |

## Component element sets

| Component | {definition.element_type} elements |
|---|---:|
{component_rows}

## Solver result

| Quantity | Value |
|---|---:|
| CalculiX return code | {completed.returncode} |
| Expected zero-DOF warning found | {expected_zero_dof_warning} |
| DAT size | {dat_path.stat().st_size} bytes |
| FRD size | {frd_path.stat().st_size} bytes |
| STA size | {sta_path.stat().st_size} bytes |

## Smoke-test interpretation

Every mesh node was intentionally constrained in all three translational
degrees of freedom and no load was applied.

CalculiX therefore reported that the model contained no active degrees
of freedom. This warning is expected for this deliberately nonphysical
parser and solver-read test.

The gate verifies:

- All {deck_summary.node_count:,} nodes are readable
- All {deck_summary.element_count:,} {definition.element_type} elements are readable
- Four component ELSETs are accepted
- {deck_summary.boundary_node_set_count} boundary NSETs are accepted
- {deck_summary.element_surface_count} element-based surfaces are accepted
- All {deck_summary.mapped_element_face_count:,} mapped {definition.element_type} faces are accepted
- Three independent material and section definitions are accepted
- CalculiX returns exit code zero
- No CalculiX `*ERROR` diagnostic is present
- DAT, FRD and STA outputs are created

## Solver outputs

| Output | Path |
|---|---|
| Input deck | `{input_path}` |
| DAT file | `{dat_path}` |
| FRD file | `{frd_path}` |
| STA file | `{sta_path}` |
| Standard-output log | `{stdout_path}` |
| Error-output log | `{stderr_path}` |

## Next gate

Define and verify the four nonlinear contact interfaces:

1. Bolt external thread to nut internal thread
2. Bolt under-head bearing to head-side member
3. Nut bearing to nut-side member
4. Head-side member to nut-side member
"""

    report_path = (
        project_root
        / "docs"
        / "verification"
        / (f"{definition.simulation_id}_COMPLETE_JOINT_CALCULIX_TRANSFER.md")
    )

    report_path.write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print("Complete-joint CalculiX transfer: VERIFIED")
    print(f"CalculiX return code: {completed.returncode}")
    print(f"Nodes: {deck_summary.node_count}")
    print(f"{definition.element_type} elements: {deck_summary.element_count}")
    print(f"Element surfaces: {deck_summary.element_surface_count}")
    print(f"Mapped element faces: {deck_summary.mapped_element_face_count}")
    print(f"Expected zero-DOF warning: {expected_zero_dof_warning}")
    print(f"Input deck: {input_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

"""Generate and verify the complete-joint contact smoke model."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
    write_complete_joint_contact_smoke_deck,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Run the governed CalculiX contact parser smoke test."""

    transfer = load_complete_joint_calculix_transfer_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_calculix_transfer.toml"
    )

    contact = load_complete_joint_contact_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_contact.toml"
    )

    mesh_path = (
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / transfer.mesh_id
        / "mesh"
        / transfer.source_mesh_name
    )

    mesh_data = read_grouped_complete_joint_mesh(
        mesh_path,
        transfer,
    )

    working_directory = (
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / contact.simulation_id
        / "contact_smoke"
        / transfer.mesh_level
    )

    working_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path = (
        working_directory
        / f"{contact.solver_job_name}.inp"
    )

    deck_summary = write_complete_joint_contact_smoke_deck(
        mesh_data,
        transfer,
        contact,
        input_path,
    )

    executable_path = (
        PROJECT_ROOT
        / transfer.executable_relative_path
    )

    if not executable_path.exists():
        raise FileNotFoundError(
            f"CalculiX executable not found: {executable_path}"
        )

    for suffix in (
        ".12d",
        ".cvg",
        ".dat",
        ".eig",
        ".frd",
        ".sta",
    ):
        stale_path = working_directory / (
            contact.solver_job_name + suffix
        )

        if stale_path.exists():
            stale_path.unlink()

    completed = subprocess.run(
        [
            str(executable_path),
            "-i",
            contact.solver_job_name,
        ],
        cwd=working_directory,
        capture_output=True,
        text=True,
        timeout=transfer.timeout_seconds,
        check=False,
    )

    stdout_path = working_directory / (
        contact.solver_job_name + ".stdout.log"
    )

    stderr_path = working_directory / (
        contact.solver_job_name + ".stderr.log"
    )

    stdout_path.write_text(
        completed.stdout,
        encoding="utf-8",
        errors="replace",
    )

    stderr_path.write_text(
        completed.stderr,
        encoding="utf-8",
        errors="replace",
    )

    diagnostics = (
        completed.stdout
        + "\n"
        + completed.stderr
    )

    dat_path = working_directory / (
        contact.solver_job_name + ".dat"
    )

    if dat_path.exists():
        diagnostics += (
            "\n"
            + dat_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        )

    output_sizes: dict[str, int] = {}

    for suffix in (".dat", ".frd", ".sta"):
        output_path = working_directory / (
            contact.solver_job_name + suffix
        )

        if not output_path.exists():
            raise RuntimeError(
                f"Expected CalculiX output is missing: "
                f"{output_path}"
            )

        output_size = output_path.stat().st_size

        if output_size <= 0:
            raise RuntimeError(
                f"CalculiX output is empty: {output_path}"
            )

        output_sizes[suffix] = output_size

    expected_zero_dof_warning = (
        "no degrees of freedom in the model"
        in diagnostics.lower()
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "CalculiX contact smoke run returned "
            f"{completed.returncode}."
        )

    if "*ERROR" in diagnostics.upper():
        raise RuntimeError(
            "CalculiX reported an input or contact error."
        )

    if not expected_zero_dof_warning:
        raise RuntimeError(
            "The expected fully constrained zero-DOF "
            "warning was not found."
        )

    generated_at = datetime.now(UTC).isoformat()

    manifest_path = (
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / contact.simulation_id
        / "metadata"
        / "complete_joint_contact_smoke.json"
    )

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest = {
        "generated_at_utc": generated_at,
        "contact_model_id": contact.contact_model_id,
        "simulation_id": contact.simulation_id,
        "mesh_id": contact.mesh_id,
        "solver_job_name": contact.solver_job_name,
        "mesh_level": transfer.mesh_level,
        "calculix_return_code": completed.returncode,
        "node_count": deck_summary.transfer.node_count,
        "element_count": deck_summary.transfer.element_count,
        "element_surface_count": (
            deck_summary.transfer.element_surface_count
        ),
        "mapped_element_face_count": (
            deck_summary.transfer.mapped_element_face_count
        ),
        "interaction_count": (
            deck_summary.interaction_count
        ),
        "contact_pair_count": (
            deck_summary.contact_pair_count
        ),
        "normal_stiffness_n_per_mm3": (
            deck_summary.normal_stiffness_n_per_mm3
        ),
        "friction_coefficient": (
            contact.friction_coefficient
        ),
        "friction_stick_slope_n_per_mm3": (
            deck_summary.friction_stick_slope_n_per_mm3
        ),
        "expected_zero_dof_warning": (
            expected_zero_dof_warning
        ),
        "output_sizes_bytes": output_sizes,
        "input_deck": str(input_path),
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
    }

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    report_path = (
        PROJECT_ROOT
        / "docs"
        / "verification"
        / (
            f"{contact.simulation_id}_"
            "COMPLETE_JOINT_CONTACT_SMOKE.md"
        )
    )

    report = f"""# Complete-Joint Contact Smoke Verification

## Identity

- Contact model: `{contact.contact_model_id}`
- Simulation: `{contact.simulation_id}`
- Mesh: `{contact.mesh_id}`
- Mesh level: `{transfer.mesh_level}`
- Solver job: `{contact.solver_job_name}`
- Generated UTC: `{generated_at}`

## Model content

- Nodes: {deck_summary.transfer.node_count}
- C3D4 elements: {deck_summary.transfer.element_count}
- Element surfaces: {
    deck_summary.transfer.element_surface_count
}
- Mapped element faces: {
    deck_summary.transfer.mapped_element_face_count
}
- Surface interactions: {deck_summary.interaction_count}
- Contact pairs: {deck_summary.contact_pair_count}

## Governed interaction

- Contact formulation: `{contact.contact_type}`
- Pressure-overclosure law: `{
    contact.pressure_overclosure
}`
- Normal stiffness: {
    deck_summary.normal_stiffness_n_per_mm3
:.6f} N/mm?
- Friction coefficient: {
    contact.friction_coefficient
:.6f}
- Friction stick slope: {
    deck_summary.friction_stick_slope_n_per_mm3
:.6f} N/mm?

## Contact pairs

"""

    for pair in contact.contact_pairs:
        report += (
            f"- `{pair.name}`: "
            f"`{pair.slave_surface}` ? "
            f"`{pair.master_surface}`\n"
        )

    report += f"""
## Solver verification

- CalculiX return code: {completed.returncode}
- `.dat` size: {output_sizes[".dat"]} bytes
- `.frd` size: {output_sizes[".frd"]} bytes
- `.sta` size: {output_sizes[".sta"]} bytes
- Expected zero-DOF warning found: {
    expected_zero_dof_warning
}
- CalculiX `*ERROR` detected: false

## Scope

This is a solver-read and contact-keyword smoke test.
All mesh nodes are constrained and no physical load is applied.
It verifies that CalculiX accepts the transferred surfaces,
interaction law, and four contact-pair definitions. It does not
constitute a converged physical contact solution.

## Verdict

**VERIFIED**
"""

    report_path.write_text(
        report,
        encoding="utf-8",
        newline="\n",
    )

    print("Complete-joint CalculiX contact smoke: VERIFIED")
    print(f"CalculiX return code: {completed.returncode}")
    print(
        f"Nodes: {deck_summary.transfer.node_count}"
    )
    print(
        f"C3D4 elements: "
        f"{deck_summary.transfer.element_count}"
    )
    print(
        f"Element surfaces: "
        f"{deck_summary.transfer.element_surface_count}"
    )
    print(
        f"Contact interactions: "
        f"{deck_summary.interaction_count}"
    )
    print(
        f"Contact pairs: "
        f"{deck_summary.contact_pair_count}"
    )
    print(
        f"Expected zero-DOF warning: "
        f"{expected_zero_dof_warning}"
    )
    print(f"Input deck: {input_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

"""Regression tests for restart-safe Phase-3 calibration decks."""

from __future__ import annotations

from pathlib import Path

import pytest

from threadrom.case.reference_cases import phase2_certification_case
from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_case_definition_bundle import (
    build_generic_fem_definition_bundle,
)
from threadrom.factory.fem_preload_calibration_deck import (
    BOLT_THERMAL_SET,
    write_fem_preload_calibration_trial_deck,
)
from threadrom.factory.fem_profile import (
    PHASE2_CERTIFIED_FEM_PROFILE,
    PHASE3_CP8_EXECUTION_RESILIENCE,
)
from threadrom.factory.preload_calibration_campaign import (
    derive_initial_preload_calibration_trial,
)
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
from threadrom.solver.complete_joint_pretension_restart import (
    prepare_pretension_restart_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _real_bundle_and_mesh():
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
    boundary = load_complete_joint_boundary_region_definition(
        PROJECT_ROOT
        / "config"
        / "complete_joint_boundary_regions.toml"
    )

    resolved = resolve_case(
        phase2_certification_case()
    )

    bundle = build_generic_fem_definition_bundle(
        resolved,
        mesh_id=transfer.mesh_id,
        geometry_id=transfer.geometry_id,
        classification_id=(
            "phase3-restart-regression"
        ),
        source_mesh_name=transfer.source_mesh_name,
        transfer_template=transfer,
        contact_template=contact,
        boundary_template=boundary,
    )

    mesh_path = (
        PROJECT_ROOT
        / "simulations"
        / "staging"
        / transfer.mesh_id
        / "mesh"
        / transfer.source_mesh_name
    )

    if not mesh_path.is_file():
        pytest.skip(
            "Certified grouped mesh is not available."
        )

    mesh = read_grouped_complete_joint_mesh(
        mesh_path,
        bundle.transfer,
    )

    return bundle, mesh


def _bolt_temperatures(text: str) -> tuple[float, ...]:
    lines = text.splitlines()
    values: list[float] = []

    for index, line in enumerate(lines):
        if line.strip().upper() != "*TEMPERATURE":
            continue

        if index + 1 >= len(lines):
            raise AssertionError(
                "*TEMPERATURE has no data row."
            )

        row = lines[index + 1]
        name, value = (
            item.strip()
            for item in row.split(",", maxsplit=1)
        )

        assert name == BOLT_THERMAL_SET
        values.append(float(value))

    return tuple(values)


def test_cp8_execution_resilience_policy_is_separate_from_backend():
    backend = PHASE2_CERTIFIED_FEM_PROFILE.backend
    resilience = PHASE3_CP8_EXECUTION_RESILIENCE

    # Certified physics identity remains untouched.
    assert backend.policy_id == "phase2_complete_joint_c3d4_v1"
    assert backend.step.maximum_increments == 100
    assert backend.step.initial_increment == pytest.approx(0.05)
    assert backend.step.total_time == pytest.approx(1.0)
    assert backend.step.minimum_increment == pytest.approx(1.0e-6)
    assert backend.step.maximum_increment == pytest.approx(0.05)

    # Restart resilience is governed independently.

    assert resilience.checkpoint_count == 20
    assert resilience.write_enabled
    assert resilience.write_frequency_steps == 1
    assert resilience.overlay_latest is False
    assert resilience.preserve_total_pseudo_time
    assert resilience.policy_id == (
        "phase3_cp8_thermal_calibration_restart_v2_windows_nonoverlay"
    )

    assert resilience.checkpoint_fractions == pytest.approx(
        tuple(index / 20 for index in range(1, 21))
    )


def test_real_calibration_deck_is_restart_safe(
    tmp_path: Path,
) -> None:
    bundle, mesh = _real_bundle_and_mesh()

    trial = derive_initial_preload_calibration_trial(
        seed=bundle.calibration_seed,
        case_run_id=bundle.preparation.identity.run_id,
    )

    input_path = tmp_path / "restart_safe_calibration.inp"

    result = write_fem_preload_calibration_trial_deck(
        mesh_data=mesh,
        bundle=bundle,
        trial=trial,
        reference_temperature_c=20.0,
        input_path=input_path,
    )

    text = input_path.read_text(
        encoding="utf-8",
    )

    resilience = PHASE3_CP8_EXECUTION_RESILIENCE
    backend = PHASE2_CERTIFIED_FEM_PROFILE.backend

    # --------------------------------------------------------
    # Deck topology / restart contract
    # --------------------------------------------------------

    assert text.count("*STEP,") == 20
    assert text.count("*END STEP") == 20

    assert (
        text.count(
            "*RESTART,WRITE,FREQUENCY=1"
        )
        == 1
    )

    for checkpoint in range(1, 21):
        fraction = checkpoint / 20

        assert (
            f"** Step {checkpoint}: "
            f"preload checkpoint {fraction:.6f}"
            in text
        )

    # --------------------------------------------------------
    # Timing equivalence
    # --------------------------------------------------------

    expected_step_time = (
        backend.step.total_time
        / resilience.checkpoint_count
    )

    assert expected_step_time == pytest.approx(0.05)
    assert result.checkpoint_step_time == pytest.approx(
        expected_step_time
    )

    assert (
        result.checkpoint_step_time
        * result.checkpoint_count
        == pytest.approx(
            backend.step.total_time
        )
    )

    static_row = (
        "5.000000000000e-02, "
        "5.000000000000e-02, "
        "1.000000000000e-06, "
        "5.000000000000e-02"
    )

    assert text.count(static_row) == 20

    # --------------------------------------------------------
    # Thermal path equivalence
    # --------------------------------------------------------

    temperatures = _bolt_temperatures(text)

    assert len(temperatures) == 20

    expected_temperatures = tuple(
        20.0
        + trial.delta_temperature_c
        * checkpoint
        / 20
        for checkpoint in range(1, 21)
    )

    assert temperatures == pytest.approx(
        expected_temperatures,
        abs=1.0e-9,
    )

    # Final checkpoint must preserve the original governed
    # thermal actuator exactly.
    assert temperatures[-1] == pytest.approx(
        20.0 + trial.delta_temperature_c,
        abs=1.0e-9,
    )

    assert result.delta_temperature_c == pytest.approx(
        trial.delta_temperature_c
    )

    assert result.applied_bolt_temperature_c == pytest.approx(
        temperatures[-1],
        abs=1.0e-9,
    )

    # --------------------------------------------------------
    # Result provenance
    # --------------------------------------------------------

    assert result.checkpoint_count == 20
    assert result.restart_write_count == 1
    assert (
        result.execution_resilience_policy_id
        == resilience.policy_id
    )

    # --------------------------------------------------------
    # Existing restart engine must understand the generated
    # thermal deck without a second restart implementation.
    # --------------------------------------------------------

    sta_path = tmp_path / "interrupted.sta"
    rout_path = tmp_path / "interrupted.rout"

    sta_lines = []

    for step_index in range(1, 8):
        total_time = step_index * 0.05

        sta_lines.append(
            (
                f"{step_index} 1 1 4 "
                f"{total_time:.12e} "
                "5.000000000000e-02 "
                "5.000000000000e-02"
            )
        )

    sta_path.write_text(
        "\n".join(sta_lines) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    rout_path.write_bytes(
        b"synthetic-restart-payload"
    )

    restart_directory = (
        tmp_path / "restart_bundle"
    )

    summary = prepare_pretension_restart_bundle(
        original_input_path=input_path,
        sta_path=sta_path,
        restart_output_path=rout_path,
        output_directory=restart_directory,
        continuation_job_name="thermal_resume_s08",
        checkpoint_count=20,
        configured_step_time=0.05,
        restart_write_frequency_steps=1,
        overlay_latest=False,
    )

    assert summary.completed_checkpoint == 7
    assert summary.next_checkpoint == 8
    assert summary.remaining_checkpoint_count == 13

    continuation = (
        summary.continuation_input_path.read_text(
            encoding="utf-8"
        )
    )

    assert continuation.startswith("*RESTART,READ\n")

    assert "** Step 7:" not in continuation
    assert "** Step 8:" in continuation
    assert "** Step 20:" in continuation

    assert (
        continuation.count(
            "*RESTART,WRITE,FREQUENCY=1"
        )
        == 1
    )

    assert (
        summary.restart_input_path.read_bytes()
        == b"synthetic-restart-payload"
    )

from __future__ import annotations

import argparse
import json
import math
import tomllib

from dataclasses import replace
from pathlib import Path

from threadrom.case.resolver import resolve_case

from threadrom.factory.pilot_doe import (
    PilotDoeCaseId,
    build_phase3_cp7_pilot_doe,
)

from threadrom.factory.preload_calibration_seed import (
    derive_analytical_thermal_preload_seed,
)

from threadrom.factory.fem_calibration_knowledge import (
    FemWarmStartSource,
    build_fem_calibration_knowledge_record,
    load_fem_warm_start_policy,
    predict_fem_warm_start,
)

from threadrom.factory.preload_calibration_campaign import (
    derive_fem_warm_start_preload_calibration_trial,
)

from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)
from threadrom.factory.preload_calibration_campaign import (
    evaluate_preload_calibration_trial,
)

import threadrom.factory.fem_case_definition_bundle as bundle_mod

from threadrom.factory.fem_case_definition_bundle import (
    build_generic_fem_definition_bundle,
)

from threadrom.factory.fem_preload_calibration_deck import (
    write_fem_preload_calibration_trial_deck,
)

from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
)

from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)

from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
)

from threadrom.solver.complete_joint_boundary_regions import (
    load_complete_joint_boundary_region_definition,
)

from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
)

from threadrom.factory.fem_solver_orchestrator import (
    orchestrate_calculix_run,
)


ROOT = Path(r"D:\ThreadROM")

ARTIFACT_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp8_overnight"
)

BASELINE_MESH = (
    ROOT
    / "simulations"
    / "staging"
    / "TRM-MSH-000005"
    / "mesh"
    / "complete_joint_grouped_medium_first_order.msh"
)


def pilot(case_id: PilotDoeCaseId):
    campaign = build_phase3_cp7_pilot_doe()

    item = next(
        item
        for item in campaign.cases
        if item.case_id is case_id
    )

    resolved = resolve_case(
        item.case
    )

    seed = derive_analytical_thermal_preload_seed(
        resolved
    )

    return item, resolved, seed


def reference_temperature() -> float:
    path = (
        ROOT
        / "config"
        / "complete_joint_preload.toml"
    )

    with path.open("rb") as stream:
        data = tomllib.load(stream)

    matches: list[float] = []

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "reference_temperature_c":
                    matches.append(float(child))
                else:
                    walk(child)

        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)

    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one governed "
            "reference_temperature_c in "
            "complete_joint_preload.toml; "
            f"found {len(matches)}."
        )

    value = matches[0]

    if not math.isfinite(value):
        raise RuntimeError(
            "Governed reference temperature is not finite."
        )

    return value


def strict_geometry_reuse_gate(
    baseline,
    target,
) -> None:
    """Allow reuse only when loading is the sole case difference."""

    normalized_target = replace(
        target.source_case,
        loading=baseline.source_case.loading,
    )

    if normalized_target != baseline.source_case:
        raise RuntimeError(
            "GEOMETRY REUSE BLOCKED: target case differs "
            "from baseline in fields other than loading."
        )

    # Additional resolved-assembly check.
    left = baseline.assembly
    right = target.assembly

    names = (
        "bolt_length_mm",
        "pitch_mm",
        "upper_member_thickness_mm",
        "lower_member_thickness_mm",
        "total_grip_length_mm",
        "nut_thickness_mm",
        "thread_engagement_length_mm",
        "protrusion_length_mm",
        "clearance_hole_diameter_mm",
        "outer_diameter_mm",
    )

    for name in names:
        if getattr(left, name) != getattr(right, name):
            raise RuntimeError(
                "GEOMETRY REUSE BLOCKED: "
                f"assembly field {name!r} differs."
            )


def knowledge_base():
    _, p00, p00_seed = pilot(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    _, p03, p03_seed = pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    # Certified Phase-2 FEM evidence.
    p00_record = (
        build_fem_calibration_knowledge_record(
            resolved=p00,
            seed=p00_seed,
            accepted_run_id=(
                "trm_sim_000004_run_a2_thermal_20kn"
            ),
            accepted_delta_temperature_c=-243.2744971,
            measured_mean_clamp_force_n=20063.5,
        )
    )

    # Accepted CP7 P03 FEM evidence.
    p03_record = (
        build_fem_calibration_knowledge_record(
            resolved=p03,
            seed=p03_seed,
            accepted_run_id=(
                "trm_fem_30059c410f5c_cal_02"
            ),
            accepted_delta_temperature_c=(
                -263.562942251128
            ),
            measured_mean_clamp_force_n=(
                19820.576667
            ),
        )
    )

    return (
        p00_record,
        p03_record,
    )


def prepare(
    case_id: PilotDoeCaseId,
    trial_index: int = 1,
):
    if case_id not in (
        PilotDoeCaseId.PRELOAD_LOW,
        PilotDoeCaseId.PRELOAD_HIGH,
    ):
        raise RuntimeError(
            "Tonight's governed launch permits only P01/P02."
        )

    _, baseline, _ = pilot(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    item, resolved, seed = pilot(
        case_id
    )

    strict_geometry_reuse_gate(
        baseline,
        resolved,
    )

    if (
        not BASELINE_MESH.exists()
        or BASELINE_MESH.stat().st_size <= 0
    ):
        raise FileNotFoundError(
            f"Certified baseline mesh not found: "
            f"{BASELINE_MESH}"
        )

    policy = load_fem_warm_start_policy(
        ROOT
        / "config"
        / "fem_calibration_warm_start.toml"
    )

    prediction = predict_fem_warm_start(
        resolved=resolved,
        seed=seed,
        knowledge=knowledge_base(),
        policy=policy,
    )

    if (
        prediction.source
        is not FemWarmStartSource.FEM_NEIGHBORS
    ):
        raise RuntimeError(
            "Overnight launch requires a FEM-neighbor warm start."
        )

    trial1 = (
        derive_fem_warm_start_preload_calibration_trial(
            predicted_delta_temperature_c=(
                prediction.predicted_delta_temperature_c
            ),
            case_run_id=(
                f"trm_fem_{resolved.case_hash[:12]}"
            ),
        )
    )

    transfer_template = (
        load_complete_joint_calculix_transfer_definition(
            ROOT
            / "config"
            / "complete_joint_calculix_transfer.toml"
        )
    )

    contact_template = (
        load_complete_joint_contact_definition(
            ROOT
            / "config"
            / "complete_joint_contact.toml"
        )
    )

    preload_template = (
        load_complete_joint_preload_definition(
            ROOT
            / "config"
            / "complete_joint_preload.toml"
        )
    )

    boundary_template = (
        load_complete_joint_boundary_region_definition(
            ROOT
            / "config"
            / "complete_joint_boundary_regions.toml"
        )
    )

    token = resolved.case_hash[:16]

    bundle = build_generic_fem_definition_bundle(
        resolved,
        mesh_id=f"mesh-reuse-{token}",
        geometry_id=f"geometry-reuse-{token}",
        classification_id=f"classification-reuse-{token}",
        source_mesh_name=BASELINE_MESH.name,
        transfer_template=transfer_template,
        contact_template=contact_template,
        boundary_template=boundary_template,
    )

    if (
        bundle.calibration_seed.target_force_n
        != resolved.source_case.loading.target_preload_n
    ):
        raise RuntimeError(
            "Case preload did not propagate into FEM bundle."
        )

    mesh_data = read_grouped_complete_joint_mesh(
        BASELINE_MESH,
        bundle.transfer,
    )

    previous_mean_force_n = None
    previous_target_relative_error = None
    previous_trial_run_id = None

    target_relative_tolerance = (
        preload_template.target_relative_tolerance
    )

    spread_relative_tolerance = (
        preload_template.interface_spread_relative_tolerance
    )

    if trial_index == 1:
        trial = trial1

    elif trial_index in (2, 3):
        trial1_run_dir = (
            ARTIFACT_ROOT
            / bundle.preparation.identity.run_id
            / trial1.run_id
        )

        trial1_extraction = (
            extract_clamp_force_measurement_from_dat(
                dat_path=(
                    trial1_run_dir
                    / f"{trial1.run_id}.dat"
                ),
                contact_pairs=contact_template.contact_pairs,
            )
        )

        trial1_evaluation = evaluate_preload_calibration_trial(
            case_run_id=(
                f"trm_fem_{resolved.case_hash[:12]}"
            ),
            target_force_n=(
                resolved.source_case.loading.target_preload_n
            ),
            target_relative_tolerance=(
                target_relative_tolerance
            ),
            spread_relative_tolerance=(
                spread_relative_tolerance
            ),
            current_trial=trial1,
            measurement=trial1_extraction.measurement,
        )

        if trial1_evaluation.accepted:
            raise RuntimeError(
                "Trial 1 is already accepted; continuation is forbidden."
            )

        if trial1_evaluation.next_trial is None:
            raise RuntimeError(
                "Calibration campaign did not derive Trial 2."
            )

        trial2 = trial1_evaluation.next_trial

        if trial2.trial_index != 2:
            raise RuntimeError(
                "Expected governed calibration Trial 2."
            )

        if trial_index == 2:
            trial = trial2

            previous_trial_run_id = trial1.run_id
            previous_mean_force_n = (
                trial1_extraction.measurement.mean_force_n
            )
            previous_target_relative_error = (
                trial1_evaluation.decision.target_relative_error
            )

        else:
            trial2_run_dir = (
                ARTIFACT_ROOT
                / bundle.preparation.identity.run_id
                / trial2.run_id
            )

            trial2_extraction = (
                extract_clamp_force_measurement_from_dat(
                    dat_path=(
                        trial2_run_dir
                        / f"{trial2.run_id}.dat"
                    ),
                    contact_pairs=contact_template.contact_pairs,
                )
            )

            trial2_evaluation = evaluate_preload_calibration_trial(
                case_run_id=(
                    f"trm_fem_{resolved.case_hash[:12]}"
                ),
                target_force_n=(
                    resolved.source_case.loading.target_preload_n
                ),
                target_relative_tolerance=(
                    target_relative_tolerance
                ),
                spread_relative_tolerance=(
                    spread_relative_tolerance
                ),
                current_trial=trial2,
                measurement=trial2_extraction.measurement,
                previous_trial=trial1,
                previous_measurement=(
                    trial1_extraction.measurement
                ),
            )

            if trial2_evaluation.accepted:
                raise RuntimeError(
                    "Trial 2 is already accepted; Trial 3 is forbidden."
                )

            if trial2_evaluation.next_trial is None:
                raise RuntimeError(
                    "Calibration campaign did not derive Trial 3."
                )

            if trial2_evaluation.next_trial.trial_index != 3:
                raise RuntimeError(
                    "Expected governed calibration Trial 3."
                )

            trial = trial2_evaluation.next_trial

            previous_trial_run_id = trial2.run_id
            previous_mean_force_n = (
                trial2_extraction.measurement.mean_force_n
            )
            previous_target_relative_error = (
                trial2_evaluation.decision.target_relative_error
            )

    else:
        raise ValueError(
            "CP8 launcher currently supports trial_index 1, 2 or 3."
        )

    run_dir = (
        ARTIFACT_ROOT
        / bundle.preparation.identity.run_id
        / trial.run_id
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path = (
        run_dir
        / f"{trial.run_id}.inp"
    )

    deck = write_fem_preload_calibration_trial_deck(
        mesh_data=mesh_data,
        bundle=bundle,
        trial=trial,
        reference_temperature_c=(
            reference_temperature()
        ),
        input_path=input_path,
    )

    if (
        not input_path.exists()
        or input_path.stat().st_size <= 0
    ):
        raise RuntimeError(
            "Generated CalculiX deck is missing or empty."
        )

    if deck.trial_run_id != trial.run_id:
        raise RuntimeError(
            "Deck/trial run identity mismatch."
        )

    if not math.isclose(
        deck.delta_temperature_c,
        trial.delta_temperature_c,
        rel_tol=0.0,
        abs_tol=1.0e-10,
    ):
        raise RuntimeError(
            "Deck/trial temperature mismatch."
        )

    preflight = {
        "case_id": case_id.value,
        "case_hash": resolved.case_hash,
        "purpose": item.purpose,
        "target_preload_n": (
            resolved.source_case.loading.target_preload_n
        ),
        "geometry_reuse_gate": "PASS",
        "reused_mesh": str(
            BASELINE_MESH.relative_to(ROOT)
        ),
        "warm_start_policy_id": prediction.policy_id,
        "warm_start_source": prediction.source.value,
        "analytical_delta_temperature_c": (
            prediction.analytical_delta_temperature_c
        ),
        "predicted_delta_temperature_c": (
            prediction.predicted_delta_temperature_c
        ),
        "correction_factor": (
            prediction.correction_factor
        ),
        "neighbors_used": (
            prediction.reused_evidence_count
        ),
        "neighbor_case_hashes": (
            prediction.neighbor_case_hashes
        ),
        "nearest_distance": prediction.nearest_distance,
        "trial_run_id": trial.run_id,
        "trial_index": trial.trial_index,
        "trial_source": trial.source.value,
        "trial_delta_temperature_c": (
            trial.delta_temperature_c
        ),
        "previous_trial_run_id": (
            previous_trial_run_id
        ),
        "previous_mean_force_n": (
            previous_mean_force_n
        ),
        "previous_target_relative_error": (
            previous_target_relative_error
        ),
        "deck_sha256": deck.sha256,
        "deck_size_bytes": deck.size_bytes,
        "input_path": str(
            input_path.relative_to(ROOT)
        ),
        "node_count": deck.node_count,
        "element_count": deck.element_count,
        "status": "PASS",
    }

    preflight_path = (
        run_dir
        / "cp8_launch_preflight.json"
    )

    preflight_path.write_text(
        json.dumps(
            preflight,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return (
        resolved,
        bundle,
        trial,
        prediction,
        deck,
        input_path,
        run_dir,
        preflight_path,
    )


def run(
    case_id: PilotDoeCaseId,
    trial_index: int = 1,
) -> int:
    (
        resolved,
        bundle,
        trial,
        prediction,
        deck,
        input_path,
        run_dir,
        preflight_path,
    ) = prepare(
        case_id,
        trial_index=trial_index,
    )

    backend = (
        bundle_mod
        .PHASE2_CERTIFIED_FEM_PROFILE
        .backend
    )

    definition = CalculixJobDefinition(
        executable_relative_path=(
            bundle.transfer.executable_relative_path
        ),
        job_name=trial.run_id,
        timeout_seconds=(
            bundle.transfer.timeout_seconds
        ),
    )

    print(
        "=== CP8 OVERNIGHT RUN START ===",
        flush=True,
    )
    print(
        "Case        :", case_id.value,
        flush=True,
    )
    print(
        "Target N    :",
        resolved.source_case.loading.target_preload_n,
        flush=True,
    )
    print(
        "Trial dT C  :",
        trial.delta_temperature_c,
        flush=True,
    )
    print(
        "Run ID      :", trial.run_id,
        flush=True,
    )
    print(
        "Deck SHA256 :", deck.sha256,
        flush=True,
    )
    print(
        "Preflight   :", preflight_path,
        flush=True,
    )

    result = orchestrate_calculix_run(
        project_root=ROOT,
        input_path=input_path,
        definition=definition,
        run_id=trial.run_id,
        case_hash=resolved.case_hash,
        backend_policy_id=backend.policy_id,
        solver_name=backend.solver_name,
        solver_version=backend.solver_version,
        manifest_path=(
            run_dir
            / "fem_run_manifest.json"
        ),
    )

    print()
    print(
        "=== CP8 OVERNIGHT RUN FINISHED ===",
        flush=True,
    )
    print(
        "Case       :", case_id.value,
        flush=True,
    )
    print(
        "Disposition:",
        result.manifest.disposition,
        flush=True,
    )
    print(
        "Manifest   :",
        result.manifest_path,
        flush=True,
    )

    return 0


def parse_case(value: str) -> PilotDoeCaseId:
    for item in PilotDoeCaseId:
        if (
            value == item.name
            or value == item.value
        ):
            return item

    raise ValueError(
        f"Unknown Pilot DOE case: {value}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--case",
        required=True,
    )

    parser.add_argument(
        "--prepare-only",
        action="store_true",
    )

    parser.add_argument(
        "--trial-index",
        type=int,
        choices=(1, 2, 3),
        default=1,
    )

    args = parser.parse_args()

    case_id = parse_case(
        args.case
    )

    if args.prepare_only:
        (
            resolved,
            bundle,
            trial,
            prediction,
            deck,
            input_path,
            run_dir,
            preflight_path,
        ) = prepare(
            case_id,
            trial_index=args.trial_index,
        )

        print()
        print(
            "=== CP8 OVERNIGHT PREPARED ==="
        )
        print("Case       :", case_id.value)
        print(
            "Target N   :",
            resolved.source_case.loading.target_preload_n,
        )
        print(
            "Trial dT C :",
            trial.delta_temperature_c,
        )
        print("Run ID     :", trial.run_id)
        print("Deck       :", input_path)
        print("Deck SHA   :", deck.sha256)
        print("Preflight  :", preflight_path)
        print("STATUS     : PASS")

        return 0

    return run(
        case_id,
        trial_index=args.trial_index,
    )


if __name__ == "__main__":
    raise SystemExit(main())

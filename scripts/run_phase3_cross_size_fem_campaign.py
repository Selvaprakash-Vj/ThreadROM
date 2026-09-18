from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import threadrom.factory.fem_case_definition_bundle as bundle_mod

from threadrom.case.resolver import resolve_case

from threadrom.factory.cross_size_fem_sentinel import (
    build_phase3_cross_size_fem_sentinels,
)

from threadrom.factory.fem_preload_calibration_deck import (
    write_fem_preload_calibration_trial_deck,
)

from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)

from threadrom.factory.fem_solver_orchestrator import (
    orchestrate_calculix_run,
)

from threadrom.factory.preload_calibration_campaign import (
    derive_initial_preload_calibration_trial,
    evaluate_preload_calibration_trial,
)

from threadrom.factory.preload_calibration_controller import (
    PreloadCalibrationDisposition,
)

from threadrom.solver.calculix_job import (
    CalculixJobDefinition,
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

from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
)


ROOT = Path(r"D:\ThreadROM")
CONFIG = ROOT / "config"

CAMPAIGN_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp11_cross_size_fem_campaign"
)

PREPARATION_ROOTS = {
    "TRM-XFEM-M8-001": (
        ROOT
        / "simulations"
        / "staging"
        / "phase3_cp11_m8_two_pitch_nut022_final"
        / "prepared_cases"
    ),
    "TRM-XFEM-M12-001": (
        ROOT
        / "simulations"
        / "staging"
        / "phase3_cp11_m12_two_pitch_nut022_proof"
        / "prepared_cases"
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def recursive_values(
    obj: Any,
    field_name: str,
    *,
    _seen: set[int] | None = None,
) -> list[Any]:
    if _seen is None:
        _seen = set()

    oid = id(obj)

    if oid in _seen:
        return []

    _seen.add(oid)

    result: list[Any] = []

    if dataclasses.is_dataclass(obj):
        for field in dataclasses.fields(obj):
            value = getattr(
                obj,
                field.name,
            )

            if field.name == field_name:
                result.append(value)

            result.extend(
                recursive_values(
                    value,
                    field_name,
                    _seen=_seen,
                )
            )

    elif isinstance(obj, dict):
        for key, value in obj.items():
            if key == field_name:
                result.append(value)

            result.extend(
                recursive_values(
                    value,
                    field_name,
                    _seen=_seen,
                )
            )

    elif isinstance(
        obj,
        (tuple, list),
    ):
        for value in obj:
            result.extend(
                recursive_values(
                    value,
                    field_name,
                    _seen=_seen,
                )
            )

    return result


def unique_numeric(
    obj: Any,
    field_name: str,
) -> float:
    values = [
        float(value)
        for value in recursive_values(
            obj,
            field_name,
        )
        if isinstance(
            value,
            (int, float),
        )
        and not isinstance(value, bool)
    ]

    unique = []

    for value in values:
        if not any(
            math.isclose(
                value,
                other,
                rel_tol=0.0,
                abs_tol=1.0e-12,
            )
            for other in unique
        ):
            unique.append(value)

    if len(unique) != 1:
        raise RuntimeError(
            f"Expected exactly one governed value for "
            f"{field_name!r}; found {unique!r}."
        )

    return unique[0]


def load_preload_template():
    preferred = (
        CONFIG
        / "complete_joint_preload.toml"
    )

    if preferred.is_file():
        return (
            preferred,
            load_complete_joint_preload_definition(
                preferred
            ),
        )

    successes = []

    for path in sorted(
        CONFIG.glob("*.toml")
    ):
        if (
            "preload" not in path.name.lower()
            or "pretension" in path.name.lower()
        ):
            continue

        try:
            obj = (
                load_complete_joint_preload_definition(
                    path
                )
            )
        except Exception:
            continue

        successes.append(
            (path, obj)
        )

    if len(successes) != 1:
        raise RuntimeError(
            "Unable to uniquely identify governed "
            "complete-joint preload config. "
            f"Candidates: {[p.name for p, _ in successes]}"
        )

    return successes[0]


def find_preparation_record(
    sentinel_id: str,
) -> tuple[Path, dict[str, Any]]:
    root = PREPARATION_ROOTS[
        sentinel_id
    ]

    paths = tuple(
        root.glob(
            "*/cross_size_fem_sentinel_preparation_record.json"
        )
    )

    matches = []

    for path in paths:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if (
            payload.get("sentinel_id")
            == sentinel_id
            and payload.get(
                "overall_disposition"
            )
            == "CROSS_SIZE_SENTINEL_PREPARED"
        ):
            matches.append(
                (path, payload)
            )

    if len(matches) != 1:
        raise RuntimeError(
            f"{sentinel_id}: expected exactly one "
            f"authoritative PASS preparation record; "
            f"found {len(matches)}."
        )

    return matches[0]


def verify_preparation(
    *,
    sentinel,
    resolved,
    preparation,
    record_path: Path,
    record: dict[str, Any],
) -> Path:
    if record["case_hash"] != resolved.case_hash:
        raise RuntimeError(
            f"{sentinel.definition.sentinel_id}: "
            "case hash mismatch."
        )

    if (
        record["run_id"]
        != preparation.identity.run_id
    ):
        raise RuntimeError(
            f"{sentinel.definition.sentinel_id}: "
            "run identity mismatch."
        )

    gates = record["gates"]

    required_pass = (
        "case_resolution",
        "geometry_validation",
        "step_round_trip_validation",
        "grouped_mesh_generation",
        "mesh_quality_validation",
    )

    for gate in required_pass:
        if gates.get(gate) != "PASS":
            raise RuntimeError(
                f"{sentinel.definition.sentinel_id}: "
                f"{gate} is not PASS."
            )

    if (
        gates.get("calculix_invoked") is not False
        or gates.get("holdouts_accessed") is not False
        or gates.get(
            "capability_upgrade_performed"
        )
        is not False
    ):
        raise RuntimeError(
            f"{sentinel.definition.sentinel_id}: "
            "preparation provenance is not clean."
        )

    mesh_info = record["mesh"]

    mesh_path = (
        ROOT
        / mesh_info["msh_path"]
    )

    if (
        not mesh_path.is_file()
        or mesh_path.stat().st_size <= 0
    ):
        raise RuntimeError(
            f"{sentinel.definition.sentinel_id}: "
            f"mesh missing: {mesh_path}"
        )

    actual_hash = sha256(
        mesh_path
    )

    if (
        actual_hash
        != mesh_info["msh_sha256"]
    ):
        raise RuntimeError(
            f"{sentinel.definition.sentinel_id}: "
            "certified mesh SHA-256 drift."
        )

    if (
        int(mesh_info["degenerate_count"])
        != 0
        or float(
            mesh_info[
                "minimum_mean_ratio"
            ]
        )
        < 0.05
        or float(
            mesh_info[
                "maximum_edge_ratio"
            ]
        )
        > 50.0
        or bool(
            mesh_info[
                "mixed_orientation"
            ]
        )
    ):
        raise RuntimeError(
            f"{sentinel.definition.sentinel_id}: "
            "recorded governed mesh-quality "
            "evidence is not acceptable."
        )

    target_from_record = float(
        record["physics"][
            "target_preload_n"
        ]
    )

    if not math.isclose(
        target_from_record,
        sentinel.target_preload_n,
        rel_tol=1.0e-12,
        abs_tol=1.0e-8,
    ):
        raise RuntimeError(
            f"{sentinel.definition.sentinel_id}: "
            "target preload drift."
        )

    return mesh_path


def make_bundle(
    *,
    sentinel,
    resolved,
    preparation,
    record,
    mesh_path: Path,
    transfer_template,
    contact_template,
    boundary_template,
):
    mesh_sha = (
        record["mesh"]["msh_sha256"]
    )

    step_sha = (
        record["geometry"]["step_sha256"]
    )

    # Provenance identities are derived from immutable
    # evidence rather than hand-entered node/element IDs.
    mesh_id = (
        "xfem_mesh_"
        + mesh_sha[:16]
    )

    geometry_id = (
        "xfem_geometry_"
        + step_sha[:16]
    )

    classification_id = (
        "xfem_classification_"
        + resolved.case_hash[:16]
    )

    bundle = (
        bundle_mod
        .build_generic_fem_definition_bundle(
            resolved,
            mesh_id=mesh_id,
            geometry_id=geometry_id,
            classification_id=(
                classification_id
            ),
            source_mesh_name=(
                mesh_path.name
            ),
            transfer_template=(
                transfer_template
            ),
            contact_template=(
                contact_template
            ),
            boundary_template=(
                boundary_template
            ),
        )
    )

    if (
        bundle.preparation.identity.run_id
        != preparation.identity.run_id
    ):
        raise RuntimeError(
            f"{sentinel.definition.sentinel_id}: "
            "bundle/preparation run-ID mismatch."
        )

    return bundle


def reject_existing_solver_evidence(
    run_dir: Path,
    trial_run_id: str,
) -> None:
    manifest = (
        run_dir
        / "fem_run_manifest.json"
    )

    if manifest.exists():
        raise RuntimeError(
            f"Authoritative manifest already exists "
            f"for {trial_run_id}. Refusing duplicate FEM."
        )

    solver_suffixes = (
        ".dat",
        ".frd",
        ".sta",
        ".cvg",
        ".rout",
        ".12d",
        ".eig",
    )

    existing = [
        run_dir
        / f"{trial_run_id}{suffix}"
        for suffix in solver_suffixes
        if (
            run_dir
            / f"{trial_run_id}{suffix}"
        ).exists()
    ]

    if existing:
        raise RuntimeError(
            f"Solver evidence exists without a fresh "
            f"campaign manifest for {trial_run_id}: "
            + ", ".join(
                str(path)
                for path in existing
            )
        )


def prepare_trial_deck(
    state,
):
    trial = state["current_trial"]

    run_dir = (
        CAMPAIGN_ROOT
        / state["case_run_id"]
        / trial.run_id
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    reject_existing_solver_evidence(
        run_dir,
        trial.run_id,
    )

    input_path = (
        run_dir
        / f"{trial.run_id}.inp"
    )

    old_hash = (
        sha256(input_path)
        if input_path.exists()
        else None
    )

    deck = (
        write_fem_preload_calibration_trial_deck(
            mesh_data=state["mesh_data"],
            bundle=state["bundle"],
            trial=trial,
            reference_temperature_c=(
                state[
                    "reference_temperature_c"
                ]
            ),
            input_path=input_path,
            backend=state["backend"],
        )
    )

    if (
        not input_path.is_file()
        or input_path.stat().st_size <= 0
    ):
        raise RuntimeError(
            f"{trial.run_id}: generated deck "
            "is missing or empty."
        )

    actual_hash = sha256(
        input_path
    )

    if (
        hasattr(deck, "sha256")
        and actual_hash != deck.sha256
    ):
        raise RuntimeError(
            f"{trial.run_id}: deck SHA mismatch."
        )

    if (
        old_hash is not None
        and old_hash != actual_hash
    ):
        raise RuntimeError(
            f"{trial.run_id}: deterministic deck "
            "regeneration changed SHA-256."
        )

    manifest_path = (
        run_dir
        / "fem_run_manifest.json"
    )

    return {
        "run_dir": run_dir,
        "input_path": input_path,
        "manifest_path": manifest_path,
        "deck_sha256": actual_hash,
    }


def execute_trial(
    state,
):
    trial = state["current_trial"]

    prepared = prepare_trial_deck(
        state
    )

    definition = CalculixJobDefinition(
        executable_relative_path=(
            state["bundle"]
            .transfer
            .executable_relative_path
        ),
        job_name=trial.run_id,
        timeout_seconds=None,
    )

    print(
        f"\n[{state['sentinel_id']}] "
        f"LAUNCH Trial {trial.trial_index}"
    )
    print(
        f"[{state['sentinel_id']}] "
        f"dT = {trial.delta_temperature_c:.9f} C"
    )
    print(
        f"[{state['sentinel_id']}] "
        f"target = {state['target_force_n']:.6f} N"
    )
    print(
        f"[{state['sentinel_id']}] "
        "timeout = NONE"
    )
    print(
        f"[{state['sentinel_id']}] "
        f"run = {trial.run_id}",
        flush=True,
    )

    result = orchestrate_calculix_run(
        project_root=ROOT,
        input_path=prepared[
            "input_path"
        ],
        definition=definition,
        run_id=trial.run_id,
        case_hash=state[
            "resolved"
        ].case_hash,
        backend_policy_id=(
            state["backend"].policy_id
        ),
        solver_name=(
            state["backend"].solver_name
        ),
        solver_version=(
            state["backend"].solver_version
        ),
        manifest_path=prepared[
            "manifest_path"
        ],
    )

    return (
        result,
        prepared,
    )


def final_dat_path(
    run_dir: Path,
    trial_run_id: str,
) -> Path:
    path = (
        run_dir
        / f"{trial_run_id}.dat"
    )

    if (
        not path.is_file()
        or path.stat().st_size <= 0
    ):
        raise RuntimeError(
            f"{trial_run_id}: non-empty DAT "
            "output not found."
        )

    return path


def evaluate_completed_trial(
    state,
    result,
    prepared,
):
    trial = state["current_trial"]

    disposition = str(
        result.manifest.disposition
    )

    print(
        f"\n[{state['sentinel_id']}] "
        f"solver disposition = {disposition}"
    )

    dat_path = final_dat_path(
        prepared["run_dir"],
        trial.run_id,
    )

    extraction = (
        extract_clamp_force_measurement_from_dat(
            dat_path=dat_path,
            contact_pairs=tuple(
                state[
                    "bundle"
                ].contact.contact_pairs
            ),
        )
    )

    measurement = (
        extraction.measurement
    )

    evaluation = (
        evaluate_preload_calibration_trial(
            case_run_id=(
                state["case_run_id"]
            ),
            target_force_n=(
                state["target_force_n"]
            ),
            target_relative_tolerance=(
                state[
                    "target_relative_tolerance"
                ]
            ),
            spread_relative_tolerance=(
                state[
                    "spread_relative_tolerance"
                ]
            ),
            current_trial=trial,
            measurement=measurement,
            previous_trial=(
                state[
                    "previous_trial"
                ]
            ),
            previous_measurement=(
                state[
                    "previous_measurement"
                ]
            ),
            policy=(
                state[
                    "bundle"
                ].calibration_policy
            ),
        )
    )

    mean_force = (
        measurement.mean_force_n
    )

    relative_error = (
        (mean_force - state["target_force_n"])
        / state["target_force_n"]
    )

    print(
        f"[{state['sentinel_id']}] "
        f"under-head   = "
        f"{measurement.under_head_force_n:.6f} N"
    )
    print(
        f"[{state['sentinel_id']}] "
        f"nut-bearing  = "
        f"{measurement.nut_bearing_force_n:.6f} N"
    )
    print(
        f"[{state['sentinel_id']}] "
        f"member-intf  = "
        f"{measurement.member_interface_force_n:.6f} N"
    )
    print(
        f"[{state['sentinel_id']}] "
        f"thread CFN   = "
        f"{extraction.thread_normal_force_n:.6f} N"
    )
    print(
        f"[{state['sentinel_id']}] "
        f"mean clamp   = {mean_force:.6f} N"
    )
    print(
        f"[{state['sentinel_id']}] "
        f"target error = {relative_error:+.6%}"
    )
    print(
        f"[{state['sentinel_id']}] "
        f"path spread  = "
        f"{measurement.spread_relative:.6%}"
    )
    print(
        f"[{state['sentinel_id']}] "
        f"calibration  = "
        f"{evaluation.decision.disposition}"
    )

    history_row = {
        "trial_index": (
            trial.trial_index
        ),
        "run_id": trial.run_id,
        "source": str(
            trial.source
        ),
        "delta_temperature_c": (
            trial.delta_temperature_c
        ),
        "solver_disposition": (
            disposition
        ),
        "mean_force_n": mean_force,
        "under_head_force_n": (
            measurement
            .under_head_force_n
        ),
        "nut_bearing_force_n": (
            measurement
            .nut_bearing_force_n
        ),
        "member_interface_force_n": (
            measurement
            .member_interface_force_n
        ),
        "thread_normal_force_n": (
            extraction.thread_normal_force_n
        ),
        "target_relative_error": (
            relative_error
        ),
        "spread_relative": (
            measurement.spread_relative
        ),
        "calibration_disposition": (
            str(
                evaluation
                .decision
                .disposition
            )
        ),
        "manifest_path": (
            prepared[
                "manifest_path"
            ]
            .resolve()
            .relative_to(
                ROOT.resolve()
            )
            .as_posix()
        ),
    }

    state[
        "history"
    ].append(
        history_row
    )

    if evaluation.accepted:
        state["accepted"] = True
        state[
            "accepted_trial"
        ] = trial
        state[
            "accepted_measurement"
        ] = measurement
        state[
            "accepted_extraction"
        ] = extraction
        state[
            "accepted_evaluation"
        ] = evaluation
        state[
            "accepted_run_dir"
        ] = prepared[
            "run_dir"
        ]

        print(
            f"[{state['sentinel_id']}] "
            "PRELOAD PHYSICS: ACCEPT"
        )

        return

    if (
        evaluation.decision.disposition
        is PreloadCalibrationDisposition
        .NON_MONOTONIC_RESPONSE
    ):
        raise RuntimeError(
            f"{state['sentinel_id']}: "
            "non-monotonic preload response. "
            "Fail closed; do not continue calibration."
        )

    if evaluation.next_trial is None:
        raise RuntimeError(
            f"{state['sentinel_id']}: "
            "CONTINUE disposition without next trial."
        )

    print(
        f"[{state['sentinel_id']}] "
        f"next dT = "
        f"{evaluation.next_trial.delta_temperature_c:.9f} C "
        f"({evaluation.next_trial.source})"
    )

    state[
        "previous_trial"
    ] = trial

    state[
        "previous_measurement"
    ] = measurement

    state[
        "current_trial"
    ] = evaluation.next_trial


def write_summary(
    states,
):
    CAMPAIGN_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "schema_version": 1,
        "campaign": (
            "PHASE3_CP11_CROSS_SIZE_FEM"
        ),
        "execution": {
            "maximum_concurrent_calculix_runs": 2,
            "solver_timeout_seconds": None,
            "holdouts_accessed": False,
            "capability_upgrade_performed": False,
        },
        "sentinels": {},
        "overall_disposition": (
            "CROSS_SIZE_PRELOAD_CALIBRATION_ACCEPTED"
            if all(
                state["accepted"]
                for state in states.values()
            )
            else "CROSS_SIZE_PRELOAD_CALIBRATION_INCOMPLETE"
        ),
    }

    for sid, state in states.items():
        accepted_trial = state.get(
            "accepted_trial"
        )

        payload["sentinels"][
            sid
        ] = {
            "thread_designation": (
                state[
                    "thread_designation"
                ]
            ),
            "case_hash": (
                state["resolved"].case_hash
            ),
            "case_run_id": (
                state["case_run_id"]
            ),
            "target_force_n": (
                state["target_force_n"]
            ),
            "target_relative_tolerance": (
                state[
                    "target_relative_tolerance"
                ]
            ),
            "spread_relative_tolerance": (
                state[
                    "spread_relative_tolerance"
                ]
            ),
            "accepted": (
                state["accepted"]
            ),
            "accepted_trial_index": (
                accepted_trial.trial_index
                if accepted_trial
                else None
            ),
            "accepted_delta_temperature_c": (
                accepted_trial.delta_temperature_c
                if accepted_trial
                else None
            ),
            "accepted_run_id": (
                accepted_trial.run_id
                if accepted_trial
                else None
            ),
            "history": (
                state["history"]
            ),
        }

    path = (
        CAMPAIGN_ROOT
        / "cross_size_fem_calibration_campaign.json"
    )

    text = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    ) + "\n"

    if path.exists():
        old = path.read_text(
            encoding="utf-8"
        )

        if old != text:
            raise RuntimeError(
                "Campaign summary already exists "
                "with different content."
            )

    else:
        path.write_text(
            text,
            encoding="utf-8",
        )

    return (
        path,
        payload,
    )


def main() -> int:
    print("=" * 128)
    print(
        "THREADROM — PAIRED M8/M12 "
        "ADAPTIVE CROSS-SIZE FEM CAMPAIGN"
    )
    print("=" * 128)
    print("Concurrency          : 2 CalculiX jobs")
    print("Calibration          : independent per size")
    print("Trial-1              : analytical seed")
    print("Trial-2              : proportional if required")
    print("Trial-3+             : governed secant if required")
    print("Maximum trials/size  : 6")
    print("Solver timeout       : NONE")
    print("Mesh regeneration    : NO")
    print("Holdouts             : NO")
    print("Capability upgrade   : NO")
    print("=" * 128)
    print()

    transfer_template = (
        load_complete_joint_calculix_transfer_definition(
            CONFIG
            / "complete_joint_calculix_transfer.toml"
        )
    )

    contact_template = (
        load_complete_joint_contact_definition(
            CONFIG
            / "complete_joint_contact.toml"
        )
    )

    boundary_template = (
        load_complete_joint_boundary_region_definition(
            CONFIG
            / "complete_joint_boundary_regions.toml"
        )
    )

    (
        preload_config_path,
        preload_template,
    ) = load_preload_template()

    reference_temperature_c = unique_numeric(
        preload_template,
        "reference_temperature_c",
    )

    target_relative_tolerance = unique_numeric(
        preload_template,
        "target_relative_tolerance",
    )

    spread_relative_tolerance = unique_numeric(
        preload_template,
        "interface_spread_relative_tolerance",
    )

    print(
        "Preload policy config : "
        f"{preload_config_path.relative_to(ROOT)}"
    )
    print(
        "Reference temp        : "
        f"{reference_temperature_c:.9f} C"
    )
    print(
        "Target tolerance      : "
        f"{target_relative_tolerance:.6%}"
    )
    print(
        "Spread tolerance      : "
        f"{spread_relative_tolerance:.6%}"
    )
    print()

    backend = (
        bundle_mod
        .PHASE2_CERTIFIED_FEM_PROFILE
        .backend
    )

    sentinels = tuple(
        build_phase3_cross_size_fem_sentinels()
    )

    if len(sentinels) != 2:
        raise RuntimeError(
            "Expected exactly two governed "
            "cross-size sentinels."
        )

    states = {}

    for sentinel in sentinels:
        sid = (
            sentinel
            .definition
            .sentinel_id
        )

        if sid not in PREPARATION_ROOTS:
            raise RuntimeError(
                f"Unexpected sentinel: {sid}"
            )

        resolved = resolve_case(
            sentinel.case
        )

        preparation = (
            bundle_mod
            .derive_fem_case_preparation(
                resolved
            )
        )

        (
            record_path,
            record,
        ) = find_preparation_record(
            sid
        )

        mesh_path = verify_preparation(
            sentinel=sentinel,
            resolved=resolved,
            preparation=preparation,
            record_path=record_path,
            record=record,
        )

        bundle = make_bundle(
            sentinel=sentinel,
            resolved=resolved,
            preparation=preparation,
            record=record,
            mesh_path=mesh_path,
            transfer_template=(
                transfer_template
            ),
            contact_template=(
                contact_template
            ),
            boundary_template=(
                boundary_template
            ),
        )

        mesh_data = (
            read_grouped_complete_joint_mesh(
                mesh_path,
                bundle.transfer,
            )
        )

        initial_trial = (
            derive_initial_preload_calibration_trial(
                seed=(
                    bundle.calibration_seed
                ),
                case_run_id=(
                    preparation
                    .identity
                    .run_id
                ),
            )
        )

        # Independent check that the generic bundle's
        # analytical target agrees with the governed sentinel.
        seed_targets = [
            float(value)
            for value in recursive_values(
                bundle.calibration_seed,
                "target_force_n",
            )
            if isinstance(
                value,
                (int, float),
            )
            and not isinstance(
                value,
                bool,
            )
        ]

        if seed_targets:
            if not any(
                math.isclose(
                    target,
                    sentinel.target_preload_n,
                    rel_tol=1.0e-12,
                    abs_tol=1.0e-8,
                )
                for target in seed_targets
            ):
                raise RuntimeError(
                    f"{sid}: calibration-seed target "
                    "does not match sentinel preload."
                )

        states[sid] = {
            "sentinel_id": sid,
            "thread_designation": (
                sentinel
                .definition
                .thread_designation
            ),
            "sentinel": sentinel,
            "resolved": resolved,
            "preparation": preparation,
            "record_path": record_path,
            "record": record,
            "mesh_path": mesh_path,
            "mesh_data": mesh_data,
            "bundle": bundle,
            "backend": backend,
            "case_run_id": (
                preparation
                .identity
                .run_id
            ),
            "target_force_n": (
                sentinel.target_preload_n
            ),
            "reference_temperature_c": (
                reference_temperature_c
            ),
            "target_relative_tolerance": (
                target_relative_tolerance
            ),
            "spread_relative_tolerance": (
                spread_relative_tolerance
            ),
            "current_trial": (
                initial_trial
            ),
            "previous_trial": None,
            "previous_measurement": None,
            "accepted": False,
            "history": [],
        }

        print(
            f"{sid} | "
            f"{sentinel.definition.thread_designation}"
        )
        print(
            f"  Run identity : "
            f"{preparation.identity.run_id}"
        )
        print(
            f"  Mesh         : "
            f"{mesh_path.relative_to(ROOT)}"
        )
        print(
            f"  Target       : "
            f"{sentinel.target_preload_n:.9f} N"
        )
        print(
            f"  Trial-1 dT   : "
            f"{initial_trial.delta_temperature_c:.9f} C"
        )
        print()

    # ---------------------------------------------------------
    # ADAPTIVE PAIRED CALIBRATION
    # ---------------------------------------------------------

    wave_index = 0

    while True:
        active = [
            state
            for state in states.values()
            if not state["accepted"]
        ]

        if not active:
            break

        wave_index += 1

        print()
        print("=" * 128)
        print(
            f"CALIBRATION WAVE {wave_index}"
        )
        print("=" * 128)

        failures = []

        with ThreadPoolExecutor(
            max_workers=min(
                2,
                len(active),
            )
        ) as executor:

            future_to_state = {
                executor.submit(
                    execute_trial,
                    state,
                ): state
                for state in active
            }

            completed = []

            for future in as_completed(
                future_to_state
            ):
                state = (
                    future_to_state[
                        future
                    ]
                )

                try:
                    result, prepared = (
                        future.result()
                    )
                except Exception as exc:
                    failures.append(
                        (
                            state[
                                "sentinel_id"
                            ],
                            exc,
                        )
                    )
                    continue

                completed.append(
                    (
                        state,
                        result,
                        prepared,
                    )
                )

        # Evaluate every completed job even if its sibling failed.
        for (
            state,
            result,
            prepared,
        ) in completed:
            evaluate_completed_trial(
                state,
                result,
                prepared,
            )

        if failures:
            messages = [
                f"{sid}: {exc!r}"
                for sid, exc in failures
            ]

            raise RuntimeError(
                "One or more paired FEM jobs failed:\n"
                + "\n".join(messages)
            )

    summary_path, payload = (
        write_summary(
            states
        )
    )

    print()
    print("=" * 128)
    print(
        "CROSS-SIZE PRELOAD CALIBRATION CAMPAIGN COMPLETE"
    )
    print("=" * 128)

    for sid, state in states.items():
        trial = (
            state[
                "accepted_trial"
            ]
        )

        measurement = (
            state[
                "accepted_measurement"
            ]
        )

        print(
            f"{sid}: ACCEPT"
        )
        print(
            f"  accepted trial : "
            f"{trial.trial_index}"
        )
        print(
            f"  accepted dT    : "
            f"{trial.delta_temperature_c:.9f} C"
        )
        print(
            f"  mean clamp     : "
            f"{measurement.mean_force_n:.6f} N"
        )
        print(
            f"  target         : "
            f"{state['target_force_n']:.6f} N"
        )
        print(
            f"  spread         : "
            f"{measurement.spread_relative:.6%}"
        )
        print(
            f"  run directory  : "
            f"{state['accepted_run_dir'].relative_to(ROOT)}"
        )

    print()
    print(
        "Summary             : "
        f"{summary_path.relative_to(ROOT)}"
    )
    print(
        "Holdouts accessed   : NO"
    )
    print(
        "Capability upgraded : NO"
    )
    print(
        "Full physics cert   : PENDING NEXT CHECKPOINT"
    )
    print("=" * 128)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

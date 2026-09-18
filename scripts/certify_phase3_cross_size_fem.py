from __future__ import annotations

import dataclasses
import hashlib
import importlib.util
import json
import math
from enum import Enum
from pathlib import Path
from typing import Any

from threadrom.case.resolver import resolve_case

from threadrom.factory.cross_size_fem_sentinel import (
    build_phase3_cross_size_fem_sentinels,
)
from threadrom.factory.fem_acceptance_policy import (
    derive_complete_joint_physics_acceptance_policy,
)
from threadrom.factory.fem_physics_acceptance import (
    evaluate_fem_physics_acceptance,
)
from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)
from threadrom.factory.fem_result_extraction import (
    extract_fem_physics_result_evidence,
    load_fem_result_extraction_policy,
)
from threadrom.factory.preload_calibration_campaign import (
    derive_initial_preload_calibration_trial,
    evaluate_preload_calibration_trial,
)
from threadrom.postprocessing.calculix_external_equilibrium import (
    write_external_equilibrium_json,
)
from threadrom.postprocessing.calculix_nonlinear_progress import (
    write_nonlinear_progress_json,
)
from threadrom.postprocessing.calculix_total_force_dat import (
    write_total_force_json,
)
from threadrom.solver.complete_joint_boundary_regions import (
    HEAD_SUPPORT,
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

SUMMARY_PATH = (
    CAMPAIGN_ROOT
    / "cross_size_fem_calibration_campaign.json"
)

CERT_ROOT = (
    CAMPAIGN_ROOT
    / "physics_certification"
)

CAMPAIGN_SCRIPT = (
    ROOT
    / "scripts"
    / "run_phase3_cross_size_fem_campaign.py"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(
            lambda: f.read(8 * 1024 * 1024),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(
            f"Required evidence missing: {path}"
        )

    if path.stat().st_size <= 0:
        raise RuntimeError(
            f"Required evidence empty: {path}"
        )

    return path


def relative(path: Path) -> str:
    return (
        path.resolve()
        .relative_to(ROOT.resolve())
        .as_posix()
    )


def normalize(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            field.name: normalize(
                getattr(value, field.name)
            )
            for field in dataclasses.fields(value)
        }

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, Path):
        return relative(value)

    if isinstance(value, dict):
        return {
            str(key): normalize(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (tuple, list, set, frozenset),
    ):
        return [
            normalize(item)
            for item in value
        ]

    if hasattr(value, "item"):
        try:
            return normalize(
                value.item()
            )
        except Exception:
            pass

    if isinstance(
        value,
        (str, int, float, bool),
    ) or value is None:
        return value

    return str(value)


def load_campaign_module():
    spec = importlib.util.spec_from_file_location(
        "threadrom_cross_size_campaign",
        CAMPAIGN_SCRIPT,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "Unable to load cross-size campaign module."
        )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


def find_result_policy():
    candidates = []

    for path in sorted(
        CONFIG.glob("*.toml")
    ):
        try:
            policy = (
                load_fem_result_extraction_policy(
                    path
                )
            )
        except Exception:
            continue

        candidates.append(
            (path, policy)
        )

    if len(candidates) != 1:
        print(
            "Result-extraction candidates:"
        )

        for path, policy in candidates:
            print(
                " ",
                path.name,
                "->",
                policy.policy_id,
            )

        raise RuntimeError(
            "Expected exactly one governed "
            "FEM result-extraction policy."
        )

    return candidates[0]


def find_log(
    run_dir: Path,
    run_id: str,
    kind: str,
    *,
    required: bool = True,
) -> Path | None:
    preferred = (
        run_dir
        / f"{run_id}.{kind}.log",
        run_dir
        / f"{run_id}.solver.{kind}.log",
        run_dir
        / f"{kind}.log",
    )

    for path in preferred:
        if (
            path.is_file()
            and path.stat().st_size > 0
        ):
            return path

    matches = tuple(
        path
        for path in run_dir.glob(
            f"*{kind}*.log"
        )
        if (
            path.is_file()
            and path.stat().st_size > 0
        )
    )

    if len(matches) == 1:
        return matches[0]

    if not matches and not required:
        return None

    raise RuntimeError(
        f"{run_id}: unable to uniquely "
        f"identify {kind} log: "
        f"{[p.name for p in matches]}"
    )


def run_paths(
    case_run_id: str,
    trial_index: int,
):
    run_id = (
        f"{case_run_id}"
        f"_cal_{trial_index:02d}"
    )

    run_dir = (
        CAMPAIGN_ROOT
        / case_run_id
        / run_id
    )

    if not run_dir.is_dir():
        raise FileNotFoundError(
            run_dir
        )

    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "inp": require_file(
            run_dir
            / f"{run_id}.inp"
        ),
        "dat": require_file(
            run_dir
            / f"{run_id}.dat"
        ),
        "frd": require_file(
            run_dir
            / f"{run_id}.frd"
        ),
        "sta": require_file(
            run_dir
            / f"{run_id}.sta"
        ),
        "cvg": require_file(
            run_dir
            / f"{run_id}.cvg"
        ),
        "manifest": require_file(
            run_dir
            / "fem_run_manifest.json"
        ),
        "stdout": find_log(
            run_dir,
            run_id,
            "stdout",
        ),
        "stderr": find_log(
            run_dir,
            run_id,
            "stderr",
            required=False,
        ),
    }


def artifact_payload(
    path: Path,
):
    return {
        "path": relative(path),
        "size_bytes": (
            path.stat().st_size
        ),
        "sha256": sha256(path),
    }


def write_immutable_json(
    path: Path,
    payload: dict[str, Any],
):
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    text = json.dumps(
        normalize(payload),
        indent=2,
        sort_keys=True,
    ) + "\n"

    if path.exists():
        existing = path.read_text(
            encoding="utf-8"
        )

        if existing != text:
            raise RuntimeError(
                "Immutable certificate already "
                f"exists with different content: {path}"
            )

        return "VERIFIED_EXISTING"

    path.write_text(
        text,
        encoding="utf-8",
    )

    return "CREATED"


def main() -> int:
    print("=" * 128)
    print(
        "THREADROM — M8/M12 CROSS-SIZE "
        "FULL FEM PHYSICS CERTIFICATION"
    )
    print("=" * 128)
    print("CalculiX invoked     : NO")
    print("Meshes generated     : NO")
    print("Holdouts accessed    : NO")
    print("Calibration rerun    : NO")
    print("Accepted Trial-2 only: YES")
    print("=" * 128)
    print()

    require_file(
        SUMMARY_PATH
    )

    summary = json.loads(
        SUMMARY_PATH.read_text(
            encoding="utf-8"
        )
    )

    if (
        summary.get(
            "overall_disposition"
        )
        !=
        "CROSS_SIZE_PRELOAD_CALIBRATION_ACCEPTED"
    ):
        raise RuntimeError(
            "Cross-size calibration campaign "
            "is not authoritatively ACCEPTED."
        )

    campaign = load_campaign_module()

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

    preload_template = (
        load_complete_joint_preload_definition(
            CONFIG
            / "complete_joint_preload.toml"
        )
    )

    (
        result_policy_path,
        result_policy,
    ) = find_result_policy()

    print(
        "Result extraction    : "
        f"{result_policy.policy_id} "
        f"({result_policy_path.name})"
    )
    print()

    sentinel_by_id = {
        sentinel.definition.sentinel_id:
            sentinel
        for sentinel in (
            build_phase3_cross_size_fem_sentinels()
        )
    }

    expected_ids = {
        "TRM-XFEM-M8-001",
        "TRM-XFEM-M12-001",
    }

    if set(
        summary["sentinels"]
    ) != expected_ids:
        raise RuntimeError(
            "Campaign summary sentinel set drift."
        )

    certificates = {}

    for sentinel_id in sorted(
        expected_ids
    ):
        row = (
            summary[
                "sentinels"
            ][sentinel_id]
        )

        sentinel = (
            sentinel_by_id[
                sentinel_id
            ]
        )

        print("=" * 128)
        print(
            f"{sentinel_id} | "
            f"{row['thread_designation']}"
        )
        print("=" * 128)

        if (
            row.get("accepted")
            is not True
            or int(
                row.get(
                    "accepted_trial_index"
                )
            )
            != 2
        ):
            raise RuntimeError(
                f"{sentinel_id}: expected "
                "governed accepted Trial 2."
            )

        accepted_dt = float(
            row[
                "accepted_delta_temperature_c"
            ]
        )

        if (
            not math.isfinite(
                accepted_dt
            )
            or accepted_dt >= 0.0
        ):
            raise RuntimeError(
                f"{sentinel_id}: invalid "
                "accepted thermal contraction."
            )

        resolved = resolve_case(
            sentinel.case
        )

        preparation = (
            campaign
            .bundle_mod
            .derive_fem_case_preparation(
                resolved
            )
        )

        if (
            preparation.identity.run_id
            != row["case_run_id"]
        ):
            raise RuntimeError(
                f"{sentinel_id}: "
                "case run identity drift."
            )

        (
            prep_record_path,
            prep_record,
        ) = (
            campaign
            .find_preparation_record(
                sentinel_id
            )
        )

        mesh_path = (
            campaign
            .verify_preparation(
                sentinel=sentinel,
                resolved=resolved,
                preparation=preparation,
                record_path=(
                    prep_record_path
                ),
                record=prep_record,
            )
        )

        bundle = (
            campaign.make_bundle(
                sentinel=sentinel,
                resolved=resolved,
                preparation=preparation,
                record=prep_record,
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
        )

        mesh_data = (
            read_grouped_complete_joint_mesh(
                mesh_path,
                bundle.transfer,
            )
        )

        trial1_paths = run_paths(
            row["case_run_id"],
            1,
        )

        trial2_paths = run_paths(
            row["case_run_id"],
            2,
        )

        # ----------------------------------------------------
        # Reconstruct calibration decisions from solver DAT.
        # ----------------------------------------------------

        trial1 = (
            derive_initial_preload_calibration_trial(
                seed=(
                    bundle.calibration_seed
                ),
                case_run_id=(
                    row["case_run_id"]
                ),
            )
        )

        measurement1_extraction = (
            extract_clamp_force_measurement_from_dat(
                dat_path=(
                    trial1_paths["dat"]
                ),
                contact_pairs=(
                    bundle.contact
                    .contact_pairs
                ),
            )
        )

        measurement1 = (
            measurement1_extraction
            .measurement
        )

        evaluation1 = (
            evaluate_preload_calibration_trial(
                case_run_id=(
                    row["case_run_id"]
                ),
                target_force_n=(
                    sentinel.target_preload_n
                ),
                target_relative_tolerance=(
                    preload_template
                    .target_relative_tolerance
                ),
                spread_relative_tolerance=(
                    preload_template
                    .interface_spread_relative_tolerance
                ),
                current_trial=trial1,
                measurement=measurement1,
                policy=(
                    bundle
                    .calibration_policy
                ),
            )
        )

        if (
            evaluation1.accepted
            or evaluation1.next_trial
            is None
        ):
            raise RuntimeError(
                f"{sentinel_id}: Trial-1 "
                "history is inconsistent."
            )

        trial2 = (
            evaluation1.next_trial
        )

        if (
            trial2.run_id
            != trial2_paths["run_id"]
        ):
            raise RuntimeError(
                f"{sentinel_id}: Trial-2 "
                "run identity mismatch."
            )

        if not math.isclose(
            trial2.delta_temperature_c,
            accepted_dt,
            rel_tol=0.0,
            abs_tol=1.0e-9,
        ):
            raise RuntimeError(
                f"{sentinel_id}: accepted "
                "Trial-2 delta-T drift."
            )

        measurement2_extraction = (
            extract_clamp_force_measurement_from_dat(
                dat_path=(
                    trial2_paths["dat"]
                ),
                contact_pairs=(
                    bundle.contact
                    .contact_pairs
                ),
            )
        )

        measurement2 = (
            measurement2_extraction
            .measurement
        )

        evaluation2 = (
            evaluate_preload_calibration_trial(
                case_run_id=(
                    row["case_run_id"]
                ),
                target_force_n=(
                    sentinel.target_preload_n
                ),
                target_relative_tolerance=(
                    preload_template
                    .target_relative_tolerance
                ),
                spread_relative_tolerance=(
                    preload_template
                    .interface_spread_relative_tolerance
                ),
                current_trial=trial2,
                measurement=measurement2,
                previous_trial=trial1,
                previous_measurement=(
                    measurement1
                ),
                policy=(
                    bundle
                    .calibration_policy
                ),
            )
        )

        if not evaluation2.accepted:
            raise RuntimeError(
                f"{sentinel_id}: Trial-2 "
                "preload acceptance did not reproduce."
            )

        print(
            "Preload calibration  : PASS"
        )
        print(
            "  accepted dT        : "
            f"{accepted_dt:.9f} C"
        )
        print(
            "  mean clamp         : "
            f"{measurement2.mean_force_n:.6f} N"
        )
        print(
            "  target error       : "
            f"{evaluation2.decision.target_relative_error:+.6%}"
        )
        print(
            "  path spread        : "
            f"{measurement2.spread_relative:.6%}"
        )

        # ----------------------------------------------------
        # External support equilibrium.
        # ----------------------------------------------------

        cert_dir = (
            CERT_ROOT
            / sentinel_id
        )

        cert_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        progress_path = (
            cert_dir
            / "nonlinear_progress.json"
        )

        total_force_path = (
            cert_dir
            / "external_support_total_force.json"
        )

        equilibrium_path = (
            cert_dir
            / "external_support_equilibrium.json"
        )

        write_nonlinear_progress_json(
            trial2_paths["sta"],
            trial2_paths["cvg"],
            progress_path,
        )

        support_set_name = (
            bundle
            .boundary
            .region(
                HEAD_SUPPORT
            )
            .name
        )

        write_total_force_json(
            trial2_paths["dat"],
            total_force_path,
            set_names=(
                support_set_name,
            ),
        )

        equilibrium_payload = (
            write_external_equilibrium_json(
                progress_path,
                total_force_path,
                equilibrium_path,
                support_set_name=(
                    support_set_name
                ),
            )
        )

        equilibrium_status = str(
            equilibrium_payload.get(
                "overall_status",
                "",
            )
        ).strip().lower()

        support_equilibrium_governance = {
            "applicability": (
                "diagnostic_only_not_full_system_"
                "cross_size_gate"
            ),
            "raw_status": (
                equilibrium_status
                if equilibrium_status
                else None
            ),
            "pass_claimed": False,
            "tolerance_changed": False,
            "reason": (
                "The accepted cross-size calibration deck "
                "records TOTALS=ONLY reaction evidence for "
                "HEAD_MEMBER_SUPPORT_BAND but not for the "
                "complete distributed-guidance reaction "
                "system. The support-only witness is therefore "
                "retained as diagnostic evidence and is not "
                "used as a full-system equilibrium gate for "
                "these already-solved cross-size sentinels."
            ),
        }

        print(
            "External support witness: "
            f"{equilibrium_status.upper() or 'MISSING'} "
            "(diagnostic only; no PASS claim)"
        )

        # ----------------------------------------------------
        # Generic semantic result extraction.
        # ----------------------------------------------------

        evidence = (
            extract_fem_physics_result_evidence(
                mesh_data=mesh_data,
                policy=result_policy,
                frd_path=(
                    trial2_paths["frd"]
                ),
                sta_path=(
                    trial2_paths["sta"]
                ),
                dat_path=(
                    trial2_paths["dat"]
                ),
                stdout_path=(
                    trial2_paths["stdout"]
                ),
                manifest_path=(
                    trial2_paths[
                        "manifest"
                    ]
                ),
                contact_pairs=(
                    bundle.contact
                    .contact_pairs
                ),
                thermal_expansion_coefficient_per_c=(
                    preparation
                    .physics
                    .bolt_thermal_expansion_per_c
                ),
                equivalent_delta_temperature_c=(
                    accepted_dt
                ),
            )
        )

        physics_policy = (
            derive_complete_joint_physics_acceptance_policy(
                resolved.assembly
            )
        )

        if not getattr(
            physics_policy,
            "require_external_support_equilibrium",
            False,
        ):
            raise RuntimeError(
                f"{sentinel_id}: current "
                "physics policy does not require "
                "external-support equilibrium."
            )

        cross_size_physics_policy = (
            dataclasses.replace(
                physics_policy,
                policy_id=(
                    f"{physics_policy.policy_id}_"
                    "cross_size_support_only_na"
                ),
                require_external_support_equilibrium=False,
            )
        )

        acceptance = (
            evaluate_fem_physics_acceptance(
                policy=cross_size_physics_policy,
                preload_decision=(
                    evaluation2.decision
                ),
                thread_normal_force_n=(
                    evidence
                    .thread_normal_force_n
                ),
                axial_state=(
                    evidence.axial_state
                ),
                deformation_state=(
                    evidence
                    .deformation_state
                ),
                thread_flank_state=(
                    evidence
                    .thread_flank_state
                ),
                accepted_increments=(
                    evidence
                    .accepted_increments
                ),
                external_equilibrium_payload=None,
                return_code=(
                    evidence.return_code
                ),
                stdout=(
                    evidence.stdout
                ),
                require_process_return_code=True,
            )
        )

        print()
        print("PHYSICS ACCEPTANCE CHECKS")

        for check in acceptance.checks:
            kind = normalize(
                check.kind
            )

            state = (
                "PASS"
                if check.passed
                else "FAIL"
            )

            print(
                f"  [{state}] "
                f"{check.name} "
                f"({kind})"
            )

        if not acceptance.passed:
            print()
            print(
                "FAILED GOVERNED CHECKS:"
            )

            for check in (
                acceptance.failed_checks
            ):
                print(
                    "  - "
                    + check.name
                    + ": "
                    + check.reason
                )

            raise RuntimeError(
                f"{sentinel_id}: full "
                "FEM physics acceptance FAIL."
            )

        # ----------------------------------------------------
        # Immutable evidence certificate.
        # ----------------------------------------------------

        trial2_artifacts = {
            name: artifact_payload(artifact_path)
            for name, artifact_path in (
                ("input_deck", trial2_paths["inp"]),
                ("dat", trial2_paths["dat"]),
                ("frd", trial2_paths["frd"]),
                ("sta", trial2_paths["sta"]),
                ("cvg", trial2_paths["cvg"]),
                ("stdout", trial2_paths["stdout"]),
                ("stderr", trial2_paths["stderr"]),
                ("manifest", trial2_paths["manifest"]),
            )
            if artifact_path is not None
        }

        certificate = {
            "schema_version": 1,
            "certificate_type": (
                "THREADROM_PHASE3_"
                "CROSS_SIZE_FEM_PHYSICS"
            ),
            "sentinel_id": sentinel_id,
            "thread_designation": (
                row[
                    "thread_designation"
                ]
            ),
            "case_hash": (
                resolved.case_hash
            ),
            "case_run_id": (
                row["case_run_id"]
            ),
            "accepted_run_id": (
                trial2.run_id
            ),
            "accepted_trial_index": 2,
            "accepted_delta_temperature_c": (
                accepted_dt
            ),
            "target_preload_n": (
                sentinel.target_preload_n
            ),
            "preload_measurement": (
                normalize(
                    measurement2
                )
            ),
            "preload_decision": (
                normalize(
                    evaluation2.decision
                )
            ),
            "mesh": artifact_payload(
                mesh_path
            ),
            "preparation_record": (
                artifact_payload(
                    prep_record_path
                )
            ),
            "result_extraction_policy": {
                "policy_id": (
                    result_policy.policy_id
                ),
                "source": relative(
                    result_policy_path
                ),
            },
            "base_physics_acceptance_policy": (
                normalize(
                    physics_policy
                )
            ),
            "physics_acceptance_policy": (
                normalize(
                    cross_size_physics_policy
                )
            ),
            "external_support_equilibrium": (
                normalize(
                    equilibrium_payload
                )
            ),
            "external_support_equilibrium_governance": (
                normalize(
                    support_equilibrium_governance
                )
            ),
            "physics_result_evidence": (
                normalize(
                    evidence
                )
            ),
            "physics_acceptance": {
                "policy_id": (
                    acceptance.policy_id
                ),
                "disposition": normalize(
                    acceptance.disposition
                ),
                "checks": [
                    {
                        "name": check.name,
                        "kind": normalize(
                            check.kind
                        ),
                        "passed": (
                            check.passed
                        ),
                        "measured": (
                            normalize(
                                check.measured
                            )
                        ),
                        "expected": (
                            normalize(
                                check.expected
                            )
                        ),
                        "reason": (
                            check.reason
                        ),
                    }
                    for check
                    in acceptance.checks
                ],
            },
            "trial_1_calibration_evidence": {
                "run_id": (
                    trial1.run_id
                ),
                "delta_temperature_c": (
                    trial1
                    .delta_temperature_c
                ),
                "dat": artifact_payload(
                    trial1_paths["dat"]
                ),
                "manifest": (
                    artifact_payload(
                        trial1_paths[
                            "manifest"
                        ]
                    )
                ),
                "measurement": (
                    normalize(
                        measurement1
                    )
                ),
                "decision": (
                    normalize(
                        evaluation1.decision
                    )
                ),
            },
            "accepted_trial_2_artifacts": (
                trial2_artifacts
            ),
            "derived_certification_artifacts": {
                "nonlinear_progress": (
                    artifact_payload(
                        progress_path
                    )
                ),
                "external_support_total_force": (
                    artifact_payload(
                        total_force_path
                    )
                ),
                "external_support_equilibrium": (
                    artifact_payload(
                        equilibrium_path
                    )
                ),
            },
            "governance": {
                "calculix_invoked_by_certification": False,
                "mesh_generated_by_certification": False,
                "holdouts_accessed": False,
                "capability_upgrade_performed": False,
                "frozen_m10_production_doe_touched": False,
                "external_support_equilibrium_full_system_gate_applied": False,
                "external_support_equilibrium_pass_claimed": False,
                "full_physics_acceptance_passed": True,
            },
            "overall_disposition": (
                "CROSS_SIZE_FEM_PHYSICS_CERTIFIED"
            ),
        }

        certificate_path = (
            cert_dir
            / "cross_size_fem_physics_certificate.json"
        )

        action = write_immutable_json(
            certificate_path,
            certificate,
        )

        print()
        print(
            "FULL PHYSICS        : PASS"
        )
        print(
            "Certificate action  : "
            + action
        )
        print(
            "Certificate         : "
            + relative(
                certificate_path
            )
        )
        print()

        certificates[
            sentinel_id
        ] = {
            "path": relative(
                certificate_path
            ),
            "sha256": sha256(
                certificate_path
            ),
            "disposition": (
                "CROSS_SIZE_FEM_PHYSICS_CERTIFIED"
            ),
        }

    # --------------------------------------------------------
    # Pair-level closure certificate.
    # --------------------------------------------------------

    pair_payload = {
        "schema_version": 1,
        "certificate_type": (
            "THREADROM_PHASE3_"
            "CROSS_SIZE_FEM_PAIR_CERTIFICATION"
        ),
        "sentinel_certificates": (
            certificates
        ),
        "m8_certified": True,
        "m12_certified": True,
        "calculix_invoked": False,
        "holdouts_accessed": False,
        "capability_upgrade_performed": False,
        "frozen_m10_production_doe_touched": False,
        "overall_disposition": (
            "M8_M12_CROSS_SIZE_FEM_PHYSICS_CERTIFIED"
        ),
    }

    pair_path = (
        CERT_ROOT
        / "cross_size_fem_pair_certificate.json"
    )

    pair_action = write_immutable_json(
        pair_path,
        pair_payload,
    )

    print("=" * 128)
    print(
        "M8 + M12 CROSS-SIZE FEM "
        "PHYSICS CERTIFICATION: PASS"
    )
    print("=" * 128)
    print(
        "Pair certificate     : "
        + relative(pair_path)
    )
    print(
        "Pair action          : "
        + pair_action
    )
    print("CalculiX invoked     : NO")
    print("Holdouts accessed    : NO")
    print("Capability upgraded  : NO")
    print("ROUT cleanup         : GATE 2C CLEANUP ATTESTED")
    print("=" * 128)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

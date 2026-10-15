from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import tomllib

from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path

from threadrom.case.resolver import resolve_case
from threadrom.factory.diversified_doe_design import _build_case
from threadrom.factory.fem_case_definition_bundle import (
    build_generic_fem_definition_bundle,
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
    PreloadCalibrationCampaignPolicy,
    derive_initial_preload_calibration_trial,
    evaluate_preload_calibration_trial,
)
from threadrom.factory.production_doe_adaptive_controller import (
    AdaptiveCalibrationAction,
    plan_adaptive_calibration,
)
from threadrom.materials.diversified_candidate_catalog import (
    DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
)
from threadrom.solver.calculix_job import CalculixJobDefinition
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

import threadrom.factory.fem_case_definition_bundle as bundle_mod


ROOT = Path(r"D:\ThreadROM")

CASE_HASH = (
    "db4f5abb0986d0527a06fd72849bfc948041448f6a8a320a4aad0a0858028d53"
)

CASE_RUN_ID = "trm_fem_0f92f7fbf611"

TRIAL1_ID = CASE_RUN_ID + "_cal_01"
EXPECTED_TRIAL2_ID = CASE_RUN_ID + "_cal_02"

MEMBER_MATERIAL_ID = "member_aluminium_en_aw_6082_t6"

EXPECTED_TRIAL1_DT_C = -153.53865493868906
EXPECTED_TRIAL2_DT_C = -245.0189356383562

EXPECTED_TRIAL1_DECK_SHA256 = (
    "2134f8e662fd58ce646a6b8c4914fdadfe575d74cba4433d4ce901aad944b6b6"
)

EXPECTED_TRIAL1_DAT_SHA256 = (
    "1760a36fd3a3556067c4f6aa1cea84a1c89e17f2a3c94525311ae0f8c3372279"
)

EXPECTED_STEP_SHA256 = (
    "7f312b6bd799dafaaf7e10404ffd18e1dc62f9a1fe22cc045cbde8c25cf407e9"
)

EXPECTED_MESH_SHA256 = (
    "21022f69b866f95da500b821153c5c6dbb7b6269a9f6d91b7047716f20a4971e"
)

REFERENCE_TEMPERATURE_C = 20.0

PILOT_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / "pilot_calibration_preflight"
    / CASE_RUN_ID
)

TRIAL1_DIR = PILOT_ROOT / TRIAL1_ID
TRIAL1_INP = TRIAL1_DIR / f"{TRIAL1_ID}.inp"
TRIAL1_DAT = TRIAL1_DIR / f"{TRIAL1_ID}.dat"

STEP_PATH = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp8_production_doe"
    / "TRM-PDOE-C01"
    / "prepared_cases"
    / "trm_fem_a5e86e9150fb"
    / "geometry"
    / "complete_joint_assembly.step"
)

MESH_PATH = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp8_production_doe"
    / "TRM-PDOE-C01"
    / "prepared_cases"
    / "trm_fem_a5e86e9150fb"
    / "mesh"
    / "complete_joint_grouped_medium_first_order.msh"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def value_of(value):
    return value.value if isinstance(value, Enum) else value


def jsonable(value):
    if is_dataclass(value):
        return {
            key: jsonable(item)
            for key, item in asdict(value).items()
        }

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            str(key): jsonable(item)
            for key, item in value.items()
        }

    if isinstance(value, (tuple, list)):
        return [jsonable(item) for item in value]

    return value


def require_close(
    label: str,
    actual: float,
    expected: float,
    *,
    abs_tol: float = 1.0e-10,
) -> None:

    if not math.isclose(
        float(actual),
        float(expected),
        rel_tol=0.0,
        abs_tol=abs_tol,
    ):
        raise RuntimeError(
            f"{label} drift: actual={actual!r}; expected={expected!r}"
        )


def elastic_card(
    text: str,
    material_name: str,
) -> tuple[float, float]:

    pattern = re.compile(
        rf"(?ims)"
        rf"^\s*\*MATERIAL\s*,\s*NAME\s*=\s*"
        rf"{re.escape(material_name)}\s*$"
        rf"(.*?)"
        rf"(?=^\s*\*MATERIAL\b|\Z)"
    )

    match = pattern.search(text)

    require(
        match is not None,
        f"Missing material card: {material_name}",
    )

    elastic = re.search(
        r"(?im)"
        r"^\s*\*ELASTIC(?:\s*,[^\r\n]*)?\s*$"
        r"\r?\n"
        r"\s*([+-]?[0-9.eE+-]+)"
        r"\s*,\s*"
        r"([+-]?[0-9.eE+-]+)",
        match.group(1),
    )

    require(
        elastic is not None,
        f"Missing *ELASTIC data: {material_name}",
    )

    return (
        float(elastic.group(1)),
        float(elastic.group(2)),
    )


def build_state():

    # ----------------------------------------------------------
    # Canonical diversified case
    # ----------------------------------------------------------

    policy = tomllib.loads(
        (
            ROOT / "config/phase3_diversified_doe.toml"
        ).read_text(encoding="utf-8-sig")
    )

    manifest = json.loads(
        (
            ROOT
            / "docs"
            / "phase3_diversified_doe"
            / "design_proposal.json"
        ).read_text(encoding="utf-8-sig")
    )

    pilot = next(
        row
        for row in manifest["cases"]
        if row["case_hash"] == CASE_HASH
    )

    require(
        pilot["member_material_id"] == MEMBER_MATERIAL_ID,
        "Canonical diversified member-material identity drift.",
    )

    size = next(
        row
        for row in policy["size_candidates"]
        if row["designation"] == pilot["thread_designation"]
    )

    case, _ = _build_case(
        policy,
        size,
        pilot["member_material_id"],
        tuple(pilot["normalized_coordinates"]),
    )

    resolved = resolve_case(
        case,
        material_catalog=DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
    )

    require(
        resolved.case_hash == CASE_HASH,
        "Diversified pilot case hash drift.",
    )

    require_close(
        "Target preload",
        resolved.source_case.loading.target_preload_n,
        15000.0,
        abs_tol=1.0e-9,
    )

    # ----------------------------------------------------------
    # Governed templates / mixed-material bundle
    # ----------------------------------------------------------

    transfer = load_complete_joint_calculix_transfer_definition(
        ROOT / "config/complete_joint_calculix_transfer.toml"
    )

    contact = load_complete_joint_contact_definition(
        ROOT / "config/complete_joint_contact.toml"
    )

    boundary = load_complete_joint_boundary_region_definition(
        ROOT / "config/complete_joint_boundary_regions.toml"
    )

    preload = load_complete_joint_preload_definition(
        ROOT / "config/complete_joint_preload.toml"
    )

    bundle = build_generic_fem_definition_bundle(
        resolved,
        mesh_id=f"mesh-{CASE_HASH[:16]}",
        geometry_id=f"geometry-{CASE_HASH[:16]}",
        classification_id=f"classification-{CASE_HASH[:16]}",
        source_mesh_name=MESH_PATH.name,
        transfer_template=transfer,
        contact_template=contact,
        boundary_template=boundary,
        material_catalog=DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG,
    )

    require(
        bundle.preparation.identity.run_id == CASE_RUN_ID,
        "FEM case-run identity drift.",
    )

    require_close(
        "Fastener E",
        bundle.transfer.youngs_modulus_mpa,
        210000.0,
    )

    require_close(
        "Fastener nu",
        bundle.transfer.poissons_ratio,
        0.30,
    )

    require_close(
        "Member E",
        bundle.transfer.member_youngs_modulus_mpa,
        70000.0,
    )

    require_close(
        "Member nu",
        bundle.transfer.member_poissons_ratio,
        0.33,
    )

    # ----------------------------------------------------------
    # Historical reusable geometry/mesh provenance
    # ----------------------------------------------------------

    require(
        STEP_PATH.is_file(),
        "Historical pilot STEP missing.",
    )

    require(
        MESH_PATH.is_file(),
        "Historical pilot mesh missing.",
    )

    require(
        sha256(STEP_PATH) == EXPECTED_STEP_SHA256,
        "Historical STEP SHA-256 drift.",
    )

    require(
        sha256(MESH_PATH) == EXPECTED_MESH_SHA256,
        "Historical mesh SHA-256 drift.",
    )

    mesh_data = read_grouped_complete_joint_mesh(
        MESH_PATH,
        bundle.transfer,
    )

    # ----------------------------------------------------------
    # Reconstruct completed CAL_01 from governed seed
    # ----------------------------------------------------------

    require(
        TRIAL1_INP.is_file(),
        "CAL_01 INP missing.",
    )

    require(
        TRIAL1_DAT.is_file()
        and TRIAL1_DAT.stat().st_size > 0,
        "CAL_01 DAT missing or empty.",
    )

    require(
        sha256(TRIAL1_INP)
        == EXPECTED_TRIAL1_DECK_SHA256,
        "CAL_01 deck SHA-256 drift.",
    )

    trial1_dat_sha = sha256(TRIAL1_DAT)

    require(
        trial1_dat_sha
        == EXPECTED_TRIAL1_DAT_SHA256,
        "CAL_01 DAT SHA-256 drift.",
    )

    trial1 = derive_initial_preload_calibration_trial(
        seed=bundle.calibration_seed,
        case_run_id=CASE_RUN_ID,
    )

    require(
        trial1.run_id == TRIAL1_ID,
        "CAL_01 governed identity drift.",
    )

    require(
        trial1.trial_index == 1,
        "CAL_01 governed index drift.",
    )

    require(
        value_of(trial1.source) == "analytical_seed",
        "CAL_01 source drift.",
    )

    require_close(
        "CAL_01 delta-T",
        trial1.delta_temperature_c,
        EXPECTED_TRIAL1_DT_C,
        abs_tol=1.0e-12,
    )

    extraction1 = extract_clamp_force_measurement_from_dat(
        dat_path=TRIAL1_DAT,
        contact_pairs=contact.contact_pairs,
    )

    require_close(
        "CAL_01 synchronized result time",
        extraction1.time,
        1.0,
        abs_tol=1.0e-12,
    )

    measurement1 = extraction1.measurement

    require_close(
        "CAL_01 mean clamp force",
        measurement1.mean_force_n,
        9399.599333333334,
        abs_tol=1.0e-6,
    )

    require(
        sha256(TRIAL1_DAT) == trial1_dat_sha,
        "CAL_01 DAT changed during extraction.",
    )

    # ----------------------------------------------------------
    # Existing adaptive evaluator + planner
    # ----------------------------------------------------------

    evaluation1 = evaluate_preload_calibration_trial(
        case_run_id=CASE_RUN_ID,
        target_force_n=(
            resolved.source_case.loading.target_preload_n
        ),
        target_relative_tolerance=(
            preload.target_relative_tolerance
        ),
        spread_relative_tolerance=(
            preload.interface_spread_relative_tolerance
        ),
        current_trial=trial1,
        measurement=measurement1,
        previous_trial=None,
        previous_measurement=None,
    )

    plan = plan_adaptive_calibration(
        case_run_id=CASE_RUN_ID,
        evaluation=evaluation1,
        maximum_trials=(
            PreloadCalibrationCampaignPolicy().maximum_trials
        ),
    )

    require(
        plan.action
        is AdaptiveCalibrationAction.NEXT_TRIAL_REQUIRES_AUTHORIZATION,
        "Adaptive planner did not request a continuation trial.",
    )

    require(
        plan.completed_run_id == TRIAL1_ID,
        "Adaptive planner predecessor identity drift.",
    )

    require(
        evaluation1.next_trial is not None,
        "Adaptive evaluator returned no CAL_02 trial.",
    )

    trial2 = evaluation1.next_trial

    require(
        plan.next_run_id == trial2.run_id,
        "Adaptive planner/evaluator Trial-2 identity disagreement.",
    )

    require(
        trial2.run_id == EXPECTED_TRIAL2_ID,
        "CAL_02 identity drift.",
    )

    require(
        trial2.trial_index == 2,
        "CAL_02 trial-index drift.",
    )

    require(
        value_of(trial2.source) == "proportional",
        "CAL_02 adaptive source drift.",
    )

    require_close(
        "CAL_02 adaptive delta-T",
        trial2.delta_temperature_c,
        EXPECTED_TRIAL2_DT_C,
        abs_tol=1.0e-12,
    )

    return {
        "pilot": pilot,
        "resolved": resolved,
        "transfer": transfer,
        "contact": contact,
        "preload": preload,
        "bundle": bundle,
        "mesh_data": mesh_data,
        "trial1": trial1,
        "measurement1": measurement1,
        "evaluation1": evaluation1,
        "plan": plan,
        "trial2": trial2,
        "trial1_dat_sha": trial1_dat_sha,
    }


def prepare_trial2(state):

    trial2 = state["trial2"]
    bundle = state["bundle"]
    mesh_data = state["mesh_data"]

    run_dir = PILOT_ROOT / trial2.run_id

    # Solver outputs must not pre-exist.
    for suffix in (
        ".dat",
        ".sta",
        ".cvg",
        ".frd",
        ".rout",
    ):
        require(
            not (run_dir / f"{trial2.run_id}{suffix}").exists(),
            f"Duplicate CAL_02 solver output exists: {suffix}",
        )

    manifest_path = run_dir / "fem_run_manifest.json"

    require(
        not manifest_path.exists(),
        "CAL_02 FEM run manifest already exists.",
    )

    candidate = (
        PILOT_ROOT
        / f".{trial2.run_id}.adaptive_factory_candidate.inp"
    )

    if candidate.exists():
        candidate.unlink()

    deck = write_fem_preload_calibration_trial_deck(
        mesh_data=mesh_data,
        bundle=bundle,
        trial=trial2,
        reference_temperature_c=REFERENCE_TEMPERATURE_C,
        input_path=candidate,
    )

    require(
        candidate.is_file()
        and candidate.stat().st_size > 0,
        "Adaptive factory candidate deck missing.",
    )

    candidate_sha = sha256(candidate)

    require(
        candidate_sha == deck.sha256,
        "Adaptive factory candidate/deck SHA mismatch.",
    )

    require(
        deck.trial_run_id == trial2.run_id,
        "Adaptive factory deck/trial identity mismatch.",
    )

    require_close(
        "Adaptive factory deck delta-T",
        deck.delta_temperature_c,
        trial2.delta_temperature_c,
        abs_tol=1.0e-12,
    )

    # ----------------------------------------------------------
    # Physical material-card verification in rendered INP
    # ----------------------------------------------------------

    deck_text = candidate.read_text(
        encoding="utf-8",
        errors="strict",
    )

    expectations = {}

    for name, expected_e, expected_nu in (
        (
            bundle.transfer.bolt_material_name,
            210000.0,
            0.30,
        ),
        (
            bundle.transfer.nut_material_name,
            210000.0,
            0.30,
        ),
        (
            bundle.transfer.member_material_name,
            70000.0,
            0.33,
        ),
    ):
        prior = expectations.get(name)

        if prior is None:
            expectations[name] = (
                expected_e,
                expected_nu,
            )
        else:
            require(
                prior == (expected_e, expected_nu),
                f"Conflicting material expectation: {name}",
            )

    for name, (
        expected_e,
        expected_nu,
    ) in expectations.items():

        actual_e, actual_nu = elastic_card(
            deck_text,
            name,
        )

        require_close(
            f"{name} E",
            actual_e,
            expected_e,
            abs_tol=1.0e-6,
        )

        require_close(
            f"{name} nu",
            actual_nu,
            expected_nu,
            abs_tol=1.0e-12,
        )

    require(
        bundle.transfer.member_material_name
        not in {
            bundle.transfer.bolt_material_name,
            bundle.transfer.nut_material_name,
        },
        "Member and fastener material identities collapsed.",
    )

    # ----------------------------------------------------------
    # Immutable publication / deterministic reuse
    # ----------------------------------------------------------

    run_dir.mkdir(
        parents=False,
        exist_ok=True,
    )

    deck_path = run_dir / f"{trial2.run_id}.inp"

    if deck_path.exists():
        existing_sha = sha256(deck_path)

        require(
            existing_sha == candidate_sha,
            "Existing CAL_02 deck differs from adaptive-factory candidate.",
        )

        candidate.unlink()
    else:
        candidate.replace(deck_path)

    final_sha = sha256(deck_path)

    require(
        final_sha == candidate_sha,
        "Published CAL_02 deck SHA drift.",
    )

    preflight_path = (
        run_dir
        / "pilot_adaptive_factory_preflight.json"
    )

    preflight_record = {
        "scope": "phase3_diversified_pilot_only",
        "production_doe_authorization_claimed": False,
        "doe_wide_solver_launch_authorized": False,
        "dataset_admission_authorized": False,
        "sealed_holdouts_accessed": False,
        "solver_launched": False,

        "case_hash": CASE_HASH,
        "case_run_id": CASE_RUN_ID,
        "member_material_id": MEMBER_MATERIAL_ID,

        "predecessor": {
            "trial": jsonable(state["trial1"]),
            "dat_sha256": state["trial1_dat_sha"],
            "measurement": jsonable(
                state["measurement1"]
            ),
        },

        "adaptive_evaluation": jsonable(
            state["evaluation1"]
        ),

        "adaptive_plan": jsonable(
            state["plan"]
        ),

        "next_trial": jsonable(
            trial2
        ),

        "historical_mesh_reuse": {
            "source_case": "D-BND-001",
            "step_sha256": EXPECTED_STEP_SHA256,
            "mesh_sha256": EXPECTED_MESH_SHA256,
            "generalized_mesh_reuse_certified": False,
        },

        "deck": {
            "relative_path": str(
                deck_path.relative_to(ROOT)
            ),
            "sha256": final_sha,
        },
    }

    preflight_path.write_text(
        json.dumps(
            preflight_record,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )

    return (
        run_dir,
        deck_path,
        preflight_path,
        final_sha,
    )


def execute_trial2(
    state,
    run_dir: Path,
    deck_path: Path,
    preflight_path: Path,
    expected_deck_sha: str,
):

    # This is a PILOT execution gate, not Production-DOE authorization.
    # Recompute all adaptive evidence immediately before launch.

    fresh = build_state()

    require(
        fresh["trial1_dat_sha"]
        == state["trial1_dat_sha"],
        "CAL_01 DAT changed after preflight.",
    )

    require(
        fresh["trial2"].run_id
        == state["trial2"].run_id,
        "Adaptive Trial-2 identity changed after preflight.",
    )

    require_close(
        "Adaptive Trial-2 delta-T before launch",
        fresh["trial2"].delta_temperature_c,
        state["trial2"].delta_temperature_c,
        abs_tol=1.0e-12,
    )

    require(
        sha256(deck_path) == expected_deck_sha,
        "CAL_02 deck changed after preflight.",
    )

    for suffix in (
        ".dat",
        ".sta",
        ".cvg",
        ".frd",
        ".rout",
    ):
        require(
            not (run_dir / f"{state['trial2'].run_id}{suffix}").exists(),
            f"Refusing duplicate execution: {suffix} already exists.",
        )

    manifest_path = run_dir / "fem_run_manifest.json"

    require(
        not manifest_path.exists(),
        "Refusing duplicate execution: FEM manifest already exists.",
    )

    backend = (
        bundle_mod.PHASE2_CERTIFIED_FEM_PROFILE.backend
    )

    definition = CalculixJobDefinition(
        executable_relative_path=(
            state["transfer"].executable_relative_path
        ),
        job_name=state["trial2"].run_id,
        timeout_seconds=None,
    )

    print()
    print("PILOT EXECUTION AUTHORIZED BY EXPLICIT --execute")
    print("Production DOE authorization claimed: FALSE")
    print("Trial:", state["trial2"].run_id)
    print(
        "Delta-T:",
        repr(
            float(
                state["trial2"].delta_temperature_c
            )
        ),
    )
    print("Deck SHA-256:", expected_deck_sha)
    print()

    result = orchestrate_calculix_run(
        project_root=ROOT,
        input_path=deck_path,
        definition=definition,
        run_id=state["trial2"].run_id,
        case_hash=CASE_HASH,
        backend_policy_id=backend.policy_id,
        solver_name=backend.solver_name,
        solver_version=backend.solver_version,
        manifest_path=manifest_path,
    )

    print()
    print("=== PILOT ADAPTIVE FACTORY EXECUTION FINISHED ===")
    print("Run ID     :", state["trial2"].run_id)
    print("Disposition:", value_of(result.manifest.disposition))
    print("Manifest   :", manifest_path)


def main() -> int:

    parser = argparse.ArgumentParser(
        description=(
            "Pilot-only adaptive FEM factory for the first "
            "Phase-3 diversified aluminium case."
        )
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Execute exactly the currently required adaptive trial "
            "after full preflight."
        ),
    )

    args = parser.parse_args()

    print(
        "=== PHASE 3 DIVERSIFIED PILOT ADAPTIVE FACTORY ==="
    )
    print(
        "Mode:",
        "EXECUTE" if args.execute else "PREFLIGHT ONLY",
    )
    print()

    state = build_state()

    print("PASS: canonical diversified pilot resolved.")
    print("PASS: mixed-material FEM bundle verified.")
    print("PASS: STEP/mesh provenance verified.")
    print("PASS: CAL_01 immutable evidence verified.")
    print(
        "CAL_01 measured mean clamp force:",
        f"{state['measurement1'].mean_force_n:.6f} N",
    )

    print()
    print("=== ADAPTIVE DECISION ===")
    print(
        "Planner action :",
        value_of(state["plan"].action),
    )
    print(
        "Completed trial:",
        state["plan"].completed_run_id,
    )
    print(
        "Next trial     :",
        state["plan"].next_run_id,
    )
    print(
        "Source         :",
        value_of(state["trial2"].source),
    )
    print(
        "Delta-T        :",
        repr(
            float(
                state["trial2"].delta_temperature_c
            )
        ),
        "degC",
    )

    (
        run_dir,
        deck_path,
        preflight_path,
        deck_sha,
    ) = prepare_trial2(state)

    print()
    print("=== CAL_02 ADAPTIVE FACTORY PREFLIGHT ===")
    print("PASS")
    print("Run directory:", run_dir)
    print("Deck         :", deck_path)
    print("Deck SHA-256 :", deck_sha)
    print("Preflight    :", preflight_path)
    print("Solver launch:", "YES" if args.execute else "NO")
    print("Production DOE authorization claimed: FALSE")
    print("Dataset admission authorization: FALSE")
    print("Generalized mesh reuse certified: FALSE")

    if not args.execute:
        return 0

    execute_trial2(
        state,
        run_dir,
        deck_path,
        preflight_path,
        deck_sha,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
from __future__ import annotations

import argparse
import hashlib
import json
import re

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(
            message
        )


def sha256(
    path: Path,
) -> str:
    require(
        path.is_file(),
        f"Required file missing: {path}",
    )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(
                8 * 1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def load_json(
    path: Path,
):
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def relative(
    path: Path,
) -> str:
    return (
        path.resolve()
        .relative_to(ROOT)
        .as_posix()
    )


def encoded_json(
    payload: dict,
) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def write_immutable(
    path: Path,
    payload: dict,
) -> str:
    data = encoded_json(
        payload
    )

    digest = hashlib.sha256(
        data
    ).hexdigest()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if path.exists():
        require(
            path.read_bytes()
            == data,
            (
                "Immutable authorization conflict: "
                f"{path}"
            ),
        )

        return digest

    path.write_bytes(
        data
    )

    return digest


def repository_path(
    text: str,
) -> Path:
    candidate = (
        ROOT
        / text
    ).resolve()

    try:
        candidate.relative_to(
            ROOT
        )
    except ValueError as exc:
        raise RuntimeError(
            f"Path escapes repository: {text}"
        ) from exc

    return candidate


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--wave-id",
        required=True,
    )

    parser.add_argument(
        "--geometry-atlas",
        required=True,
    )

    parser.add_argument(
        "--observation-store",
        required=True,
    )

    parser.add_argument(
        "--predictor-policy",
        required=True,
    )

    parser.add_argument(
        "--approved-by",
        required=True,
    )

    return parser.parse_args()


args = parse_args()


require(
    re.fullmatch(
        r"TRM-DDOE-001-W\d{2}",
        args.wave_id,
    )
    is not None,
    (
        "Malformed governed wave identity: "
        f"{args.wave_id}"
    ),
)


wave_root = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
    / "waves"
    / args.wave_id
)

wave_path = (
    wave_root
    / "wave_plan.json"
)

trial_auth_path = (
    wave_root
    / "trial1_owner_authorization.json"
)

artifact_auth_path = (
    wave_root
    / "geometry_mesh_owner_authorization.json"
)

atlas_path = repository_path(
    args.geometry_atlas
)

observation_path = repository_path(
    args.observation_store
)

predictor_path = repository_path(
    args.predictor_policy
)

hardening_closure = (
    ROOT
    / "docs"
    / "phase3_pre_w03_hardening"
    / "slice6_closure.json"
)

campaign_root = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / "TRM-DDOE-001"
    / args.wave_id.rsplit(
        "-",
        1,
    )[-1]
)


# ==============================================================================
# Required immutable dependencies
# ==============================================================================

for path in (
    wave_path,
    atlas_path,
    observation_path,
    predictor_path,
    hardening_closure,
):
    require(
        path.is_file(),
        f"Required governed dependency missing: {path}",
    )


wave = load_json(
    wave_path
)

hardening = load_json(
    hardening_closure
)


# ==============================================================================
# Plan / hardening state
# ==============================================================================

require(
    wave.get(
        "schema"
    )
    == "threadrom.phase3_diversified_doe_wave_plan.v1",
    "Unexpected wave-plan schema.",
)

require(
    wave.get(
        "record_status"
    )
    == "FINAL",
    "Wave plan is not FINAL.",
)

require(
    wave.get(
        "selection_status"
    )
    == "FROZEN_SELECTION",
    "Wave selection is not frozen.",
)

require(
    wave.get(
        "campaign_id"
    )
    == "TRM-DDOE-001",
    "Campaign identity drift.",
)

require(
    wave.get(
        "wave_id"
    )
    == args.wave_id,
    "Wave identity drift.",
)

require(
    wave.get(
        "wave_size"
    )
    == 4,
    "Current governed preparation contract requires four cases.",
)

require(
    wave.get(
        "initial_trial_index"
    )
    == 1,
    "Current governed preparation contract requires Trial-1.",
)


for authority_key in (
    "preparation_authorized",
    "fem_execution_authorized",
    "adaptive_continuation_authorized",
    "full_physics_certification_authorized",
    "dataset_admission_authorized",
    "holdout_access_authorized",
    "artifact_retirement_authorized",
):
    require(
        wave.get(
            authority_key
        )
        is False,
        (
            "Wave plan itself unexpectedly contains authority: "
            f"{authority_key}"
        ),
    )


# ==============================================================================
# Frozen pre-W03 hardening contract
# ==============================================================================

EXPECTED_HARDENING_SHA256 = (
    "66a57419bbf42a1726bb4fb8519eee10"
    "c4889ebb63852d534c6c9992638826ee"
)

require(
    sha256(
        hardening_closure
    )
    == EXPECTED_HARDENING_SHA256,
    "Pre-W03 hardening closure SHA drift.",
)

require(
    hardening.get(
        "schema"
    )
    == (
        "threadrom.phase3_pre_w03_"
        "hardening_slice6_closure.v1"
    ),
    "Pre-W03 hardening closure schema drift.",
)

require(
    hardening.get(
        "slice"
    )
    == 6,
    "Pre-W03 hardening slice identity drift.",
)

require(
    hardening.get(
        "disposition"
    )
    == (
        "SLICE_6_PRODUCTION_HARDENING_"
        "REGRESSION_GATE_V1_CLOSED"
    ),
    "Pre-W03 hardening closure disposition drift.",
)

require(
    hardening.get(
        "pre_w03_disposition"
    )
    == (
        "PRE_W03_HARDENING_COMPLETE_"
        "W03_PREPARATION_READY"
    ),
    "Pre-W03 readiness disposition drift.",
)

claims = hardening.get(
    "certified_claims"
)

require(
    isinstance(
        claims,
        dict,
    ),
    "Pre-W03 certified claims missing.",
)

require(
    claims.get(
        "all_six_hardening_slices_closed"
    )
    is True,
    "All-six-slices closure claim absent.",
)

require(
    claims.get(
        "full_repository_regression_passed"
    )
    is True,
    "Full repository regression claim absent.",
)

require(
    claims.get(
        "w03_preparation_ready"
    )
    is True,
    "W03 preparation readiness claim absent.",
)

require(
    claims.get(
        "w03_execution_authorized"
    )
    is False,
    "W03 execution unexpectedly authorized.",
)

require(
    claims.get(
        "w03_launched"
    )
    is False,
    "W03 unexpectedly marked launched.",
)

require(
    claims.get(
        "calculix_launched_by_closure"
    )
    is False,
    "Slice-6 closure unexpectedly launched CalculiX.",
)

require(
    claims.get(
        "holdouts_sealed"
    )
    is True,
    "Holdout-sealed claim absent.",
)

require(
    claims.get(
        "rom_dataset_untouched"
    )
    is True,
    "ROM-dataset untouched claim absent.",
)


# ==============================================================================
# Refuse authorization over existing downstream execution state
# ==============================================================================

if campaign_root.exists():
    existing_files = tuple(
        path
        for path in campaign_root.rglob("*")
        if path.is_file()
    )
else:
    existing_files = ()


require(
    not existing_files,
    (
        "Downstream wave artifacts already exist before "
        "preparation authorization:\n"
        + "\n".join(
            str(path)
            for path in existing_files
        )
    ),
)


# ==============================================================================
# Exact four-case authorization scope
# ==============================================================================

selected = wave.get(
    "selected_cases"
)

require(
    isinstance(
        selected,
        list,
    )
    and len(
        selected
    )
    == 4,
    "Expected exactly four selected cases.",
)


authorized_cases = []

seen_case_ids = set()
seen_hashes = set()
seen_runs = set()


for row in sorted(
    selected,
    key=lambda item: item[
        "wave_order"
    ],
):
    case_id = row.get(
        "proposal_id"
    )

    case_hash = row.get(
        "case_hash"
    )

    case_run_id = row.get(
        "preparation_run_id"
    )

    trial_run_id = row.get(
        "trial_1_run_id"
    )

    require(
        isinstance(
            case_id,
            str,
        )
        and case_id.startswith(
            "TRM-DDOE-D-"
        ),
        "Malformed case identity.",
    )

    require(
        isinstance(
            case_hash,
            str,
        )
        and re.fullmatch(
            r"[0-9a-f]{64}",
            case_hash,
        )
        is not None,
        f"{case_id}: malformed case SHA.",
    )

    require(
        isinstance(
            case_run_id,
            str,
        )
        and re.fullmatch(
            r"trm_fem_[0-9a-f]{12}",
            case_run_id,
        )
        is not None,
        f"{case_id}: malformed case-run identity.",
    )

    require(
        trial_run_id
        == f"{case_run_id}_cal_01",
        f"{case_id}: Trial-1 identity drift.",
    )

    require(
        case_id not in seen_case_ids,
        f"Duplicate case identity: {case_id}",
    )

    require(
        case_hash not in seen_hashes,
        f"Duplicate case hash: {case_hash}",
    )

    require(
        case_run_id not in seen_runs,
        f"Duplicate case run: {case_run_id}",
    )

    seen_case_ids.add(
        case_id
    )

    seen_hashes.add(
        case_hash
    )

    seen_runs.add(
        case_run_id
    )

    authorized_cases.append(
        {
            "wave_order": row[
                "wave_order"
            ],
            "case_id": case_id,
            "case_hash": case_hash,
            "case_run_id": case_run_id,
            "trial_1_run_id": trial_run_id,
        }
    )


# ==============================================================================
# Dependency fingerprints
# ==============================================================================

wave_sha = sha256(
    wave_path
)

atlas_sha = sha256(
    atlas_path
)

observation_sha = sha256(
    observation_path
)

predictor_sha = sha256(
    predictor_path
)

hardening_sha = sha256(
    hardening_closure
)


bound_dependencies = {
    "wave_plan": {
        "path": relative(
            wave_path
        ),
        "sha256": wave_sha,
    },
    "geometry_mesh_atlas": {
        "path": relative(
            atlas_path
        ),
        "sha256": atlas_sha,
    },
    "calibration_observation_store": {
        "path": relative(
            observation_path
        ),
        "sha256": observation_sha,
    },
    "trial_1_predictor_policy": {
        "path": relative(
            predictor_path
        ),
        "sha256": predictor_sha,
    },
    "pre_w03_hardening_closure": {
        "path": relative(
            hardening_closure
        ),
        "sha256": hardening_sha,
    },
}


# ==============================================================================
# Trial-1 PREPARATION authority
#
# IMPORTANT:
# This authorizes creation of the deterministic CAL_01 preparation artifact.
# It deliberately grants zero solver execution authority.
# ==============================================================================

trial_authorization = {
    "schema": (
        "threadrom.phase3_governed_trial1_"
        "preparation_owner_authorization.v1"
    ),
    "record_status": "FINAL",
    "approval_status": "OWNER_APPROVED",
    "approved_by": args.approved_by,
    "authorization_type": (
        "OWNER_TRIAL1_PREPARATION_ONLY_AUTHORIZATION"
    ),
    "campaign_id": "TRM-DDOE-001",
    "wave_id": args.wave_id,
    "wave_plan_sha256": wave_sha,
    "authorized_case_count": 4,
    "authorized_cases": authorized_cases,
    "bound_dependencies": bound_dependencies,
    "permissions": {
        "prepare_trial_1": True,
        "execute_trial_1": False,
        "additional_trials": False,
        "adaptive_continuation": False,
        "full_physics_certification": False,
        "dataset_admission": False,
        "artifact_retirement": False,
        "holdout_access": False,
        "surrogate_training": False,
    },
    "trial_1_policy": {
        "trial_index": 1,
        "knowledge_store_required": True,
        "predictor_policy_required": True,
        "governed_fem_neighbor_reuse_allowed": True,
        "analytical_fallback_allowed": True,
        "duplicate_solver_execution_forbidden": True,
        "solver_launch_by_preparation": False,
    },
    "scope_boundary": (
        "This authorization permits deterministic preparation of "
        "CAL_01 artifacts for exactly the four frozen wave cases. "
        "It does not authorize CalculiX execution, CAL_02+, adaptive "
        "continuation, physics certification, ROM admission, holdout "
        "access, artifact retirement, or surrogate training."
    ),
}


# ==============================================================================
# Geometry / mesh PREPARATION authority
#
# Classification is intentionally runtime-derived from the immutable Atlas:
#
# exact Atlas hit  -> mandatory reuse, SHA verified, no regeneration
# Atlas miss       -> fresh generation is allowed
#
# Atlas V1 itself remains immutable.
# ==============================================================================

artifact_authorization = {
    "schema": (
        "threadrom.phase3_governed_geometry_mesh_"
        "preparation_owner_authorization.v1"
    ),
    "record_status": "FINAL",
    "approval_status": "OWNER_APPROVED",
    "approved_by": args.approved_by,
    "authorization_type": (
        "OWNER_GEOMETRY_MESH_PREPARATION_ONLY_AUTHORIZATION"
    ),
    "campaign_id": "TRM-DDOE-001",
    "wave_id": args.wave_id,
    "wave_plan_sha256": wave_sha,
    "authorized_case_count": 4,
    "authorized_cases": authorized_cases,
    "bound_dependencies": bound_dependencies,
    "classification_contract": {
        "mode": (
            "RUNTIME_EXACT_ATLAS_REUSE_OR_FRESH_GENERATION_ON_MISS"
        ),
        "exact_atlas_hit_action": (
            "MANDATORY_REUSE_VERIFIED_ARTIFACT"
        ),
        "atlas_miss_action": (
            "FRESH_GENERATION_AUTHORIZED"
        ),
        "partial_identity_match_action": (
            "FAIL_CLOSED"
        ),
        "artifact_sha_mismatch_action": (
            "FAIL_CLOSED"
        ),
    },
    "permissions": {
        # Historical-compatible surface:
        "generate_geometry_for_fresh_cases": True,
        "generate_mesh_for_fresh_cases": True,
        "regenerate_geometry_for_reuse_cases": False,
        "regenerate_mesh_for_reuse_cases": False,

        # Generic post-hardening surface:
        "resolve_exact_atlas_reuse": True,
        "generate_geometry_on_atlas_miss": True,
        "generate_mesh_on_atlas_miss": True,
        "mutate_frozen_atlas_v1": False,
        "overwrite_historical_geometry": False,
        "overwrite_historical_mesh": False,
        "delete_historical_artifacts": False,
        "solver_execution": False,
        "holdout_access": False,
    },
    "scope_boundary": (
        "This authorization permits exact Atlas lookup and, only when "
        "no exact governed reusable geometry/mesh artifact exists, fresh "
        "geometry/mesh generation for the four frozen wave cases. Exact "
        "reusable assets must be reused and SHA verified. Frozen Atlas V1 "
        "and historical artifacts must not be mutated. No solver execution "
        "or holdout access is authorized."
    ),
}


trial_sha = write_immutable(
    trial_auth_path,
    trial_authorization,
)

artifact_sha = write_immutable(
    artifact_auth_path,
    artifact_authorization,
)


# ==============================================================================
# Immutable readback / safety verification
# ==============================================================================

trial_readback = load_json(
    trial_auth_path
)

artifact_readback = load_json(
    artifact_auth_path
)


require(
    trial_readback
    == trial_authorization,
    "Trial-1 authorization readback drift.",
)

require(
    artifact_readback
    == artifact_authorization,
    "Geometry/mesh authorization readback drift.",
)


require(
    trial_readback[
        "permissions"
    ][
        "prepare_trial_1"
    ]
    is True,
    "Trial-1 preparation authority absent.",
)

require(
    trial_readback[
        "permissions"
    ][
        "execute_trial_1"
    ]
    is False,
    "Trial-1 execution was accidentally authorized.",
)

require(
    trial_readback[
        "permissions"
    ][
        "additional_trials"
    ]
    is False,
    "CAL_02+ was accidentally authorized.",
)

require(
    artifact_readback[
        "permissions"
    ][
        "mutate_frozen_atlas_v1"
    ]
    is False,
    "Frozen Atlas mutation was accidentally authorized.",
)

require(
    artifact_readback[
        "permissions"
    ][
        "regenerate_geometry_for_reuse_cases"
    ]
    is False
    and artifact_readback[
        "permissions"
    ][
        "regenerate_mesh_for_reuse_cases"
    ]
    is False,
    "Exact-reuse regeneration was accidentally authorized.",
)


print()
print("=" * 108)
print(
    "THREADROM - GOVERNED WAVE PREPARATION AUTHORIZATION"
)
print("=" * 108)
print(
    "Wave ID                    :",
    args.wave_id,
)
print(
    "Wave plan SHA              :",
    wave_sha,
)
print(
    "Authorized cases           : 4"
)
print(
    "Trial-1 auth SHA           :",
    trial_sha,
)
print(
    "Geometry/mesh auth SHA     :",
    artifact_sha,
)
print()
print(
    "Prepare CAL_01             : AUTHORIZED"
)
print(
    "Execute CAL_01             : NOT AUTHORIZED"
)
print(
    "CAL_02+                    : NOT AUTHORIZED"
)
print(
    "Atlas exact reuse          : AUTHORIZED / MANDATORY"
)
print(
    "Fresh geometry on miss     : AUTHORIZED"
)
print(
    "Fresh mesh on miss         : AUTHORIZED"
)
print(
    "Regenerate exact reuse     : FORBIDDEN"
)
print(
    "Mutate frozen Atlas V1     : FORBIDDEN"
)
print(
    "Adaptive continuation      : NOT AUTHORIZED"
)
print(
    "Physics certification      : NOT AUTHORIZED"
)
print(
    "Dataset admission          : NOT AUTHORIZED"
)
print(
    "Holdout access             : NOT AUTHORIZED"
)
print(
    "Solver execution           : NOT AUTHORIZED"
)
print("=" * 108)
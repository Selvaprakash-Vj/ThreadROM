from __future__ import annotations

import hashlib
import json

from pathlib import Path


ROOT = Path(r"D:\ThreadROM")

CAMPAIGN_ROOT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_cp8_production_doe"
    / "TRM-PDOE-C01"
)

SOLVER_ROOT = (
    CAMPAIGN_ROOT
    / "solver_preparation"
)

ROLLOUT_CERT_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_rollout_preparation_certification.json"
)

WAVE_MANIFEST_PATH = (
    CAMPAIGN_ROOT
    / "cp8_restart_v2_wave_01_preparation_manifest.json"
)

OUTPUT_PATH = (
    CAMPAIGN_ROOT
    / "cp8_restart_v2_wave_01_execution_certification.json"
)


EXPECTED_ROLLOUT_CERT_SHA256 = (
    "a11662817427d9131b92f798e953d116"
    "269ad672c49434365a75f68dac4709a7"
)

EXPECTED_WAVE_MANIFEST_SHA256 = (
    "081db1e1b27424b509b82476716ed6f9"
    "6ab5bd96de5f6b91c7730d11dba2c37b"
)

EXPECTED_RESILIENCE_POLICY_ID = (
    "phase3_cp8_thermal_calibration_restart_"
    "v2_windows_nonoverlay"
)

EXPECTED_CASE_IDS = (
    "D-INT-001",
    "D-INT-003",
    "D-INT-004",
    "D-INT-005",
)

INTERRUPTED_CASE_IDS = {
    "D-INT-001",
    "D-INT-003",
    "D-INT-004",
}

SOLVER_SUFFIXES = {
    ".dat",
    ".frd",
    ".sta",
    ".cvg",
    ".12d",
    ".eig",
    ".equ",
    ".rout",
}


def sha256(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)

    if path.stat().st_size <= 0:
        raise RuntimeError(
            f"Required artifact is empty: {path}"
        )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def require_sha256(
    path: Path,
    expected: str,
    label: str,
) -> str:
    actual = sha256(path)

    if actual != expected:
        raise RuntimeError(
            f"{label} SHA drift.\n"
            f"Expected: {expected}\n"
            f"Actual  : {actual}\n"
            f"Path    : {path}"
        )

    return actual


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def relative(path: Path) -> str:
    return (
        path.resolve()
        .relative_to(ROOT.resolve())
        .as_posix()
    )


def write_immutable_json(
    path: Path,
    payload: dict,
) -> tuple[str, str]:
    serialized = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    if path.exists():
        existing = path.read_text(
            encoding="utf-8"
        )

        if existing != serialized:
            raise RuntimeError(
                "Immutable restart-v2 certification "
                "already exists with different content. "
                f"Refusing overwrite: {path}"
            )

        action = "UNCHANGED / IDENTICAL"

    else:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = path.with_suffix(
            ".json.tmp"
        )

        temporary.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )

        temporary.replace(path)

        action = "CREATED"

    record_sha = sha256(path)

    sidecar = path.with_suffix(
        ".sha256"
    )

    expected_sidecar = (
        f"{record_sha}  {path.name}\n"
    )

    if sidecar.exists():
        observed = sidecar.read_text(
            encoding="ascii"
        )

        if observed != expected_sidecar:
            raise RuntimeError(
                "Certification SHA sidecar drift: "
                f"{sidecar}"
            )

    else:
        sidecar.write_text(
            expected_sidecar,
            encoding="ascii",
            newline="\n",
        )

    return action, record_sha


def find_unique(
    rows: list[dict],
    case_id: str,
    *,
    label: str,
) -> dict:
    matches = [
        row
        for row in rows
        if row["case_id"] == case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected one {label}; "
            f"found {len(matches)}."
        )

    return matches[0]


def solver_outputs_present(
    run_dir: Path,
) -> tuple[str, ...]:
    if not run_dir.exists():
        return ()

    found = []

    for path in run_dir.iterdir():
        if not path.is_file():
            continue

        if (
            path.name == "fem_run_manifest.json"
            or path.suffix.lower()
            in SOLVER_SUFFIXES
        ):
            found.append(path.name)

    return tuple(sorted(found))


def deck_structure(
    path: Path,
) -> tuple[int, tuple[str, ...], bool]:
    lines = path.read_text(
        encoding="utf-8-sig"
    ).splitlines()

    step_count = sum(
        1
        for line in lines
        if line.strip().upper().startswith(
            "*STEP"
        )
    )

    restart_lines = tuple(
        line.strip()
        for line in lines
        if line.strip().upper().startswith(
            "*RESTART"
        )
    )

    overlay_present = any(
        ",OVERLAY"
        in line.strip().upper()
        for line in lines
        if line.strip().upper().startswith(
            "*RESTART"
        )
    )

    return (
        step_count,
        restart_lines,
        overlay_present,
    )


# ============================================================
# 1. LOCK IMMUTABLE INPUT EVIDENCE
# ============================================================

rollout_cert_sha = require_sha256(
    ROLLOUT_CERT_PATH,
    EXPECTED_ROLLOUT_CERT_SHA256,
    "Frozen V2.1 rollout certification",
)

wave_manifest_sha = require_sha256(
    WAVE_MANIFEST_PATH,
    EXPECTED_WAVE_MANIFEST_SHA256,
    "CP8 restart-v2 wave preparation manifest",
)

certifier_path = Path(__file__).resolve()
certifier_sha = sha256(
    certifier_path
)


# ============================================================
# 2. VERIFY INHERITED FROZEN ROLLOUT AUTHORIZATION
# ============================================================

rollout_cert = load_json(
    ROLLOUT_CERT_PATH
)

if (
    rollout_cert.get("record_status")
    != "FINAL"
    or rollout_cert.get(
        "overall_disposition"
    )
    != (
        "V2_1_ROLLOUT_PREPARATION_"
        "CERTIFIED_READY_FOR_FEM"
    )
):
    raise RuntimeError(
        "Source V2.1 rollout certification "
        "is not FINAL / READY_FOR_FEM."
    )

source_authorization = rollout_cert[
    "rollout_execution_authorization"
]

if (
    source_authorization.get(
        "authorized"
    )
    is not True
    or source_authorization.get(
        "predictor"
    )
    != "warm_start_delta_t_v2_1"
    or source_authorization.get(
        "authorized_trial"
    )
    != "V2_1_FIRST_SHOT_ONLY"
    or int(
        source_authorization[
            "maximum_concurrent_calculix_runs"
        ]
    )
    != 4
    or source_authorization.get(
        "v2_1_model_must_remain_frozen"
    )
    is not True
    or source_authorization.get(
        "blind_holdout_execution_authorized"
    )
    is not False
    or source_authorization.get(
        "blind_holdouts_remain_sealed"
    )
    is not True
):
    raise RuntimeError(
        "Source V2.1 rollout authorization drift."
    )

authorized_source_ids = set(
    source_authorization[
        "authorized_case_ids"
    ]
)

if not set(
    EXPECTED_CASE_IDS
).issubset(
    authorized_source_ids
):
    raise RuntimeError(
        "Restart-v2 wave contains a case outside "
        "the original certified rollout scope."
    )


# ============================================================
# 3. VERIFY ZERO-SOLVE RESTART-V2 WAVE MANIFEST
# ============================================================

wave = load_json(
    WAVE_MANIFEST_PATH
)

if (
    wave.get("record_status")
    != "FINAL"
    or wave.get(
        "overall_disposition"
    )
    != (
        "CP8_RESTART_V2_WAVE_PREPARATION_PASS_"
        "AWAITING_INDEPENDENT_EXECUTION_CERTIFICATION"
    )
):
    raise RuntimeError(
        "Restart-v2 wave preparation is not "
        "the expected FINAL zero-solve record."
    )

if (
    wave["wave"]["wave_id"]
    != "CP8-WSV21-RV2-WAVE01"
    or int(
        wave["wave"]["case_count"]
    )
    != 4
    or tuple(
        wave["wave"]["case_ids"]
    )
    != EXPECTED_CASE_IDS
    or int(
        wave["wave"][
            "maximum_future_concurrency"
        ]
    )
    != 4
):
    raise RuntimeError(
        "Restart-v2 wave identity/scope drift."
    )

if (
    wave["governance"][
        "rollout_certification_sha256"
    ]
    != rollout_cert_sha
    or wave["governance"][
        "v2_1_model_remained_frozen"
    ]
    is not True
    or wave["governance"][
        "holdout_accessed"
    ]
    is not False
):
    raise RuntimeError(
        "Restart-v2 wave governance drift."
    )

replacement = wave[
    "replacement_semantics"
]

if (
    replacement.get(
        "all_cases_remain_trial_1"
    )
    is not True
    or replacement.get(
        "no_new_calibration_attempt_created"
    )
    is not True
    or replacement.get(
        "historical_runs_preserved"
    )
    is not True
    or replacement.get(
        "historical_restart_resume_attempted"
    )
    is not False
    or replacement.get(
        "fresh_full_solve_siblings_required"
    )
    is not True
):
    raise RuntimeError(
        "Restart-v2 replacement semantics drift."
    )

policy = wave[
    "restart_v2_policy"
]

if (
    policy["policy_id"]
    != EXPECTED_RESILIENCE_POLICY_ID
    or int(
        policy["checkpoint_count"]
    )
    != 20
    or int(
        policy[
            "restart_write_frequency_steps"
        ]
    )
    != 1
    or policy["overlay_latest"]
    is not False
    or policy[
        "preserve_total_pseudo_time"
    ]
    is not True
):
    raise RuntimeError(
        "Restart-v2 execution policy drift."
    )

zero_solve = wave[
    "zero_solve_evidence"
]

if (
    zero_solve.get(
        "calculix_invoked"
    )
    is not False
    or zero_solve.get(
        "solver_results_read_for_replacement"
    )
    is not False
    or zero_solve.get(
        "execution_authorized"
    )
    is not False
    or zero_solve.get(
        "independent_execution_certification_required"
    )
    is not True
    or zero_solve.get(
        "blind_holdout_accessed"
    )
    is not False
):
    raise RuntimeError(
        "Zero-solve wave semantics drift."
    )


# ============================================================
# 4. INDEPENDENTLY VERIFY ALL FOUR REPLACEMENT SIBLINGS
# ============================================================

wave_rows = wave[
    "cases"
]

if len(wave_rows) != 4:
    raise RuntimeError(
        "Restart-v2 wave must contain exactly "
        "four cases."
    )

source_rows = rollout_cert[
    "certified_rollout_cases"
]

certified_rows = []

for case_id in EXPECTED_CASE_IDS:
    row = find_unique(
        wave_rows,
        case_id,
        label="restart-v2 wave row",
    )

    source = find_unique(
        source_rows,
        case_id,
        label="frozen V2.1 source row",
    )

    case_hash = row[
        "case_hash"
    ]

    canonical_case_run_id = (
        f"trm_fem_{case_hash[:12]}"
    )

    expected_source_run_id = (
        f"{canonical_case_run_id}"
        "_cal_01_wsv21"
    )

    expected_rv2_run_id = (
        f"{canonical_case_run_id}"
        "_cal_01_wsv21_rv2"
    )

    if (
        int(row["trial_index"]) != 1
        or row["source_trial_run_id"]
        != expected_source_run_id
        or row["restart_v2_trial_run_id"]
        != expected_rv2_run_id
    ):
        raise RuntimeError(
            f"{case_id}: Trial-1 replacement "
            "identity drift."
        )

    if (
        source["case_hash"]
        != case_hash
        or source["run_id"]
        != expected_source_run_id
    ):
        raise RuntimeError(
            f"{case_id}: source rollout identity "
            "drift."
        )

    frozen_dt = float(
        row[
            "frozen_delta_temperature_c"
        ]
    )

    if (
        float(
            source[
                "predicted_delta_temperature_c"
            ]
        )
        != frozen_dt
    ):
        raise RuntimeError(
            f"{case_id}: frozen V2.1 delta-T drift."
        )

    deck_path = (
        ROOT
        / row["deck_relative_path"]
    )

    prep_path = (
        ROOT
        / row[
            "preparation_relative_path"
        ]
    )

    expected_run_dir = (
        SOLVER_ROOT
        / canonical_case_run_id
        / expected_rv2_run_id
    )

    if (
        deck_path.parent.resolve()
        != expected_run_dir.resolve()
        or prep_path.parent.resolve()
        != expected_run_dir.resolve()
        or deck_path.name
        != f"{expected_rv2_run_id}.inp"
    ):
        raise RuntimeError(
            f"{case_id}: restart-v2 filesystem "
            "identity drift."
        )

    deck_sha = sha256(
        deck_path
    )

    prep_sha = sha256(
        prep_path
    )

    if deck_sha != row[
        "deck_sha256"
    ]:
        raise RuntimeError(
            f"{case_id}: restart-v2 deck SHA drift."
        )

    if prep_sha != row[
        "preparation_sha256"
    ]:
        raise RuntimeError(
            f"{case_id}: restart-v2 preparation "
            "SHA drift."
        )

    prep = load_json(
        prep_path
    )

    if (
        prep.get("record_status")
        != "FINAL"
        or prep.get(
            "overall_disposition"
        )
        != (
            "CP8_RESTART_V2_SIBLING_PREPARATION_PASS_"
            "AWAITING_INDEPENDENT_EXECUTION_CERTIFICATION"
        )
    ):
        raise RuntimeError(
            f"{case_id}: restart-v2 per-case "
            "preparation disposition drift."
        )

    case_record = prep[
        "case"
    ]

    if (
        case_record["case_id"]
        != case_id
        or case_record["case_hash"]
        != case_hash
        or int(
            case_record["trial_index"]
        )
        != 1
        or case_record[
            "source_v2_1_trial_run_id"
        ]
        != expected_source_run_id
        or case_record[
            "restart_v2_trial_run_id"
        ]
        != expected_rv2_run_id
    ):
        raise RuntimeError(
            f"{case_id}: per-case identity drift."
        )

    semantics = prep[
        "replacement_semantics"
    ]

    if (
        semantics[
            "calibration_trial_identity"
        ]
        != "TRIAL_1"
        or semantics[
            "new_calibration_attempt"
        ]
        is not False
        or semantics[
            "physics_prediction_changed"
        ]
        is not False
        or semantics[
            "historical_source_preserved"
        ]
        is not True
        or semantics[
            "resume_from_historical_checkpoint"
        ]
        is not False
        or semantics[
            "fresh_full_solve_required"
        ]
        is not True
        or float(
            semantics[
                "frozen_v2_1_delta_temperature_c"
            ]
        )
        != frozen_dt
    ):
        raise RuntimeError(
            f"{case_id}: Trial-1 replacement "
            "semantics drift."
        )

    if (
        prep["governance"][
            "rollout_certification_sha256"
        ]
        != rollout_cert_sha
        or prep["governance"][
            "v2_1_model_refit_performed"
        ]
        is not False
        or prep["governance"][
            "holdout_accessed"
        ]
        is not False
    ):
        raise RuntimeError(
            f"{case_id}: per-case governance drift."
        )

    historical = prep[
        "historical_source"
    ]

    source_deck = (
        ROOT
        / historical[
            "deck_relative_path"
        ]
    )

    source_prep = (
        ROOT
        / historical[
            "preparation_relative_path"
        ]
    )

    if (
        historical["run_id"]
        != expected_source_run_id
        or sha256(source_deck)
        != historical[
            "deck_sha256"
        ]
        or sha256(source_prep)
        != historical[
            "preparation_sha256"
        ]
    ):
        raise RuntimeError(
            f"{case_id}: immutable historical "
            "source evidence drift."
        )

    if (
        historical["deck_sha256"]
        != source["deck_sha256"]
        or historical[
            "preparation_sha256"
        ]
        != source[
            "preparation_sha256"
        ]
    ):
        raise RuntimeError(
            f"{case_id}: restart-v2/source rollout "
            "provenance mismatch."
        )

    (
        historical_step_count,
        historical_restart_lines,
        historical_overlay,
    ) = deck_structure(
        source_deck
    )

    if (
        historical_step_count != 1
        or historical_restart_lines
        or historical_overlay
    ):
        raise RuntimeError(
            f"{case_id}: historical pre-resilience "
            "deck structure drift."
        )

    expected_historical_state = (
        "INTERRUPTED_WITH_PARTIAL_OUTPUTS"
        if case_id
        in INTERRUPTED_CASE_IDS
        else "PREPARED_NOT_EXECUTED"
    )

    if historical[
        "historical_state"
    ] != expected_historical_state:
        raise RuntimeError(
            f"{case_id}: historical-state "
            "classification drift."
        )

    trial = prep[
        "trial"
    ]

    if (
        int(trial["trial_index"]) != 1
        or trial["run_id"]
        != expected_rv2_run_id
        or float(
            trial[
                "delta_temperature_c"
            ]
        )
        != frozen_dt
    ):
        raise RuntimeError(
            f"{case_id}: serialized Trial-1 "
            "definition drift."
        )

    resilience = prep[
        "execution_resilience"
    ]

    if (
        resilience[
            "policy_id"
        ]
        != EXPECTED_RESILIENCE_POLICY_ID
        or int(
            resilience[
                "checkpoint_count"
            ]
        )
        != 20
        or resilience[
            "restart_write_enabled"
        ]
        is not True
        or int(
            resilience[
                "restart_write_frequency_steps"
            ]
        )
        != 1
        or resilience[
            "overlay_latest"
        ]
        is not False
        or resilience[
            "preserve_total_pseudo_time"
        ]
        is not True
        or resilience[
            "live_restart_smoke_previously_verified"
        ]
        is not True
    ):
        raise RuntimeError(
            f"{case_id}: execution-resilience "
            "evidence drift."
        )

    deck_record = prep[
        "deck"
    ]

    if (
        deck_record["sha256"]
        != deck_sha
        or int(
            deck_record[
                "checkpoint_count"
            ]
        )
        != 20
        or int(
            deck_record[
                "restart_write_count"
            ]
        )
        != 1
        or deck_record[
            "execution_resilience_policy_id"
        ]
        != EXPECTED_RESILIENCE_POLICY_ID
        or float(
            deck_record[
                "delta_temperature_c"
            ]
        )
        != frozen_dt
    ):
        raise RuntimeError(
            f"{case_id}: recorded restart-v2 "
            "deck metadata drift."
        )

    (
        step_count,
        restart_lines,
        overlay_present,
    ) = deck_structure(
        deck_path
    )

    if (
        step_count != 20
        or restart_lines
        != (
            "*RESTART,WRITE,FREQUENCY=1",
        )
        or overlay_present
    ):
        raise RuntimeError(
            f"{case_id}: restart-v2 deck "
            "structure certification failed."
        )

    execution = prep[
        "execution_authorization"
    ]

    if (
        execution[
            "calculix_invoked_by_this_record"
        ]
        is not False
        or execution[
            "solver_results_read_for_replacement"
        ]
        is not False
        or execution[
            "execution_authorized_by_this_record"
        ]
        is not False
        or execution[
            "requires_independent_pre_execution_certification"
        ]
        is not True
        or int(
            execution[
                "maximum_future_concurrency"
            ]
        )
        != 4
        or execution[
            "blind_holdout_execution_authorized"
        ]
        is not False
    ):
        raise RuntimeError(
            f"{case_id}: pre-certification "
            "execution semantics drift."
        )

    existing_outputs = (
        solver_outputs_present(
            expected_run_dir
        )
    )

    if existing_outputs:
        raise RuntimeError(
            f"{case_id}: solver output already "
            "exists in restart-v2 sibling. "
            "Execution certification refused:\n"
            + "\n".join(
                existing_outputs
            )
        )

    accepted_evidence = (
        SOLVER_ROOT
        / canonical_case_run_id
        / "production_doe_accepted_fem_evidence.json"
    )

    if accepted_evidence.exists():
        raise RuntimeError(
            f"{case_id}: governed accepted FEM "
            "evidence already exists. Duplicate "
            "Trial-1 execution authorization refused."
        )

    certified_rows.append(
        {
            "case_id": case_id,
            "case_hash": case_hash,
            "trial_index": 1,
            "source_v2_1_trial_run_id": (
                expected_source_run_id
            ),
            "authorized_restart_v2_run_id": (
                expected_rv2_run_id
            ),
            "frozen_delta_temperature_c": (
                frozen_dt
            ),
            "deck_relative_path": (
                relative(deck_path)
            ),
            "deck_sha256": deck_sha,
            "preparation_relative_path": (
                relative(prep_path)
            ),
            "preparation_sha256": prep_sha,
            "checkpoint_count": 20,
            "restart_keyword": (
                "*RESTART,WRITE,FREQUENCY=1"
            ),
            "overlay_latest": False,
            "historical_state": (
                expected_historical_state
            ),
        }
    )


# ============================================================
# 5. FINAL INDEPENDENT EXECUTION CERTIFICATION
# ============================================================

record = {
    "schema_version": 1,
    "record_id": (
        "TRM-P3-CP8-WSV21-RV2-WAVE01-"
        "EXECUTION-CERT-P01"
    ),
    "record_status": "FINAL",
    "campaign_id": "TRM-PDOE-C01",

    "source_evidence": {
        "frozen_rollout_certification": {
            "relative_path": (
                relative(
                    ROLLOUT_CERT_PATH
                )
            ),
            "sha256": (
                rollout_cert_sha
            ),
        },
        "restart_v2_wave_preparation": {
            "relative_path": (
                relative(
                    WAVE_MANIFEST_PATH
                )
            ),
            "sha256": (
                wave_manifest_sha
            ),
        },
        "certifier": {
            "relative_path": (
                relative(
                    certifier_path
                )
            ),
            "sha256": (
                certifier_sha
            ),
        },
    },

    "independent_restart_v2_verification": {
        "case_count": 4,
        "case_ids": list(
            EXPECTED_CASE_IDS
        ),
        "all_cases_remain_trial_1": True,
        "frozen_v2_1_predictions_preserved": True,
        "all_source_decks_verified": True,
        "all_source_preparations_verified": True,
        "all_restart_v2_deck_hashes_verified": True,
        "all_restart_v2_preparation_hashes_verified": True,
        "all_restart_v2_decks_have_20_checkpoints": True,
        "all_restart_keywords_nonoverlay": True,
        "historical_interrupted_runs_preserved": True,
        "historical_restart_resume_used": False,
        "fresh_full_replacement_solves_required": True,
        "v2_1_refit_performed": False,
        "blind_holdout_accessed": False,
    },

    "certified_restart_v2_cases": (
        certified_rows
    ),

    "zero_solve_verification": {
        "prepared_case_count": 4,
        "solver_outputs_detected_in_restart_v2_siblings": False,
        "fem_run_manifests_present": False,
        "solver_results_read": False,
        "calculix_invoked": False,
        "accepted_case_evidence_already_present": False,
        "v2_1_refit_performed": False,
        "blind_holdout_accessed": False,
    },

    "execution_authorization": {
        "authorized": True,
        "authorization_basis": (
            "FROZEN_V2_1_ROLLOUT_AUTHORIZATION_PLUS_"
            "INDEPENDENT_RESTART_V2_ZERO_SOLVE_CERTIFICATION"
        ),
        "predictor": (
            "warm_start_delta_t_v2_1"
        ),
        "scope": (
            "CP8_RESTART_V2_WAVE01_"
            "TRIAL1_REPLACEMENT_SIBLINGS_ONLY"
        ),
        "authorized_case_ids": list(
            EXPECTED_CASE_IDS
        ),
        "authorized_run_ids": [
            row[
                "authorized_restart_v2_run_id"
            ]
            for row in certified_rows
        ],
        "authorized_trial": (
            "V2_1_TRIAL_1_REPLACEMENT_EXECUTION_ONLY"
        ),
        "replacement_execution_is_new_calibration_attempt": False,
        "fresh_full_solve_required": True,
        "historical_checkpoint_resume_authorized": False,
        "maximum_concurrent_calculix_runs": 4,
        "trial_2_only_after_governed_first_shot_reject": True,
        "v2_1_model_must_remain_frozen": True,
        "blind_holdout_execution_authorized": False,
        "blind_holdouts_remain_sealed": True,
    },

    "evidence_semantics": {
        "restart_v2_preparation_independently_verified": True,
        "solver_execution_performed_by_certifier": False,
        "production_fem_execution_now_authorized": True,
        "authorization_limited_to_four_certified_restart_v2_runs": True,
        "replacement_runs_remain_original_trial_1_physics": True,
        "replacement_runs_are_not_additional_calibration_attempts": True,
        "historical_partial_outputs_not_used_as_final_physics_evidence": True,
        "holdout_execution_authorized": False,
    },

    "overall_disposition": (
        "CP8_RESTART_V2_WAVE_EXECUTION_"
        "CERTIFIED_READY_FOR_FEM"
    ),
}


action, record_sha = (
    write_immutable_json(
        OUTPUT_PATH,
        record,
    )
)


print("=" * 132)
print(
    "THREADROM - CP8 RESTART-V2 "
    "WAVE EXECUTION CERTIFICATION"
)
print("=" * 132)

print()
print(
    "Source rollout cert SHA256    :",
    rollout_cert_sha,
)
print(
    "Restart-v2 wave manifest SHA  :",
    wave_manifest_sha,
)

print()
print(
    "Cases independently certified :",
    len(certified_rows),
)

for row in certified_rows:
    print(
        f"{row['case_id']:12s} | "
        f"{row['authorized_restart_v2_run_id']} | "
        f"dT={row['frozen_delta_temperature_c']:.9f} C | "
        f"deck={row['deck_sha256'][:16]}..."
    )

print()
print(
    "All remain Trial 1            : YES"
)
print(
    "All restart checkpoints       : 20"
)
print(
    "Restart OVERLAY               : NO"
)
print(
    "Historical partial runs       : PRESERVED"
)
print(
    "Historical checkpoint resume  : NO"
)
print(
    "CalculiX invoked              : NO"
)
print(
    "Solver results read           : NO"
)
print(
    "V2.1 refit                    : NO"
)
print(
    "Blind holdouts accessed       : NO"
)

print()
print(
    "Restart-v2 FEM execution      : AUTHORIZED"
)
print(
    "Maximum concurrency           : 4"
)
print(
    "Authorized scope              : FOUR RV2 TRIAL-1 SIBLINGS ONLY"
)
print(
    "Trial 2                       : ONLY AFTER GOVERNED REJECT"
)
print(
    "Blind holdout execution       : NOT AUTHORIZED"
)

print()
print(
    "Certification record          :",
    OUTPUT_PATH,
)
print(
    "Certification SHA256          :",
    record_sha,
)
print(
    "Record action                 :",
    action,
)

print()
print(
    "OVERALL DISPOSITION           : "
    "CP8_RESTART_V2_WAVE_EXECUTION_"
    "CERTIFIED_READY_FOR_FEM"
)
print("=" * 132)

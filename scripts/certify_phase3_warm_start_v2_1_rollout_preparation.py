from __future__ import annotations

import hashlib
import json
import math
import tomllib

from pathlib import Path

from threadrom.case.resolver import resolve_case

from threadrom.factory.preload_calibration_seed import (
    derive_analytical_thermal_preload_seed,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
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
    / "phase3_cp8_production_doe"
    / "TRM-PDOE-C01"
)

SOLVER_ROOT = (
    CAMPAIGN_ROOT
    / "solver_preparation"
)

DOE_POLICY_PATH = (
    CONFIG
    / "phase3_production_doe.toml"
)

CAMPAIGN_MANIFEST_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_campaign_manifest.json"
)

PREPARATION_CERT_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_preparation_certification_record.json"
)

WARM_V1_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_warm_start_knowledge_record.json"
)

V21_POLICY_PATH = (
    CONFIG
    / "phase3_warm_start_delta_t_v2_1.toml"
)

FROZEN_PREDICTION_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_prospective_prediction.json"
)

ROLLOUT_AUTHORIZATION_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_prospective_validation.json"
)

ROLLOUT_MANIFEST_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_rollout_preparation_manifest.json"
)

OUTPUT_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_rollout_preparation_certification.json"
)


EXPECTED_DOE_POLICY_SHA256 = (
    "43032557cb2abead0118362bcfc6a9b2e"
    "5246a7d363ca83eef5fcf35054befc1"
)

EXPECTED_CAMPAIGN_SHA256 = (
    "84516519bbb188664268936e2d116e133"
    "431d90d037bed407ffb2d1fe92d2a67"
)

EXPECTED_PREPARATION_CERT_SHA256 = (
    "ad49cc35b61e95147ae669f0f915b8d7a"
    "e403145d098729e5540285f319befd5"
)

EXPECTED_WARM_V1_SHA256 = (
    "21e525db65d36a13ca6e2ee96514307f"
    "6234b2518bd60423f872f6dfa6fae8f7"
)

EXPECTED_V21_POLICY_SHA256 = (
    "db2a2af4a2954801d7e1db931672a197"
    "629a5dfcab19431c3a38db65b580268c"
)

EXPECTED_FROZEN_PREDICTION_SHA256 = (
    "36b0230083c98fc2674adf98b5d5f3ab"
    "a75c736888cfb44c113b86272c53ec4f"
)

EXPECTED_ROLLOUT_AUTHORIZATION_SHA256 = (
    "cf03ca248142c043bf8fe4cff4f59b2d"
    "aa657b37f2a4e0aa82ae671873d69ad9"
)

EXPECTED_ROLLOUT_MANIFEST_SHA256 = (
    "5b1bda58b08ed75b4baa2cd286bbaba9"
    "1e03d22c767f76b8499e66dcb1b89bad"
)


CORNER_IDS = (
    "A00",
    "A01",
    "A02",
    "A03",
    "D-BND-001",
    "D-BND-002",
    "D-BND-003",
    "D-BND-004",
)

LEGACY_ANCHORS = {
    "A00",
    "A01",
    "A02",
    "A03",
}

BOUNDARY_ANCHORS = {
    "D-BND-001",
    "D-BND-002",
    "D-BND-003",
    "D-BND-004",
}

DEVELOPMENT_ID = "D-INT-010"


def sha256(
    path: Path,
    *,
    allow_empty: bool = False,
) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)

    if (
        not allow_empty
        and path.stat().st_size <= 0
    ):
        raise RuntimeError(
            f"Required artifact is empty: {path}"
        )

    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(
                8 * 1024 * 1024
            ),
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


def load_toml(path: Path) -> dict:
    return tomllib.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def relative(path: Path) -> str:
    return (
        path
        .relative_to(ROOT)
        .as_posix()
    )


def require_close(
    label: str,
    actual: float,
    expected: float,
    *,
    tolerance: float = 1.0e-10,
) -> None:
    if not math.isclose(
        actual,
        expected,
        rel_tol=0.0,
        abs_tol=tolerance,
    ):
        raise RuntimeError(
            f"{label} drift.\n"
            f"Expected: {expected}\n"
            f"Actual  : {actual}"
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
                "Rollout-preparation certification "
                "already exists with different content. "
                f"Refusing overwrite: {path}"
            )

        action = "UNCHANGED / IDENTICAL"

    else:
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = (
            path.with_suffix(
                ".json.tmp"
            )
        )

        temporary.write_text(
            serialized,
            encoding="utf-8",
            newline="\n",
        )

        temporary.replace(path)

        action = "CREATED"

    record_hash = sha256(path)

    sidecar = (
        path.with_suffix(
            ".sha256"
        )
    )

    expected_sidecar = (
        f"{record_hash}  {path.name}\n"
    )

    if sidecar.exists():
        observed = sidecar.read_text(
            encoding="ascii"
        )

        if observed != expected_sidecar:
            raise RuntimeError(
                "Rollout-certification SHA "
                "sidecar drift."
            )

    else:
        sidecar.write_text(
            expected_sidecar,
            encoding="ascii",
            newline="\n",
        )

    return action, record_hash


def get_design_case(
    campaign,
    case_id: str,
):
    matches = tuple(
        row
        for row in campaign.design_cases
        if row.case_id == case_id
    )

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected one design case; "
            f"found {len(matches)}."
        )

    return matches[0]


def get_manifest_row(
    manifest: dict,
    case_id: str,
) -> dict:
    matches = [
        row
        for row in manifest["design_cases"]
        if row.get("case_id") == case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected one campaign "
            f"manifest row; found {len(matches)}."
        )

    return matches[0]


def coordinates(
    manifest: dict,
    case_id: str,
    order: tuple[str, ...],
) -> tuple[float, float, float]:
    raw = get_manifest_row(
        manifest,
        case_id,
    )["normalized_coordinates"]

    if not isinstance(raw, dict):
        raise RuntimeError(
            f"{case_id}: coordinates are not a mapping."
        )

    xyz = tuple(
        float(raw[key])
        for key in order
    )

    if len(xyz) != 3:
        raise RuntimeError(
            "V2.1 requires exactly three dimensions."
        )

    if not all(
        0.0 <= value <= 1.0
        for value in xyz
    ):
        raise RuntimeError(
            f"{case_id}: coordinates outside "
            "the governed unit cube."
        )

    return xyz


def bubble(
    xyz: tuple[float, float, float],
) -> float:
    x, y, z = xyz

    return (
        64.0
        * x
        * (1.0 - x)
        * y
        * (1.0 - y)
        * z
        * (1.0 - z)
    )


def trilinear(
    xyz: tuple[float, float, float],
    corners: dict[
        tuple[float, float, float],
        float,
    ],
) -> float:
    if not all(
        0.0 <= value <= 1.0
        for value in xyz
    ):
        raise RuntimeError(
            "Trilinear extrapolation forbidden."
        )

    x, y, z = xyz
    result = 0.0

    for ix in (0, 1):
        for iy in (0, 1):
            for iz in (0, 1):
                key = (
                    float(ix),
                    float(iy),
                    float(iz),
                )

                if key not in corners:
                    raise RuntimeError(
                        f"Missing cube corner {key}."
                    )

                wx = (
                    x
                    if ix
                    else 1.0 - x
                )
                wy = (
                    y
                    if iy
                    else 1.0 - y
                )
                wz = (
                    z
                    if iz
                    else 1.0 - z
                )

                result += (
                    wx
                    * wy
                    * wz
                    * corners[key]
                )

    return result


def accepted_evidence_path(
    doe_case,
) -> Path:
    return (
        SOLVER_ROOT
        / (
            "trm_fem_"
            + doe_case.case_hash[:12]
        )
        / "production_doe_accepted_fem_evidence.json"
    )


def solver_outputs_present(
    root: Path,
) -> tuple[str, ...]:
    if not root.exists():
        return ()

    forbidden_names = {
        "fem_run_manifest.json",
    }

    forbidden_suffixes = {
        ".dat",
        ".frd",
        ".sta",
        ".cvg",
        ".12d",
        ".eig",
        ".equ",
        ".rout",
    }

    found = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if (
            path.name in forbidden_names
            or path.suffix.lower()
            in forbidden_suffixes
        ):
            found.append(
                relative(path)
            )

    return tuple(
        sorted(found)
    )


def governed_accepted_case(
    doe_case,
) -> tuple[bool, str | None]:
    path = accepted_evidence_path(
        doe_case
    )

    if not path.exists():
        return False, None

    evidence = load_json(path)

    if (
        evidence.get("record_status")
        != "FINAL"
        or evidence.get(
            "overall_disposition"
        )
        != "PRODUCTION_DOE_FEM_CALIBRATION_ACCEPTED"
        or evidence[
            "accepted_calibration"
        ][
            "decision"
        ][
            "disposition"
        ]
        != "accept"
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: standard "
            "accepted-evidence file is not "
            "governed FINAL ACCEPT."
        )

    return True, sha256(path)


# ============================================================
# 1. FREEZE ALL GOVERNING INPUTS
# ============================================================

doe_policy_sha = require_sha256(
    DOE_POLICY_PATH,
    EXPECTED_DOE_POLICY_SHA256,
    "Production DOE policy",
)

campaign_sha = require_sha256(
    CAMPAIGN_MANIFEST_PATH,
    EXPECTED_CAMPAIGN_SHA256,
    "Production DOE campaign manifest",
)

preparation_cert_sha = require_sha256(
    PREPARATION_CERT_PATH,
    EXPECTED_PREPARATION_CERT_SHA256,
    "Production DOE preparation certification",
)

warm_v1_sha = require_sha256(
    WARM_V1_PATH,
    EXPECTED_WARM_V1_SHA256,
    "Warm-Start V1 knowledge",
)

v21_policy_sha = require_sha256(
    V21_POLICY_PATH,
    EXPECTED_V21_POLICY_SHA256,
    "Frozen Warm-Start V2.1 policy",
)

frozen_prediction_sha = require_sha256(
    FROZEN_PREDICTION_PATH,
    EXPECTED_FROZEN_PREDICTION_SHA256,
    "Frozen V2.1 prospective prediction",
)

rollout_authorization_sha = require_sha256(
    ROLLOUT_AUTHORIZATION_PATH,
    EXPECTED_ROLLOUT_AUTHORIZATION_SHA256,
    "V2.1 rollout authorization",
)

rollout_manifest_sha = require_sha256(
    ROLLOUT_MANIFEST_PATH,
    EXPECTED_ROLLOUT_MANIFEST_SHA256,
    "V2.1 rollout preparation manifest",
)

certifier_sha = sha256(
    Path(__file__).resolve()
)


# ============================================================
# 2. VERIFY AUTHORIZATION + PREPARATION MANIFEST
# ============================================================

authorization = load_json(
    ROLLOUT_AUTHORIZATION_PATH
)

if (
    authorization.get("record_status")
    != "FINAL"
    or authorization.get(
        "overall_disposition"
    )
    != "V2_1_PROSPECTIVE_PASS_ROLLOUT_AUTHORIZED"
):
    raise RuntimeError(
        "Rollout authorization is not "
        "FINAL / authorized."
    )

rollout_auth = authorization[
    "rollout_authorization"
]

if (
    rollout_auth.get("authorized") is not True
    or rollout_auth.get("predictor")
    != "warm_start_delta_t_v2_1"
    or rollout_auth.get("scope")
    != (
        "TRM-PDOE-C01_REMAINING_"
        "COVERED_DESIGN_CASES_ONLY"
    )
):
    raise RuntimeError(
        "Rollout authorization scope drift."
    )

if (
    rollout_auth.get(
        "remaining_design_cases_at_authorization"
    )
    != 14
):
    raise RuntimeError(
        "Authorized remaining-case count drift."
    )

if (
    rollout_auth.get(
        "v2_1_model_must_remain_frozen_during_rollout"
    )
    is not True
    or rollout_auth.get(
        "trial_2_only_if_governed_first_shot_rejects"
    )
    is not True
):
    raise RuntimeError(
        "Frozen-model / Trial-2 governance drift."
    )

if (
    rollout_auth.get(
        "blind_holdout_execution_authorized"
    )
    is not False
    or rollout_auth.get(
        "blind_holdouts_remain_sealed"
    )
    is not True
):
    raise RuntimeError(
        "Blind-holdout seal drift."
    )


rollout_manifest = load_json(
    ROLLOUT_MANIFEST_PATH
)

if (
    rollout_manifest.get("record_status")
    != "FINAL"
    or rollout_manifest.get(
        "overall_disposition"
    )
    != (
        "V2_1_ROLLOUT_PREPARATION_PASS_"
        "AWAITING_INDEPENDENT_CERTIFICATION"
    )
):
    raise RuntimeError(
        "Rollout preparation manifest "
        "is not the expected FINAL PASS."
    )

if (
    rollout_manifest[
        "authorization"
    ][
        "sha256"
    ]
    != rollout_authorization_sha
):
    raise RuntimeError(
        "Preparation-manifest authorization "
        "binding drift."
    )

if (
    rollout_manifest[
        "frozen_model"
    ][
        "policy_sha256"
    ]
    != v21_policy_sha
    or rollout_manifest[
        "frozen_model"
    ][
        "prospective_prediction_sha256"
    ]
    != frozen_prediction_sha
):
    raise RuntimeError(
        "Preparation-manifest frozen-model "
        "binding drift."
    )

zero = rollout_manifest[
    "zero_solve_certification_input"
]

required_true = (
    "all_case_preflights_passed",
    "all_canonical_v1_preparations_preserved",
    "all_canonical_v1_decks_preserved",
    "all_v2_1_sibling_decks_written",
    "ready_for_independent_batch_certification",
)

for key in required_true:
    if zero.get(key) is not True:
        raise RuntimeError(
            f"Preparation-manifest flag "
            f"{key!r} is not true."
        )

required_false = (
    "solver_outputs_detected",
    "solver_results_read",
    "calculix_invoked",
    "solver_execution_authorized_by_this_record",
    "blind_holdout_accessed",
)

for key in required_false:
    if zero.get(key) is not False:
        raise RuntimeError(
            f"Preparation-manifest flag "
            f"{key!r} is not false."
        )

if zero.get(
    "prepared_case_count"
) != 14:
    raise RuntimeError(
        "Prepared-case count is not 14."
    )


# ============================================================
# 3. INDEPENDENTLY REBUILD CAMPAIGN + FROZEN V2.1 MODEL
# ============================================================

policy = (
    load_phase3_production_doe_policy(
        DOE_POLICY_PATH
    )
)

campaign = (
    build_phase3_production_doe(
        policy
    )
)

campaign_manifest = load_json(
    CAMPAIGN_MANIFEST_PATH
)

warm = load_json(
    WARM_V1_PATH
)

v21 = load_toml(
    V21_POLICY_PATH
)

frozen_prediction = load_json(
    FROZEN_PREDICTION_PATH
)

preload = (
    load_complete_joint_preload_definition(
        CONFIG
        / "complete_joint_preload.toml"
    )
)

if (
    v21["identity"]["status"]
    != "frozen"
):
    raise RuntimeError(
        "V2.1 policy is not frozen."
    )

order = tuple(
    v21[
        "base_surface"
    ][
        "normalized_dimension_order"
    ]
)

if order != (
    "target_preload",
    "head_member_thickness",
    "radial_geometry_fraction",
):
    raise RuntimeError(
        "V2.1 dimension-order drift."
    )

legacy = {
    item["case_id"]: item
    for item in warm["anchors"]
}

corner_factors = {}

for case_id in CORNER_IDS:
    doe_case = get_design_case(
        campaign,
        case_id,
    )

    resolved = resolve_case(
        doe_case.case
    )

    analytical_dt = (
        derive_analytical_thermal_preload_seed(
            resolved
        )
        .predicted_delta_temperature_c
    )

    xyz = coordinates(
        campaign_manifest,
        case_id,
        order,
    )

    if case_id in LEGACY_ANCHORS:
        evidence = legacy[
            case_id
        ]

        if (
            evidence.get("status")
            != "CERTIFIED_REUSABLE"
            or evidence["case_hash"]
            != doe_case.case_hash
        ):
            raise RuntimeError(
                f"{case_id}: invalid legacy anchor."
            )

        accepted_dt = float(
            evidence[
                "accepted_delta_temperature_c"
            ]
        )

        factor = (
            accepted_dt
            / analytical_dt
        )

        require_close(
            f"{case_id} stored correction factor",
            factor,
            float(
                evidence[
                    "correction_factor"
                ]
            ),
        )

    elif case_id in BOUNDARY_ANCHORS:
        path = accepted_evidence_path(
            doe_case
        )

        evidence = load_json(path)

        if (
            evidence.get("record_status")
            != "FINAL"
            or evidence.get(
                "overall_disposition"
            )
            != "PRODUCTION_DOE_FEM_CALIBRATION_ACCEPTED"
            or evidence[
                "accepted_calibration"
            ][
                "decision"
            ][
                "disposition"
            ]
            != "accept"
        ):
            raise RuntimeError(
                f"{case_id}: invalid boundary anchor."
            )

        semantics = evidence[
            "evidence_semantics"
        ]

        if (
            semantics.get(
                "governed_calibration_accept_verified"
            )
            is not True
            or semantics.get(
                "eligible_for_v2_anchor_use"
            )
            is not True
        ):
            raise RuntimeError(
                f"{case_id}: not V2-anchor eligible."
            )

        accepted_dt = float(
            evidence[
                "accepted_calibration"
            ][
                "accepted_delta_temperature_c"
            ]
        )

        factor = (
            accepted_dt
            / analytical_dt
        )

    else:
        raise RuntimeError(
            f"Unexpected cube corner: {case_id}"
        )

    if xyz in corner_factors:
        raise RuntimeError(
            f"Duplicate cube coordinate: {xyz}"
        )

    corner_factors[xyz] = factor


expected_cube = {
    (
        float(x),
        float(y),
        float(z),
    )
    for x in (0, 1)
    for y in (0, 1)
    for z in (0, 1)
}

if set(corner_factors) != expected_cube:
    raise RuntimeError(
        "Independent eight-corner cube "
        "reconstruction failed."
    )


development_case = get_design_case(
    campaign,
    DEVELOPMENT_ID,
)

development_resolved = resolve_case(
    development_case.case
)

development_analytical_dt = (
    derive_analytical_thermal_preload_seed(
        development_resolved
    )
    .predicted_delta_temperature_c
)

development_xyz = coordinates(
    campaign_manifest,
    DEVELOPMENT_ID,
    order,
)

development_evidence_path = (
    accepted_evidence_path(
        development_case
    )
)

development_evidence_sha = sha256(
    development_evidence_path
)

if (
    development_evidence_sha
    != v21[
        "development_evidence"
    ][
        "accepted_fem_evidence_sha256"
    ]
):
    raise RuntimeError(
        "Frozen D-INT-010 development "
        "evidence SHA drift."
    )

development_evidence = load_json(
    development_evidence_path
)

development_accepted_dt = float(
    development_evidence[
        "accepted_calibration"
    ][
        "accepted_delta_temperature_c"
    ]
)

development_actual_factor = (
    development_accepted_dt
    / development_analytical_dt
)

development_base_factor = trilinear(
    development_xyz,
    corner_factors,
)

development_bubble = bubble(
    development_xyz
)

if development_bubble <= 0.0:
    raise RuntimeError(
        "Development bubble must be positive."
    )

derived_k = (
    (
        development_actual_factor
        - development_base_factor
    )
    / development_bubble
)

frozen_k = float(
    frozen_prediction[
        "development_residual"
    ][
        "derived_k"
    ]
)

require_close(
    "Independent frozen k",
    derived_k,
    frozen_k,
    tolerance=1.0e-12,
)

require_close(
    "Manifest frozen k",
    float(
        rollout_manifest[
            "frozen_model"
        ][
            "derived_and_verified_frozen_k"
        ]
    ),
    derived_k,
    tolerance=1.0e-12,
)


# ============================================================
# 4. INDEPENDENTLY DERIVE THE 14 AUTHORIZED UNSOLVED CASES
# ============================================================

fresh_design_cases = tuple(
    row
    for row in campaign.design_cases
    if row.source_case_id is None
)

if len(fresh_design_cases) != 20:
    raise RuntimeError(
        "Fresh Production DOE design-space "
        "count is not 20."
    )

accepted_ids = set()

for doe_case in fresh_design_cases:
    accepted, _ = governed_accepted_case(
        doe_case
    )

    if accepted:
        accepted_ids.add(
            doe_case.case_id
        )


sentinel_case_id = authorization[
    "case"
][
    "case_id"
]

if (
    authorization[
        "governed_acceptance"
    ][
        "accepted"
    ]
    is not True
    or authorization[
        "evidence_semantics"
    ][
        "eligible_for_production_dataset"
    ]
    is not True
):
    raise RuntimeError(
        "Prospective sentinel no longer "
        "qualifies as accepted evidence."
    )

accepted_ids.add(
    sentinel_case_id
)

if len(accepted_ids) != 6:
    raise RuntimeError(
        "Accepted fresh-state count "
        "before rollout is not 6."
    )

remaining_cases = tuple(
    sorted(
        (
            row
            for row in fresh_design_cases
            if row.case_id not in accepted_ids
        ),
        key=lambda row: row.case_id,
    )
)

if len(remaining_cases) != 14:
    raise RuntimeError(
        "Independently derived remaining "
        "rollout count is not 14."
    )

derived_case_ids = [
    row.case_id
    for row in remaining_cases
]

manifest_case_ids = rollout_manifest[
    "case_selection"
][
    "remaining_case_ids"
]

if manifest_case_ids != derived_case_ids:
    raise RuntimeError(
        "Rollout case selection drift.\n"
        f"Derived : {derived_case_ids}\n"
        f"Manifest: {manifest_case_ids}"
    )

if (
    rollout_manifest[
        "case_selection"
    ][
        "accepted_before_rollout_case_ids"
    ]
    != sorted(accepted_ids)
):
    raise RuntimeError(
        "Accepted-case exclusion set drift."
    )

for doe_case in remaining_cases:
    if (
        doe_case.source_case_id is not None
        or doe_case.case_id.startswith("H")
    ):
        raise RuntimeError(
            f"Unauthorized case selected: "
            f"{doe_case.case_id}"
        )


# ============================================================
# 5. VERIFY ALL 14 CASE RECORDS + DECKS INDEPENDENTLY
# ============================================================

rollout_rows = rollout_manifest[
    "rollout_cases"
]

if (
    not isinstance(
        rollout_rows,
        list,
    )
    or len(rollout_rows) != 14
):
    raise RuntimeError(
        "Rollout manifest does not contain "
        "exactly 14 case rows."
    )

row_by_case_id = {}

for row in rollout_rows:
    case_id = row["case_id"]

    if case_id in row_by_case_id:
        raise RuntimeError(
            f"Duplicate rollout row: {case_id}"
        )

    row_by_case_id[case_id] = row

if set(row_by_case_id) != set(
    derived_case_ids
):
    raise RuntimeError(
        "Rollout row identities do not match "
        "the independently derived case set."
    )


certified_rows = []

for doe_case in remaining_cases:
    case_id = doe_case.case_id
    row = row_by_case_id[
        case_id
    ]

    resolved = resolve_case(
        doe_case.case
    )

    if (
        resolved.case_hash
        != doe_case.case_hash
        or row["case_hash"]
        != doe_case.case_hash
    ):
        raise RuntimeError(
            f"{case_id}: case-hash drift."
        )

    xyz = coordinates(
        campaign_manifest,
        case_id,
        order,
    )

    analytical_dt = (
        derive_analytical_thermal_preload_seed(
            resolved
        )
        .predicted_delta_temperature_c
    )

    base_factor = trilinear(
        xyz,
        corner_factors,
    )

    bubble_value = bubble(
        xyz
    )

    residual_factor = (
        derived_k
        * bubble_value
    )

    v21_factor = (
        base_factor
        + residual_factor
    )

    predicted_dt = (
        analytical_dt
        * v21_factor
    )

    if (
        not math.isfinite(predicted_dt)
        or predicted_dt >= 0.0
    ):
        raise RuntimeError(
            f"{case_id}: independently "
            "predicted delta T invalid."
        )

    expected_run_id = (
        "trm_fem_"
        + doe_case.case_hash[:12]
        + "_cal_01_wsv21"
    )

    if (
        row[
            "v2_1_trial_run_id"
        ]
        != expected_run_id
    ):
        raise RuntimeError(
            f"{case_id}: V2.1 run-ID drift."
        )

    expected_numeric = (
        (
            "analytical_delta_temperature_c",
            analytical_dt,
        ),
        (
            "trilinear_correction_factor",
            base_factor,
        ),
        (
            "bubble_value",
            bubble_value,
        ),
        (
            "frozen_k",
            derived_k,
        ),
        (
            "bubble_residual_correction_factor",
            residual_factor,
        ),
        (
            "v2_1_correction_factor",
            v21_factor,
        ),
        (
            "predicted_delta_temperature_c",
            predicted_dt,
        ),
    )

    for field, expected in expected_numeric:
        require_close(
            f"{case_id} {field}",
            float(row[field]),
            expected,
            tolerance=1.0e-10,
        )

    prep_path = (
        ROOT
        / row[
            "preparation_relative_path"
        ]
    )

    prep_sha = sha256(
        prep_path
    )

    if (
        prep_sha
        != row[
            "preparation_sha256"
        ]
    ):
        raise RuntimeError(
            f"{case_id}: per-case "
            "preparation SHA drift."
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
            "V2_1_ROLLOUT_CASE_PREPARATION_PASS_"
            "AWAITING_BATCH_CERTIFICATION"
        )
    ):
        raise RuntimeError(
            f"{case_id}: preparation record "
            "is not governed FINAL PASS."
        )

    if (
        prep[
            "case"
        ][
            "case_id"
        ]
        != case_id
        or prep[
            "case"
        ][
            "case_hash"
        ]
        != doe_case.case_hash
        or prep[
            "case"
        ][
            "v2_1_trial1_run_id"
        ]
        != expected_run_id
    ):
        raise RuntimeError(
            f"{case_id}: preparation identity drift."
        )

    governance = prep[
        "governance"
    ]

    required_bindings = {
        "doe_policy_sha256": doe_policy_sha,
        "campaign_manifest_sha256": campaign_sha,
        "preparation_certification_sha256": preparation_cert_sha,
        "warm_v1_knowledge_sha256": warm_v1_sha,
        "v2_1_policy_sha256": v21_policy_sha,
        "frozen_prospective_prediction_sha256": (
            frozen_prediction_sha
        ),
        "rollout_authorization_sha256": (
            rollout_authorization_sha
        ),
    }

    for field, expected in required_bindings.items():
        if governance.get(field) != expected:
            raise RuntimeError(
                f"{case_id}: governance binding "
                f"drift for {field}."
            )

    prediction = prep[
        "frozen_v2_1_prediction"
    ]

    prep_numeric = (
        (
            "analytical_delta_temperature_c",
            analytical_dt,
        ),
        (
            "trilinear_correction_factor",
            base_factor,
        ),
        (
            "bubble_value",
            bubble_value,
        ),
        (
            "frozen_k",
            derived_k,
        ),
        (
            "bubble_residual_correction_factor",
            residual_factor,
        ),
        (
            "v2_1_correction_factor",
            v21_factor,
        ),
        (
            "predicted_delta_temperature_c",
            predicted_dt,
        ),
    )

    for field, expected in prep_numeric:
        require_close(
            f"{case_id} prep {field}",
            float(
                prediction[field]
            ),
            expected,
            tolerance=1.0e-10,
        )

    if (
        prediction.get(
            "model_refit_performed"
        )
        is not False
    ):
        raise RuntimeError(
            f"{case_id}: V2.1 refit flag "
            "is not false."
        )

    zero_assertion = prep[
        "zero_solve_assertion"
    ]

    for field in (
        "solver_outputs_detected",
        "solver_results_read",
        "calculix_invoked",
        "solver_authorized_by_this_script",
        "blind_holdout_accessed",
        "v2_1_refit_performed",
    ):
        if zero_assertion.get(field) is not False:
            raise RuntimeError(
                f"{case_id}: zero-solve "
                f"assertion failed for {field}."
            )

    if (
        prep[
            "fem_preflight"
        ][
            "status"
        ]
        != "PASS"
        or prep[
            "fem_preflight"
        ][
            "blocking_error_count"
        ]
        != 0
    ):
        raise RuntimeError(
            f"{case_id}: FEM preflight "
            "is not certified PASS."
        )

    require_close(
        f"{case_id} target tolerance",
        float(
            prep[
                "calibration_acceptance"
            ][
                "target_relative_tolerance"
            ]
        ),
        float(
            preload.target_relative_tolerance
        ),
        tolerance=1.0e-15,
    )

    require_close(
        f"{case_id} spread tolerance",
        float(
            prep[
                "calibration_acceptance"
            ][
                "interface_spread_relative_tolerance"
            ]
        ),
        float(
            preload.interface_spread_relative_tolerance
        ),
        tolerance=1.0e-15,
    )

    if (
        prep[
            "calibration_acceptance"
        ][
            "evaluation_status"
        ]
        != "NOT_RUN"
        or prep[
            "calibration_acceptance"
        ][
            "trial_2_policy"
        ]
        != (
            "ONLY_IF_GOVERNED_FIRST_SHOT_REJECTS"
        )
    ):
        raise RuntimeError(
            f"{case_id}: calibration "
            "execution-policy drift."
        )

    deck_path = (
        ROOT
        / row[
            "deck_relative_path"
        ]
    )

    deck_sha = sha256(
        deck_path
    )

    if (
        deck_sha
        != row[
            "deck_sha256"
        ]
        or deck_sha
        != prep[
            "deck"
        ][
            "sha256"
        ]
    ):
        raise RuntimeError(
            f"{case_id}: sibling deck SHA drift."
        )

    if (
        deck_path.stat().st_size
        != int(
            row[
                "deck_size_bytes"
            ]
        )
        or deck_path.stat().st_size
        != int(
            prep[
                "deck"
            ][
                "size_bytes"
            ]
        )
    ):
        raise RuntimeError(
            f"{case_id}: sibling deck "
            "size drift."
        )

    require_close(
        f"{case_id} deck delta T",
        float(
            prep[
                "deck"
            ][
                "delta_temperature_c"
            ]
        ),
        predicted_dt,
    )

    canonical = prep[
        "canonical_v1_protection"
    ]

    if (
        canonical.get("preserved")
        is not True
        or canonical.get(
            "canonical_v1_executed"
        )
        is not False
    ):
        raise RuntimeError(
            f"{case_id}: canonical V1 "
            "protection semantics drift."
        )

    canonical_prep_path = (
        ROOT
        / canonical[
            "canonical_preparation_relative_path"
        ]
    )

    canonical_deck_path = (
        ROOT
        / canonical[
            "canonical_deck_relative_path"
        ]
    )

    if (
        sha256(canonical_prep_path)
        != canonical[
            "canonical_preparation_sha256"
        ]
        or sha256(canonical_deck_path)
        != canonical[
            "canonical_deck_sha256"
        ]
    ):
        raise RuntimeError(
            f"{case_id}: canonical V1 "
            "evidence SHA drift."
        )

    mesh_path = (
        ROOT
        / row[
            "mesh_relative_path"
        ]
    )

    step_path = (
        ROOT
        / row[
            "step_relative_path"
        ]
    )

    if (
        sha256(mesh_path)
        != row["mesh_sha256"]
        or sha256(step_path)
        != row["step_sha256"]
    ):
        raise RuntimeError(
            f"{case_id}: certified geometry/"
            "mesh artifact SHA drift."
        )

    case_root = (
        SOLVER_ROOT
        / (
            "trm_fem_"
            + doe_case.case_hash[:12]
        )
    )

    outputs = solver_outputs_present(
        case_root
    )

    if outputs:
        raise RuntimeError(
            f"{case_id}: solver outputs detected "
            "before rollout authorization:\n"
            + "\n".join(outputs)
        )

    run_dir = deck_path.parent

    if (
        run_dir
        / "fem_run_manifest.json"
    ).exists():
        raise RuntimeError(
            f"{case_id}: FEM run manifest "
            "already exists."
        )

    certified_rows.append(
        {
            "case_id": case_id,
            "case_hash": doe_case.case_hash,
            "run_id": expected_run_id,
            "target_preload_n": (
                resolved
                .source_case
                .loading
                .target_preload_n
            ),
            "normalized_coordinates": list(
                xyz
            ),
            "analytical_delta_temperature_c": (
                analytical_dt
            ),
            "trilinear_correction_factor": (
                base_factor
            ),
            "bubble_value": bubble_value,
            "frozen_k": derived_k,
            "v2_1_correction_factor": (
                v21_factor
            ),
            "predicted_delta_temperature_c": (
                predicted_dt
            ),
            "preparation_relative_path": (
                relative(prep_path)
            ),
            "preparation_sha256": prep_sha,
            "deck_relative_path": (
                relative(deck_path)
            ),
            "deck_sha256": deck_sha,
            "deck_size_bytes": (
                deck_path.stat().st_size
            ),
            "mesh_relative_path": (
                relative(mesh_path)
            ),
            "mesh_sha256": (
                row["mesh_sha256"]
            ),
            "step_relative_path": (
                relative(step_path)
            ),
            "step_sha256": (
                row["step_sha256"]
            ),
            "fem_preflight": "PASS",
            "solver_outputs_present": False,
        }
    )


# ============================================================
# 6. FINAL GLOBAL PURITY / GOVERNANCE CHECKS
# ============================================================

if len(certified_rows) != 14:
    raise RuntimeError(
        "Certification did not verify "
        "exactly 14 rollout cases."
    )

if not math.isclose(
    float(
        preload.target_relative_tolerance
    ),
    float(
        rollout_auth[
            "first_shot_target_relative_tolerance"
        ]
    ),
    rel_tol=0.0,
    abs_tol=1.0e-15,
):
    raise RuntimeError(
        "Governed target tolerance "
        "does not match rollout authorization."
    )

if not math.isclose(
    float(
        preload.interface_spread_relative_tolerance
    ),
    float(
        rollout_auth[
            "first_shot_interface_spread_relative_tolerance"
        ]
    ),
    rel_tol=0.0,
    abs_tol=1.0e-15,
):
    raise RuntimeError(
        "Governed spread tolerance "
        "does not match rollout authorization."
    )

if (
    authorization[
        "evidence_semantics"
    ][
        "eligible_for_v2_1_parameter_refit_before_rollout"
    ]
    is not False
):
    raise RuntimeError(
        "Prospective sentinel unexpectedly "
        "became V2.1-refit eligible."
    )


# ============================================================
# 7. FREEZE INDEPENDENT CERTIFICATION
# ============================================================

record = {
    "schema_version": 1,

    "record_id": (
        "TRM-P3-CP8-WSV21-"
        "ROLLOUT-PREPARATION-CERT-P01"
    ),

    "record_status": "FINAL",

    "campaign_id": "TRM-PDOE-C01",

    "certification_role": (
        "INDEPENDENT_ZERO_SOLVE_"
        "ROLLOUT_PREPARATION_CERTIFICATION"
    ),

    "governance": {
        "doe_policy": {
            "relative_path": (
                relative(DOE_POLICY_PATH)
            ),
            "sha256": doe_policy_sha,
        },
        "campaign_manifest": {
            "relative_path": (
                relative(
                    CAMPAIGN_MANIFEST_PATH
                )
            ),
            "sha256": campaign_sha,
        },
        "production_doe_preparation_certification": {
            "relative_path": (
                relative(
                    PREPARATION_CERT_PATH
                )
            ),
            "sha256": preparation_cert_sha,
        },
        "warm_v1_knowledge": {
            "relative_path": (
                relative(WARM_V1_PATH)
            ),
            "sha256": warm_v1_sha,
        },
        "v2_1_policy": {
            "relative_path": (
                relative(V21_POLICY_PATH)
            ),
            "sha256": v21_policy_sha,
        },
        "frozen_prospective_prediction": {
            "relative_path": (
                relative(
                    FROZEN_PREDICTION_PATH
                )
            ),
            "sha256": frozen_prediction_sha,
        },
        "rollout_authorization": {
            "relative_path": (
                relative(
                    ROLLOUT_AUTHORIZATION_PATH
                )
            ),
            "sha256": rollout_authorization_sha,
        },
        "rollout_preparation_manifest": {
            "relative_path": (
                relative(
                    ROLLOUT_MANIFEST_PATH
                )
            ),
            "sha256": rollout_manifest_sha,
        },
        "certifier": {
            "relative_path": (
                relative(
                    Path(__file__).resolve()
                )
            ),
            "sha256": certifier_sha,
        },
    },

    "independent_model_verification": {
        "method": (
            "exact_trilinear_plus_single_"
            "interior_bubble_residual"
        ),
        "certified_corner_count": 8,
        "dimension_order": list(order),
        "development_case_id": (
            DEVELOPMENT_ID
        ),
        "development_evidence_sha256": (
            development_evidence_sha
        ),
        "derived_frozen_k": (
            derived_k
        ),
        "frozen_prediction_k": (
            frozen_k
        ),
        "k_match": True,
        "model_refit_performed": False,
        "prospective_sentinel_used_for_refit": False,
        "rollout_results_used_for_refit": False,
    },

    "independent_case_selection": {
        "fresh_design_case_count": 20,
        "accepted_before_rollout_count": 6,
        "accepted_case_ids": sorted(
            accepted_ids
        ),
        "remaining_case_count": 14,
        "remaining_case_ids": (
            derived_case_ids
        ),
        "selection_matches_preparation_manifest": True,
        "legacy_anchors_excluded": True,
        "already_accepted_cases_excluded": True,
        "prospective_sentinel_excluded": True,
        "blind_holdouts_excluded": True,
    },

    "certified_rollout_cases": (
        certified_rows
    ),

    "zero_solve_verification": {
        "prepared_case_count": 14,
        "all_case_preflights_passed": True,
        "all_sibling_deck_hashes_verified": True,
        "all_canonical_v1_preparations_verified": True,
        "all_canonical_v1_decks_verified": True,
        "all_geometry_mesh_hashes_verified": True,
        "solver_outputs_detected": False,
        "solver_results_read": False,
        "calculix_invoked": False,
        "fem_run_manifests_present": False,
        "v2_1_refit_performed": False,
        "blind_holdout_accessed": False,
    },

    "rollout_execution_authorization": {
        "authorized": True,
        "authorization_basis": (
            "PROSPECTIVE_PASS_PLUS_"
            "INDEPENDENT_ZERO_SOLVE_PREPARATION_CERTIFICATION"
        ),
        "predictor": (
            "warm_start_delta_t_v2_1"
        ),
        "scope": (
            "CERTIFIED_14_REMAINING_"
            "TRM_PDOE_C01_COVERED_DESIGN_CASES_ONLY"
        ),
        "authorized_case_ids": (
            derived_case_ids
        ),
        "authorized_trial": (
            "V2_1_FIRST_SHOT_ONLY"
        ),
        "maximum_concurrent_calculix_runs": 4,
        "trial_2_only_after_governed_first_shot_reject": True,
        "target_relative_tolerance": (
            preload.target_relative_tolerance
        ),
        "interface_spread_relative_tolerance": (
            preload.interface_spread_relative_tolerance
        ),
        "v2_1_model_must_remain_frozen": True,
        "blind_holdout_execution_authorized": False,
        "blind_holdouts_remain_sealed": True,
    },

    "evidence_semantics": {
        "rollout_preparation_independently_verified": True,
        "solver_execution_performed_by_certifier": False,
        "production_fem_execution_now_authorized": True,
        "authorization_limited_to_certified_case_ids": True,
        "holdout_execution_authorized": False,
    },

    "overall_disposition": (
        "V2_1_ROLLOUT_PREPARATION_"
        "CERTIFIED_READY_FOR_FEM"
    ),
}


action, record_sha = (
    write_immutable_json(
        OUTPUT_PATH,
        record,
    )
)


# ============================================================
# 8. REPORT
# ============================================================

print("=" * 132)
print(
    "THREADROM - WARM-START V2.1 "
    "ROLLOUT PREPARATION CERTIFICATION"
)
print("=" * 132)

print()
print(
    "Rollout manifest SHA256        :",
    rollout_manifest_sha,
)
print(
    "Rollout authorization SHA256   :",
    rollout_authorization_sha,
)
print(
    "V2.1 policy SHA256             :",
    v21_policy_sha,
)

print()
print(
    "Independent frozen k           :",
    derived_k,
)
print(
    "Frozen-model verification      : PASS"
)

print()
print(
    "Fresh Production DOE states    : 20"
)
print(
    "Accepted before rollout        : 6"
)
print(
    "Independently derived remaining: 14"
)
print(
    "Prepared/certified cases       :",
    len(certified_rows),
)

print()
for row in certified_rows:
    print(
        f"{row['case_id']:12s} | "
        f"{row['run_id']} | "
        f"dT={row['predicted_delta_temperature_c']:.9f} C | "
        f"deck={row['deck_sha256'][:16]}..."
    )

print()
print(
    "All sibling deck hashes        : VERIFIED"
)
print(
    "All canonical V1 evidence      : VERIFIED / PRESERVED"
)
print(
    "All geometry/mesh hashes       : VERIFIED"
)
print(
    "All FEM preflights             : PASS"
)

print()
print(
    "Solver outputs detected        : NONE"
)
print(
    "FEM run manifests present      : NONE"
)
print(
    "CalculiX invoked               : NO"
)
print(
    "Solver results read            : NO"
)
print(
    "V2.1 refit performed           : NO"
)
print(
    "Blind holdouts accessed        : NO"
)

print()
print(
    "First-shot FEM rollout         : AUTHORIZED"
)
print(
    "Maximum concurrency            : 4"
)
print(
    "Trial 2                        : ONLY AFTER GOVERNED REJECT"
)
print(
    "Blind holdout execution        : NOT AUTHORIZED"
)

print()
print(
    "Certification record           :",
    OUTPUT_PATH,
)
print(
    "Certification SHA256           :",
    record_sha,
)
print(
    "Record action                  :",
    action,
)

print()
print(
    "OVERALL DISPOSITION            : "
    "V2_1_ROLLOUT_PREPARATION_"
    "CERTIFIED_READY_FOR_FEM"
)

print("=" * 132)
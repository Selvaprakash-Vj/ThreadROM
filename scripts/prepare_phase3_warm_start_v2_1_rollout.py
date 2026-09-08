from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import tomllib

from enum import Enum
from pathlib import Path

from threadrom.case.preflight import (
    PreflightSeverity,
    PreflightTarget,
)
from threadrom.case.preflight_engine import preflight_case
from threadrom.case.resolver import resolve_case

from threadrom.factory.fem_case_definition_bundle import (
    build_generic_fem_definition_bundle,
)
from threadrom.factory.fem_preload_calibration_deck import (
    write_fem_preload_calibration_trial_deck,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
)
from threadrom.factory.preload_calibration_seed import (
    derive_analytical_thermal_preload_seed,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
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
    / "phase3_cp8_production_doe"
    / "TRM-PDOE-C01"
)

SOLVER_ROOT = CAMPAIGN_ROOT / "solver_preparation"

DOE_POLICY_PATH = CONFIG / "phase3_production_doe.toml"

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


def sha256(path: Path) -> str:
    if (
        not path.is_file()
        or path.stat().st_size <= 0
    ):
        raise FileNotFoundError(
            f"Missing/non-positive file: {path}"
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


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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


def require_close(
    label: str,
    actual: float,
    expected: float,
    *,
    abs_tol: float = 1.0e-10,
) -> None:
    if not math.isclose(
        actual,
        expected,
        rel_tol=0.0,
        abs_tol=abs_tol,
    ):
        raise RuntimeError(
            f"{label} mismatch: "
            f"{actual!r} != {expected!r}"
        )


def jsonable(value):
    if dataclasses.is_dataclass(value):
        return {
            field.name: jsonable(
                getattr(
                    value,
                    field.name,
                )
            )
            for field in dataclasses.fields(value)
        }

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, dict):
        return {
            str(key): jsonable(child)
            for key, child in value.items()
        }

    if isinstance(value, (tuple, list)):
        return [
            jsonable(child)
            for child in value
        ]

    return value


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
                "Immutable rollout evidence already "
                "exists with different content. "
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

    record_hash = sha256(path)

    sidecar = path.with_suffix(
        ".sha256"
    )

    sidecar_text = (
        f"{record_hash}  {path.name}\n"
    )

    if sidecar.exists():
        observed = sidecar.read_text(
            encoding="ascii"
        )

        if observed != sidecar_text:
            raise RuntimeError(
                f"SHA sidecar drift: {sidecar}"
            )

    else:
        sidecar.write_text(
            sidecar_text,
            encoding="ascii",
            newline="\n",
        )

    return action, record_hash


def verify_sha_sidecar(path: Path) -> str:
    actual = sha256(path)

    sidecar = path.with_suffix(
        ".sha256"
    )

    if not sidecar.is_file():
        raise RuntimeError(
            f"Missing SHA sidecar: {sidecar}"
        )

    expected = (
        f"{actual}  {path.name}\n"
    )

    observed = sidecar.read_text(
        encoding="ascii"
    )

    if observed != expected:
        raise RuntimeError(
            f"SHA sidecar mismatch: {path}"
        )

    return actual


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
            f"{case_id}: normalized coordinates "
            "are not a mapping."
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
            f"{case_id}: normalized coordinates "
            "outside the governed unit cube."
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


def find_preparation_row(
    certification: dict,
    case_id: str,
) -> dict:
    matches = [
        row
        for row in certification[
            "design_case_preparation_evidence"
        ]
        if row["case_id"] == case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected one certified "
            f"preparation row; found {len(matches)}."
        )

    return matches[0]


def reference_temperature_c() -> float:
    path = (
        CONFIG
        / "complete_joint_preload.toml"
    )

    data = load_toml(path)

    matches = []

    def walk(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if (
                    key
                    == "reference_temperature_c"
                ):
                    matches.append(
                        float(child)
                    )
                else:
                    walk(child)

        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)

    if len(matches) != 1:
        raise RuntimeError(
            "Expected exactly one governed "
            "reference_temperature_c."
        )

    result = matches[0]

    if not math.isfinite(result):
        raise RuntimeError(
            "Reference temperature is not finite."
        )

    return result


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

    return tuple(sorted(found))


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
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: accepted-evidence "
            "file exists but is not FINAL accepted."
        )

    decision = (
        evidence[
            "accepted_calibration"
        ][
            "decision"
        ][
            "disposition"
        ]
    )

    if decision != "accept":
        raise RuntimeError(
            f"{doe_case.case_id}: accepted-evidence "
            "record lacks governed ACCEPT."
        )

    return True, sha256(path)


# ============================================================
# 1. LOCKED GOVERNANCE
# ============================================================

doe_policy_hash = require_sha256(
    DOE_POLICY_PATH,
    EXPECTED_DOE_POLICY_SHA256,
    "Production DOE policy",
)

campaign_hash = require_sha256(
    CAMPAIGN_MANIFEST_PATH,
    EXPECTED_CAMPAIGN_SHA256,
    "Production DOE campaign manifest",
)

preparation_cert_hash = require_sha256(
    PREPARATION_CERT_PATH,
    EXPECTED_PREPARATION_CERT_SHA256,
    "Production DOE preparation certification",
)

warm_v1_hash = require_sha256(
    WARM_V1_PATH,
    EXPECTED_WARM_V1_SHA256,
    "Warm-Start V1 knowledge record",
)

v21_policy_hash = require_sha256(
    V21_POLICY_PATH,
    EXPECTED_V21_POLICY_SHA256,
    "Warm-Start V2.1 policy",
)

frozen_prediction_hash = require_sha256(
    FROZEN_PREDICTION_PATH,
    EXPECTED_FROZEN_PREDICTION_SHA256,
    "Frozen V2.1 prospective prediction",
)

rollout_authorization_hash = require_sha256(
    ROLLOUT_AUTHORIZATION_PATH,
    EXPECTED_ROLLOUT_AUTHORIZATION_SHA256,
    "V2.1 rollout authorization",
)

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
        "V2.1 rollout authorization is not "
        "FINAL authorized evidence."
    )

if (
    authorization[
        "prospective_validation"
    ][
        "verdict"
    ]
    != "PROSPECTIVE_PASS"
):
    raise RuntimeError(
        "Prospective validation verdict "
        "is not PROSPECTIVE_PASS."
    )

rollout = authorization[
    "rollout_authorization"
]

if rollout.get("authorized") is not True:
    raise RuntimeError(
        "V2.1 rollout is not authorized."
    )

if (
    rollout.get("predictor")
    != "warm_start_delta_t_v2_1"
):
    raise RuntimeError(
        "Unexpected rollout predictor."
    )

if (
    rollout.get("scope")
    != (
        "TRM-PDOE-C01_REMAINING_"
        "COVERED_DESIGN_CASES_ONLY"
    )
):
    raise RuntimeError(
        "Unexpected rollout authorization scope."
    )

if (
    rollout.get(
        "v2_1_model_must_remain_frozen_during_rollout"
    )
    is not True
):
    raise RuntimeError(
        "Frozen-model rollout requirement missing."
    )

if (
    rollout.get(
        "trial_2_only_if_governed_first_shot_rejects"
    )
    is not True
):
    raise RuntimeError(
        "Trial-2 exception-path governance missing."
    )

if (
    rollout.get(
        "blind_holdout_execution_authorized"
    )
    is not False
    or rollout.get(
        "blind_holdouts_remain_sealed"
    )
    is not True
):
    raise RuntimeError(
        "Blind-holdout seal is not intact."
    )

required_remaining_count = int(
    rollout[
        "remaining_design_cases_at_authorization"
    ]
)

if required_remaining_count != 14:
    raise RuntimeError(
        "Rollout authorization no longer describes "
        "the certified 14-case scope."
    )

if not math.isclose(
    float(
        rollout[
            "first_shot_target_relative_tolerance"
        ]
    ),
    0.01,
    rel_tol=0.0,
    abs_tol=1.0e-15,
):
    raise RuntimeError(
        "Target tolerance drift."
    )

if not math.isclose(
    float(
        rollout[
            "first_shot_interface_spread_relative_tolerance"
        ]
    ),
    0.005,
    rel_tol=0.0,
    abs_tol=1.0e-15,
):
    raise RuntimeError(
        "Interface-spread tolerance drift."
    )


# ============================================================
# 2. FROZEN CAMPAIGN + V2.1 POLICY
# ============================================================

doe_policy = (
    load_phase3_production_doe_policy(
        DOE_POLICY_PATH
    )
)

campaign = (
    build_phase3_production_doe(
        doe_policy
    )
)

campaign_manifest = load_json(
    CAMPAIGN_MANIFEST_PATH
)

preparation_cert = load_json(
    PREPARATION_CERT_PATH
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

if (
    v21["identity"]["status"]
    != "frozen"
):
    raise RuntimeError(
        "V2.1 policy is not frozen."
    )

if (
    authorization[
        "development_provenance"
    ][
        "v2_1_policy"
    ][
        "sha256"
    ]
    != v21_policy_hash
):
    raise RuntimeError(
        "Authorization/V2.1-policy provenance mismatch."
    )

if (
    authorization[
        "development_provenance"
    ][
        "prospective_prediction"
    ][
        "sha256"
    ]
    != frozen_prediction_hash
):
    raise RuntimeError(
        "Authorization/frozen-prediction "
        "provenance mismatch."
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
        "V2.1 normalized-dimension order drift."
    )


# ============================================================
# 3. REBUILD EXACT CERTIFIED EIGHT-CORNER SURFACE
# ============================================================

legacy = {
    item["case_id"]: item
    for item in warm["anchors"]
}

corner_factors = {}
corner_records = []

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
        ):
            raise RuntimeError(
                f"{case_id}: legacy anchor "
                "not certified reusable."
            )

        if (
            evidence["case_hash"]
            != doe_case.case_hash
        ):
            raise RuntimeError(
                f"{case_id}: legacy anchor "
                "case-hash mismatch."
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
            f"{case_id} correction factor",
            factor,
            float(
                evidence[
                    "correction_factor"
                ]
            ),
        )

        evidence_path = WARM_V1_PATH
        evidence_hash = warm_v1_hash
        evidence_type = (
            "CERTIFIED_REUSABLE_WARM_KNOWLEDGE"
        )

    elif case_id in BOUNDARY_ANCHORS:
        evidence_path = (
            accepted_evidence_path(
                doe_case
            )
        )

        evidence = load_json(
            evidence_path
        )

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
                f"{case_id}: boundary anchor "
                "is not governed accepted FEM evidence."
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
                f"{case_id}: boundary anchor "
                "is not V2-anchor eligible."
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

        evidence_hash = sha256(
            evidence_path
        )

        evidence_type = (
            "FINAL_GOVERNED_ACCEPTED_FEM_EVIDENCE"
        )

    else:
        raise RuntimeError(
            f"Unexpected V2.1 cube corner: {case_id}"
        )

    if xyz in corner_factors:
        raise RuntimeError(
            f"Duplicate cube coordinate: {xyz}"
        )

    corner_factors[xyz] = factor

    corner_records.append(
        {
            "case_id": case_id,
            "case_hash": doe_case.case_hash,
            "normalized_coordinates": list(xyz),
            "analytical_delta_temperature_c": (
                analytical_dt
            ),
            "accepted_delta_temperature_c": (
                accepted_dt
            ),
            "correction_factor": factor,
            "evidence_type": evidence_type,
            "evidence_relative_path": (
                relative(evidence_path)
            ),
            "evidence_sha256": evidence_hash,
        }
    )


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
        "Certified eight-corner cube is incomplete."
    )


# ============================================================
# 4. RE-DERIVE AND VERIFY THE SINGLE FROZEN k
# ============================================================

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

development_evidence_hash = sha256(
    development_evidence_path
)

if (
    development_evidence_hash
    != v21[
        "development_evidence"
    ][
        "accepted_fem_evidence_sha256"
    ]
):
    raise RuntimeError(
        "D-INT-010 frozen development-evidence "
        "SHA drift."
    )

development_evidence = load_json(
    development_evidence_path
)

if (
    development_evidence.get(
        "record_status"
    )
    != "FINAL"
    or development_evidence.get(
        "overall_disposition"
    )
    != "PRODUCTION_DOE_FEM_CALIBRATION_ACCEPTED"
    or development_evidence[
        "accepted_calibration"
    ][
        "decision"
    ][
        "disposition"
    ]
    != "accept"
):
    raise RuntimeError(
        "D-INT-010 is not governed accepted "
        "development evidence."
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
        "D-INT-010 bubble must be positive."
    )

development_residual = (
    development_actual_factor
    - development_base_factor
)

derived_k = (
    development_residual
    / development_bubble
)

if (
    not math.isfinite(derived_k)
    or derived_k <= 0.0
):
    raise RuntimeError(
        "Derived frozen V2.1 k is invalid."
    )

frozen_k = float(
    frozen_prediction[
        "development_residual"
    ][
        "derived_k"
    ]
)

require_close(
    "Frozen V2.1 k",
    derived_k,
    frozen_k,
    abs_tol=1.0e-12,
)

if (
    frozen_prediction[
        "development_residual"
    ][
        "case_id"
    ]
    != DEVELOPMENT_ID
):
    raise RuntimeError(
        "Frozen V2.1 development-case drift."
    )


# ============================================================
# 5. DERIVE ACCEPTED + REMAINING COVERED DESIGN STATES
# ============================================================

fresh_design_cases = tuple(
    row
    for row in campaign.design_cases
    if row.source_case_id is None
)

accepted_ids = set()
accepted_evidence = []

for doe_case in fresh_design_cases:
    accepted, evidence_hash = (
        governed_accepted_case(
            doe_case
        )
    )

    if accepted:
        accepted_ids.add(
            doe_case.case_id
        )

        accepted_evidence.append(
            {
                "case_id": doe_case.case_id,
                "case_hash": doe_case.case_hash,
                "evidence_kind": (
                    "STANDARD_ACCEPTED_FEM_EVIDENCE"
                ),
                "evidence_relative_path": relative(
                    accepted_evidence_path(
                        doe_case
                    )
                ),
                "evidence_sha256": evidence_hash,
            }
        )


sentinel_case_id = authorization[
    "case"
][
    "case_id"
]

sentinel_case = get_design_case(
    campaign,
    sentinel_case_id,
)

if sentinel_case.source_case_id is not None:
    raise RuntimeError(
        "Prospective sentinel unexpectedly "
        "resolves to a legacy anchor."
    )

semantics = authorization[
    "evidence_semantics"
]

if (
    semantics.get(
        "first_shot_is_accepted_physics_solve"
    )
    is not True
    or semantics.get(
        "governed_calibration_accept_verified"
    )
    is not True
    or semantics.get(
        "eligible_for_production_dataset"
    )
    is not True
    or authorization[
        "governed_acceptance"
    ][
        "accepted"
    ]
    is not True
):
    raise RuntimeError(
        "Prospective sentinel is not governed "
        "accepted production evidence."
    )

accepted_ids.add(
    sentinel_case_id
)

if not any(
    row["case_id"] == sentinel_case_id
    for row in accepted_evidence
):
    accepted_evidence.append(
        {
            "case_id": sentinel_case_id,
            "case_hash": sentinel_case.case_hash,
            "evidence_kind": (
                "PROSPECTIVE_VALIDATION_ACCEPTED_FEM_EVIDENCE"
            ),
            "evidence_relative_path": relative(
                ROLLOUT_AUTHORIZATION_PATH
            ),
            "evidence_sha256": (
                rollout_authorization_hash
            ),
        }
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

if (
    len(remaining_cases)
    != required_remaining_count
):
    raise RuntimeError(
        "Derived remaining-case count does not "
        "match rollout authorization.\n"
        f"Derived   : {len(remaining_cases)}\n"
        f"Authorized: {required_remaining_count}\n"
        f"Accepted  : {sorted(accepted_ids)}"
    )

for doe_case in remaining_cases:
    if (
        doe_case.source_case_id is not None
        or doe_case.case_id.startswith("H")
    ):
        raise RuntimeError(
            f"Unauthorized rollout selection: "
            f"{doe_case.case_id}"
        )


# ============================================================
# 6. VERIFY EVERY REMAINING CASE IS GENUINELY UNSOLVED
# ============================================================

for doe_case in remaining_cases:
    canonical_case_run_id = (
        "trm_fem_"
        + doe_case.case_hash[:12]
    )

    case_root = (
        SOLVER_ROOT
        / canonical_case_run_id
    )

    outputs = solver_outputs_present(
        case_root
    )

    if outputs:
        raise RuntimeError(
            f"{doe_case.case_id}: solver outputs already "
            "exist, so this case cannot be treated as "
            "an unsolved rollout state:\n"
            + "\n".join(outputs)
        )


# ============================================================
# 7. LOAD PROVEN FEM TEMPLATES
# ============================================================

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

preload_template = (
    load_complete_joint_preload_definition(
        CONFIG
        / "complete_joint_preload.toml"
    )
)

boundary_template = (
    load_complete_joint_boundary_region_definition(
        CONFIG
        / "complete_joint_boundary_regions.toml"
    )
)

reference_temperature = (
    reference_temperature_c()
)


# ============================================================
# 8. BUILD ALL 14 V2.1 SIBLING TRIAL-1 PREPARATIONS
# ============================================================

rollout_rows = []

for doe_case in remaining_cases:
    resolved = resolve_case(
        doe_case.case
    )

    if (
        resolved.case_hash
        != doe_case.case_hash
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: resolved "
            "case-hash drift."
        )

    canonical_case_run_id = (
        "trm_fem_"
        + resolved.case_hash[:12]
    )

    canonical_trial1_run_id = (
        f"{canonical_case_run_id}_cal_01"
    )

    rollout_trial_run_id = (
        f"{canonical_case_run_id}_cal_01_wsv21"
    )

    canonical_trial_dir = (
        SOLVER_ROOT
        / canonical_case_run_id
        / canonical_trial1_run_id
    )

    canonical_prep_path = (
        canonical_trial_dir
        / "production_doe_solver_preparation_record.json"
    )

    canonical_prep_hash = (
        verify_sha_sidecar(
            canonical_prep_path
        )
    )

    canonical_prep = load_json(
        canonical_prep_path
    )

    if (
        canonical_prep.get("record_status")
        != "FINAL"
        or canonical_prep.get(
            "overall_disposition"
        )
        != (
            "PRODUCTION_DOE_TRIAL1_"
            "SOLVER_PREPARATION_PASS"
        )
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: canonical V1 "
            "Trial-1 preparation is not FINAL PASS."
        )

    if (
        canonical_prep[
            "case"
        ][
            "case_hash"
        ]
        != doe_case.case_hash
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: canonical V1 "
            "case identity mismatch."
        )

    canonical_deck_path = (
        ROOT
        / canonical_prep[
            "deck"
        ][
            "relative_path"
        ]
    )

    canonical_deck_hash = sha256(
        canonical_deck_path
    )

    if (
        canonical_deck_hash
        != canonical_prep[
            "deck"
        ][
            "sha256"
        ]
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: canonical V1 "
            "deck hash drift."
        )

    canonical_v1_delta_t = float(
        canonical_prep[
            "trial_1"
        ][
            "delta_temperature_c"
        ]
    )

    xyz = coordinates(
        campaign_manifest,
        doe_case.case_id,
        order,
    )

    analytical_seed = (
        derive_analytical_thermal_preload_seed(
            resolved
        )
    )

    analytical_dt = (
        analytical_seed
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

    if (
        not math.isfinite(v21_factor)
        or v21_factor <= 0.0
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: invalid "
            "V2.1 correction factor."
        )

    predicted_delta_t = (
        analytical_dt
        * v21_factor
    )

    if (
        not math.isfinite(
            predicted_delta_t
        )
        or predicted_delta_t >= 0.0
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: invalid "
            "V2.1 thermal contraction."
        )

    preflight = preflight_case(
        doe_case.case,
        PreflightTarget.FEM,
    )

    blocking = tuple(
        finding
        for finding in preflight.findings
        if (
            finding.severity
            is PreflightSeverity.ERROR
        )
    )

    if blocking:
        raise RuntimeError(
            f"{doe_case.case_id}: FEM preflight BLOCKED: "
            + "; ".join(
                str(finding)
                for finding in blocking
            )
        )

    preparation_row = find_preparation_row(
        preparation_cert,
        doe_case.case_id,
    )

    if (
        preparation_row["case_hash"]
        != doe_case.case_hash
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: certified "
            "preparation case-hash mismatch."
        )

    if (
        preparation_row[
            "mesh_policy_name"
        ]
        != doe_case.mesh_policy_name
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: certified "
            "mesh-policy mismatch."
        )

    mesh_path = (
        ROOT
        / preparation_row[
            "mesh_relative_path"
        ]
    )

    step_path = (
        ROOT
        / preparation_row[
            "step_relative_path"
        ]
    )

    mesh_hash = sha256(
        mesh_path
    )

    step_hash = sha256(
        step_path
    )

    if (
        mesh_hash
        != preparation_row[
            "mesh_sha256"
        ]
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: certified "
            "mesh SHA drift."
        )

    if (
        step_hash
        != preparation_row[
            "step_sha256"
        ]
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: certified "
            "STEP SHA drift."
        )

    token = resolved.case_hash[:16]

    bundle = (
        build_generic_fem_definition_bundle(
            resolved,
            mesh_id=f"mesh-{token}",
            geometry_id=f"geometry-{token}",
            classification_id=(
                f"classification-{token}"
            ),
            source_mesh_name=mesh_path.name,
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

    require_close(
        f"{doe_case.case_id} analytical seed",
        bundle.calibration_seed
        .predicted_delta_temperature_c,
        analytical_dt,
    )

    if (
        bundle.calibration_seed.target_force_n
        != resolved.source_case.loading.target_preload_n
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: preload "
            "did not propagate into FEM bundle."
        )

    mesh_data = (
        read_grouped_complete_joint_mesh(
            mesh_path,
            bundle.transfer,
        )
    )

    trial = PreloadCalibrationTrial(
        trial_index=1,
        run_id=rollout_trial_run_id,
        delta_temperature_c=(
            predicted_delta_t
        ),
        source=(
            PreloadCalibrationTrialSource.FEM_WARM_START
        ),
    )

    if (
        trial.run_id
        == canonical_trial1_run_id
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: V2.1 sibling "
            "collided with canonical V1 Trial 1."
        )

    run_dir = (
        SOLVER_ROOT
        / canonical_case_run_id
        / rollout_trial_run_id
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    input_path = (
        run_dir
        / f"{rollout_trial_run_id}.inp"
    )

    prior_deck_hash = (
        sha256(input_path)
        if input_path.exists()
        else None
    )

    deck = (
        write_fem_preload_calibration_trial_deck(
            mesh_data=mesh_data,
            bundle=bundle,
            trial=trial,
            reference_temperature_c=(
                reference_temperature
            ),
            input_path=input_path,
        )
    )

    actual_deck_hash = sha256(
        input_path
    )

    if (
        actual_deck_hash
        != deck.sha256
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: generated "
            "deck SHA mismatch."
        )

    if (
        prior_deck_hash is not None
        and prior_deck_hash
        != actual_deck_hash
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: existing "
            "V2.1 rollout deck changed."
        )

    require_close(
        f"{doe_case.case_id} deck delta T",
        deck.delta_temperature_c,
        predicted_delta_t,
    )

    record = {
        "schema_version": 1,
        "record_id": (
            "TRM-P3-CP8-WSV21-ROLLOUT-"
            f"{doe_case.case_id}-PREP-P01"
        ),
        "record_status": "FINAL",

        "case": {
            "case_id": doe_case.case_id,
            "case_hash": doe_case.case_hash,
            "canonical_case_run_id": (
                canonical_case_run_id
            ),
            "canonical_trial1_run_id": (
                canonical_trial1_run_id
            ),
            "v2_1_trial1_run_id": (
                rollout_trial_run_id
            ),
            "normalized_coordinates": list(
                xyz
            ),
            "target_preload_n": (
                resolved
                .source_case
                .loading
                .target_preload_n
            ),
            "mesh_policy_name": (
                doe_case.mesh_policy_name
            ),
            "role": (
                "V2_1_PRODUCTION_ROLLOUT_FIRST_SHOT"
            ),
        },

        "governance": {
            "doe_policy_sha256": (
                doe_policy_hash
            ),
            "campaign_manifest_sha256": (
                campaign_hash
            ),
            "preparation_certification_sha256": (
                preparation_cert_hash
            ),
            "warm_v1_knowledge_sha256": (
                warm_v1_hash
            ),
            "v2_1_policy_sha256": (
                v21_policy_hash
            ),
            "frozen_prospective_prediction_sha256": (
                frozen_prediction_hash
            ),
            "rollout_authorization_relative_path": (
                relative(
                    ROLLOUT_AUTHORIZATION_PATH
                )
            ),
            "rollout_authorization_sha256": (
                rollout_authorization_hash
            ),
        },

        "frozen_v2_1_prediction": {
            "dimension_order": list(order),
            "analytical_delta_temperature_c": (
                analytical_dt
            ),
            "trilinear_correction_factor": (
                base_factor
            ),
            "bubble_value": bubble_value,
            "frozen_k": derived_k,
            "bubble_residual_correction_factor": (
                residual_factor
            ),
            "v2_1_correction_factor": (
                v21_factor
            ),
            "predicted_delta_temperature_c": (
                predicted_delta_t
            ),
            "model_refit_performed": False,
        },

        "canonical_v1_protection": {
            "preserved": True,
            "canonical_preparation_relative_path": (
                relative(
                    canonical_prep_path
                )
            ),
            "canonical_preparation_sha256": (
                canonical_prep_hash
            ),
            "canonical_deck_relative_path": (
                relative(
                    canonical_deck_path
                )
            ),
            "canonical_deck_sha256": (
                canonical_deck_hash
            ),
            "canonical_v1_delta_temperature_c": (
                canonical_v1_delta_t
            ),
            "canonical_v1_executed": False,
        },

        "fem_preflight": {
            "target": "fem",
            "blocking_error_count": 0,
            "status": "PASS",
            "report": jsonable(
                preflight
            ),
        },

        "prepared_artifacts": {
            "preparation_evidence_kind": (
                preparation_row[
                    "preparation_evidence_kind"
                ]
            ),
            "step_relative_path": (
                relative(step_path)
            ),
            "step_sha256": step_hash,
            "mesh_relative_path": (
                relative(mesh_path)
            ),
            "mesh_sha256": mesh_hash,
        },

        "trial_1": jsonable(
            trial
        ),

        "deck": {
            "relative_path": (
                relative(input_path)
            ),
            "sha256": actual_deck_hash,
            "size_bytes": (
                input_path.stat().st_size
            ),
            "node_count": deck.node_count,
            "element_count": (
                deck.element_count
            ),
            "delta_temperature_c": (
                deck.delta_temperature_c
            ),
        },

        "calibration_acceptance": {
            "target_relative_tolerance": (
                preload_template
                .target_relative_tolerance
            ),
            "interface_spread_relative_tolerance": (
                preload_template
                .interface_spread_relative_tolerance
            ),
            "evaluation_status": "NOT_RUN",
            "trial_2_policy": (
                "ONLY_IF_GOVERNED_FIRST_SHOT_REJECTS"
            ),
        },

        "zero_solve_assertion": {
            "solver_outputs_detected": False,
            "solver_results_read": False,
            "calculix_invoked": False,
            "solver_authorized_by_this_script": False,
            "blind_holdout_accessed": False,
            "v2_1_refit_performed": False,
        },

        "overall_disposition": (
            "V2_1_ROLLOUT_CASE_PREPARATION_PASS_"
            "AWAITING_BATCH_CERTIFICATION"
        ),
    }

    record_path = (
        run_dir
        / "production_doe_v2_1_rollout_solver_preparation_record.json"
    )

    action, preparation_hash = (
        write_immutable_json(
            record_path,
            record,
        )
    )

    if (
        sha256(canonical_prep_path)
        != canonical_prep_hash
        or sha256(canonical_deck_path)
        != canonical_deck_hash
    ):
        raise RuntimeError(
            f"{doe_case.case_id}: canonical "
            "V1 evidence changed during rollout "
            "preparation."
        )

    outputs_after = solver_outputs_present(
        SOLVER_ROOT
        / canonical_case_run_id
    )

    if outputs_after:
        raise RuntimeError(
            f"{doe_case.case_id}: solver output "
            "appeared during zero-solve preparation:\n"
            + "\n".join(outputs_after)
        )

    rollout_rows.append(
        {
            "case_id": doe_case.case_id,
            "case_hash": doe_case.case_hash,
            "normalized_coordinates": list(
                xyz
            ),
            "target_preload_n": (
                resolved
                .source_case
                .loading
                .target_preload_n
            ),
            "mesh_policy_name": (
                doe_case.mesh_policy_name
            ),
            "analytical_delta_temperature_c": (
                analytical_dt
            ),
            "trilinear_correction_factor": (
                base_factor
            ),
            "bubble_value": bubble_value,
            "frozen_k": derived_k,
            "bubble_residual_correction_factor": (
                residual_factor
            ),
            "v2_1_correction_factor": (
                v21_factor
            ),
            "predicted_delta_temperature_c": (
                predicted_delta_t
            ),
            "canonical_v1_delta_temperature_c": (
                canonical_v1_delta_t
            ),
            "step_relative_path": (
                relative(step_path)
            ),
            "step_sha256": step_hash,
            "mesh_relative_path": (
                relative(mesh_path)
            ),
            "mesh_sha256": mesh_hash,
            "v2_1_trial_run_id": (
                rollout_trial_run_id
            ),
            "deck_relative_path": (
                relative(input_path)
            ),
            "deck_sha256": actual_deck_hash,
            "deck_size_bytes": (
                input_path.stat().st_size
            ),
            "preparation_relative_path": (
                relative(record_path)
            ),
            "preparation_sha256": (
                preparation_hash
            ),
            "record_action": action,
            "solver_outputs_present": False,
        }
    )


# ============================================================
# 9. CAMPAIGN-LEVEL ZERO-SOLVE ROLLOUT MANIFEST
# ============================================================

rollout_manifest = {
    "schema_version": 1,
    "record_id": (
        "TRM-P3-CP8-WSV21-"
        "ROLLOUT-PREPARATION-P01"
    ),
    "record_status": "FINAL",
    "campaign_id": "TRM-PDOE-C01",

    "authorization": {
        "relative_path": (
            relative(
                ROLLOUT_AUTHORIZATION_PATH
            )
        ),
        "sha256": (
            rollout_authorization_hash
        ),
        "overall_disposition": (
            authorization[
                "overall_disposition"
            ]
        ),
        "scope": rollout["scope"],
        "predictor": rollout["predictor"],
    },

    "frozen_model": {
        "policy_relative_path": (
            relative(V21_POLICY_PATH)
        ),
        "policy_sha256": (
            v21_policy_hash
        ),
        "prospective_prediction_relative_path": (
            relative(
                FROZEN_PREDICTION_PATH
            )
        ),
        "prospective_prediction_sha256": (
            frozen_prediction_hash
        ),
        "method": (
            "exact_trilinear_plus_single_"
            "interior_bubble_residual"
        ),
        "dimension_order": list(order),
        "certified_corner_count": 8,
        "corner_records": sorted(
            corner_records,
            key=lambda row: row["case_id"],
        ),
        "development_case_id": (
            DEVELOPMENT_ID
        ),
        "development_evidence_relative_path": (
            relative(
                development_evidence_path
            )
        ),
        "development_evidence_sha256": (
            development_evidence_hash
        ),
        "derived_and_verified_frozen_k": (
            derived_k
        ),
        "model_refit_performed": False,
        "prospective_sentinel_used_for_refit": False,
        "rollout_results_used_for_refit": False,
    },

    "case_selection": {
        "selection_method": (
            "derive_from_frozen_campaign_minus_"
            "governed_accepted_design_evidence"
        ),
        "fresh_design_case_count": (
            len(fresh_design_cases)
        ),
        "accepted_before_rollout_count": (
            len(accepted_ids)
        ),
        "accepted_before_rollout_case_ids": (
            sorted(accepted_ids)
        ),
        "accepted_evidence": sorted(
            accepted_evidence,
            key=lambda row: row["case_id"],
        ),
        "remaining_authorized_count": (
            required_remaining_count
        ),
        "derived_remaining_count": (
            len(remaining_cases)
        ),
        "remaining_case_ids": [
            row.case_id
            for row in remaining_cases
        ],
        "legacy_anchors_excluded": True,
        "already_accepted_design_cases_excluded": True,
        "prospective_sentinel_excluded": True,
        "blind_holdouts_excluded": True,
    },

    "rollout_cases": rollout_rows,

    "execution_policy": {
        "first_shot_target_relative_tolerance": (
            float(
                rollout[
                    "first_shot_target_relative_tolerance"
                ]
            )
        ),
        "first_shot_interface_spread_relative_tolerance": (
            float(
                rollout[
                    "first_shot_interface_spread_relative_tolerance"
                ]
            )
        ),
        "trial_2_only_if_governed_first_shot_rejects": True,
        "v2_1_model_frozen_for_entire_rollout": True,
        "blind_holdout_execution_authorized": False,
    },

    "zero_solve_certification_input": {
        "prepared_case_count": (
            len(rollout_rows)
        ),
        "all_case_preflights_passed": True,
        "all_canonical_v1_preparations_preserved": True,
        "all_canonical_v1_decks_preserved": True,
        "all_v2_1_sibling_decks_written": True,
        "solver_outputs_detected": False,
        "solver_results_read": False,
        "calculix_invoked": False,
        "solver_execution_authorized_by_this_record": False,
        "blind_holdout_accessed": False,
        "ready_for_independent_batch_certification": True,
    },

    "overall_disposition": (
        "V2_1_ROLLOUT_PREPARATION_PASS_"
        "AWAITING_INDEPENDENT_CERTIFICATION"
    ),
}


manifest_action, manifest_hash = (
    write_immutable_json(
        ROLLOUT_MANIFEST_PATH,
        rollout_manifest,
    )
)


# ============================================================
# 10. FINAL ZERO-SOLVE GUARDS + REPORT
# ============================================================

for doe_case in remaining_cases:
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
            f"{doe_case.case_id}: final zero-solve "
            "guard found solver outputs:\n"
            + "\n".join(outputs)
        )


print("=" * 132)
print(
    "THREADROM - WARM-START V2.1 "
    "BULK ROLLOUT PREPARATION"
)
print("=" * 132)

print()
print(
    "Authorization SHA256            :",
    rollout_authorization_hash,
)
print(
    "Authorization disposition       :",
    authorization["overall_disposition"],
)
print(
    "V2.1 policy SHA256              :",
    v21_policy_hash,
)
print(
    "Frozen prediction SHA256        :",
    frozen_prediction_hash,
)

print()
print(
    "Re-derived frozen k             :",
    derived_k,
)
print(
    "Frozen k verification           : PASS"
)

print()
print(
    "Fresh design states             :",
    len(fresh_design_cases),
)
print(
    "Governed accepted states        :",
    len(accepted_ids),
)
print(
    "Remaining authorized states     :",
    len(remaining_cases),
)

print()
for row in rollout_rows:
    print(
        f"{row['case_id']:12s} | "
        f"run={row['v2_1_trial_run_id']} | "
        f"analytical={row['analytical_delta_temperature_c']:.9f} C | "
        f"factor={row['v2_1_correction_factor']:.12f} | "
        f"V2.1={row['predicted_delta_temperature_c']:.9f} C"
    )

print()
print(
    "Canonical V1 evidence preserved : YES"
)
print(
    "V2.1 sibling decks prepared     :",
    len(rollout_rows),
)
print(
    "Solver outputs detected         : NONE"
)
print(
    "CalculiX invoked                : NO"
)
print(
    "Solver results read             : NO"
)
print(
    "V2.1 refit performed            : NO"
)
print(
    "Blind holdouts accessed         : NO"
)
print(
    "Solver authorized by this step  : NO"
)

print()
print(
    "Rollout manifest action         :",
    manifest_action,
)
print(
    "Rollout manifest SHA256         :",
    manifest_hash,
)
print(
    "Rollout manifest                :",
    ROLLOUT_MANIFEST_PATH,
)

print()
print(
    "Disposition                     : "
    "V2_1_ROLLOUT_PREPARATION_PASS_"
    "AWAITING_INDEPENDENT_CERTIFICATION"
)

print("=" * 132)
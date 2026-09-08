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

V2_POLICY_PATH = (
    CONFIG
    / "phase3_warm_start_delta_t_v2.toml"
)

V21_POLICY_PATH = (
    CONFIG
    / "phase3_warm_start_delta_t_v2_1.toml"
)

CAMPAIGN_MANIFEST_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_campaign_manifest.json"
)

WARM_V1_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_warm_start_knowledge_record.json"
)

V2_DIAGNOSTIC_SCRIPT = (
    ROOT
    / "scripts"
    / "diagnose_phase3_warm_start_delta_t_v2.py"
)

V2_FAILURE_LOG = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_retrospective_diagnostic.txt"
)

OUTPUT_PATH = (
    CAMPAIGN_ROOT
    / "warm_start_delta_t_v2_1_prospective_prediction.json"
)

EXPECTED_V21_POLICY_SHA256 = (
    "db2a2af4a2954801d7e1db931672a197629a5dfc"
    "ab19431c3a38db65b580268c"
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
PROSPECTIVE_ID = "D-INT-008"


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
            lambda: stream.read(
                8 * 1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


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
    name: str,
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
            f"{name} mismatch: "
            f"{actual!r} != {expected!r}"
        )


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
            f"{case_id}: expected exactly one "
            f"design case; found {len(matches)}."
        )

    return matches[0]


def get_manifest_row(
    manifest: dict,
    case_id: str,
) -> dict:
    matches = [
        row
        for row in manifest[
            "design_cases"
        ]
        if row.get(
            "case_id"
        ) == case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected exactly one "
            f"manifest row; found {len(matches)}."
        )

    return matches[0]


def coordinates(
    manifest: dict,
    case_id: str,
    order: tuple[str, ...],
) -> tuple[
    float,
    float,
    float,
]:
    raw = get_manifest_row(
        manifest,
        case_id,
    )[
        "normalized_coordinates"
    ]

    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError(
            f"{case_id}: coordinates are not a mapping."
        )

    xyz = tuple(
        float(
            raw[key]
        )
        for key in order
    )

    if len(xyz) != 3:
        raise RuntimeError(
            "V2.1 requires exactly three dimensions."
        )

    return xyz


def bubble(
    xyz: tuple[
        float,
        float,
        float,
    ],
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
    xyz: tuple[
        float,
        float,
        float,
    ],
    corners: dict[
        tuple[
            float,
            float,
            float,
        ],
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
                    x if ix
                    else 1.0 - x
                )

                wy = (
                    y if iy
                    else 1.0 - y
                )

                wz = (
                    z if iz
                    else 1.0 - z
                )

                result += (
                    wx
                    * wy
                    * wz
                    * corners[key]
                )

    return result


def solver_outputs_present(
    case_root: Path,
) -> tuple[str, ...]:

    if not case_root.exists():
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

    for path in case_root.rglob("*"):

        if not path.is_file():
            continue

        if (
            path.name in forbidden_names
            or path.suffix.lower()
            in forbidden_suffixes
        ):
            found.append(
                path.relative_to(
                    ROOT
                ).as_posix()
            )

    return tuple(
        sorted(
            found
        )
    )


# ============================================================
# 1. VERIFY FROZEN V2.1 POLICY
# ============================================================

actual_v21_sha = sha256(
    V21_POLICY_PATH
)

if (
    actual_v21_sha
    != EXPECTED_V21_POLICY_SHA256
):
    raise RuntimeError(
        "Frozen V2.1 policy SHA drift."
    )

v21 = load_toml(
    V21_POLICY_PATH
)

if (
    v21[
        "identity"
    ][
        "status"
    ]
    != "frozen"
):
    raise RuntimeError(
        "V2.1 policy is not frozen."
    )

if (
    v21[
        "prospective_validation"
    ][
        "case_id"
    ]
    != PROSPECTIVE_ID
):
    raise RuntimeError(
        "Prospective case-ID drift."
    )


# ============================================================
# 2. VERIFY V2 FAILURE PROVENANCE
# ============================================================

provenance = (
    v21[
        "provenance"
    ]
)

if (
    sha256(
        V2_POLICY_PATH
    )
    != provenance[
        "v2_policy_sha256"
    ]
):
    raise RuntimeError(
        "V2 policy provenance drift."
    )

if (
    sha256(
        V2_DIAGNOSTIC_SCRIPT
    )
    != provenance[
        "v2_diagnostic_script_sha256"
    ]
):
    raise RuntimeError(
        "V2 diagnostic-script provenance drift."
    )

if (
    sha256(
        V2_FAILURE_LOG
    )
    != provenance[
        "v2_proxy_fail_log_sha256"
    ]
):
    raise RuntimeError(
        "Frozen V2 failure-log provenance drift."
    )

failure_text = (
    V2_FAILURE_LOG.read_text(
        encoding="utf-8-sig"
    )
)

if (
    "RETROSPECTIVE VERDICT         : PROXY_FAIL"
    not in failure_text
):
    raise RuntimeError(
        "Frozen V2 failure evidence does not "
        "contain PROXY_FAIL."
    )


# ============================================================
# 3. LOAD FROZEN DESIGN INFORMATION ONLY
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

manifest = load_json(
    CAMPAIGN_MANIFEST_PATH
)

warm = load_json(
    WARM_V1_PATH
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


# ============================================================
# 4. VERIFY PROSPECTIVE CASE HAS NO SOLVER RESPONSE
# ============================================================

prospective_case = (
    get_design_case(
        campaign,
        PROSPECTIVE_ID,
    )
)

prospective_case_root = (
    SOLVER_ROOT
    / (
        "trm_fem_"
        + prospective_case.case_hash[:12]
    )
)

detected_outputs = (
    solver_outputs_present(
        prospective_case_root
    )
)

if detected_outputs:
    raise RuntimeError(
        "Prospective purity violated: "
        "D-INT-008 solver outputs already exist:\n"
        + "\n".join(
            detected_outputs
        )
    )


# ============================================================
# 5. VERIFY RESPONSE-BLIND SENTINEL SELECTION
# ============================================================

development_xyz = coordinates(
    manifest,
    DEVELOPMENT_ID,
    order,
)

margin = float(
    v21[
        "prospective_selection"
    ][
        "meaningful_interior_margin"
    ]
)

excluded = (
    set(
        CORNER_IDS
    )
    | {
        DEVELOPMENT_ID,
    }
)

eligible = []

for row in manifest[
    "design_cases"
]:

    case_id = row[
        "case_id"
    ]

    if case_id in excluded:
        continue

    if not case_id.startswith(
        "D-INT-"
    ):
        raise RuntimeError(
            f"Unexpected remaining design case: {case_id}"
        )

    xyz = coordinates(
        manifest,
        case_id,
        order,
    )

    if not all(
        margin
        <= value
        <= 1.0 - margin
        for value in xyz
    ):
        continue

    b = bubble(
        xyz
    )

    distance = math.dist(
        xyz,
        development_xyz,
    )

    score = (
        b
        * distance
    )

    eligible.append(
        (
            score,
            case_id,
            xyz,
            b,
            distance,
        )
    )


if not eligible:
    raise RuntimeError(
        "No meaningful-interior prospective "
        "candidates found."
    )

ranking = sorted(
    eligible,
    key=lambda item: (
        -item[0],
        item[1],
    ),
)

winner = ranking[0]

if winner[1] != PROSPECTIVE_ID:
    raise RuntimeError(
        "Response-blind prospective-selection "
        f"winner drift: {winner[1]}"
    )

prospective_xyz = winner[
    2
]

prospective_bubble = winner[
    3
]

prospective_distance = winner[
    4
]

prospective_score = winner[
    0
]

policy_xyz = tuple(
    float(value)
    for value in v21[
        "prospective_selection"
    ][
        "selected_normalized_coordinates"
    ]
)

for index, (
    actual,
    expected,
) in enumerate(
    zip(
        prospective_xyz,
        policy_xyz,
        strict=True,
    )
):
    require_close(
        f"Prospective coordinate {index}",
        actual,
        expected,
    )

require_close(
    "Prospective bubble",
    prospective_bubble,
    float(
        v21[
            "prospective_selection"
        ][
            "selected_bubble_value"
        ]
    ),
    abs_tol=5.0e-8,
)

require_close(
    "Prospective development distance",
    prospective_distance,
    float(
        v21[
            "prospective_selection"
        ][
            "selected_distance_from_development"
        ]
    ),
    abs_tol=5.0e-8,
)

require_close(
    "Prospective selection score",
    prospective_score,
    float(
        v21[
            "prospective_selection"
        ][
            "selected_selection_score_approx"
        ]
    ),
    abs_tol=5.0e-8,
)


# ============================================================
# 6. RECONSTRUCT CERTIFIED EIGHT-CORNER SURFACE
# ============================================================

legacy = {
    item[
        "case_id"
    ]: item
    for item in warm[
        "anchors"
    ]
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
        manifest,
        case_id,
        order,
    )

    if case_id in LEGACY_ANCHORS:

        evidence = legacy[
            case_id
        ]

        if (
            evidence.get(
                "status"
            )
            != "CERTIFIED_REUSABLE"
        ):
            raise RuntimeError(
                f"{case_id}: legacy anchor "
                "not certified reusable."
            )

        if (
            evidence[
                "case_hash"
            ]
            != doe_case.case_hash
        ):
            raise RuntimeError(
                f"{case_id}: anchor hash mismatch."
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
            f"{case_id} stored factor",
            factor,
            float(
                evidence[
                    "correction_factor"
                ]
            ),
        )

        evidence_path = (
            WARM_V1_PATH
        )

        evidence_sha = sha256(
            WARM_V1_PATH
        )

        evidence_type = (
            "CERTIFIED_REUSABLE_WARM_KNOWLEDGE"
        )

    elif case_id in BOUNDARY_ANCHORS:

        evidence_path = (
            SOLVER_ROOT
            / (
                "trm_fem_"
                + doe_case.case_hash[:12]
            )
            / "production_doe_accepted_fem_evidence.json"
        )

        evidence = load_json(
            evidence_path
        )

        if (
            evidence[
                "record_status"
            ]
            != "FINAL"
            or evidence[
                "overall_disposition"
            ]
            != "PRODUCTION_DOE_FEM_CALIBRATION_ACCEPTED"
        ):
            raise RuntimeError(
                f"{case_id}: boundary evidence "
                "not FINAL accepted FEM."
            )

        semantics = (
            evidence[
                "evidence_semantics"
            ]
        )

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
                f"{case_id}: boundary evidence "
                "not V2-anchor eligible."
            )

        if (
            evidence[
                "accepted_calibration"
            ][
                "decision"
            ][
                "disposition"
            ]
            != "accept"
        ):
            raise RuntimeError(
                f"{case_id}: governed ACCEPT missing."
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

        evidence_sha = sha256(
            evidence_path
        )

        evidence_type = (
            "FINAL_GOVERNED_ACCEPTED_FEM_EVIDENCE"
        )

    else:
        raise RuntimeError(
            f"Unexpected corner: {case_id}"
        )

    corner_factors[
        xyz
    ] = factor

    corner_records.append(
        {
            "case_id": case_id,
            "case_hash": doe_case.case_hash,
            "normalized_coordinates": list(
                xyz
            ),
            "analytical_delta_temperature_c": (
                analytical_dt
            ),
            "accepted_delta_temperature_c": (
                accepted_dt
            ),
            "correction_factor": factor,
            "evidence_type": evidence_type,
            "evidence_relative_path": (
                evidence_path
                .relative_to(
                    ROOT
                )
                .as_posix()
            ),
            "evidence_sha256": (
                evidence_sha
            ),
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

if (
    set(
        corner_factors
    )
    != expected_cube
):
    raise RuntimeError(
        "Eight-corner correction-factor cube incomplete."
    )


# ============================================================
# 7. DERIVE SINGLE INTERIOR RESIDUAL COEFFICIENT k
# ============================================================

development_case = (
    get_design_case(
        campaign,
        DEVELOPMENT_ID,
    )
)

development_resolved = (
    resolve_case(
        development_case.case
    )
)

development_seed = (
    derive_analytical_thermal_preload_seed(
        development_resolved
    )
)

development_analytical_dt = (
    development_seed
    .predicted_delta_temperature_c
)

development_evidence_path = (
    SOLVER_ROOT
    / (
        "trm_fem_"
        + development_case.case_hash[:12]
    )
    / "production_doe_accepted_fem_evidence.json"
)

development_sha = sha256(
    development_evidence_path
)

expected_development_sha = (
    v21[
        "development_evidence"
    ][
        "accepted_fem_evidence_sha256"
    ]
)

if (
    development_sha
    != expected_development_sha
):
    raise RuntimeError(
        "D-INT-010 development-evidence SHA drift."
    )

development_evidence = load_json(
    development_evidence_path
)

if (
    development_evidence[
        "record_status"
    ]
    != "FINAL"
    or development_evidence[
        "overall_disposition"
    ]
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

development_base_factor = (
    trilinear(
        development_xyz,
        corner_factors,
    )
)

development_bubble = bubble(
    development_xyz
)

if development_bubble <= 0.0:
    raise RuntimeError(
        "D-INT-010 bubble value must be positive."
    )

residual_factor = (
    development_actual_factor
    - development_base_factor
)

k = (
    residual_factor
    / development_bubble
)

if not math.isfinite(
    k
):
    raise RuntimeError(
        "Derived V2.1 coefficient k is not finite."
    )


# ============================================================
# 8. DERIVE PROSPECTIVE D-INT-008 PREDICTION
# ============================================================

prospective_resolved = (
    resolve_case(
        prospective_case.case
    )
)

prospective_seed = (
    derive_analytical_thermal_preload_seed(
        prospective_resolved
    )
)

prospective_analytical_dt = (
    prospective_seed
    .predicted_delta_temperature_c
)

prospective_base_factor = (
    trilinear(
        prospective_xyz,
        corner_factors,
    )
)

prospective_residual_factor = (
    k
    * prospective_bubble
)

prospective_v21_factor = (
    prospective_base_factor
    + prospective_residual_factor
)

if (
    not math.isfinite(
        prospective_v21_factor
    )
    or prospective_v21_factor <= 0.0
):
    raise RuntimeError(
        "V2.1 prospective correction factor invalid."
    )

predicted_delta_t = (
    prospective_analytical_dt
    * prospective_v21_factor
)

if (
    not math.isfinite(
        predicted_delta_t
    )
    or predicted_delta_t >= 0.0
):
    raise RuntimeError(
        "V2.1 prospective delta T is not "
        "finite thermal contraction."
    )


# ============================================================
# 9. FREEZE IMMUTABLE PROSPECTIVE PREDICTION
# ============================================================

record = {
    "schema_version": 1,

    "record_id": (
        "TRM-P3-CP8-WSV21-"
        "D-INT-008-PROSPECTIVE-001"
    ),

    "record_status": "FINAL",

    "policy": {
        "policy_id": (
            v21[
                "identity"
            ][
                "policy_id"
            ]
        ),
        "relative_path": (
            V21_POLICY_PATH
            .relative_to(
                ROOT
            )
            .as_posix()
        ),
        "sha256": (
            actual_v21_sha
        ),
    },

    "method": {
        "base_surface": (
            "exact_trilinear_interpolation"
        ),
        "interior_correction": (
            "single_bubble_residual"
        ),
        "bubble_formula": (
            "64*x*(1-x)*y*(1-y)*z*(1-z)"
        ),
        "additional_fit_parameters": 1,
    },

    "corner_surface": {
        "certified_corner_count": 8,
        "records": sorted(
            corner_records,
            key=lambda row: (
                row[
                    "case_id"
                ]
            ),
        ),
    },

    "development_residual": {
        "case_id": (
            DEVELOPMENT_ID
        ),
        "case_hash": (
            development_case.case_hash
        ),
        "normalized_coordinates": list(
            development_xyz
        ),
        "analytical_delta_temperature_c": (
            development_analytical_dt
        ),
        "accepted_delta_temperature_c": (
            development_accepted_dt
        ),
        "actual_correction_factor": (
            development_actual_factor
        ),
        "trilinear_correction_factor": (
            development_base_factor
        ),
        "bubble_value": (
            development_bubble
        ),
        "correction_factor_residual": (
            residual_factor
        ),
        "derived_k": (
            k
        ),
        "accepted_evidence_relative_path": (
            development_evidence_path
            .relative_to(
                ROOT
            )
            .as_posix()
        ),
        "accepted_evidence_sha256": (
            development_sha
        ),
        "validation_role": (
            "DEVELOPMENT_ONLY_NOT_V2_1_VALIDATION"
        ),
    },

    "prospective_selection": {
        "response_blind": True,
        "meaningful_interior_margin": (
            margin
        ),
        "eligible_candidate_count": (
            len(
                ranking
            )
        ),
        "selection_rule": (
            "maximum_bubble_times_"
            "distance_then_case_id"
        ),
        "selected_case_id": (
            PROSPECTIVE_ID
        ),
        "selected_normalized_coordinates": list(
            prospective_xyz
        ),
        "bubble_value": (
            prospective_bubble
        ),
        "distance_from_development": (
            prospective_distance
        ),
        "selection_score": (
            prospective_score
        ),
    },

    "prospective_prediction": {
        "case_id": (
            PROSPECTIVE_ID
        ),
        "case_hash": (
            prospective_case.case_hash
        ),
        "analytical_delta_temperature_c": (
            prospective_analytical_dt
        ),
        "trilinear_correction_factor": (
            prospective_base_factor
        ),
        "bubble_residual_correction_factor": (
            prospective_residual_factor
        ),
        "v2_1_correction_factor": (
            prospective_v21_factor
        ),
        "predicted_delta_temperature_c": (
            predicted_delta_t
        ),
        "target_preload_n": (
            prospective_resolved
            .source_case
            .loading
            .target_preload_n
        ),
        "prediction_status": (
            "FROZEN_BEFORE_FEM_RESULT_ACCESS"
        ),
    },

    "prospective_purity": {
        "solver_outputs_detected_before_freeze": False,
        "solver_results_read": False,
        "calculix_invoked": False,
        "solver_authorized_by_this_script": False,
        "existing_v1_solver_preparation_modified": False,
        "blind_holdout_results_accessed": False,
    },

    "deployment": {
        "rollout_authorized": False,
        "prospective_fem_confirmation_required": True,
        "required_success_label": (
            "PROSPECTIVE_PASS"
        ),
        "target_relative_tolerance": (
            float(
                v21[
                    "prospective_validation"
                ][
                    "target_relative_tolerance"
                ]
            )
        ),
    },

    "overall_disposition": (
        "V2_1_PROSPECTIVE_PREDICTION_"
        "FROZEN_AWAITING_FEM"
    ),
}


serialized = (
    json.dumps(
        record,
        indent=2,
        sort_keys=True,
    )
    + "\n"
)


if OUTPUT_PATH.exists():

    existing = (
        OUTPUT_PATH.read_text(
            encoding="utf-8"
        )
    )

    if existing != serialized:
        raise RuntimeError(
            "Prospective prediction already exists "
            "with different content. "
            "Refusing overwrite."
        )

    action = (
        "UNCHANGED / IDENTICAL"
    )

else:

    OUTPUT_PATH.write_text(
        serialized,
        encoding="utf-8",
        newline="\n",
    )

    action = "CREATED"


record_sha = sha256(
    OUTPUT_PATH
)

sidecar = (
    OUTPUT_PATH.with_suffix(
        ".sha256"
    )
)

sidecar_text = (
    f"{record_sha}  "
    f"{OUTPUT_PATH.name}\n"
)

if sidecar.exists():

    if (
        sidecar.read_text(
            encoding="ascii"
        )
        != sidecar_text
    ):
        raise RuntimeError(
            "Prospective prediction SHA sidecar drift."
        )

else:

    sidecar.write_text(
        sidecar_text,
        encoding="ascii",
        newline="\n",
    )


# ============================================================
# 10. REPORT
# ============================================================

print("=" * 126)
print(
    "THREADROM - WARM-START V2.1 "
    "PROSPECTIVE PREDICTION FREEZE"
)
print("=" * 126)

print()
print(
    "Policy SHA256                :",
    actual_v21_sha,
)

print()
print(
    "Development case             :",
    DEVELOPMENT_ID,
)

print(
    "Development coordinates      :",
    development_xyz,
)

print(
    "Development bubble           :",
    development_bubble,
)

print(
    "Actual correction factor     :",
    development_actual_factor,
)

print(
    "Trilinear correction factor  :",
    development_base_factor,
)

print(
    "Residual correction factor   :",
    residual_factor,
)

print(
    "Derived k                    :",
    k,
)

print()
print(
    "Prospective case             :",
    PROSPECTIVE_ID,
)

print(
    "Prospective coordinates      :",
    prospective_xyz,
)

print(
    "Prospective bubble           :",
    prospective_bubble,
)

print(
    "Selection distance           :",
    prospective_distance,
)

print(
    "Selection score              :",
    prospective_score,
)

print()
print(
    "Analytical delta T C         :",
    prospective_analytical_dt,
)

print(
    "Trilinear base factor        :",
    prospective_base_factor,
)

print(
    "Bubble residual factor       :",
    prospective_residual_factor,
)

print(
    "V2.1 correction factor       :",
    prospective_v21_factor,
)

print(
    "FROZEN predicted delta T C   :",
    predicted_delta_t,
)

print()
print(
    "Prospective solver outputs   : NONE DETECTED"
)

print(
    "Prospective FEM result read  : NO"
)

print(
    "CalculiX invoked             : NO"
)

print(
    "Old V1 preparation modified  : NO"
)

print(
    "Blind holdout results used   : NO"
)

print(
    "Rollout authorized           : NO"
)

print()
print(
    "Record action                :",
    action,
)

print(
    "Record SHA256                :",
    record_sha,
)

print(
    "Record path                  :",
    OUTPUT_PATH,
)

print()
print(
    "Disposition                  : "
    "V2_1_PROSPECTIVE_PREDICTION_"
    "FROZEN_AWAITING_FEM"
)

print("=" * 126)
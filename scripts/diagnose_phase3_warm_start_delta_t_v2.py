from __future__ import annotations

import hashlib
import json
import math
import tomllib

from pathlib import Path

from threadrom.case.resolver import resolve_case
from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)
from threadrom.factory.preload_calibration_seed import (
    derive_analytical_thermal_preload_seed,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
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

CAMPAIGN_MANIFEST_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_campaign_manifest.json"
)

PREPARATION_CERT_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_preparation_certification_record.json"
)

ANCHOR_BINDING_PATH = (
    CAMPAIGN_ROOT
    / "existing_anchor_binding_record.json"
)

WARM_V1_PATH = (
    CAMPAIGN_ROOT
    / "production_doe_warm_start_knowledge_record.json"
)

EXPECTED_V2_POLICY_SHA256 = (
    "a548e95b538a7ec94eeb76d77502c7e75e2394d"
    "5847ab50e6b57d497e7f0a941"
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

LEGACY_ANCHOR_IDS = {
    "A00",
    "A01",
    "A02",
    "A03",
}

NEW_BOUNDARY_IDS = {
    "D-BND-001",
    "D-BND-002",
    "D-BND-003",
    "D-BND-004",
}

SENTINEL_ID = "D-INT-010"


def sha256(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)

    if path.stat().st_size <= 0:
        raise RuntimeError(
            f"Empty governed evidence file: {path}"
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


def require_negative_finite(
    name: str,
    value: float,
) -> None:

    if (
        not math.isfinite(value)
        or value >= 0.0
    ):
        raise RuntimeError(
            f"{name} must be finite thermal contraction."
        )


def verify_sha_sidecar(
    record_path: Path,
) -> str:

    actual = sha256(
        record_path
    )

    sidecar = (
        record_path
        .with_suffix(".sha256")
    )

    if not sidecar.is_file():
        raise RuntimeError(
            f"Missing evidence SHA sidecar: {sidecar}"
        )

    expected_line = (
        f"{actual}  {record_path.name}"
    )

    observed_line = (
        sidecar.read_text(
            encoding="ascii"
        )
        .strip()
    )

    if observed_line != expected_line:
        raise RuntimeError(
            f"Evidence SHA sidecar mismatch: {record_path}"
        )

    return actual


def get_campaign_design_case(
    campaign,
    case_id: str,
):

    matches = tuple(
        item
        for item in campaign.design_cases
        if item.case_id == case_id
    )

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected exactly one "
            f"Production DOE design case; "
            f"found {len(matches)}."
        )

    return matches[0]


def get_manifest_design_row(
    manifest: dict,
    case_id: str,
) -> dict:

    matches = [
        item
        for item in manifest[
            "design_cases"
        ]
        if item.get("case_id") == case_id
    ]

    if len(matches) != 1:
        raise RuntimeError(
            f"{case_id}: expected exactly one "
            f"frozen manifest design row; "
            f"found {len(matches)}."
        )

    return matches[0]


def normalized_xyz(
    manifest: dict,
    case_id: str,
    dimension_order: tuple[str, ...],
) -> tuple[
    float,
    float,
    float,
]:

    row = get_manifest_design_row(
        manifest,
        case_id,
    )

    raw = row.get(
        "normalized_coordinates"
    )

    if not isinstance(
        raw,
        dict,
    ):
        raise RuntimeError(
            f"{case_id}: normalized coordinates "
            "are not a mapping."
        )

    missing = [
        key
        for key in dimension_order
        if key not in raw
    ]

    if missing:
        raise RuntimeError(
            f"{case_id}: missing normalized "
            f"coordinate fields {missing}."
        )

    values = tuple(
        float(
            raw[key]
        )
        for key in dimension_order
    )

    if len(values) != 3:
        raise RuntimeError(
            "V2 requires exactly three "
            "normalized dimensions."
        )

    return values


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
            "Trilinear extrapolation outside "
            "the unit cube is forbidden."
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
                        f"Missing trilinear corner {key}."
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


# ============================================================
# 1. FROZEN V2 METHODOLOGY
# ============================================================

actual_v2_sha = sha256(
    V2_POLICY_PATH
)

if (
    actual_v2_sha
    != EXPECTED_V2_POLICY_SHA256
):
    raise RuntimeError(
        "Frozen V2 policy SHA256 drift detected."
    )

v2_policy = tomllib.loads(
    V2_POLICY_PATH.read_text(
        encoding="utf-8-sig"
    )
)

if (
    v2_policy[
        "identity"
    ][
        "status"
    ]
    != "frozen"
):
    raise RuntimeError(
        "V2 methodology is not frozen."
    )

if (
    v2_policy[
        "corner_surface"
    ][
        "method"
    ]
    != "exact_trilinear_interpolation"
):
    raise RuntimeError(
        "Unexpected V2 surface method."
    )

dimension_order = tuple(
    v2_policy[
        "corner_surface"
    ][
        "normalized_dimension_order"
    ]
)

expected_dimension_order = (
    "target_preload",
    "head_member_thickness",
    "radial_geometry_fraction",
)

if (
    dimension_order
    != expected_dimension_order
):
    raise RuntimeError(
        "Normalized dimension-order drift."
    )

required_corner_count = int(
    v2_policy[
        "corner_surface"
    ][
        "required_corner_count"
    ]
)

if required_corner_count != 8:
    raise RuntimeError(
        "V2 exact trilinear surface "
        "must require eight corners."
    )

margin = float(
    v2_policy[
        "retrospective_sentinel"
    ][
        "meaningful_interior_margin"
    ]
)

if not (
    0.0 < margin < 0.5
):
    raise RuntimeError(
        "Invalid meaningful-interior margin."
    )


# ============================================================
# 2. EXISTING GOVERNANCE CHAIN
# ============================================================

for path in (
    DOE_POLICY_PATH,
    CAMPAIGN_MANIFEST_PATH,
    PREPARATION_CERT_PATH,
    ANCHOR_BINDING_PATH,
    WARM_V1_PATH,
):
    sha256(path)

warm = load_json(
    WARM_V1_PATH
)

if (
    warm.get(
        "record_status"
    )
    != "FINAL"
):
    raise RuntimeError(
        "Warm-start knowledge record is not FINAL."
    )

if (
    warm.get(
        "overall_disposition"
    )
    != (
        "FOUR_CERTIFIED_FEM_ANCHORS_"
        "BOUND_AS_WARM_START_KNOWLEDGE"
    )
):
    raise RuntimeError(
        "Existing anchor knowledge disposition mismatch."
    )

if not isinstance(
    warm.get(
        "warm_start_policy"
    ),
    dict,
):
    raise RuntimeError(
        "Warm-start policy provenance missing."
    )

campaign_refs = warm[
    "campaign"
]

governance_checks = (
    (
        DOE_POLICY_PATH,
        "doe_policy_sha256",
    ),
    (
        CAMPAIGN_MANIFEST_PATH,
        "campaign_manifest_sha256",
    ),
    (
        PREPARATION_CERT_PATH,
        "preparation_certification_sha256",
    ),
    (
        ANCHOR_BINDING_PATH,
        "anchor_binding_sha256",
    ),
)

for path, field in governance_checks:

    actual = sha256(
        path
    )

    expected = (
        campaign_refs[
            field
        ]
    )

    if actual != expected:
        raise RuntimeError(
            f"Governance SHA drift: {field}"
        )


# ============================================================
# 3. FROZEN CAMPAIGN
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


# ============================================================
# 4. VERIFY THE EIGHT GOVERNED CORNERS
# ============================================================

corner_coordinates = {
    case_id: normalized_xyz(
        manifest,
        case_id,
        dimension_order,
    )
    for case_id in CORNER_IDS
}

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

actual_cube = set(
    corner_coordinates.values()
)

if actual_cube != expected_cube:
    raise RuntimeError(
        "Eight governed V2 anchors do not form "
        "the complete normalized unit cube."
    )


# ============================================================
# 5. CERTIFIED CORNER CALIBRATION FACTORS
# ============================================================

legacy_anchors = {
    item["case_id"]: item
    for item in warm[
        "anchors"
    ]
}

if (
    set(
        legacy_anchors
    )
    != LEGACY_ANCHOR_IDS
):
    raise RuntimeError(
        "Legacy certified-anchor set mismatch."
    )

corner_factors = {}

print("=" * 144)
print(
    "THREADROM — WARM-START DELTA-T V2 "
    "RETROSPECTIVE DIAGNOSTIC"
)
print("=" * 144)

print()
print("=== CERTIFIED EIGHT-CORNER SURFACE ===")
print()


for case_id in CORNER_IDS:

    doe_case = (
        get_campaign_design_case(
            campaign,
            case_id,
        )
    )

    resolved = resolve_case(
        doe_case.case
    )

    if (
        resolved.case_hash
        != doe_case.case_hash
    ):
        raise RuntimeError(
            f"{case_id}: resolved case-hash drift."
        )

    analytical_dt = (
        derive_analytical_thermal_preload_seed(
            resolved
        )
        .predicted_delta_temperature_c
    )

    require_negative_finite(
        f"{case_id} analytical delta T",
        analytical_dt,
    )

    if case_id in LEGACY_ANCHOR_IDS:

        evidence = (
            legacy_anchors[
                case_id
            ]
        )

        if (
            evidence.get(
                "status"
            )
            != "CERTIFIED_REUSABLE"
        ):
            raise RuntimeError(
                f"{case_id}: legacy anchor is "
                "not CERTIFIED_REUSABLE."
            )

        if (
            evidence.get(
                "case_hash"
            )
            != doe_case.case_hash
        ):
            raise RuntimeError(
                f"{case_id}: certified anchor "
                "case-hash mismatch."
            )

        accepted_dt = float(
            evidence[
                "accepted_delta_temperature_c"
            ]
        )

        stored_analytical = float(
            evidence[
                "analytical_delta_temperature_c"
            ]
        )

        stored_factor = float(
            evidence[
                "correction_factor"
            ]
        )

        require_negative_finite(
            f"{case_id} accepted delta T",
            accepted_dt,
        )

        require_close(
            f"{case_id} analytical delta T",
            analytical_dt,
            stored_analytical,
        )

        factor = (
            accepted_dt
            / analytical_dt
        )

        require_close(
            f"{case_id} correction factor",
            factor,
            stored_factor,
        )

        if (
            float(
                evidence[
                    "measured_mean_clamp_force_n"
                ]
            )
            <= 0.0
        ):
            raise RuntimeError(
                f"{case_id}: invalid accepted "
                "mean clamp force."
            )

        evidence_type = (
            "CERTIFIED_REUSABLE_WARM_KNOWLEDGE"
        )

        evidence_sha = sha256(
            WARM_V1_PATH
        )

    elif case_id in NEW_BOUNDARY_IDS:

        case_run_id = (
            f"trm_fem_"
            f"{doe_case.case_hash[:12]}"
        )

        record_path = (
            SOLVER_ROOT
            / case_run_id
            / "production_doe_accepted_fem_evidence.json"
        )

        evidence_sha = (
            verify_sha_sidecar(
                record_path
            )
        )

        evidence = load_json(
            record_path
        )

        if (
            evidence.get(
                "record_status"
            )
            != "FINAL"
        ):
            raise RuntimeError(
                f"{case_id}: accepted FEM evidence "
                "is not FINAL."
            )

        if (
            evidence.get(
                "overall_disposition"
            )
            != (
                "PRODUCTION_DOE_FEM_"
                "CALIBRATION_ACCEPTED"
            )
        ):
            raise RuntimeError(
                f"{case_id}: accepted FEM "
                "disposition mismatch."
            )

        if (
            evidence[
                "case"
            ][
                "case_id"
            ]
            != case_id
            or evidence[
                "case"
            ][
                "case_hash"
            ]
            != doe_case.case_hash
        ):
            raise RuntimeError(
                f"{case_id}: accepted FEM "
                "identity mismatch."
            )

        semantics = (
            evidence[
                "evidence_semantics"
            ]
        )

        completed_solution_verified = (
            semantics.get(
                "completed_solution_evidence_verified"
            )
        )

        if completed_solution_verified is None:
            # Backward compatibility for historical clean
            # accepted-FEM evidence written before the
            # completed-solution semantic was introduced.
            completed_solution_verified = (
                semantics.get(
                    "solver_success_verified"
                )
            )

        if completed_solution_verified is not True:
            raise RuntimeError(
                f"{case_id}: completed FEM solution "
                "evidence is not verified."
            )

        required_true = (
            "governed_calibration_accept_verified",
            "trial_1_preserved",
            "trial_2_is_accepted_physics_solve",
            "eligible_for_warm_start_knowledge",
            "eligible_for_v2_anchor_use",
        )

        for field in required_true:

            if (
                semantics.get(
                    field
                )
                is not True
            ):
                raise RuntimeError(
                    f"{case_id}: required evidence "
                    f"semantic false/missing: {field}"
                )

        if (
            semantics.get(
                "holdout_accessed"
            )
            is not False
        ):
            raise RuntimeError(
                f"{case_id}: holdout provenance is not clean."
            )

        if (
            semantics.get(
                "additional_calibration_required"
            )
            is not False
        ):
            raise RuntimeError(
                f"{case_id}: evidence still requires "
                "calibration."
            )

        accepted = (
            evidence[
                "accepted_calibration"
            ]
        )

        if (
            accepted[
                "decision"
            ][
                "disposition"
            ]
            != "accept"
        ):
            raise RuntimeError(
                f"{case_id}: governed calibration "
                "decision is not ACCEPT."
            )

        if int(
            accepted[
                "accepted_trial_index"
            ]
        ) != 2:
            raise RuntimeError(
                f"{case_id}: unexpected accepted "
                "trial index."
            )

        target_error = float(
            accepted[
                "target_relative_error"
            ]
        )

        target_tolerance = float(
            accepted[
                "target_relative_tolerance"
            ]
        )

        spread = float(
            accepted[
                "interface_spread_relative"
            ]
        )

        spread_tolerance = float(
            accepted[
                "spread_relative_tolerance"
            ]
        )

        if (
            abs(
                target_error
            )
            > target_tolerance
        ):
            raise RuntimeError(
                f"{case_id}: accepted target error "
                "exceeds governed tolerance."
            )

        if (
            spread
            > spread_tolerance
        ):
            raise RuntimeError(
                f"{case_id}: accepted interface spread "
                "exceeds governed tolerance."
            )

        accepted_dt = float(
            accepted[
                "accepted_delta_temperature_c"
            ]
        )

        require_negative_finite(
            f"{case_id} accepted delta T",
            accepted_dt,
        )

        factor = (
            accepted_dt
            / analytical_dt
        )

        evidence_type = (
            "FINAL_GOVERNED_ACCEPTED_FEM_EVIDENCE"
        )

    else:
        raise RuntimeError(
            f"Unexpected corner identity: {case_id}"
        )

    xyz = (
        corner_coordinates[
            case_id
        ]
    )

    if xyz in corner_factors:
        raise RuntimeError(
            f"Duplicate cube corner coordinate: {xyz}"
        )

    corner_factors[
        xyz
    ] = factor

    print(
        f"{case_id:<10} "
        f"xyz={xyz} | "
        f"analytical={analytical_dt:12.6f} C | "
        f"accepted={accepted_dt:12.6f} C | "
        f"factor={factor:10.7f}"
    )

    print(
        "           evidence =",
        evidence_type,
    )

    print(
        "           evidence SHA256 =",
        evidence_sha,
    )


if (
    set(
        corner_factors
    )
    != expected_cube
):
    raise RuntimeError(
        "Certified correction-factor cube incomplete."
    )


# ============================================================
# 6. RETROSPECTIVE INTERIOR SENTINEL
# ============================================================

sentinel_case = (
    get_campaign_design_case(
        campaign,
        SENTINEL_ID,
    )
)

sentinel_xyz = normalized_xyz(
    manifest,
    SENTINEL_ID,
    dimension_order,
)

policy_xyz = tuple(
    float(value)
    for value in v2_policy[
        "retrospective_sentinel"
    ][
        "normalized_coordinates"
    ]
)

for index, (
    observed,
    frozen,
) in enumerate(
    zip(
        sentinel_xyz,
        policy_xyz,
        strict=True,
    )
):
    require_close(
        f"Sentinel normalized coordinate {index}",
        observed,
        frozen,
    )


inside_closed_cube = all(
    0.0 <= value <= 1.0
    for value in sentinel_xyz
)

boundary_distances = tuple(
    min(
        value,
        1.0 - value,
    )
    for value in sentinel_xyz
)

minimum_boundary_distance = min(
    boundary_distances
)

require_close(
    "Frozen sentinel minimum boundary distance",
    minimum_boundary_distance,
    float(
        v2_policy[
            "retrospective_sentinel"
        ][
            "minimum_boundary_distance_observed"
        ]
    ),
)

meaningfully_interior = (
    inside_closed_cube
    and all(
        margin
        <= value
        <= 1.0 - margin
        for value in sentinel_xyz
    )
)


# ============================================================
# 7. V2 DELTA-T PREDICTION
# ============================================================

sentinel_resolved = resolve_case(
    sentinel_case.case
)

if (
    sentinel_resolved.case_hash
    != sentinel_case.case_hash
):
    raise RuntimeError(
        "D-INT-010 resolved case-hash drift."
    )

sentinel_seed = (
    derive_analytical_thermal_preload_seed(
        sentinel_resolved
    )
)

analytical_sentinel_dt = (
    sentinel_seed
    .predicted_delta_temperature_c
)

require_negative_finite(
    "Sentinel analytical delta T",
    analytical_sentinel_dt,
)

v2_factor = trilinear(
    sentinel_xyz,
    corner_factors,
)

v2_delta_t = (
    analytical_sentinel_dt
    * v2_factor
)

require_negative_finite(
    "V2 predicted delta T",
    v2_delta_t,
)


# ============================================================
# 8. D-INT-010 GOVERNED ACCEPTED EVIDENCE
# ============================================================

sentinel_case_run_id = (
    f"trm_fem_"
    f"{sentinel_case.case_hash[:12]}"
)

sentinel_evidence_path = (
    SOLVER_ROOT
    / sentinel_case_run_id
    / "production_doe_accepted_fem_evidence.json"
)

sentinel_evidence = load_json(
    sentinel_evidence_path
)

sentinel_evidence_sha = sha256(
    sentinel_evidence_path
)

if (
    sentinel_evidence.get(
        "record_status"
    )
    != "FINAL"
):
    raise RuntimeError(
        "D-INT-010 accepted FEM evidence is not FINAL."
    )

if (
    sentinel_evidence.get(
        "overall_disposition"
    )
    != (
        "PRODUCTION_DOE_FEM_"
        "CALIBRATION_ACCEPTED"
    )
):
    raise RuntimeError(
        "D-INT-010 accepted FEM disposition mismatch."
    )

if (
    sentinel_evidence[
        "case"
    ][
        "case_id"
    ]
    != SENTINEL_ID
    or sentinel_evidence[
        "case"
    ][
        "case_hash"
    ]
    != sentinel_case.case_hash
):
    raise RuntimeError(
        "D-INT-010 evidence identity mismatch."
    )

sentinel_accepted = (
    sentinel_evidence[
        "accepted_calibration"
    ]
)

if (
    sentinel_accepted[
        "decision"
    ][
        "disposition"
    ]
    != "accept"
):
    raise RuntimeError(
        "D-INT-010 governed calibration "
        "decision is not ACCEPT."
    )

accepted_delta_t = float(
    sentinel_accepted[
        "accepted_delta_temperature_c"
    ]
)

require_negative_finite(
    "D-INT-010 accepted delta T",
    accepted_delta_t,
)

accepted_target_error = float(
    sentinel_accepted[
        "target_relative_error"
    ]
)

accepted_target_tolerance = float(
    sentinel_accepted[
        "target_relative_tolerance"
    ]
)

accepted_spread = float(
    sentinel_accepted[
        "interface_spread_relative"
    ]
)

accepted_spread_tolerance = float(
    sentinel_accepted[
        "spread_relative_tolerance"
    ]
)

if (
    abs(
        accepted_target_error
    )
    > accepted_target_tolerance
):
    raise RuntimeError(
        "D-INT-010 accepted target error "
        "exceeds governed tolerance."
    )

if (
    accepted_spread
    > accepted_spread_tolerance
):
    raise RuntimeError(
        "D-INT-010 accepted interface spread "
        "exceeds governed tolerance."
    )

delta_t_error_c = (
    v2_delta_t
    - accepted_delta_t
)

delta_t_relative_error = (
    delta_t_error_c
    / abs(
        accepted_delta_t
    )
)


# ============================================================
# 9. RETROSPECTIVE FORCE PROXY
#    INTERPOLATION ONLY — NEVER EXTRAPOLATION
# ============================================================

trial1_run_id = (
    f"{sentinel_case_run_id}_cal_01"
)

trial2_run_id = (
    f"{sentinel_case_run_id}_cal_02"
)

trial1_root = (
    SOLVER_ROOT
    / sentinel_case_run_id
    / trial1_run_id
)

trial2_root = (
    SOLVER_ROOT
    / sentinel_case_run_id
    / trial2_run_id
)

trial1_prep = load_json(
    trial1_root
    / "production_doe_solver_preparation_record.json"
)

trial2_prep = load_json(
    trial2_root
    / "production_doe_calibration_solver_preparation_record.json"
)

trial1_delta_t = float(
    trial1_prep[
        "warm_start_prediction"
    ][
        "predicted_delta_temperature_c"
    ]
)

trial2_delta_t = float(
    trial2_prep[
        "next_trial"
    ][
        "delta_temperature_c"
    ]
)

require_close(
    "D-INT-010 accepted Trial-2 delta T",
    trial2_delta_t,
    accepted_delta_t,
)

if (
    trial2_prep[
        "next_trial"
    ][
        "run_id"
    ]
    != sentinel_accepted[
        "accepted_run_id"
    ]
):
    raise RuntimeError(
        "D-INT-010 accepted run-ID drift."
    )

contact = (
    load_complete_joint_contact_definition(
        CONFIG
        / "complete_joint_contact.toml"
    )
)

measurement1 = (
    extract_clamp_force_measurement_from_dat(
        dat_path=(
            trial1_root
            / f"{trial1_run_id}.dat"
        ),
        contact_pairs=contact.contact_pairs,
    )
    .measurement
)

measurement2 = (
    extract_clamp_force_measurement_from_dat(
        dat_path=(
            trial2_root
            / f"{trial2_run_id}.dat"
        ),
        contact_pairs=contact.contact_pairs,
    )
    .measurement
)

require_close(
    "Accepted mean clamp force",
    measurement2.mean_force_n,
    float(
        sentinel_accepted[
            "mean_clamp_force_n"
        ]
    ),
    abs_tol=1.0e-8,
)

lo, hi = sorted(
    (
        trial1_delta_t,
        trial2_delta_t,
    )
)

proxy_is_interpolation = (
    lo
    <= v2_delta_t
    <= hi
)

proxy_force = None
proxy_target_error = None

proxy_basis = (
    "NOT_EVALUATED"
)

verdict = (
    "INDETERMINATE"
)


if not meaningfully_interior:

    proxy_basis = (
        "INELIGIBLE_SENTINEL_NOT_"
        "MEANINGFULLY_INTERIOR"
    )

elif not proxy_is_interpolation:

    proxy_basis = (
        "INELIGIBLE_REQUIRES_"
        "DELTA_T_EXTRAPOLATION"
    )

else:

    denominator = (
        trial2_delta_t
        - trial1_delta_t
    )

    if math.isclose(
        denominator,
        0.0,
        rel_tol=0.0,
        abs_tol=1.0e-12,
    ):
        raise RuntimeError(
            "Sentinel calibration points "
            "have identical delta T."
        )

    force_slope = (
        measurement2.mean_force_n
        - measurement1.mean_force_n
    ) / denominator

    proxy_force = (
        measurement1.mean_force_n
        + force_slope
        * (
            v2_delta_t
            - trial1_delta_t
        )
    )

    target_force = float(
        sentinel_accepted[
            "decision"
        ][
            "target_force_n"
        ]
    )

    require_close(
        "Sentinel resolved target preload",
        target_force,
        float(
            sentinel_resolved
            .source_case
            .loading
            .target_preload_n
        ),
        abs_tol=1.0e-8,
    )

    proxy_target_error = (
        proxy_force
        - target_force
    ) / target_force

    proxy_basis = (
        v2_policy[
            "retrospective_force_proxy"
        ][
            "eligible_basis_label"
        ]
    )

    if (
        abs(
            proxy_target_error
        )
        <= accepted_target_tolerance
    ):
        verdict = (
            "PROXY_PASS"
        )

    else:
        verdict = (
            "PROXY_FAIL"
        )


allowed_verdicts = set(
    v2_policy[
        "verdicts"
    ][
        "allowed"
    ]
)

if verdict not in allowed_verdicts:
    raise RuntimeError(
        "Diagnostic produced a verdict "
        "outside the frozen methodology."
    )


# ============================================================
# 10. REPORT
# ============================================================

print()
print("=" * 144)
print(
    "RETROSPECTIVE INTERIOR SENTINEL — D-INT-010"
)
print("=" * 144)

print(
    "Role                          :",
    v2_policy[
        "retrospective_sentinel"
    ][
        "role"
    ],
)

print(
    "Blind holdout                 : NO"
)

print(
    "Normalized coordinates        :",
    sentinel_xyz,
)

print(
    "Boundary distances            :",
    boundary_distances,
)

print(
    "Minimum boundary distance     :",
    minimum_boundary_distance,
)

print(
    "Meaningful-interior margin    :",
    margin,
)

print(
    "Meaningfully interior         :",
    meaningfully_interior,
)

print()
print(
    "Analytical delta T C          :",
    analytical_sentinel_dt,
)

print(
    "V2 trilinear factor           :",
    v2_factor,
)

print(
    "V2 predicted delta T C        :",
    v2_delta_t,
)

print(
    "Actual accepted delta T C     :",
    accepted_delta_t,
)

print(
    "Delta T error C               :",
    delta_t_error_c,
)

print(
    "Delta T relative error        :",
    delta_t_relative_error,
)

print()
print(
    "Real FEM Trial-1 delta T C    :",
    trial1_delta_t,
)

print(
    "Real FEM Trial-1 clamp N      :",
    measurement1.mean_force_n,
)

print(
    "Real FEM Trial-2 delta T C    :",
    trial2_delta_t,
)

print(
    "Real FEM Trial-2 clamp N      :",
    measurement2.mean_force_n,
)

print(
    "Sorted real-FEM dT bracket    :",
    (
        lo,
        hi,
    ),
)

print(
    "V2 prediction inside bracket  :",
    proxy_is_interpolation,
)

print(
    "Force proxy basis             :",
    proxy_basis,
)

if proxy_force is None:

    print(
        "Retrospective proxy force N  : NOT EVALUATED"
    )

    print(
        "Proxy target error           : NOT EVALUATED"
    )

else:

    print(
        "Retrospective proxy force N  :",
        proxy_force,
    )

    print(
        "Proxy target error           :",
        proxy_target_error,
    )

    print(
        "Governed target tolerance    :",
        accepted_target_tolerance,
    )


print()
print("-" * 144)

print(
    "RETROSPECTIVE VERDICT         :",
    verdict,
)

print(
    "Rollout authorized            : NO"
)

print(
    "Prospective FEM required      : YES"
)

print("-" * 144)

print(
    "Sentinel evidence SHA256      :",
    sentinel_evidence_sha,
)

print(
    "V2 policy SHA256              :",
    actual_v2_sha,
)

print(
    "CalculiX invoked              : NO"
)

print(
    "Blind holdout results used    : NO"
)

print("=" * 144)
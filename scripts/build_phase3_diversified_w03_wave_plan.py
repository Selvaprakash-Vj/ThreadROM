from __future__ import annotations

import copy
import hashlib
import json

from pathlib import Path


ROOT = Path(
    r"D:\ThreadROM"
).resolve()

DOE_ROOT = (
    ROOT
    / "docs"
    / "phase3_diversified_doe"
)

PROPOSAL_PATH = (
    DOE_ROOT
    / "design_proposal.json"
)

POLICY_PATH = (
    ROOT
    / "config"
    / "phase3_diversified_doe.toml"
)

W01_PATH = (
    DOE_ROOT
    / "waves"
    / "TRM-DDOE-001-W01"
    / "wave_plan.json"
)

W02_PATH = (
    DOE_ROOT
    / "waves"
    / "TRM-DDOE-001-W02"
    / "wave_plan.json"
)

W03_ROOT = (
    DOE_ROOT
    / "waves"
    / "TRM-DDOE-001-W03"
)

W03_PATH = (
    W03_ROOT
    / "wave_plan.json"
)

READINESS_PATH = (
    ROOT
    / "docs"
    / "phase3_pre_w03_hardening"
    / "w03_readiness_gate_v1.json"
)

SLICE6_PATH = (
    ROOT
    / "docs"
    / "phase3_pre_w03_hardening"
    / "slice6_closure.json"
)


EXPECTED = {
    PROPOSAL_PATH: (
        "a386da9648af88b5577386efdc16643b0"
        "b099fe2614c2bcc18c0e8973d141e1e"
    ),
    POLICY_PATH: (
        "6d0e45c109b1ba0a279ec0f06467ea91"
        "392760171b9a91bf0467d763896108d9"
    ),
    W01_PATH: (
        "7896622edb754e5ce970b1cc6b5ccf15"
        "7b591ae826e78c0abb9f8e373382a79d"
    ),
    W02_PATH: (
        "02f37a7515604b5c76e54aa69ed56991"
        "289eedd6100bc6448fd1c660e5bf5c67"
    ),
    READINESS_PATH: (
        "bc3ae1d724d05571db29320ccf698522"
        "13bcb3270be57a4c6917987e83e86445"
    ),
    SLICE6_PATH: (
        "66a57419bbf42a1726bb4fb8519eee10"
        "c4889ebb63852d534c6c9992638826ee"
    ),
}


SELECTION = (
    {
        "wave_order": 1,
        "proposal_id": (
            "TRM-DDOE-D-M10x1_5__"
            "member_aluminium_en_aw_6082_t6-03"
        ),
        "predecessor": (
            "TRM-DDOE-D-M10x1_5__"
            "member_aluminium_en_aw_6082_t6-02"
        ),
        "expected_case_hash": (
            "eac55af4d11fd8b23203f51c738cac51"
            "90cf203b637fb9f5be16169fdcbdfd12"
        ),
        "expected_case_run_id": (
            "trm_fem_a57f61f13b9d"
        ),
        "expected_coordinates": (
            0.0,
            0.5,
            1.0,
        ),
    },
    {
        "wave_order": 2,
        "proposal_id": (
            "TRM-DDOE-D-M12x1_75__"
            "member_aluminium_en_aw_6082_t6-03"
        ),
        "predecessor": (
            "TRM-DDOE-D-M12x1_75__"
            "member_aluminium_en_aw_6082_t6-02"
        ),
        "expected_case_hash": (
            "602fde21267d63e3d3cb6c88b6b5757e"
            "f511506876f8c7c3a6b41ee199e81dad"
        ),
        "expected_case_run_id": (
            "trm_fem_22c109e1e52b"
        ),
        "expected_coordinates": (
            0.0,
            0.5,
            1.0,
        ),
    },
    {
        "wave_order": 3,
        "proposal_id": (
            "TRM-DDOE-D-M8x1_25__"
            "member_aluminium_en_aw_6082_t6-03"
        ),
        "predecessor": (
            "TRM-DDOE-D-M8x1_25__"
            "member_aluminium_en_aw_6082_t6-02"
        ),
        "expected_case_hash": (
            "c3a38bcc699ebe5a031942a9d8a4a7c2"
            "4f2151c0c7824de777623878793b89ed"
        ),
        "expected_case_run_id": (
            "trm_fem_c802d7334f6c"
        ),
        "expected_coordinates": (
            0.0,
            0.5,
            1.0,
        ),
    },
    {
        "wave_order": 4,
        "proposal_id": (
            "TRM-DDOE-D-M12x1_75__"
            "steel_member-03"
        ),
        "predecessor": (
            "TRM-DDOE-D-M12x1_75__"
            "steel_member-02"
        ),
        "expected_case_hash": (
            "e86a17501ebe95d56da60e49d195c75d"
            "21a8fd29199cfbcf48eb5f97b2bbcab6"
        ),
        "expected_case_run_id": (
            "trm_fem_323293011028"
        ),
        "expected_coordinates": (
            0.0,
            0.5,
            0.0,
        ),
    },
)


NEW_EVIDENCE_STATUS = (
    "NEW_EVIDENCE_REQUIRED_NO_EXECUTION_AUTHORITY"
)


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(
            message
        )


def sha256_file(
    path: Path,
) -> str:
    require(
        path.is_file(),
        f"Missing governed dependency: {path}",
    )

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as stream:
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


def encoded_json(
    payload: dict,
) -> bytes:
    return (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
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
    encoded = encoded_json(
        payload
    )

    digest = hashlib.sha256(
        encoded
    ).hexdigest()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if path.exists():
        require(
            path.read_bytes()
            == encoded,
            (
                "Immutable W03 wave-plan conflict: "
                f"{path}"
            ),
        )

        return digest

    path.write_bytes(
        encoded
    )

    return digest


# ==============================================================================
# Frozen dependencies
# ==============================================================================

for path, expected in EXPECTED.items():
    actual = sha256_file(
        path
    )

    require(
        actual == expected,
        (
            f"Governed dependency SHA drift: {path}\n"
            f"expected={expected}\n"
            f"actual={actual}"
        ),
    )


proposal = load_json(
    PROPOSAL_PATH
)

w01 = load_json(
    W01_PATH
)

w02 = load_json(
    W02_PATH
)

readiness = load_json(
    READINESS_PATH
)


# ==============================================================================
# Confirm historical serializer / schema convention
# ==============================================================================

require(
    hashlib.sha256(
        encoded_json(
            w01
        )
    ).hexdigest()
    == EXPECTED[
        W01_PATH
    ],
    (
        "W01 wave-plan serialization convention "
        "does not replay exactly."
    ),
)

require(
    hashlib.sha256(
        encoded_json(
            w02
        )
    ).hexdigest()
    == EXPECTED[
        W02_PATH
    ],
    (
        "W02 wave-plan serialization convention "
        "does not replay exactly."
    ),
)

# Historical W01 and W02 may carry harmless metadata-surface
# evolution. W03 uses W02 as the canonical predecessor template.
#
# Fail closed on the governed contract surface instead of requiring
# every top-level metadata key to be identical across historical waves.

REQUIRED_WAVE_KEYS = {
    "adaptive_continuation_authorized",
    "artifact_retirement_authorized",
    "campaign_id",
    "dataset_admission_authorized",
    "design_freeze_certificate_sha256",
    "design_proposal_sha256",
    "fem_execution_authorized",
    "full_physics_certification_authorized",
    "holdout_access_authorized",
    "holdout_configurations_generated",
    "initial_trial_index",
    "maximum_concurrent_solver_slots",
    "meaning",
    "policy_sha256",
    "preparation_authorized",
    "record_status",
    "schema",
    "selected_cases",
    "selection_status",
    "wave_id",
    "wave_purpose",
    "wave_size",
}


for label, historical_wave in (
    ("W01", w01),
    ("W02", w02),
):
    missing = (
        REQUIRED_WAVE_KEYS
        - set(
            historical_wave
        )
    )

    require(
        not missing,
        (
            f"{label} wave plan lacks required governed "
            f"contract keys: {sorted(missing)}"
        ),
    )


w01_only = sorted(
    set(
        w01
    )
    - set(
        w02
    )
)

w02_only = sorted(
    set(
        w02
    )
    - set(
        w01
    )
)

print()
print("Historical wave metadata delta:")
print(
    "  W01-only:",
    w01_only,
)
print(
    "  W02-only:",
    w02_only,
)
print(
    "  W03 template: W02"
)

require(
    w01.get(
        "schema"
    )
    == "threadrom.phase3_diversified_doe_wave_plan.v1",
    "Unexpected historical wave-plan schema.",
)

require(
    w02.get(
        "schema"
    )
    == w01.get(
        "schema"
    ),
    "W02 wave-plan schema drift.",
)


# ==============================================================================
# Pre-W03 readiness must still grant NO execution authority
# ==============================================================================

w03_readiness = readiness.get(
    "w03"
)

require(
    readiness.get(
        "status"
    )
    == "PASS",
    "Pre-W03 readiness gate is not PASS.",
)

require(
    isinstance(
        w03_readiness,
        dict,
    ),
    "W03 readiness section missing.",
)

require(
    w03_readiness.get(
        "preparation_ready"
    )
    is True,
    "W03 preparation readiness missing.",
)

require(
    w03_readiness.get(
        "execution_authorized"
    )
    is False,
    "W03 already has execution authority unexpectedly.",
)

require(
    w03_readiness.get(
        "launched"
    )
    is False,
    "W03 already launched unexpectedly.",
)


# ==============================================================================
# Frozen proposal lookup
# ==============================================================================

cases = proposal.get(
    "cases"
)

require(
    isinstance(
        cases,
        list,
    )
    and len(
        cases
    )
    == 72,
    "Frozen diversified DOE design count drift.",
)

case_by_id = {
    row[
        "proposal_id"
    ]: row
    for row in cases
}

require(
    len(
        case_by_id
    )
    == 72,
    "Duplicate proposal identities detected.",
)


used = set()

for historical_wave in (
    w01,
    w02,
):
    selected_cases = historical_wave.get(
        "selected_cases"
    )

    require(
        isinstance(
            selected_cases,
            list,
        )
        and len(
            selected_cases
        )
        == 4,
        "Historical wave selected-case structure drift.",
    )

    for row in selected_cases:
        used.add(
            row[
                "proposal_id"
            ]
        )


require(
    len(
        used
    )
    == 8,
    "Historical W01/W02 cohort count drift.",
)


# ==============================================================================
# Build W03 case bindings entirely from frozen proposal
# ==============================================================================

selected_cases = []


for requested in SELECTION:
    case_id = requested[
        "proposal_id"
    ]

    require(
        case_id
        not in used,
        (
            "W03 case was already selected historically: "
            f"{case_id}"
        ),
    )

    row = case_by_id.get(
        case_id
    )

    require(
        isinstance(
            row,
            dict,
        ),
        (
            "W03 selection absent from frozen proposal: "
            f"{case_id}"
        ),
    )

    require(
        row.get(
            "historical_case_id"
        )
        is None,
        (
            "W03 fresh-FEM selection unexpectedly "
            "references historical evidence: "
            f"{case_id}"
        ),
    )

    require(
        row.get(
            "evidence_status"
        )
        == NEW_EVIDENCE_STATUS,
        (
            "W03 selection is not a governed "
            f"new-evidence state: {case_id}"
        ),
    )

    require(
        row.get(
            "fem_execution_authorized"
        )
        is False,
        (
            "Frozen proposal unexpectedly grants "
            f"execution authority: {case_id}"
        ),
    )

    require(
        row.get(
            "dataset_admission_status"
        )
        == "NOT_EVALUATED",
        (
            "Unexpected dataset state for W03 case: "
            f"{case_id}"
        ),
    )

    require(
        row.get(
            "case_hash"
        )
        == requested[
            "expected_case_hash"
        ],
        f"W03 case-hash drift: {case_id}",
    )

    require(
        row.get(
            "preparation_run_id"
        )
        == requested[
            "expected_case_run_id"
        ],
        f"W03 case-run drift: {case_id}",
    )

    require(
        tuple(
            row.get(
                "normalized_coordinates"
            )
        )
        == requested[
            "expected_coordinates"
        ],
        f"W03 coordinate drift: {case_id}",
    )

    case_run_id = row[
        "preparation_run_id"
    ]

    selected_cases.append(
        {
            "case_hash": (
                row[
                    "case_hash"
                ]
            ),
            "member_material_id": (
                row[
                    "member_material_id"
                ]
            ),
            "normalized_coordinates": (
                row[
                    "normalized_coordinates"
                ]
            ),
            "preparation_run_id": (
                case_run_id
            ),
            "proposal_id": (
                case_id
            ),
            "selection_reason": (
                "Deterministic post-hardening "
                "W02-lane continuation to next "
                "unused governed new-evidence state; "
                "predecessor="
                + requested[
                    "predecessor"
                ]
            ),
            "thread_designation": (
                row[
                    "thread_designation"
                ]
            ),
            "trial_1_run_id": (
                case_run_id
                + "_cal_01"
            ),
            "wave_order": (
                requested[
                    "wave_order"
                ]
            ),
        }
    )


require(
    len(
        selected_cases
    )
    == 4,
    "W03 selected-case count drift.",
)

require(
    len(
        {
            row[
                "proposal_id"
            ]
            for row in selected_cases
        }
    )
    == 4,
    "Duplicate W03 case selection.",
)


# ==============================================================================
# Reuse the historical Wave-v1 governance surface.
#
# Start from W02 only so every existing schema key is retained, then replace
# every wave-specific field deliberately.
# ==============================================================================

wave = copy.deepcopy(
    w02
)

wave[
    "wave_id"
] = "TRM-DDOE-001-W03"

wave[
    "wave_size"
] = 4

wave[
    "selected_cases"
] = selected_cases

wave[
    "initial_trial_index"
] = 1

wave[
    "maximum_concurrent_solver_slots"
] = 4

wave[
    "meaning"
] = (
    "Immutable four-case Wave-3 selection from the frozen "
    "Phase-3 diversified DOE after completion of the six-slice "
    "pre-W03 hardening gate. The cohort is the deterministic next "
    "unused governed new-evidence state in each W02 lane. "
    "This record grants no preparation, solver execution, adaptive "
    "continuation, dataset admission, physics certification, artifact "
    "retirement, surrogate training, or holdout access."
)

wave[
    "wave_purpose"
] = (
    "POST_HARDENING_W03_NEXT_UNUSED_NEW_EVIDENCE_LANE_CONTINUATION"
)


# ==============================================================================
# Wave-chain and selection metadata
#
# W03 must bind directly to W02, not inherit W02's W01 predecessor.
# The selection basis also advances with the newly accepted W02 evidence.
# ==============================================================================

require(
    w02.get(
        "previous_wave_plan_sha256"
    )
    == EXPECTED[
        W01_PATH
    ],
    "W02 does not bind to the frozen W01 predecessor.",
)

wave[
    "previous_wave_plan_sha256"
] = EXPECTED[
    W02_PATH
]

wave[
    "selection_basis"
] = {
    "anchor_inventory_count": 23,
    "anchor_inventory_meaning": (
        "14 exact historical reuse states + "
        "1 accepted diversified pilot + "
        "4 W01 governed full-physics accepted states + "
        "4 W02 governed full-physics accepted states"
    ),
    "selected_group_count": 4,
    "selection_rule": (
        "Continue each W02 thread/material lane to its "
        "deterministic next unused governed new-evidence state "
        "after completion of the pre-W03 hardening gate."
    ),
    "validation_reservation": (
        "18 reserved; configurations not generated"
    ),
}

require(
    isinstance(
        w02.get(
            "trial_1_predictor_requirement"
        ),
        str,
    )
    and bool(
        w02[
            "trial_1_predictor_requirement"
        ]
    ),
    "W02 Trial-1 predictor requirement missing.",
)

wave[
    "trial_1_predictor_requirement"
] = w02[
    "trial_1_predictor_requirement"
]


# Preserve the historical generic selection-status convention.
require(
    w01.get(
        "selection_status"
    )
    == w02.get(
        "selection_status"
    ),
    "Historical selection-status convention differs.",
)

wave[
    "selection_status"
] = w02[
    "selection_status"
]


# Explicitly restore every authority boundary, irrespective of W02 template.
for key in (
    "adaptive_continuation_authorized",
    "artifact_retirement_authorized",
    "dataset_admission_authorized",
    "fem_execution_authorized",
    "full_physics_certification_authorized",
    "holdout_access_authorized",
    "preparation_authorized",
):
    require(
        key in wave,
        (
            "Historical wave-plan schema lacks "
            f"required authority key: {key}"
        ),
    )

    wave[
        key
    ] = False


require(
    "holdout_configurations_generated"
    in wave,
    "Historical wave-plan schema lacks holdout generation field.",
)

wave[
    "holdout_configurations_generated"
] = False


# Frozen campaign/design identities must remain inherited unchanged.
require(
    wave.get(
        "campaign_id"
    )
    == "TRM-DDOE-001",
    "Campaign identity drift.",
)

require(
    wave.get(
        "design_proposal_sha256"
    )
    == EXPECTED[
        PROPOSAL_PATH
    ],
    "Design-proposal binding drift.",
)

require(
    wave.get(
        "policy_sha256"
    )
    == EXPECTED[
        POLICY_PATH
    ],
    "Design-policy binding drift.",
)

require(
    wave.get(
        "record_status"
    )
    == "FINAL",
    "Wave-plan record status drift.",
)

require(
    wave.get(
        "schema"
    )
    == "threadrom.phase3_diversified_doe_wave_plan.v1",
    "Wave-plan schema drift.",
)


# ==============================================================================
# Persist immutable W03 wave plan
# ==============================================================================

wave_sha = write_immutable(
    W03_PATH,
    wave,
)


# Exact readback / replay.
recovered = load_json(
    W03_PATH
)

require(
    recovered == wave,
    "W03 wave-plan readback differs from written payload.",
)

require(
    sha256_file(
        W03_PATH
    )
    == wave_sha,
    "W03 wave-plan SHA replay failed.",
)


print()
print("=" * 108)
print(
    "THREADROM - W03 / STEP 1 - "
    "GOVERNED WAVE PLAN FROZEN"
)
print("=" * 108)

for row in selected_cases:
    print()
    print(
        f"{row['wave_order']}. "
        f"{row['proposal_id']}"
    )
    print(
        "   thread      :",
        row[
            "thread_designation"
        ],
    )
    print(
        "   material    :",
        row[
            "member_material_id"
        ],
    )
    print(
        "   coordinates :",
        tuple(
            row[
                "normalized_coordinates"
            ]
        ),
    )
    print(
        "   case hash   :",
        row[
            "case_hash"
        ],
    )
    print(
        "   case run    :",
        row[
            "preparation_run_id"
        ],
    )
    print(
        "   trial-1 run :",
        row[
            "trial_1_run_id"
        ],
    )

print()
print(
    "Wave ID              :",
    wave[
        "wave_id"
    ],
)
print(
    "Wave plan SHA        :",
    wave_sha,
)
print(
    "Wave size            : 4"
)
print(
    "Maximum solver slots : 4"
)
print(
    "Preparation authority: NO"
)
print(
    "Execution authority  : NO"
)
print(
    "Adaptive authority   : NO"
)
print(
    "Physics certification: NO"
)
print(
    "Dataset admission    : NO"
)
print(
    "Holdout access       : NO"
)
print(
    "CalculiX launched    : NO"
)
print("=" * 108)
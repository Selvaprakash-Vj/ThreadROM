from __future__ import annotations

import hashlib
import json
import sqlite3

from collections import Counter
from pathlib import Path

from threadrom.factory.production_doe_launch_fence import (
    MAXIMUM_CONCURRENT_CCX,
    count_running_ccx,
)


ROOT = Path(r"D:\ThreadROM")

DECK_CERT = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_da08_fine_reference"
    / "da08_fine_reference_deck_preparation_certificate.json"
)

EXPECTED_DECK_CERT_SHA = (
    "0db68e52e84dd74cf40b5c6e47db772aa670b7618f50dc45299c65739345e576"
)

W06_REGISTRY = (
    ROOT
    / "simulations"
    / "staging"
    / "phase3_diversified_doe"
    / "TRM-DDOE-001"
    / "W06"
    / "factory"
    / "w06_trial1_factory.sqlite3"
)

W06_CLOSURE = (
    ROOT
    / "docs"
    / "phase3_governed_wave_closure"
    / "TRM-DDOE-001-W06.wave_closure.json"
)

AUTH_PATH = (
    ROOT
    / "docs"
    / "phase3_rom_dataset_admission"
    / "member_shortening_v1.da08_fine_reference_solver_launch_authorization.json"
)

AUTH_SIDECAR = Path(
    str(AUTH_PATH) + ".sha256"
)

LAUNCH_FENCE = (
    ROOT
    / "src"
    / "threadrom"
    / "factory"
    / "production_doe_launch_fence.py"
)

EXPECTED_LAUNCH_FENCE_SHA = (
    "73a9fcd13af0feffee0aecbd4f79af88779c532dea2837593d076bd48ecf254c"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def relative(path: Path) -> str:
    return str(
        path.resolve().relative_to(
            ROOT.resolve()
        )
    ).replace("\\", "/")


def immutable_json(
    path: Path,
    payload: dict,
) -> str:

    encoded = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")

    digest = hashlib.sha256(
        encoded
    ).hexdigest()

    if path.exists():

        if path.read_bytes() != encoded:
            raise RuntimeError(
                f"Immutable authorization drift: {path}"
            )

        return digest

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_bytes(
        encoded
    )

    return digest


print()
print("=" * 120)
print("1. PIN DA08 PRE-SOLVE AUTHORITY")
print("=" * 120)


if sha256(DECK_CERT) != EXPECTED_DECK_CERT_SHA:
    raise RuntimeError(
        "DA08 deck certificate SHA drift."
    )

if sha256(LAUNCH_FENCE) != EXPECTED_LAUNCH_FENCE_SHA:
    raise RuntimeError(
        "ThreadROM launch-fence source SHA drift."
    )


deck_cert = json.loads(
    DECK_CERT.read_text(
        encoding="utf-8"
    )
)


proof = deck_cert.get(
    "proof",
    {},
)


required_counts = {
    "expected_cases": 19,
    "exact_case_count": 19,
    "true_global_fine_mesh_count": 19,
    "accepted_source_calibration_count": 19,
    "fine_transfer_count": 19,
    "fine_backend_count": 19,
    "production_deck_count": 19,
    "deterministic_deck_count": 19,
}


for key, expected in required_counts.items():

    if proof.get(key) != expected:
        raise RuntimeError(
            f"DA08 deck certificate gate drift: "
            f"{key}={proof.get(key)!r}"
        )


cases = deck_cert.get(
    "cases"
)


if (
    not isinstance(cases, list)
    or len(cases) != 19
):
    raise RuntimeError(
        "DA08 deck inventory is not exactly 19."
    )


for row in cases:

    deck_path = (
        ROOT
        / Path(
            row[
                "deck_relative_path"
            ]
        )
    )

    if (
        not deck_path.is_file()
        or sha256(deck_path)
        != row[
            "deck_sha256"
        ]
    ):
        raise RuntimeError(
            f"{row['case_id']}: deck SHA drift."
        )


print("PASS: DA08 decks           : 19/19")
print("PASS: deterministic decks : 19/19")
print("PASS: deck certificate    :", EXPECTED_DECK_CERT_SHA)


print()
print("=" * 120)
print("2. LIVE W06 FACTORY STATUS")
print("=" * 120)


if not W06_REGISTRY.is_file():
    raise RuntimeError(
        "W06 live factory registry is missing."
    )


uri = (
    "file:"
    + W06_REGISTRY.as_posix()
    + "?mode=ro"
)


connection = sqlite3.connect(
    uri,
    uri=True,
)


connection.row_factory = (
    sqlite3.Row
)


try:

    columns = {
        row["name"]
        for row in connection.execute(
            "PRAGMA table_info(fem_jobs)"
        )
    }


    required_columns = {
        "job_id",
        "case_id",
        "case_hash",
        "trial_index",
        "run_id",
        "state",
        "manifest_path",
        "acceptance_record",
        "failure_category",
        "failure_message",
        "lease_owner",
        "lease_expires_at_utc",
        "lease_generation",
        "updated_at_utc",
    }


    if not required_columns.issubset(
        columns
    ):
        raise RuntimeError(
            "W06 factory registry schema drift."
        )


    jobs = list(
        connection.execute(
            """
            SELECT
                job_id,
                case_id,
                case_hash,
                trial_index,
                run_id,
                state,
                manifest_path,
                acceptance_record,
                failure_category,
                failure_message,
                lease_owner,
                lease_expires_at_utc,
                lease_generation,
                updated_at_utc
            FROM fem_jobs
            ORDER BY
                case_id,
                trial_index,
                job_id
            """
        )
    )

finally:

    connection.close()


if not jobs:
    raise RuntimeError(
        "W06 registry contains no jobs."
    )


states = Counter(
    str(row["state"])
    for row in jobs
)


print("Registry :", relative(W06_REGISTRY))
print("Jobs     :", len(jobs))
print("States   :", dict(states))
print()


blocking_jobs = []


for row in jobs:

    acceptance = row[
        "acceptance_record"
    ]

    failure = row[
        "failure_category"
    ]

    lease_owner = row[
        "lease_owner"
    ]


    terminal_evidence = (
        bool(acceptance)
        or bool(failure)
    )


    lease_active = bool(
        lease_owner
    )


    if (
        not terminal_evidence
        or lease_active
    ):
        blocking_jobs.append(
            row
        )


    print("-" * 120)

    print(
        "CASE       :",
        row[
            "case_id"
        ],
    )

    print(
        "TRIAL      :",
        row[
            "trial_index"
        ],
    )

    print(
        "RUN        :",
        row[
            "run_id"
        ],
    )

    print(
        "STATE      :",
        row[
            "state"
        ],
    )

    print(
        "ACCEPTANCE :",
        (
            row[
                "acceptance_record"
            ]
            or "-"
        ),
    )

    print(
        "FAILURE    :",
        (
            row[
                "failure_category"
            ]
            or "-"
        ),
    )

    print(
        "LEASE      :",
        (
            row[
                "lease_owner"
            ]
            or "-"
        ),
    )

    print(
        "UPDATED    :",
        row[
            "updated_at_utc"
        ],
    )


print()
print("=" * 120)
print("3. W06 CLOSURE STATUS")
print("=" * 120)


w06_closure_info = None


if W06_CLOSURE.is_file():

    closure = json.loads(
        W06_CLOSURE.read_text(
            encoding="utf-8"
        )
    )

    w06_closure_info = {
        "relative_path":
            relative(
                W06_CLOSURE
            ),

        "sha256":
            sha256(
                W06_CLOSURE
            ),

        "record_status":
            closure.get(
                "record_status"
            ),

        "disposition":
            closure.get(
                "disposition"
            ),

        "accepted_case_count":
            closure.get(
                "accepted_case_count"
            ),

        "authorized_case_count":
            closure.get(
                "authorized_case_count"
            ),
    }


    print(
        "Closure          : PRESENT"
    )

    print(
        "SHA256           :",
        w06_closure_info[
            "sha256"
        ],
    )

    print(
        "Record status    :",
        w06_closure_info[
            "record_status"
        ],
    )

    print(
        "Disposition      :",
        w06_closure_info[
            "disposition"
        ],
    )

    print(
        "Accepted cases   :",
        w06_closure_info[
            "accepted_case_count"
        ],
    )

    print(
        "Authorized cases :",
        w06_closure_info[
            "authorized_case_count"
        ],
    )

else:

    print(
        "Closure          : NOT YET PRESENT"
    )


print()
print("=" * 120)
print("4. GLOBAL CALCULIX CAPACITY")
print("=" * 120)


running_ccx = (
    count_running_ccx()
)


print(
    "Running ccx              :",
    running_ccx,
)

print(
    "Global ThreadROM limit   :",
    MAXIMUM_CONCURRENT_CCX,
)


# ================================================================================================
# IMPORTANT:
#
# We deliberately require ZERO existing CalculiX processes for initial
# DA08 authorization. The generic launch fence still remains authoritative
# later at every actual solver launch.
#
# DA08 fine-reference campaign gets an intentionally conservative local
# maximum of ONE fine solve at a time.
# ================================================================================================


w06_clear = (
    len(
        blocking_jobs
    )
    == 0
)


ccx_clear = (
    running_ccx
    == 0
)


print()
print("=" * 120)
print("5. EXECUTION-BOUNDARY DECISION")
print("=" * 120)


if not w06_clear:

    print(
        "W06 STATUS : ACTIVE / NONTERMINAL"
    )

    print(
        "Blocking W06 jobs:",
        len(
            blocking_jobs
        ),
    )

    print()
    print(
        "DA08 AUTHORIZATION : NOT WRITTEN"
    )

    print(
        "DA08 FEM           : NOT LAUNCHED"
    )

    print(
        "W06                : UNTOUCHED"
    )

    print()
    print(
        "DISPOSITION : WAIT_FOR_W06_TO_REACH_TERMINAL_EVIDENCE"
    )

    raise SystemExit(
        0
    )


if not ccx_clear:

    print(
        "W06 registry is terminal, but "
        "other CalculiX processes still exist."
    )

    print(
        "DA08 AUTHORIZATION : NOT WRITTEN"
    )

    print(
        "DA08 FEM           : NOT LAUNCHED"
    )

    print()
    print(
        "DISPOSITION : WAIT_FOR_GLOBAL_CALCULIX_QUIESCENCE"
    )

    raise SystemExit(
        0
    )


print(
    "PASS: W06 registry has no nonterminal jobs."
)

print(
    "PASS: global CalculiX process count is zero."
)


# ================================================================================================
# FREEZE DA08 SOLVER-LAUNCH AUTHORIZATION.
#
# Still no solver execution.
# ================================================================================================


if AUTH_PATH.exists():

    raise RuntimeError(
        "DA08 solver-launch authorization "
        "already exists; refusing overwrite."
    )


if AUTH_SIDECAR.exists():

    raise RuntimeError(
        "DA08 solver-launch authorization "
        "SHA sidecar already exists."
    )


authorization = {
    "schema":
        "threadrom.da08_fine_reference_solver_launch_authorization.v1",

    "record_status":
        "FINAL",

    "target_id":
        "member_shortening_v1",

    "purpose":
        (
            "Authorize governed execution of the already "
            "prepared 19-case true-global-fine numerical "
            "reference campaign required by frozen DA08."
        ),

    "authorities": {
        "deck_preparation_certificate": {
            "relative_path":
                relative(
                    DECK_CERT
                ),

            "sha256":
                EXPECTED_DECK_CERT_SHA,
        },

        "production_doe_launch_fence": {
            "relative_path":
                relative(
                    LAUNCH_FENCE
                ),

            "sha256":
                EXPECTED_LAUNCH_FENCE_SHA,

            "global_maximum_concurrent_ccx":
                MAXIMUM_CONCURRENT_CCX,
        },

        "w06_registry_snapshot": {
            "relative_path":
                relative(
                    W06_REGISTRY
                ),

            "job_count":
                len(
                    jobs
                ),

            "state_distribution":
                dict(
                    states
                ),

            "nonterminal_job_count":
                0,
        },

        "w06_closure":
            w06_closure_info,
    },

    "execution_scope": {
        "case_count":
            19,

        "case_run_ids":
            [
                row[
                    "fine_reference_run_id"
                ]
                for row in sorted(
                    cases,
                    key=lambda item: item[
                        "ordinal"
                    ],
                )
            ],

        "maximum_concurrent_da08_fine_runs":
            1,

        "maximum_global_concurrent_ccx":
            MAXIMUM_CONCURRENT_CCX,

        "initial_global_ccx_count":
            running_ccx,

        "launch_mode":
            "GOVERNED_SERIAL_FINE_REFERENCE",

        "automatic_case_progression":
            True,

        "new_preload_calibration":
            False,

        "accepted_calibration_state_reuse":
            True,
    },

    "safety": {
        "w06_must_remain_unmodified":
            True,

        "w06_must_be_quiescent_at_authorization":
            True,

        "global_launch_fence_required_per_run":
            True,

        "holdout_access":
            False,

        "dataset_mutation":
            False,

        "rom_training":
            False,

        "calculix_launched_by_this_authorization":
            False,
    },

    "cases":
        [
            {
                "ordinal":
                    row[
                        "ordinal"
                    ],

                "case_id":
                    row[
                        "case_id"
                    ],

                "case_hash":
                    row[
                        "case_hash"
                    ],

                "case_run_id":
                    row[
                        "case_run_id"
                    ],

                "fine_reference_run_id":
                    row[
                        "fine_reference_run_id"
                    ],

                "deck_relative_path":
                    row[
                        "deck_relative_path"
                    ],

                "deck_sha256":
                    row[
                        "deck_sha256"
                    ],
            }
            for row
            in sorted(
                cases,
                key=lambda item: item[
                    "ordinal"
                ],
            )
        ],

    "disposition":
        "DA08_FINE_REFERENCE_SOLVER_LAUNCH_AUTHORIZED",
}


auth_sha = immutable_json(
    AUTH_PATH,
    authorization,
)


AUTH_SIDECAR.write_text(
    (
        auth_sha
        + "  "
        + AUTH_PATH.name
        + "\n"
    ),
    encoding="ascii",
)


if (
    AUTH_SIDECAR.read_text(
        encoding="ascii"
    ).split()[0]
    != auth_sha
):

    raise RuntimeError(
        "DA08 authorization SHA sidecar drift."
    )


print()
print("=" * 120)
print("DA08 FINE-REFERENCE SOLVER-LAUNCH AUTHORIZATION FROZEN")
print("=" * 120)

print(
    "Cases                     : 19"
)

print(
    "DA08 concurrent fine runs : 1"
)

print(
    "Global CalculiX limit     :",
    MAXIMUM_CONCURRENT_CCX,
)

print(
    "Initial running ccx       :",
    running_ccx,
)

print(
    "Authorization             :",
    relative(
        AUTH_PATH
    ),
)

print(
    "Authorization SHA256      :",
    auth_sha,
)

print()
print(
    "CalculiX launched         : NO"
)

print(
    "W06                       : UNTOUCHED"
)

print(
    "Holdouts                  : SEALED"
)

print(
    "Dataset                   : UNTOUCHED"
)

print()
print(
    "NEXT : GOVERNED DA08 FINE-REFERENCE EXECUTION RUNNER"
)

print("=" * 120)

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from threadrom.factory.production_doe_launch_fence import (
    MAXIMUM_CONCURRENT_CCX,
    count_running_ccx,
)


ROOT = Path(r"D:\ThreadROM").resolve()


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
    str(AUTH_PATH)
    + ".sha256"
)


def sha256(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def relative(
    path: Path,
) -> str:

    return str(
        path.resolve().relative_to(
            ROOT
        )
    ).replace(
        "\\",
        "/",
    )


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
    ).encode(
        "utf-8"
    )

    digest = hashlib.sha256(
        encoded
    ).hexdigest()

    if path.exists():

        if path.read_bytes() != encoded:

            raise RuntimeError(
                "Existing DA08 solver authorization "
                "has different content."
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
print("THREADROM - DA08")
print("FINE-REFERENCE SOLVER-LAUNCH AUTHORIZATION")
print("W06 MUST BE CANONICALLY CLOSED - NO FEM LAUNCH")
print("=" * 120)


# --------------------------------------------------------------------------------------------------------------
# DA08 deterministic deck authority
# --------------------------------------------------------------------------------------------------------------

if (
    not DECK_CERT.is_file()
    or sha256(
        DECK_CERT
    )
    != EXPECTED_DECK_CERT_SHA
):

    raise RuntimeError(
        "DA08 deterministic deck certificate drift."
    )


deck = json.loads(
    DECK_CERT.read_text(
        encoding="utf-8"
    )
)


if (
    deck.get(
        "record_status"
    )
    != "FINAL_PRE_SOLVE"
    or deck.get(
        "disposition"
    )
    != "DA08_FINE_REFERENCE_DECK_PREPARATION_COMPLETE"
):

    raise RuntimeError(
        "DA08 deck campaign is not FINAL_PRE_SOLVE."
    )


cases = deck.get(
    "cases"
)


if (
    not isinstance(
        cases,
        list,
    )
    or len(
        cases
    )
    != 19
):

    raise RuntimeError(
        "DA08 deck inventory is not 19."
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
        or sha256(
            deck_path
        )
        != row[
            "deck_sha256"
        ]
    ):

        raise RuntimeError(
            f"{row['case_id']}: "
            "DA08 deck SHA drift."
        )


print(
    "PASS: deterministic DA08 decks = 19/19."
)


# --------------------------------------------------------------------------------------------------------------
# W06 must now be canonically closed.
# --------------------------------------------------------------------------------------------------------------

if not W06_CLOSURE.is_file():

    raise RuntimeError(
        "Canonical W06 closure is missing."
    )


closure = json.loads(
    W06_CLOSURE.read_text(
        encoding="utf-8"
    )
)


if (
    closure.get(
        "schema"
    )
    != "threadrom.governed_wave_closure.v1"
    or closure.get(
        "record_status"
    )
    != "FINAL"
    or closure.get(
        "wave_id"
    )
    != "TRM-DDOE-001-W06"
    or closure.get(
        "disposition"
    )
    != "GOVERNED_WAVE_FULL_PHYSICS_CLOSED"
    or closure.get(
        "authorized_case_count"
    )
    != 4
    or closure.get(
        "accepted_case_count"
    )
    != 4
):

    raise RuntimeError(
        "W06 canonical closure contract drift."
    )


closure_cases = closure.get(
    "cases"
)


if (
    not isinstance(
        closure_cases,
        list,
    )
    or len(
        closure_cases
    )
    != 4
):

    raise RuntimeError(
        "W06 closure does not contain "
        "exactly four accepted cases."
    )


print(
    "PASS: W06 canonical closure = 4/4."
)


for row in closure_cases:

    print(
        "  ",
        row[
            "case_id"
        ],
        "|",
        row[
            "run_id"
        ],
        "| trial",
        row[
            "trial_index"
        ],
    )


# --------------------------------------------------------------------------------------------------------------
# Initial execution boundary must be fully quiet.
# --------------------------------------------------------------------------------------------------------------

running_ccx = (
    count_running_ccx()
)


if running_ccx != 0:

    raise RuntimeError(
        "DA08 authorization requires zero "
        f"existing ccx processes; found {running_ccx}."
    )


print(
    "PASS: global CalculiX process count = 0."
)


# --------------------------------------------------------------------------------------------------------------
# Freeze authorization.
# --------------------------------------------------------------------------------------------------------------

authorization = {
    "schema":
        "threadrom.da08_fine_reference_solver_launch_authorization.v2",

    "record_status":
        "FINAL",

    "target_id":
        "member_shortening_v1",

    "purpose":
        (
            "Authorize governed serial execution "
            "of the already-prepared 19-case "
            "true-global-fine DA08 numerical "
            "reference campaign."
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

        "w06_governed_wave_closure": {
            "relative_path":
                relative(
                    W06_CLOSURE
                ),

            "sha256":
                sha256(
                    W06_CLOSURE
                ),

            "accepted_case_count":
                4,
        },
    },

    "execution_scope": {
        "case_count":
            19,

        "maximum_concurrent_da08_fine_runs":
            1,

        "maximum_global_concurrent_ccx":
            MAXIMUM_CONCURRENT_CCX,

        "initial_global_ccx_count":
            0,

        "launch_mode":
            "GOVERNED_SERIAL_FINE_REFERENCE",

        "automatic_case_progression":
            True,

        "accepted_calibration_state_reuse":
            True,

        "new_preload_calibration":
            False,
    },

    "cases": [
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

        for row in sorted(
            cases,
            key=lambda item: item[
                "ordinal"
            ],
        )
    ],

    "safety": {
        "global_launch_fence_required_per_run":
            True,

        "w06_mutation":
            False,

        "w06_post_wave_learning_sink_admission":
            False,

        "holdout_access":
            False,

        "dataset_mutation":
            False,

        "rom_training":
            False,

        "calculix_launched_by_this_record":
            False,
    },

    "disposition":
        "DA08_FINE_REFERENCE_SOLVER_LAUNCH_AUTHORIZED",
}


if AUTH_PATH.exists():

    raise RuntimeError(
        "DA08 solver authorization already exists; "
        "refusing accidental replacement."
    )


auth_sha = immutable_json(
    AUTH_PATH,
    authorization,
)


sidecar_text = (
    auth_sha
    + "  "
    + AUTH_PATH.name
    + "\n"
)


if AUTH_SIDECAR.exists():

    raise RuntimeError(
        "DA08 authorization sidecar already exists."
    )


AUTH_SIDECAR.write_text(
    sidecar_text,
    encoding="ascii",
)


if (
    AUTH_SIDECAR.read_text(
        encoding="ascii"
    )
    != sidecar_text
):

    raise RuntimeError(
        "DA08 authorization sidecar "
        "verification failed."
    )


print()
print("=" * 120)
print("DA08 FINE-REFERENCE SOLVER-LAUNCH AUTHORIZATION FROZEN")
print("=" * 120)

print(
    "Cases                    : 19"
)

print(
    "DA08 concurrency         : 1"
)

print(
    "Global ccx limit         :",
    MAXIMUM_CONCURRENT_CCX,
)

print(
    "Initial ccx count        :",
    running_ccx,
)

print(
    "W06 closure SHA256       :",
    sha256(
        W06_CLOSURE
    ),
)

print(
    "Authorization            :",
    relative(
        AUTH_PATH
    ),
)

print(
    "Authorization SHA256     :",
    auth_sha,
)

print()
print("CalculiX launched        : NO")
print("W06 mutated              : NO")
print("W06 learning sinks       : DEFERRED")
print("Holdouts                 : SEALED")
print("Dataset                  : UNTOUCHED")
print("ROM training             : NO")

print()
print(
    "NEXT : GOVERNED SERIAL "
    "DA08 FINE-REFERENCE EXECUTION"
)

print("=" * 120)

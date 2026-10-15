from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys

from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]

STAGE_ORDER = (
    "geometry_mesh",
    "calibration_knowledge",
    "fem_evidence",
    "rom_candidate",
)

STAGE_SCRIPTS = {
    "geometry_mesh": (
        ROOT
        / "scripts"
        / "admit_phase3_governed_wave_geometry_mesh_v1.py"
    ),
    "calibration_knowledge": (
        ROOT
        / "scripts"
        / "admit_phase3_governed_wave_calibration_knowledge_v1.py"
    ),
    "fem_evidence": (
        ROOT
        / "scripts"
        / "admit_phase3_governed_wave_fem_evidence_v1.py"
    ),
    "rom_candidate": (
        ROOT
        / "scripts"
        / "run_phase3_governed_wave_post_fem_rom_hook_v1.py"
    ),
}


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def load_plan(
    path: Path,
) -> dict[str, Any]:

    require(
        path.is_file(),
        f"Transaction plan missing: {path}",
    )

    payload = json.loads(
        path.read_text(
            encoding="utf-8-sig"
        )
    )

    require(
        isinstance(payload, dict),
        "Transaction plan must be a JSON object.",
    )

    require(
        payload.get("schema_version") == 1,
        "Unsupported transaction-plan schema.",
    )

    require(
        payload.get("record_status") == "FINAL",
        "Transaction plan must be FINAL.",
    )

    wave_id = payload.get("wave_id")

    require(
        isinstance(wave_id, str)
        and bool(wave_id.strip()),
        "Transaction plan lacks wave_id.",
    )

    stages = payload.get("stages")

    require(
        isinstance(stages, Mapping),
        "Transaction plan lacks stages.",
    )

    require(
        tuple(stages.keys()) == STAGE_ORDER,
        (
            "Transaction stage ordering drift. "
            f"Expected {STAGE_ORDER!r}; "
            f"got {tuple(stages.keys())!r}."
        ),
    )

    return payload


def verify_stage_authorities(
    plan: Mapping[str, Any],
) -> None:

    for stage_name in STAGE_ORDER:

        stage = plan["stages"][stage_name]

        require(
            isinstance(stage, Mapping),
            f"{stage_name}: stage must be an object.",
        )

        expected_script_sha = stage.get(
            "script_sha256"
        )

        require(
            isinstance(expected_script_sha, str)
            and len(expected_script_sha) == 64,
            f"{stage_name}: invalid script SHA.",
        )

        script = STAGE_SCRIPTS[
            stage_name
        ]

        require(
            script.is_file(),
            f"{stage_name}: script missing: {script}",
        )

        actual = sha256(
            script
        )

        require(
            actual == expected_script_sha,
            (
                f"{stage_name}: script SHA drift. "
                f"expected={expected_script_sha} "
                f"actual={actual}"
            ),
        )

        args = stage.get(
            "args"
        )

        require(
            isinstance(args, list),
            f"{stage_name}: args must be a list.",
        )

        require(
            all(
                isinstance(item, str)
                for item in args
            ),
            f"{stage_name}: every argument must be a string.",
        )


def build_stage_command(
    *,
    plan: Mapping[str, Any],
    stage_name: str,
) -> tuple[str, ...]:

    require(
        stage_name in STAGE_ORDER,
        f"Unknown post-wave stage: {stage_name}",
    )

    stage = plan[
        "stages"
    ][
        stage_name
    ]

    return (
        sys.executable,
        "-B",
        str(
            STAGE_SCRIPTS[
                stage_name
            ]
        ),
        *tuple(
            stage[
                "args"
            ]
        ),
    )


def build_transaction_commands(
    plan: Mapping[str, Any],
) -> tuple[
    tuple[str, tuple[str, ...]],
    ...
]:

    return tuple(
        (
            stage_name,
            build_stage_command(
                plan=plan,
                stage_name=stage_name,
            ),
        )
        for stage_name in STAGE_ORDER
    )


def execute_transaction(
    plan: Mapping[str, Any],
) -> None:

    verify_stage_authorities(
        plan
    )

    commands = build_transaction_commands(
        plan
    )

    for stage_name, command in commands:

        print()
        print("=" * 120)
        print(
            "POST-WAVE STAGE:",
            stage_name,
        )
        print("=" * 120)

        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
        )

        require(
            completed.returncode == 0,
            (
                f"{stage_name}: transaction stage "
                f"failed with return code "
                f"{completed.returncode}."
            ),
        )


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--transaction-plan",
        required=True,
    )

    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help=(
            "Verify the immutable transaction plan and "
            "component SHAs, print execution order, "
            "but execute no child stage."
        ),
    )

    args = parser.parse_args()

    plan_path = Path(
        args.transaction_plan
    ).resolve()

    plan = load_plan(
        plan_path
    )

    verify_stage_authorities(
        plan
    )

    commands = build_transaction_commands(
        plan
    )

    print()
    print("=" * 120)
    print(
        "THREADROM - GENERIC GOVERNED-WAVE "
        "POST-WAVE TRANSACTION"
    )
    print("=" * 120)

    print(
        "Wave        :",
        plan[
            "wave_id"
        ],
    )

    print(
        "Plan        :",
        plan_path,
    )

    print(
        "Plan SHA    :",
        sha256(
            plan_path
        ),
    )

    print(
        "Stage count :",
        len(
            commands
        ),
    )

    for index, (
        stage_name,
        command,
    ) in enumerate(
        commands,
        start=1,
    ):
        print(
            f"[{index}/4] "
            f"{stage_name} -> "
            f"{Path(command[2]).name}"
        )

    if args.inspect_only:

        print()
        print(
            "Execution   : INSPECT_ONLY"
        )

        print(
            "Child stages: NOT EXECUTED"
        )

    else:

        execute_transaction(
            plan
        )

        print()
        print(
            "Execution   : COMPLETE"
        )

    print()
    print(
        "DISPOSITION : "
        "GENERIC_POST_WAVE_TRANSACTION_VALID"
    )

    print("=" * 120)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

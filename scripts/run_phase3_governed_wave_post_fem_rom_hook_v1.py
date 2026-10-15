from __future__ import annotations

import argparse
import subprocess
import sys

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

ROM_ADAPTER = (
    ROOT
    / "scripts"
    / "evaluate_phase3_governed_wave_rom_admission_v1.py"
)


def require(
    condition: bool,
    message: str,
) -> None:

    if not condition:
        raise RuntimeError(
            message
        )


def build_command(
    *,
    wave_id: str,
    expected_atlas_sha256: str,
    expected_count: int,
) -> tuple[str, ...]:

    require(
        ROM_ADAPTER.is_file(),
        (
            "Generic governed-wave ROM adapter "
            "is missing."
        ),
    )

    require(
        isinstance(
            wave_id,
            str,
        )
        and bool(
            wave_id.strip()
        ),
        "wave_id must be nonblank.",
    )

    require(
        isinstance(
            expected_atlas_sha256,
            str,
        )
        and len(
            expected_atlas_sha256
        )
        == 64,
        (
            "expected_atlas_sha256 must be "
            "a SHA-256 hex string."
        ),
    )

    require(
        isinstance(
            expected_count,
            int,
        )
        and expected_count > 0,
        "expected_count must be positive.",
    )

    return (
        sys.executable,
        "-B",
        str(
            ROM_ADAPTER
        ),
        "--wave-id",
        wave_id,
        "--expected-atlas-sha256",
        expected_atlas_sha256,
        "--expected-count",
        str(
            expected_count
        ),
    )


def run_post_fem_rom_hook(
    *,
    wave_id: str,
    expected_atlas_sha256: str,
    expected_count: int,
) -> None:

    command = build_command(
        wave_id=wave_id,
        expected_atlas_sha256=expected_atlas_sha256,
        expected_count=expected_count,
    )

    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
    )

    require(
        completed.returncode == 0,
        (
            f"{wave_id}: generic post-FEM "
            "ROM-candidate hook failed with "
            f"return code {completed.returncode}."
        ),
    )


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--wave-id",
        required=True,
    )

    parser.add_argument(
        "--expected-atlas-sha256",
        required=True,
    )

    parser.add_argument(
        "--expected-count",
        type=int,
        required=True,
    )

    args = parser.parse_args()

    print()
    print("=" * 120)
    print(
        "THREADROM - GENERIC GOVERNED-WAVE "
        "POST-FEM ROM HOOK"
    )
    print("=" * 120)

    print(
        "Wave              :",
        args.wave_id,
    )

    print(
        "Expected FEM rows :",
        args.expected_count,
    )

    run_post_fem_rom_hook(
        wave_id=args.wave_id,
        expected_atlas_sha256=(
            args.expected_atlas_sha256
        ),
        expected_count=(
            args.expected_count
        ),
    )

    print()
    print("=" * 120)
    print(
        "POST-FEM ROM HOOK : PASS"
    )
    print(
        "Dataset mutation  : NO"
    )
    print(
        "Partition mutation: NO"
    )
    print(
        "ROM training      : NO"
    )
    print(
        "Solver            : NO"
    )
    print()
    print(
        "DISPOSITION : "
        "GENERIC_POST_FEM_ROM_CANDIDATE_HOOK_PASSED"
    )
    print("=" * 120)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

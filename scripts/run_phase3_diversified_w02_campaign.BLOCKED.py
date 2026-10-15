from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(r"D:\ThreadROM")

CAL01 = (
    ROOT
    / "scripts"
    / "run_phase3_diversified_w02_factory.py"
)

ADAPTIVE = (
    ROOT
    / "scripts"
    / "run_phase3_diversified_w02_adaptive_factory.py"
)


def execute(label: str, command: list[str]) -> None:

    print()
    print("=" * 118)
    print(label)
    print("=" * 118)
    print(" ".join(command))
    print(flush=True)

    completed = subprocess.run(
        command,
        cwd=ROOT,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} failed with "
            f"exit code {completed.returncode}."
        )


def main() -> int:

    python = sys.executable

    execute(
        "W02 STAGE 1 ? GOVERNED CAL_01 FOUR-WAY FACTORY",
        [
            python,
            "-u",
            "-B",
            str(CAL01),
            "--execute",
        ],
    )

    execute(
        "W02 STAGE 2 ? AUTONOMOUS ADAPTIVE PREFLIGHT",
        [
            python,
            "-u",
            "-B",
            str(ADAPTIVE),
            "--preflight",
        ],
    )

    execute(
        "W02 STAGE 3 ? CAL_02+ THROUGH FULL PHYSICS",
        [
            python,
            "-u",
            "-B",
            str(ADAPTIVE),
            "--execute",
        ],
    )

    print()
    print("=" * 118)
    print(
        "TRM-DDOE-001-W02 ? COORDINATED CAMPAIGN COMPLETE"
    )
    print("=" * 118)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )

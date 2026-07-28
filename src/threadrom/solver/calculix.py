"""CalculiX execution and verification utilities."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CalculixSmokeResult:
    """Results from the CalculiX linear-elastic smoke test."""

    exit_code: int
    mean_loaded_displacement_m: float
    mean_axial_stress_pa: float
    expected_axial_stress_pa: float
    relative_stress_error: float


def project_root() -> Path:
    """Return the ThreadROM repository root."""

    return Path(__file__).resolve().parents[3]


def resolve_ccx(root: Path | None = None) -> Path:
    """Resolve the CalculiX executable path."""

    environment_path = os.environ.get("THREADROM_CCX")

    if environment_path:
        return Path(environment_path)

    repository_root = root or project_root()

    return (
        repository_root
        / "tools"
        / "calculix"
        / "2.23.0"
        / "CalculiX-2.23.0-win-x64"
        / "bin"
        / "ccx.exe"
    )


def _parse_smoke_results(dat_path: Path) -> tuple[float, float]:
    """Extract mean loaded displacement and mean axial stress."""

    content = dat_path.read_text(encoding="utf-8", errors="replace")

    displacement_section = content.split(
        "displacements (vx,vy,vz)",
        maxsplit=1,
    )[1].split(
        "stresses (elem",
        maxsplit=1,
    )[0]

    stress_section = content.split(
        "stresses (elem",
        maxsplit=1,
    )[1]

    floating_number = r"[+-]?\d+\.\d+E[+-]\d+"

    displacement_pattern = re.compile(
        rf"^\s*\d+\s+({floating_number})\s+"
        rf"({floating_number})\s+({floating_number})\s*$",
        re.MULTILINE,
    )

    stress_pattern = re.compile(
        rf"^\s*\d+\s+\d+\s+"
        rf"({floating_number})\s+"
        rf"({floating_number})\s+"
        rf"({floating_number})\s+"
        rf"({floating_number})\s+"
        rf"({floating_number})\s+"
        rf"({floating_number})\s*$",
        re.MULTILINE,
    )

    displacement_rows = displacement_pattern.findall(displacement_section)
    stress_rows = stress_pattern.findall(stress_section)

    if len(displacement_rows) != 4:
        raise RuntimeError(
            f"Expected 4 loaded-node displacement rows, found {len(displacement_rows)}."
        )

    if len(stress_rows) != 8:
        raise RuntimeError(
            f"Expected 8 integration-point stress rows, found {len(stress_rows)}."
        )

    mean_loaded_displacement = sum(
        float(row[2]) for row in displacement_rows
    ) / len(displacement_rows)

    mean_axial_stress = sum(
        float(row[2]) for row in stress_rows
    ) / len(stress_rows)

    return mean_loaded_displacement, mean_axial_stress


def run_smoke_test(root: Path | None = None) -> CalculixSmokeResult:
    """Run and verify the ThreadROM CalculiX smoke case."""

    repository_root = root or project_root()
    ccx_path = resolve_ccx(repository_root)

    if not ccx_path.is_file():
        raise FileNotFoundError(
            "CalculiX executable not found. "
            "Install it locally or define THREADROM_CCX."
        )

    case_directory = (
        repository_root
        / "tests"
        / "fixtures"
        / "calculix"
        / "smoke_cube"
    )

    input_path = case_directory / "smoke_cube.inp"

    if not input_path.is_file():
        raise FileNotFoundError(f"Smoke-test input deck not found: {input_path}")

    generated_extensions = {
        ".12d",
        ".cvg",
        ".dat",
        ".frd",
        ".sta",
        ".out",
    }

    for path in case_directory.iterdir():
        if path.is_file() and path.suffix.lower() in generated_extensions:
            path.unlink()

    completed = subprocess.run(
        [str(ccx_path), "smoke_cube"],
        cwd=case_directory,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "CalculiX smoke test failed.\n"
            f"STDOUT:\n{completed.stdout}\n"
            f"STDERR:\n{completed.stderr}"
        )

    dat_path = case_directory / "smoke_cube.dat"

    if not dat_path.is_file():
        raise RuntimeError("CalculiX did not generate smoke_cube.dat.")

    mean_displacement, mean_stress = _parse_smoke_results(dat_path)

    applied_force_n = 1000.0
    loaded_area_m2 = 0.010 * 0.010
    expected_stress = applied_force_n / loaded_area_m2

    relative_error = abs(mean_stress - expected_stress) / expected_stress

    return CalculixSmokeResult(
        exit_code=completed.returncode,
        mean_loaded_displacement_m=mean_displacement,
        mean_axial_stress_pa=mean_stress,
        expected_axial_stress_pa=expected_stress,
        relative_stress_error=relative_error,
    )
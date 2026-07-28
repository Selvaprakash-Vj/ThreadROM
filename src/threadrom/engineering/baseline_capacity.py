"""Analytical axial-capacity checks for the baseline bolt."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from threadrom.engineering.baseline_assembly import (
    load_baseline_assembly,
)
from threadrom.engineering.baseline_reference import (
    load_baseline_thread_reference,
)


@dataclass(frozen=True)
class BoltStrengthReference:
    """Provisional strength reference for the configured bolt class."""

    property_class: str
    proof_stress_pa: float
    yield_strength_pa: float
    ultimate_tensile_strength_pa: float


@dataclass(frozen=True)
class BoltAxialCapacityCheck:
    """Analytical elastic-capacity results for the baseline bolt."""

    tensile_stress_area_mm2: float
    preload_n: float
    external_load_n: float
    preload_stress_pa: float
    conservative_combined_stress_pa: float
    proof_load_n: float
    yield_load_n: float
    ultimate_load_n: float
    preload_proof_utilisation: float
    combined_proof_utilisation: float
    combined_yield_utilisation: float
    proof_margin_n: float

    @property
    def passes_preload_proof_check(self) -> bool:
        """Return whether preload remains below 70 percent of proof load."""

        return self.preload_proof_utilisation <= 0.70

    @property
    def passes_conservative_combined_check(self) -> bool:
        """Return whether preload plus full external load remains below proof."""

        return self.combined_proof_utilisation < 1.0


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return a required TOML section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(f"Missing or invalid configuration section: {key}")

    return cast(Mapping[str, object], value)


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    """Return a required string value."""

    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"Missing or invalid string value: {key}")

    return value


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return a required positive numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"Missing or invalid numerical value: {key}")

    numeric_value = float(value)

    if numeric_value <= 0.0:
        raise ValueError(f"{key} must be positive.")

    return numeric_value


def load_strength_reference(
    fastener_config_path: Path,
) -> BoltStrengthReference:
    """Load the configured bolt strength reference."""

    with fastener_config_path.open("rb") as config_file:
        raw_data: dict[str, object] = tomllib.load(config_file)

    strength = _section(raw_data, "strength_reference")

    return BoltStrengthReference(
        property_class=_string(strength, "property_class"),
        proof_stress_pa=_number(strength, "proof_stress_pa"),
        yield_strength_pa=_number(strength, "yield_strength_pa"),
        ultimate_tensile_strength_pa=_number(
            strength,
            "ultimate_tensile_strength_pa",
        ),
    )


def evaluate_baseline_bolt_capacity(
    fastener_config_path: Path,
    assembly_config_path: Path,
) -> BoltAxialCapacityCheck:
    """Evaluate the baseline preload and conservative axial-load envelope."""

    thread_reference = load_baseline_thread_reference(
        fastener_config_path,
    )
    assembly = load_baseline_assembly(
        assembly_config_path,
    )
    strength = load_strength_reference(
        fastener_config_path,
    )

    tensile_area_mm2 = (
        thread_reference.dimensions.tensile_stress_area_mm2
    )
    tensile_area_m2 = tensile_area_mm2 * 1.0e-6

    preload_stress = assembly.target_preload_n / tensile_area_m2

    conservative_combined_load = (
        assembly.target_preload_n
        + assembly.external_axial_load_n
    )

    conservative_combined_stress = (
        conservative_combined_load / tensile_area_m2
    )

    proof_load = strength.proof_stress_pa * tensile_area_m2
    yield_load = strength.yield_strength_pa * tensile_area_m2
    ultimate_load = (
        strength.ultimate_tensile_strength_pa * tensile_area_m2
    )

    return BoltAxialCapacityCheck(
        tensile_stress_area_mm2=tensile_area_mm2,
        preload_n=assembly.target_preload_n,
        external_load_n=assembly.external_axial_load_n,
        preload_stress_pa=preload_stress,
        conservative_combined_stress_pa=conservative_combined_stress,
        proof_load_n=proof_load,
        yield_load_n=yield_load,
        ultimate_load_n=ultimate_load,
        preload_proof_utilisation=(
            assembly.target_preload_n / proof_load
        ),
        combined_proof_utilisation=(
            conservative_combined_load / proof_load
        ),
        combined_yield_utilisation=(
            conservative_combined_load / yield_load
        ),
        proof_margin_n=proof_load - conservative_combined_load,
    )


def render_capacity_report(
    check: BoltAxialCapacityCheck,
) -> str:
    """Render the baseline axial-capacity check as Markdown."""

    preload_status = (
        "PASS" if check.passes_preload_proof_check else "FAIL"
    )

    combined_status = (
        "PASS"
        if check.passes_conservative_combined_check
        else "FAIL"
    )

    return f"""# ThreadROM Baseline Bolt Axial-Capacity Check

## Record information

- Simulation identity: TRM-SIM-000001
- Material identity: TRM-MAT-000001
- Bolt property class: 8.8
- Status: Preliminary analytical verification

## Inputs

| Quantity | Value |
|---|---:|
| Tensile stress area | {check.tensile_stress_area_mm2:.6f} mm² |
| Target preload | {check.preload_n:.1f} N |
| External axial load | {check.external_load_n:.1f} N |
| Proof stress reference | 580.0 MPa |
| Yield-strength reference | 640.0 MPa |
| Ultimate-strength reference | 800.0 MPa |

## Calculated capacities

| Quantity | Value |
|---|---:|
| Proof load | {check.proof_load_n:.1f} N |
| Yield load | {check.yield_load_n:.1f} N |
| Ultimate tensile load | {check.ultimate_load_n:.1f} N |

## Load checks

| Check | Result |
|---|---:|
| Preload stress | {check.preload_stress_pa / 1.0e6:.3f} MPa |
| Preload proof utilisation | {check.preload_proof_utilisation:.4f} |
| Preload target check | {preload_status} |
| Conservative combined stress | {check.conservative_combined_stress_pa / 1.0e6:.3f} MPa |
| Conservative proof utilisation | {check.combined_proof_utilisation:.4f} |
| Conservative yield utilisation | {check.combined_yield_utilisation:.4f} |
| Remaining proof-load margin | {check.proof_margin_n:.1f} N |
| Conservative combined check | {combined_status} |

## Interpretation

The preload-only check requires the proposed preload to remain at or below
70 percent of the configured proof load.

The conservative combined check assumes that the full external axial load is
added directly to the bolt preload. This deliberately ignores load sharing by
the clamped members and therefore provides an upper-bound axial bolt load.

This is not the final joint-load prediction. The next analytical stage must
calculate bolt stiffness, member stiffness and the resulting joint load factor.

## Limitations

The strength values are provisional controlled references and must be checked
against the approved fastener-standard source before TRM-MAT-000001 is released.

This check does not include:

- Thread-root stress concentration
- Bending
- Torsional tightening stress
- Local contact stress
- Plasticity
- Fatigue
- Assembly scatter
"""
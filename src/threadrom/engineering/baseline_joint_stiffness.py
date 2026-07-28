"""Preliminary analytical stiffness model for the baseline joint."""

from __future__ import annotations

import math
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from threadrom.engineering.baseline_assembly import (
    load_baseline_assembly,
)
from threadrom.engineering.baseline_capacity import (
    load_strength_reference,
)
from threadrom.engineering.baseline_reference import (
    load_baseline_thread_reference,
)


@dataclass(frozen=True)
class JointStiffnessCheck:
    """Analytical stiffness and external-load-sharing results."""

    bolt_effective_length_m: float
    member_compression_area_m2: float
    bolt_stiffness_n_per_m: float
    member_stiffness_n_per_m: float
    joint_constant: float
    external_load_n: float
    bolt_load_increment_n: float
    member_clamp_loss_n: float
    maximum_bolt_load_n: float
    remaining_clamp_load_n: float
    separation_load_n: float
    maximum_bolt_stress_pa: float
    proof_utilisation_after_external_load: float

    @property
    def passes_separation_check(self) -> bool:
        """Return whether positive clamp load remains."""

        return self.remaining_clamp_load_n > 0.0

    @property
    def passes_proof_check(self) -> bool:
        """Return whether the estimated bolt load remains below proof."""

        return self.proof_utilisation_after_external_load < 1.0


def _section(
    data: Mapping[str, object],
    key: str,
) -> Mapping[str, object]:
    """Return a required TOML section."""

    value = data.get(key)

    if not isinstance(value, dict):
        raise TypeError(f"Missing or invalid configuration section: {key}")

    return cast(Mapping[str, object], value)


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    """Return a required numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"Missing or invalid numerical value: {key}")

    return float(value)


def evaluate_baseline_joint_stiffness(
    fastener_config_path: Path,
    assembly_config_path: Path,
) -> JointStiffnessCheck:
    """Evaluate preliminary bolt and member stiffness."""

    assembly = load_baseline_assembly(assembly_config_path)

    thread_reference = load_baseline_thread_reference(
        fastener_config_path,
    )

    strength = load_strength_reference(
        fastener_config_path,
    )

    with fastener_config_path.open("rb") as config_file:
        fastener_data: dict[str, object] = tomllib.load(config_file)

    with assembly_config_path.open("rb") as config_file:
        assembly_data: dict[str, object] = tomllib.load(config_file)

    thread = _section(fastener_data, "thread")
    bolt_material = _section(fastener_data, "material")
    stiffness_model = _section(
        assembly_data,
        "analytical_stiffness",
    )

    nominal_diameter_mm = _number(
        thread,
        "nominal_diameter_mm",
    )

    bolt_youngs_modulus_pa = _number(
        bolt_material,
        "youngs_modulus_pa",
    )

    member_youngs_modulus_pa = _number(
        stiffness_model,
        "member_youngs_modulus_pa",
    )

    head_factor = _number(
        stiffness_model,
        "bolt_head_participation_factor",
    )

    nut_factor = _number(
        stiffness_model,
        "nut_participation_factor",
    )

    if head_factor < 0.0 or nut_factor < 0.0:
        raise ValueError(
            "Bolt participation factors must be non-negative."
        )

    bolt_effective_length_mm = (
        assembly.total_grip_length_mm
        + head_factor * nominal_diameter_mm
        + nut_factor * nominal_diameter_mm
    )

    bolt_effective_length_m = (
        bolt_effective_length_mm * 1.0e-3
    )

    tensile_area_m2 = (
        thread_reference.dimensions.tensile_stress_area_mm2
        * 1.0e-6
    )

    outer_radius_m = (
        assembly.outer_diameter_mm * 0.5e-3
    )

    hole_radius_m = (
        assembly.clearance_hole_diameter_mm * 0.5e-3
    )

    member_compression_area_m2 = math.pi * (
        outer_radius_m**2 - hole_radius_m**2
    )

    member_length_m = (
        assembly.total_grip_length_mm * 1.0e-3
    )

    bolt_stiffness = (
        bolt_youngs_modulus_pa
        * tensile_area_m2
        / bolt_effective_length_m
    )

    member_stiffness = (
        member_youngs_modulus_pa
        * member_compression_area_m2
        / member_length_m
    )

    joint_constant = bolt_stiffness / (
        bolt_stiffness + member_stiffness
    )

    bolt_load_increment = (
        joint_constant
        * assembly.external_axial_load_n
    )

    member_clamp_loss = (
        (1.0 - joint_constant)
        * assembly.external_axial_load_n
    )

    maximum_bolt_load = (
        assembly.target_preload_n
        + bolt_load_increment
    )

    remaining_clamp_load = (
        assembly.target_preload_n
        - member_clamp_loss
    )

    separation_load = (
        assembly.target_preload_n
        / (1.0 - joint_constant)
    )

    maximum_bolt_stress = (
        maximum_bolt_load / tensile_area_m2
    )

    proof_utilisation = (
        maximum_bolt_stress / strength.proof_stress_pa
    )

    return JointStiffnessCheck(
        bolt_effective_length_m=bolt_effective_length_m,
        member_compression_area_m2=member_compression_area_m2,
        bolt_stiffness_n_per_m=bolt_stiffness,
        member_stiffness_n_per_m=member_stiffness,
        joint_constant=joint_constant,
        external_load_n=assembly.external_axial_load_n,
        bolt_load_increment_n=bolt_load_increment,
        member_clamp_loss_n=member_clamp_loss,
        maximum_bolt_load_n=maximum_bolt_load,
        remaining_clamp_load_n=remaining_clamp_load,
        separation_load_n=separation_load,
        maximum_bolt_stress_pa=maximum_bolt_stress,
        proof_utilisation_after_external_load=proof_utilisation,
    )


def render_joint_stiffness_report(
    check: JointStiffnessCheck,
) -> str:
    """Render the preliminary joint-stiffness report."""

    separation_status = (
        "PASS" if check.passes_separation_check else "FAIL"
    )

    proof_status = (
        "PASS" if check.passes_proof_check else "FAIL"
    )

    return f"""# ThreadROM Baseline Joint-Stiffness Check

## Record information

- Assembly identity: TRM-ASM-000001
- Simulation identity: TRM-SIM-000001
- Status: Preliminary analytical verification

## Analytical model

The bolt is represented using the tensile stress area and an effective elastic
length equal to the grip length plus 0.5 nominal diameters beneath the bolt head
and 0.5 nominal diameters within the nut.

The clamped members are represented as a uniform annular compression cylinder.
This is a deliberately simple preliminary model and is not the final compressed
cone or finite-element stiffness prediction.

## Calculated stiffness

| Quantity | Value |
|---|---:|
| Effective bolt length | {check.bolt_effective_length_m * 1.0e3:.3f} mm |
| Member compression area | {check.member_compression_area_m2 * 1.0e6:.3f} mm² |
| Bolt stiffness | {check.bolt_stiffness_n_per_m / 1.0e6:.3f} kN/mm |
| Member stiffness | {check.member_stiffness_n_per_m / 1.0e6:.3f} kN/mm |
| Joint constant | {check.joint_constant:.6f} |

## External-load sharing

| Quantity | Value |
|---|---:|
| External axial load | {check.external_load_n:.1f} N |
| Bolt-load increment | {check.bolt_load_increment_n:.1f} N |
| Member clamp-load loss | {check.member_clamp_loss_n:.1f} N |
| Maximum bolt load | {check.maximum_bolt_load_n:.1f} N |
| Remaining clamp load | {check.remaining_clamp_load_n:.1f} N |
| Estimated separation load | {check.separation_load_n:.1f} N |

## Strength check after external loading

| Quantity | Value |
|---|---:|
| Estimated maximum bolt stress | {check.maximum_bolt_stress_pa / 1.0e6:.3f} MPa |
| Proof utilisation | {check.proof_utilisation_after_external_load:.4f} |
| Proof check | {proof_status} |
| Separation check | {separation_status} |

## Interpretation

The preliminary joint constant determines the fraction of external axial load
that increases bolt force before joint separation.

The remaining fraction reduces the member clamp force.

This analytical result provides a reference trend for the future nonlinear FEM
model. It must not be treated as the final joint-stiffness prediction.

## Limitations

This model does not yet include:

- Compression-cone spreading
- Local bearing compliance
- Thread compliance
- Contact opening
- Frictional redistribution
- Member-interface slip
- Geometric nonlinearity
- Manufacturing variation
"""
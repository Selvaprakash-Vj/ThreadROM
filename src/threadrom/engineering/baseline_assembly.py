"""Baseline threaded-joint assembly configuration."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class BaselineAssembly:
    """Validated baseline threaded-joint assembly."""

    assembly_id: str
    bolt_length_mm: float
    pitch_mm: float
    upper_member_thickness_mm: float
    lower_member_thickness_mm: float
    total_grip_length_mm: float
    nut_thickness_mm: float
    thread_engagement_length_mm: float
    protrusion_length_mm: float
    clearance_hole_diameter_mm: float
    outer_diameter_mm: float
    target_preload_n: float
    external_axial_load_n: float
    friction_coefficient: float

    @property
    def engaged_thread_count(self) -> float:
        """Return the nominal number of engaged thread pitches."""

        return self.thread_engagement_length_mm / self.pitch_mm

    @property
    def stack_length_mm(self) -> float:
        """Return grip, nut and protrusion stack length."""

        return (
            self.total_grip_length_mm
            + self.nut_thickness_mm
            + self.protrusion_length_mm
        )

    @property
    def nut_translation_z_mm(self) -> float:
        """Return the nut translation from the bolt-head datum."""

        return self.total_grip_length_mm


    @property
    def nut_lower_bearing_z_mm(self) -> float:
        """Return the lower nut-bearing-plane coordinate."""

        return self.nut_translation_z_mm

    @property
    def nut_upper_bearing_z_mm(self) -> float:
        """Return the upper nut-bearing-plane coordinate."""

        return (
            self.nut_translation_z_mm
            + self.nut_thickness_mm
        )

    @property
    def calculated_protrusion_length_mm(self) -> float:
        """Return protrusion implied by the positioned nut."""

        return (
            self.bolt_length_mm
            - self.nut_upper_bearing_z_mm
        )


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
    """Return a required numerical value."""

    value = data.get(key)

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"Missing or invalid numerical value: {key}")

    return float(value)


def load_baseline_assembly(path: Path) -> BaselineAssembly:
    """Load and validate the baseline assembly configuration."""

    with path.open("rb") as config_file:
        raw_data: dict[str, object] = tomllib.load(config_file)

    identity = _section(raw_data, "identity")
    bolt = _section(raw_data, "bolt")
    members = _section(raw_data, "clamped_members")
    nut = _section(raw_data, "nut")
    protrusion = _section(raw_data, "thread_protrusion")
    loading = _section(raw_data, "loading")
    interfaces = _section(raw_data, "interfaces")

    assembly = BaselineAssembly(
        assembly_id=_string(identity, "assembly_id"),
        bolt_length_mm=_number(bolt, "nominal_length_mm"),
        pitch_mm=_number(bolt, "pitch_mm"),
        upper_member_thickness_mm=_number(
            members,
            "upper_member_thickness_mm",
        ),
        lower_member_thickness_mm=_number(
            members,
            "lower_member_thickness_mm",
        ),
        total_grip_length_mm=_number(
            members,
            "total_grip_length_mm",
        ),
        nut_thickness_mm=_number(
            nut,
            "nominal_thickness_mm",
        ),
        thread_engagement_length_mm=_number(
            nut,
            "thread_engagement_length_mm",
        ),
        protrusion_length_mm=_number(
            protrusion,
            "length_mm",
        ),
        clearance_hole_diameter_mm=_number(
            members,
            "clearance_hole_diameter_mm",
        ),
        outer_diameter_mm=_number(
            members,
            "outer_diameter_mm",
        ),
        target_preload_n=_number(
            loading,
            "target_preload_n",
        ),
        external_axial_load_n=_number(
            loading,
            "external_axial_load_n",
        ),
        friction_coefficient=_number(
            interfaces,
            "friction_coefficient",
        ),
    )

    validate_baseline_assembly(assembly)

    return assembly


def validate_baseline_assembly(
    assembly: BaselineAssembly,
) -> None:
    """Validate baseline assembly consistency."""

    positive_values = {
        "bolt length": assembly.bolt_length_mm,
        "pitch": assembly.pitch_mm,
        "upper member thickness": assembly.upper_member_thickness_mm,
        "lower member thickness": assembly.lower_member_thickness_mm,
        "grip length": assembly.total_grip_length_mm,
        "nut thickness": assembly.nut_thickness_mm,
        "thread engagement": assembly.thread_engagement_length_mm,
        "protrusion": assembly.protrusion_length_mm,
        "clearance hole diameter": assembly.clearance_hole_diameter_mm,
        "outer diameter": assembly.outer_diameter_mm,
        "preload": assembly.target_preload_n,
        "external load": assembly.external_axial_load_n,
    }

    for name, value in positive_values.items():
        if value <= 0.0:
            raise ValueError(f"{name} must be positive.")

    calculated_grip = (
        assembly.upper_member_thickness_mm
        + assembly.lower_member_thickness_mm
    )

    if abs(calculated_grip - assembly.total_grip_length_mm) > 1.0e-9:
        raise ValueError(
            "Total grip length does not equal the member-thickness sum."
        )

    if abs(assembly.stack_length_mm - assembly.bolt_length_mm) > 1.0e-9:
        raise ValueError(
            "Bolt length does not equal grip, nut and protrusion stack."
        )

    if assembly.thread_engagement_length_mm > assembly.nut_thickness_mm:
        raise ValueError(
            "Thread engagement cannot exceed nominal nut thickness."
        )

    if assembly.engaged_thread_count < 5.0:
        raise ValueError(
            "Baseline thread engagement must contain at least five pitches."
        )

    if assembly.clearance_hole_diameter_mm <= 10.0:
        raise ValueError(
            "Clearance-hole diameter must exceed the nominal bolt diameter."
        )

    if assembly.outer_diameter_mm <= assembly.clearance_hole_diameter_mm:
        raise ValueError(
            "Member outer diameter must exceed the clearance-hole diameter."
        )

    if not 0.0 <= assembly.friction_coefficient <= 1.0:
        raise ValueError(
            "Friction coefficient must lie between zero and one."
        )
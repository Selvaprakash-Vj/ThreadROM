"""Resolved Phase-3 assembly definitions.

These objects are generated from ThreadROMCase and contain derived values
needed by existing geometry/engineering consumers. They are not user inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ResolvedAssembly:
    """Resolved two-member cylindrical joint assembly."""

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

    def __post_init__(self) -> None:
        if not self.assembly_id.strip():
            raise ValueError("Assembly identity must not be blank.")

        positive_values = {
            "bolt length": self.bolt_length_mm,
            "pitch": self.pitch_mm,
            "upper member thickness": self.upper_member_thickness_mm,
            "lower member thickness": self.lower_member_thickness_mm,
            "grip length": self.total_grip_length_mm,
            "nut thickness": self.nut_thickness_mm,
            "thread engagement": self.thread_engagement_length_mm,
            "clearance hole diameter": self.clearance_hole_diameter_mm,
            "outer diameter": self.outer_diameter_mm,
        }

        for name, value in positive_values.items():
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(
                    f"{name} must be finite and positive."
                )

        if (
            not math.isfinite(self.protrusion_length_mm)
            or self.protrusion_length_mm < 0.0
        ):
            raise ValueError(
                "Protrusion length must be finite and non-negative."
            )

        if (
            abs(
                self.protrusion_length_mm
                - self.calculated_protrusion_length_mm
            )
            > 1.0e-9
        ):
            raise ValueError(
                "Resolved protrusion must match bolt and stack geometry."
            )

        if (
            abs(
                self.total_grip_length_mm
                - (
                    self.upper_member_thickness_mm
                    + self.lower_member_thickness_mm
                )
            )
            > 1.0e-9
        ):
            raise ValueError(
                "Total grip length must equal the member-thickness sum."
            )

        if self.thread_engagement_length_mm > self.nut_thickness_mm:
            raise ValueError(
                "Thread engagement must not exceed nut thickness."
            )

        if self.clearance_hole_diameter_mm >= self.outer_diameter_mm:
            raise ValueError(
                "Member outer diameter must exceed clearance-hole diameter."
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
        """Return protrusion implied by resolved stack geometry."""

        return (
            self.bolt_length_mm
            - self.nut_upper_bearing_z_mm
        )

    @property
    def engaged_thread_count(self) -> float:
        """Return nominal engaged thread-pitch count."""

        return self.thread_engagement_length_mm / self.pitch_mm

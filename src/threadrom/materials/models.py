"""Core governed material models for ThreadROM."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class MaterialFamily:
    """Base physical material properties independent of fastener class.

    Optional properties remain unset until ThreadROM has a governed source
    for them. Provenance is recorded by property group rather than inferred.
    """

    material_id: str
    display_name: str

    youngs_modulus_mpa: float
    poissons_ratio: float
    elastic_source_reference: str

    density_kg_per_m3: float | None = None
    density_source_reference: str | None = None

    thermal_expansion_per_c: float | None = None
    thermal_source_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.material_id.strip():
            raise ValueError("Material identity must not be blank.")

        if not self.display_name.strip():
            raise ValueError("Material display name must not be blank.")

        if not self.elastic_source_reference.strip():
            raise ValueError(
                "Elastic-property source reference must not be blank."
            )

        if (
            not math.isfinite(self.youngs_modulus_mpa)
            or self.youngs_modulus_mpa <= 0.0
        ):
            raise ValueError(
                "Young's modulus must be finite and positive."
            )

        if (
            not math.isfinite(self.poissons_ratio)
            or not -1.0 < self.poissons_ratio < 0.5
        ):
            raise ValueError(
                "Poisson's ratio must lie between -1 and 0.5."
            )

        if self.density_kg_per_m3 is not None:
            if (
                not math.isfinite(self.density_kg_per_m3)
                or self.density_kg_per_m3 <= 0.0
            ):
                raise ValueError(
                    "Density must be finite and positive when provided."
                )

            if (
                self.density_source_reference is None
                or not self.density_source_reference.strip()
            ):
                raise ValueError(
                    "Density requires a governed source reference."
                )

        elif self.density_source_reference is not None:
            raise ValueError(
                "Density source reference requires a density value."
            )

        if self.thermal_expansion_per_c is not None:
            if (
                not math.isfinite(self.thermal_expansion_per_c)
                or self.thermal_expansion_per_c <= 0.0
            ):
                raise ValueError(
                    "Thermal expansion coefficient must be "
                    "finite and positive when provided."
                )

            if (
                self.thermal_source_reference is None
                or not self.thermal_source_reference.strip()
            ):
                raise ValueError(
                    "Thermal expansion requires a governed source reference."
                )

        elif self.thermal_source_reference is not None:
            raise ValueError(
                "Thermal source reference requires "
                "a thermal expansion value."
            )

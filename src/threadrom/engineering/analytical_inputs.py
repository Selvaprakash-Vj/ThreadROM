"""Canonical inputs for the parametric analytical engine."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ThreadHandedness(StrEnum):
    """Supported thread handedness values."""

    RIGHT = "right"
    LEFT = "left"


class BoltSegmentKind(StrEnum):
    """Supported axial bolt-segment representations."""

    UNTHREADED_SHANK = "unthreaded_shank"
    THREADED = "threaded"
    CUSTOM_AREA = "custom_area"


@dataclass(frozen=True)
class ElasticMaterial:
    """Linear-elastic material properties."""

    material_id: str
    youngs_modulus_mpa: float
    poissons_ratio: float
    proof_stress_mpa: float | None = None
    yield_strength_mpa: float | None = None
    ultimate_strength_mpa: float | None = None

    def __post_init__(self) -> None:
        if not self.material_id.strip():
            raise ValueError("Material identity must not be blank.")

        if self.youngs_modulus_mpa <= 0.0:
            raise ValueError("Young's modulus must be positive.")

        if not -1.0 < self.poissons_ratio < 0.5:
            raise ValueError("Poisson's ratio must lie between -1 and 0.5.")

        strengths = {
            "proof stress": self.proof_stress_mpa,
            "yield strength": self.yield_strength_mpa,
            "ultimate strength": self.ultimate_strength_mpa,
        }

        for name, value in strengths.items():
            if value is not None and value <= 0.0:
                raise ValueError(f"{name} must be positive when provided.")

        if (
            self.proof_stress_mpa is not None
            and self.yield_strength_mpa is not None
            and self.proof_stress_mpa > self.yield_strength_mpa
        ):
            raise ValueError("Proof stress must not exceed yield strength.")

        if (
            self.yield_strength_mpa is not None
            and self.ultimate_strength_mpa is not None
            and self.yield_strength_mpa > self.ultimate_strength_mpa
        ):
            raise ValueError("Yield strength must not exceed ultimate strength.")


@dataclass(frozen=True)
class MetricThreadInput:
    """Parametric ISO metric-thread input."""

    nominal_diameter_mm: float
    pitch_mm: float
    handedness: ThreadHandedness = ThreadHandedness.RIGHT
    starts: int = 1
    included_angle_deg: float = 60.0
    external_tolerance_class: str | None = None
    internal_tolerance_class: str | None = None

    def __post_init__(self) -> None:
        if self.nominal_diameter_mm <= 0.0:
            raise ValueError("Nominal diameter must be positive.")

        if self.pitch_mm <= 0.0:
            raise ValueError("Thread pitch must be positive.")

        if self.starts < 1:
            raise ValueError("Thread start count must be at least one.")

        if not 0.0 < self.included_angle_deg < 180.0:
            raise ValueError("Thread included angle must lie between 0 and 180 degrees.")

        for name, value in (
            ("external tolerance class", self.external_tolerance_class),
            ("internal tolerance class", self.internal_tolerance_class),
        ):
            if value is not None and not value.strip():
                raise ValueError(f"{name} must not be blank when provided.")


@dataclass(frozen=True)
class BoltAxialSegmentInput:
    """One axial segment used in bolt-compliance calculations."""

    segment_id: str
    kind: BoltSegmentKind
    length_mm: float
    diameter_mm: float | None = None
    area_mm2: float | None = None
    material_id: str | None = None

    def __post_init__(self) -> None:
        if not self.segment_id.strip():
            raise ValueError("Bolt segment identity must not be blank.")

        if self.length_mm <= 0.0:
            raise ValueError("Bolt segment length must be positive.")

        if self.diameter_mm is not None and self.diameter_mm <= 0.0:
            raise ValueError("Bolt segment diameter must be positive when provided.")

        if self.area_mm2 is not None and self.area_mm2 <= 0.0:
            raise ValueError("Bolt segment area must be positive when provided.")

        if self.kind is BoltSegmentKind.UNTHREADED_SHANK and self.diameter_mm is None:
            raise ValueError("An unthreaded shank segment requires a diameter.")

        if self.kind is BoltSegmentKind.THREADED and self.area_mm2 is not None:
            raise ValueError(
                "A threaded segment derives its area from the thread "
                "definition and must not define a custom area."
            )

        if self.kind is BoltSegmentKind.CUSTOM_AREA and self.area_mm2 is None:
            raise ValueError("A custom-area bolt segment requires an area.")


@dataclass(frozen=True)
class MemberLayerInput:
    """One layer in an arbitrary clamped-member stack."""

    layer_id: str
    thickness_mm: float
    material_id: str
    clearance_hole_diameter_mm: float
    outer_diameter_mm: float

    def __post_init__(self) -> None:
        if not self.layer_id.strip():
            raise ValueError("Member-layer identity must not be blank.")

        if not self.material_id.strip():
            raise ValueError("Member material identity must not be blank.")

        if self.thickness_mm <= 0.0:
            raise ValueError("Member thickness must be positive.")

        if self.clearance_hole_diameter_mm <= 0.0:
            raise ValueError("Member clearance-hole diameter must be positive.")

        if self.outer_diameter_mm <= self.clearance_hole_diameter_mm:
            raise ValueError("Member outer diameter must exceed its hole diameter.")


@dataclass(frozen=True)
class LoadingInput:
    """Preload and external axial-loading definition."""

    preload_n: float
    external_axial_load_n: float = 0.0
    cyclic_minimum_axial_load_n: float | None = None
    cyclic_maximum_axial_load_n: float | None = None
    preload_scatter_fraction: float = 0.0

    def __post_init__(self) -> None:
        if self.preload_n < 0.0:
            raise ValueError("Preload must not be negative.")

        if self.external_axial_load_n < 0.0:
            raise ValueError("External separating axial load must not be negative.")

        if not 0.0 <= self.preload_scatter_fraction < 1.0:
            raise ValueError("Preload scatter fraction must lie in [0, 1).")

        cyclic_values = (
            self.cyclic_minimum_axial_load_n,
            self.cyclic_maximum_axial_load_n,
        )

        if any(value is not None for value in cyclic_values):
            if any(value is None for value in cyclic_values):
                raise ValueError("Both cyclic minimum and maximum loads are required.")

            minimum = self.cyclic_minimum_axial_load_n
            maximum = self.cyclic_maximum_axial_load_n

            if minimum is None or maximum is None:
                raise AssertionError("Cyclic load validation is inconsistent.")

            if minimum < 0.0 or maximum < 0.0:
                raise ValueError("Cyclic axial loads must not be negative.")

            if maximum < minimum:
                raise ValueError("Cyclic maximum load must not be below the minimum.")

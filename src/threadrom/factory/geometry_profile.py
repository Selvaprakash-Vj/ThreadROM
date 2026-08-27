"""Governed geometry-definition profiles for the ThreadROM factory."""

from __future__ import annotations

from dataclasses import dataclass

from threadrom.geometry.geometry_quality import (
    GeometryQualityPolicy,
)


@dataclass(frozen=True)
class GeometryDefinitionProfile:
    """CAD-policy assumptions used to build geometry definitions."""

    profile_id: str
    source_reference: str

    external_thread_overshoot_pitches: float
    external_thread_radial_clearance_mm: float
    external_thread_use_frenet_frame: bool
    internal_thread_use_frenet_frame: bool

    nut_bore_basis: str
    nut_chamfer_included: bool

    mating_clearance_mm: float
    mating_phase_offset_deg: float

    quality_policy: GeometryQualityPolicy

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError(
                "Geometry profile identity must not be blank."
            )

        if not self.source_reference.strip():
            raise ValueError(
                "Geometry profile source reference must not be blank."
            )

        if self.external_thread_overshoot_pitches < 0.0:
            raise ValueError(
                "External-thread overshoot cannot be negative."
            )

        if self.external_thread_radial_clearance_mm < 0.0:
            raise ValueError(
                "External-thread radial clearance cannot be negative."
            )

        if not self.nut_bore_basis.strip():
            raise ValueError(
                "Nut bore basis must not be blank."
            )

        if self.mating_clearance_mm < 0.0:
            raise ValueError(
                "Mating clearance cannot be negative."
            )

        if not -180.0 <= self.mating_phase_offset_deg <= 180.0:
            raise ValueError(
                "Mating phase offset must lie within "
                "[-180, 180] degrees."
            )


CERTIFIED_PHASE2_GEOMETRY_PROFILE = GeometryDefinitionProfile(
    profile_id="phase2_certified_complete_joint_v1",
    source_reference=(
        "config/external_thread_geometry.toml; "
        "config/internal_thread_geometry.toml; "
        "config/nut_geometry.toml; "
        "config/geometry_quality.toml; "
        "scripts/generate_complete_joint_assembly.py"
    ),
    external_thread_overshoot_pitches=1.0,
    external_thread_radial_clearance_mm=0.05,
    external_thread_use_frenet_frame=True,
    internal_thread_use_frenet_frame=True,
    nut_bore_basis="basic_internal_minor_diameter",
    nut_chamfer_included=False,
    mating_clearance_mm=0.0,
    mating_phase_offset_deg=0.0,
    quality_policy=GeometryQualityPolicy(
        policy_id="phase2-certified-geometry-quality-v1",
        boolean_tolerance_mm=0.000001,
        thread_boolean_overlap_mm=0.03,
        fusion_bridge_half_height_mm=0.02,
        fusion_bridge_radius_fraction=0.75,
        cad_envelope_tolerance_mm=0.001,
        step_bounds_tolerance_mm=0.002,
        step_volume_relative_tolerance=0.000001,
    ),
)

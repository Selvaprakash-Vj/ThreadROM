"""Governed analytical-definition profiles for the ThreadROM factory."""

from __future__ import annotations

from dataclasses import dataclass

from threadrom.engineering.analytical_joint_input import (
    BoltComplianceMethod,
    ExternalLoadMethod,
    MemberCompressionMethod,
    ThreadLoadDistributionMethod,
)


@dataclass(frozen=True)
class AnalyticalDefinitionProfile:
    """Backend-specific assumptions used to build analytical definitions."""

    profile_id: str
    source_reference: str

    included_angle_deg: float
    external_tolerance_class: str
    internal_tolerance_class: str

    bolt_compliance: BoltComplianceMethod
    member_compression: MemberCompressionMethod
    external_load: ExternalLoadMethod
    thread_load_distribution: ThreadLoadDistributionMethod

    head_participation_factor: float
    nut_participation_factor: float
    load_introduction_factor: float
    compression_cone_half_angle_deg: float

    def __post_init__(self) -> None:
        if not self.profile_id.strip():
            raise ValueError(
                "Analytical profile identity must not be blank."
            )

        if not self.source_reference.strip():
            raise ValueError(
                "Analytical profile source reference must not be blank."
            )

        if not 0.0 < self.included_angle_deg < 180.0:
            raise ValueError(
                "Thread included angle must lie between 0 and 180 degrees."
            )

        if not self.external_tolerance_class.strip():
            raise ValueError(
                "External thread tolerance class must not be blank."
            )

        if not self.internal_tolerance_class.strip():
            raise ValueError(
                "Internal thread tolerance class must not be blank."
            )

        if self.head_participation_factor < 0.0:
            raise ValueError(
                "Head participation factor must not be negative."
            )

        if self.nut_participation_factor < 0.0:
            raise ValueError(
                "Nut participation factor must not be negative."
            )

        if not 0.0 <= self.load_introduction_factor <= 1.0:
            raise ValueError(
                "Load-introduction factor must lie in [0, 1]."
            )

        if not 0.0 < self.compression_cone_half_angle_deg < 90.0:
            raise ValueError(
                "Compression-cone half-angle must lie "
                "strictly between 0 and 90 degrees."
            )


CERTIFIED_PHASE2_ANALYTICAL_PROFILE = AnalyticalDefinitionProfile(
    profile_id="phase2_certified_m10_v1",
    source_reference=(
        "config/analytical_m10_20kn.toml [thread] [methods]"
    ),
    included_angle_deg=60.0,
    external_tolerance_class="6g",
    internal_tolerance_class="6H",
    bolt_compliance=BoltComplianceMethod.SEGMENTED,
    member_compression=(
        MemberCompressionMethod.UNIFORM_ANNULAR_CYLINDER
    ),
    external_load=ExternalLoadMethod.BASIC_SPRING_RATIO,
    thread_load_distribution=(
        ThreadLoadDistributionMethod.DISCRETE_SPRING
    ),
    head_participation_factor=0.5,
    nut_participation_factor=0.5,
    load_introduction_factor=1.0,
    compression_cone_half_angle_deg=30.0,
)

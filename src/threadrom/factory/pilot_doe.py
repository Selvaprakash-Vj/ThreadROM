"""Governed Phase-3 CP7 Pilot DOE definition."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from threadrom.case.contract import ThreadROMCase
from threadrom.case.reference_cases import (
    phase2_certification_case,
)
from threadrom.case.serialization import case_sha256


class PilotDoeCaseId(StrEnum):
    """Stable identities of the CP7 pilot cases."""

    BASELINE_CONTROL = "P00_BASELINE_CONTROL"
    PRELOAD_LOW = "P01_PRELOAD_LOW"
    PRELOAD_HIGH = "P02_PRELOAD_HIGH"
    ASYMMETRIC_GRIP = "P03_ASYMMETRIC_GRIP"
    RADIAL_GEOMETRY = "P04_RADIAL_GEOMETRY"


class PilotDoeCapability(StrEnum):
    """Primary factory capability exercised by one pilot case."""

    GENERIC_REFERENCE_PATH = "generic_reference_path"
    PRELOAD_VARIATION = "preload_variation"
    MEMBER_STACK_ASYMMETRY = "member_stack_asymmetry"
    RADIAL_MEMBER_GEOMETRY = "radial_member_geometry"


@dataclass(frozen=True, slots=True)
class PilotDoeCase:
    """One deliberate CP7 pilot case and its engineering purpose."""

    case_id: PilotDoeCaseId
    capability: PilotDoeCapability
    purpose: str
    case: ThreadROMCase

    @property
    def case_hash(self) -> str:
        return case_sha256(self.case)


@dataclass(frozen=True, slots=True)
class PilotDoeCampaign:
    """Governed deterministic CP7 Pilot DOE campaign."""

    campaign_id: str
    cases: tuple[PilotDoeCase, ...]

    def __post_init__(self) -> None:
        if not self.campaign_id.strip():
            raise ValueError(
                "Pilot DOE campaign_id must not be blank."
            )

        if not self.cases:
            raise ValueError(
                "Pilot DOE campaign must contain cases."
            )

        case_ids = tuple(
            case.case_id
            for case in self.cases
        )

        if len(set(case_ids)) != len(case_ids):
            raise ValueError(
                "Pilot DOE case identities must be unique."
            )

        hashes = tuple(
            case.case_hash
            for case in self.cases
        )

        if len(set(hashes)) != len(hashes):
            raise ValueError(
                "Pilot DOE cases must have unique canonical hashes."
            )


def build_phase3_cp7_pilot_doe() -> PilotDoeCampaign:
    """Build the fixed five-case CP7 pilot campaign.

    This is intentionally a diagnostic pilot rather than a production
    design of experiments. Each case isolates one supported factory
    capability while retaining the currently governed complete-joint
    backend constraints.
    """

    baseline = phase2_certification_case()

    upper, lower = baseline.members.layers

    cases = (
        PilotDoeCase(
            case_id=PilotDoeCaseId.BASELINE_CONTROL,
            capability=(
                PilotDoeCapability.GENERIC_REFERENCE_PATH
            ),
            purpose=(
                "Run the certified physical input through the generic "
                "non-oracle FEM factory path."
            ),
            case=baseline,
        ),
        PilotDoeCase(
            case_id=PilotDoeCaseId.PRELOAD_LOW,
            capability=(
                PilotDoeCapability.PRELOAD_VARIATION
            ),
            purpose=(
                "Exercise lower case-specific preload calibration "
                "at 15 kN."
            ),
            case=replace(
                baseline,
                loading=replace(
                    baseline.loading,
                    target_preload_n=15_000.0,
                ),
            ),
        ),
        PilotDoeCase(
            case_id=PilotDoeCaseId.PRELOAD_HIGH,
            capability=(
                PilotDoeCapability.PRELOAD_VARIATION
            ),
            purpose=(
                "Exercise higher case-specific preload calibration "
                "at 25 kN."
            ),
            case=replace(
                baseline,
                loading=replace(
                    baseline.loading,
                    target_preload_n=25_000.0,
                ),
            ),
        ),
        PilotDoeCase(
            case_id=PilotDoeCaseId.ASYMMETRIC_GRIP,
            capability=(
                PilotDoeCapability.MEMBER_STACK_ASYMMETRY
            ),
            purpose=(
                "Exercise asymmetric 8/12 mm member geometry while "
                "holding total grip at 20 mm."
            ),
            case=replace(
                baseline,
                members=replace(
                    baseline.members,
                    layers=(
                        replace(
                            upper,
                            thickness_mm=8.0,
                        ),
                        replace(
                            lower,
                            thickness_mm=12.0,
                        ),
                    ),
                ),
            ),
        ),
        PilotDoeCase(
            case_id=PilotDoeCaseId.RADIAL_GEOMETRY,
            capability=(
                PilotDoeCapability.RADIAL_MEMBER_GEOMETRY
            ),
            purpose=(
                "Exercise 36 mm member OD and 12 mm clearance-hole "
                "geometry through analytical and FEM preparation."
            ),
            case=replace(
                baseline,
                members=replace(
                    baseline.members,
                    layers=(
                        replace(
                            upper,
                            outer_diameter_mm=36.0,
                            clearance_hole_diameter_mm=12.0,
                        ),
                        replace(
                            lower,
                            outer_diameter_mm=36.0,
                            clearance_hole_diameter_mm=12.0,
                        ),
                    ),
                ),
            ),
        ),
    )

    return PilotDoeCampaign(
        campaign_id="phase3_cp7_pilot_v1",
        cases=cases,
    )

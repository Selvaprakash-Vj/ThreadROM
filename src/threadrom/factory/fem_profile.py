"""Governed FEM reproduction policy for the certified Phase-2 baseline."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from enum import StrEnum


_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class FemPreloadActuator(StrEnum):
    """Supported numerical preload actuators."""

    BOLT_ONLY_THERMAL_EIGENSTRAIN = (
        "bolt_only_thermal_eigenstrain"
    )


@dataclass(frozen=True, slots=True)
class FemStaticStepPolicy:
    """Governed nonlinear static-step controls."""

    nonlinear_geometry: bool
    maximum_increments: int
    initial_increment: float
    total_time: float
    minimum_increment: float
    maximum_increment: float

    def __post_init__(self) -> None:
        values = (
            self.initial_increment,
            self.total_time,
            self.minimum_increment,
            self.maximum_increment,
        )
        if self.maximum_increments <= 0:
            raise ValueError(
                "maximum_increments must be positive."
            )
        if any(
            not math.isfinite(value) or value <= 0.0
            for value in values
        ):
            raise ValueError(
                "Static-step values must be finite and positive."
            )
        if self.minimum_increment > self.maximum_increment:
            raise ValueError(
                "minimum_increment cannot exceed maximum_increment."
            )


@dataclass(frozen=True, slots=True)
class FemDistributedGuidancePolicy:
    """Governed distributed rigid-mode guidance controls."""

    translation_sample_node_count: int
    rotation_sample_node_count: int
    bolt_head_max_radius_mm: float
    nut_min_radius_mm: float
    nut_max_radius_mm: float

    def __post_init__(self) -> None:
        if self.translation_sample_node_count <= 0:
            raise ValueError(
                "translation_sample_node_count must be positive."
            )

        if self.rotation_sample_node_count <= 0:
            raise ValueError(
                "rotation_sample_node_count must be positive."
            )

        for name, value in (
            (
                "bolt_head_max_radius_mm",
                self.bolt_head_max_radius_mm,
            ),
            (
                "nut_min_radius_mm",
                self.nut_min_radius_mm,
            ),
            (
                "nut_max_radius_mm",
                self.nut_max_radius_mm,
            ),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(
                    f"{name} must be finite and positive."
                )

        if self.nut_min_radius_mm >= self.nut_max_radius_mm:
            raise ValueError(
                "nut_min_radius_mm must be smaller than "
                "nut_max_radius_mm."
            )


@dataclass(frozen=True, slots=True)
class FemBackendPolicy:
    """Reusable certified CalculiX methodology.

    Case-specific physical inputs such as preload magnitude,
    friction coefficient, material constants and calibrated thermal
    actuator temperature deliberately do not live here.
    """

    policy_id: str
    solver_name: str
    solver_version: str
    element_type: str
    mesh_level: str
    preload_actuator: FemPreloadActuator

    step: FemStaticStepPolicy

    contact_type: str
    pressure_overclosure: str
    normal_stiffness_scale_per_mm: float
    friction_stick_slope_ratio: float
    required_contact_pairs: tuple[str, ...]

    boundary_region_mode: str
    guidance_mode: str
    guidance_policy: FemDistributedGuidancePolicy

    require_case_specific_preload_calibration: bool
    forbid_native_pretension_section: bool
    forbid_direct_preload_cload: bool
    forbid_manual_node_ids: bool
    forbid_manual_element_ids: bool

    # Optional long-running solver policy. None intentionally means
    # inherit the transfer/smoke execution timeout.
    solver_timeout_seconds: int | None = None

    def __post_init__(self) -> None:
        if (
            self.solver_timeout_seconds is not None
            and self.solver_timeout_seconds <= 0
        ):
            raise ValueError(
                "solver_timeout_seconds must be positive when specified."
            )

        if not self.policy_id.strip():
            raise ValueError("policy_id must not be blank.")
        if self.normal_stiffness_scale_per_mm <= 0.0:
            raise ValueError(
                "normal_stiffness_scale_per_mm must be positive."
            )
        if not 0.0 < self.friction_stick_slope_ratio <= 1.0:
            raise ValueError(
                "friction_stick_slope_ratio must be in (0, 1]."
            )
        if len(set(self.required_contact_pairs)) != len(
            self.required_contact_pairs
        ):
            raise ValueError(
                "required_contact_pairs must be unique."
            )


@dataclass(frozen=True, slots=True)
class FemCertificationOracle:
    """Immutable identity of the certified Phase-2 reference."""

    run_id: str
    case_hash: str
    preload_config_sha256: str
    analytical_config_sha256: str
    solver_deck_sha256: str
    certification_document: str

    def __post_init__(self) -> None:
        for name, value in (
            ("case_hash", self.case_hash),
            (
                "preload_config_sha256",
                self.preload_config_sha256,
            ),
            (
                "analytical_config_sha256",
                self.analytical_config_sha256,
            ),
            ("solver_deck_sha256", self.solver_deck_sha256),
        ):
            if _SHA256_PATTERN.fullmatch(value) is None:
                raise ValueError(
                    f"{name} must be a lowercase SHA256 digest."
                )


@dataclass(frozen=True, slots=True)
class FemReproductionProfile:
    """Certified backend policy plus immutable reproduction oracle."""

    backend: FemBackendPolicy
    oracle: FemCertificationOracle


PHASE2_CERTIFIED_FEM_PROFILE = FemReproductionProfile(
    backend=FemBackendPolicy(
        policy_id="phase2_complete_joint_c3d4_v1",
        solver_name="calculix",
        solver_version="2.23.0",
        element_type="C3D4",
        mesh_level="medium",
        preload_actuator=(
            FemPreloadActuator.BOLT_ONLY_THERMAL_EIGENSTRAIN
        ),
        step=FemStaticStepPolicy(
            nonlinear_geometry=True,
            maximum_increments=100,
            initial_increment=0.05,
            total_time=1.0,
            minimum_increment=1.0e-6,
            maximum_increment=0.05,
        ),
        contact_type="SURFACE TO SURFACE",
        pressure_overclosure="LINEAR",
        normal_stiffness_scale_per_mm=10.0,
        friction_stick_slope_ratio=0.01,
        required_contact_pairs=(
            "thread",
            "under_head",
            "nut_bearing",
            "member_interface",
        ),
        boundary_region_mode="derived_outer_annular_bands",
        guidance_mode="distributed_rigid_mode_guidance",
        guidance_policy=FemDistributedGuidancePolicy(
            translation_sample_node_count=40,
            rotation_sample_node_count=20,
            bolt_head_max_radius_mm=7.5,
            nut_min_radius_mm=5.5,
            nut_max_radius_mm=8.0,
        ),
        require_case_specific_preload_calibration=True,
        forbid_native_pretension_section=True,
        forbid_direct_preload_cload=True,
        forbid_manual_node_ids=True,
        forbid_manual_element_ids=True,
        # Certified nonlinear reproduction is an ~8 h-class solve.
        # Use 2x runtime headroom while keeping a finite ceiling.
        solver_timeout_seconds=57_600,
    ),
    oracle=FemCertificationOracle(
        run_id="trm_sim_000004_run_a2_thermal_20kn",
        case_hash=(
            "ee7b1a1ae89d99794ab20b390cdc1d35"
            "2645ae2e6dcf529ab69a14636ba20ca2"
        ),
        preload_config_sha256=(
            "2e5af364e52552ee3b683414842d8ee2"
            "a50d5bdb111a9e7dea2cc00037115da9"
        ),
        analytical_config_sha256=(
            "7bca8ebfd27df82dda9d9e5a98aca1e"
            "65446e436049e7fb91610b3b27dd8d28a"
        ),
        solver_deck_sha256=(
            "dcf571506a46679f2eab2f7c5e2e3a85"
            "af861544ddf56d84d60466c8dd90c634"
        ),
        certification_document=(
            "docs/verification/"
            "PHASE_2_FINAL_20KN_CERTIFICATION.md"
        ),
    ),
)

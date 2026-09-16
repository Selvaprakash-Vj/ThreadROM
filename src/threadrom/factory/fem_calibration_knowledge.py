"""FEM-informed preload warm-start knowledge for Phase 3."""

from __future__ import annotations

import json
import math
import tomllib

from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from threadrom.case.resolver import ResolvedCase
from threadrom.factory.preload_calibration_seed import (
    ThermalPreloadCalibrationSeed,
    ThermalPreloadCalibrationSeedV2,
)


LEGACY_UNVERSIONED_GEOMETRY_GENERATION_ID = (
    "legacy_unversioned"
)

LEGACY_SINGLE_STEP_EXECUTION_GENERATION_ID = (
    "legacy_single_step_unversioned"
)


@dataclass(frozen=True, slots=True)
class FemGeometryRealizationIdentity:
    """Governed CAD-realization boundary for reusable FEM evidence."""

    generation_id: str
    realization_id: str

    def __post_init__(self) -> None:
        if not self.generation_id.strip():
            raise ValueError(
                "FEM geometry generation_id must not be blank."
            )

        if not self.realization_id.strip():
            raise ValueError(
                "FEM geometry realization_id must not be blank."
            )


def build_legacy_fem_geometry_identity(
    *,
    mesh_sha256: str,
) -> FemGeometryRealizationIdentity:
    """Bind legacy FEM evidence to its immutable certified mesh."""

    if (
        len(mesh_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in mesh_sha256
        )
    ):
        raise ValueError(
            "Legacy FEM mesh_sha256 must be exactly "
            "64 lowercase hexadecimal characters."
        )

    return FemGeometryRealizationIdentity(
        generation_id=(
            LEGACY_UNVERSIONED_GEOMETRY_GENERATION_ID
        ),
        realization_id=(
            f"legacy_mesh_sha256:{mesh_sha256}"
        ),
    )


@dataclass(frozen=True, slots=True)
class FemCalibrationCompatibilityKey:
    """Categorical boundary for safe FEM-knowledge reuse."""

    bolt_standard: str
    thread_designation: str
    bolt_material_id: str
    bolt_property_class: str
    nut_standard: str
    nut_material_id: str
    nut_property_class: str
    handedness: str
    starts: int
    member_material_ids: tuple[str, ...]
    geometry_generation_id: str
    execution_generation_id: str


@dataclass(frozen=True, slots=True)
class FemCalibrationFeatureVector:
    """Dimensionless/naturally scalable FEM warm-start features."""

    compatibility: FemCalibrationCompatibilityKey

    target_preload_n: float
    analytical_delta_temperature_abs_c: float

    bolt_length_mm: float
    total_grip_length_mm: float

    upper_grip_fraction: float
    engagement_to_pitch: float
    protrusion_to_pitch: float
    clearance_to_outer_diameter: float
    outer_diameter_to_bolt_length: float

    external_axial_to_preload: float

    thread_friction: float
    head_bearing_friction: float
    nut_bearing_friction: float
    member_interface_friction: float


@dataclass(frozen=True, slots=True)
class FemCalibrationKnowledgeRecord:
    """One accepted FEM calibration retained as reusable evidence."""

    case_hash: str
    resolution_hash: str
    geometry_identity: FemGeometryRealizationIdentity
    execution_generation_id: str
    accepted_run_id: str
    feature: FemCalibrationFeatureVector

    analytical_delta_temperature_c: float
    accepted_delta_temperature_c: float

    target_force_n: float
    measured_mean_clamp_force_n: float

    @property
    def correction_factor(self) -> float:
        return (
            self.accepted_delta_temperature_c
            / self.analytical_delta_temperature_c
        )


@dataclass(frozen=True, slots=True)
class FemWarmStartPolicy:
    policy_id: str
    maximum_neighbors: int
    maximum_reuse_distance: float
    inverse_distance_power: float
    exact_distance_tolerance: float
    minimum_correction_factor: float
    maximum_correction_factor: float

    minimum_neighbors_for_reuse: int = 2
    require_target_preload_bracketing: bool = True
    maximum_correction_factor_relative_spread: float = 0.20


class FemWarmStartSource(Enum):
    EXACT_CASE = "exact_case"
    FEM_NEIGHBORS = "fem_neighbors"
    ANALYTICAL_FALLBACK = "analytical_fallback"


class FemWarmStartApplicability(Enum):
    """Governed reason for reuse or analytical fallback."""

    EXACT_CASE = "exact_case"
    INTERPOLATION = "interpolation"
    NO_LOCAL_EVIDENCE = "no_local_evidence"
    INSUFFICIENT_NEIGHBORS = "insufficient_neighbors"
    PRELOAD_EXTRAPOLATION = "preload_extrapolation"
    CORRECTION_FACTOR_DISAGREEMENT = (
        "correction_factor_disagreement"
    )


@dataclass(frozen=True, slots=True)
class FemWarmStartPrediction:
    policy_id: str
    source: FemWarmStartSource

    analytical_delta_temperature_c: float
    predicted_delta_temperature_c: float
    correction_factor: float

    reused_evidence_count: int
    neighbor_case_hashes: tuple[str, ...]
    nearest_distance: float | None

    applicability: FemWarmStartApplicability = (
        FemWarmStartApplicability.NO_LOCAL_EVIDENCE
    )


def _require_positive(
    name: str,
    value: float,
) -> float:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(
            f"{name} must be finite and positive."
        )

    return value


def _require_friction(
    name: str,
    value: float,
) -> float:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(
            f"{name} must be finite and non-negative."
        )

    return value


def build_fem_calibration_feature_vector(
    resolved: ResolvedCase,
    seed: ThermalPreloadCalibrationSeed,
    geometry_identity: FemGeometryRealizationIdentity,
    execution_generation_id: str,
) -> FemCalibrationFeatureVector:
    """Build governed similarity features from one resolved case."""

    if not execution_generation_id.strip():
        raise ValueError(
            "FEM execution generation ID must not be blank."
        )

    source = resolved.source_case
    assembly = resolved.assembly

    layers = source.members.layers

    if len(layers) != 2:
        raise ValueError(
            "Current FEM warm-start policy requires two member layers."
        )

    upper, lower = layers

    total_grip = _require_positive(
        "total_grip_length_mm",
        assembly.total_grip_length_mm,
    )

    bolt_length = _require_positive(
        "bolt_length_mm",
        assembly.bolt_length_mm,
    )

    pitch = _require_positive(
        "pitch_mm",
        assembly.pitch_mm,
    )

    outer = _require_positive(
        "outer_diameter_mm",
        assembly.outer_diameter_mm,
    )

    preload = _require_positive(
        "target_preload_n",
        source.loading.target_preload_n,
    )

    analytical_abs = abs(
        seed.predicted_delta_temperature_c
    )

    _require_positive(
        "analytical_delta_temperature_abs_c",
        analytical_abs,
    )

    if not math.isclose(
        upper.thickness_mm + lower.thickness_mm,
        total_grip,
        rel_tol=0.0,
        abs_tol=1.0e-9,
    ):
        raise ValueError(
            "Member-layer thicknesses do not match resolved total grip."
        )

    return FemCalibrationFeatureVector(
        compatibility=FemCalibrationCompatibilityKey(
            bolt_standard=source.fastener.bolt_standard,
            thread_designation=(
                source.fastener.thread_designation
            ),
            bolt_material_id=(
                source.fastener.bolt_material_id
            ),
            bolt_property_class=(
                source.fastener.bolt_property_class
            ),
            nut_standard=source.fastener.nut_standard,
            nut_material_id=(
                source.fastener.nut_material_id
            ),
            nut_property_class=(
                source.fastener.nut_property_class
            ),
            handedness=(
                source.fastener.handedness.value
            ),
            starts=source.fastener.starts,
            member_material_ids=tuple(
                layer.material_id
                for layer in layers
            ),
            geometry_generation_id=(
                geometry_identity.generation_id
            ),
            execution_generation_id=(
                execution_generation_id
            ),
        ),
        target_preload_n=preload,
        analytical_delta_temperature_abs_c=analytical_abs,
        bolt_length_mm=bolt_length,
        total_grip_length_mm=total_grip,
        upper_grip_fraction=(
            upper.thickness_mm / total_grip
        ),
        engagement_to_pitch=(
            assembly.thread_engagement_length_mm
            / pitch
        ),
        protrusion_to_pitch=(
            assembly.protrusion_length_mm
            / pitch
        ),
        clearance_to_outer_diameter=(
            assembly.clearance_hole_diameter_mm
            / outer
        ),
        outer_diameter_to_bolt_length=(
            outer / bolt_length
        ),
        external_axial_to_preload=(
            source.loading.external_axial_load_n
            / preload
        ),
        thread_friction=_require_friction(
            "thread_friction",
            source.interfaces.thread_friction_coefficient,
        ),
        head_bearing_friction=_require_friction(
            "head_bearing_friction",
            source.interfaces.head_bearing_friction_coefficient,
        ),
        nut_bearing_friction=_require_friction(
            "nut_bearing_friction",
            source.interfaces.nut_bearing_friction_coefficient,
        ),
        member_interface_friction=_require_friction(
            "member_interface_friction",
            source.interfaces.member_interface_friction_coefficient,
        ),
    )


def _log_ratio(
    left: float,
    right: float,
) -> float:
    return math.log(
        _require_positive("left distance value", left)
        / _require_positive("right distance value", right)
    )


def fem_calibration_feature_distance(
    left: FemCalibrationFeatureVector,
    right: FemCalibrationFeatureVector,
) -> float | None:
    """Return dimensionless feature distance or None if incompatible."""

    if left.compatibility != right.compatibility:
        return None

    terms = (
        _log_ratio(
            left.target_preload_n,
            right.target_preload_n,
        ),
        _log_ratio(
            left.analytical_delta_temperature_abs_c,
            right.analytical_delta_temperature_abs_c,
        ),
        _log_ratio(
            left.bolt_length_mm,
            right.bolt_length_mm,
        ),
        _log_ratio(
            left.total_grip_length_mm,
            right.total_grip_length_mm,
        ),
        (
            left.upper_grip_fraction
            - right.upper_grip_fraction
        ),
        _log_ratio(
            left.engagement_to_pitch,
            right.engagement_to_pitch,
        ),
        (
            left.protrusion_to_pitch
            - right.protrusion_to_pitch
        ),
        (
            left.clearance_to_outer_diameter
            - right.clearance_to_outer_diameter
        ),
        _log_ratio(
            left.outer_diameter_to_bolt_length,
            right.outer_diameter_to_bolt_length,
        ),
        (
            left.external_axial_to_preload
            - right.external_axial_to_preload
        ),
        left.thread_friction - right.thread_friction,
        (
            left.head_bearing_friction
            - right.head_bearing_friction
        ),
        (
            left.nut_bearing_friction
            - right.nut_bearing_friction
        ),
        (
            left.member_interface_friction
            - right.member_interface_friction
        ),
    )

    return math.sqrt(
        sum(value * value for value in terms)
    )


def load_fem_warm_start_policy(
    path: Path,
) -> FemWarmStartPolicy:
    """Load the governed FEM warm-start policy."""

    with path.open("rb") as stream:
        data = tomllib.load(stream)

    identity = data["identity"]
    neighbors = data["neighbors"]
    correction = data["correction"]
    applicability = data["applicability"]

    policy = FemWarmStartPolicy(
        policy_id=str(identity["policy_id"]),
        maximum_neighbors=int(
            neighbors["maximum_neighbors"]
        ),
        maximum_reuse_distance=float(
            neighbors["maximum_reuse_distance"]
        ),
        inverse_distance_power=float(
            neighbors["inverse_distance_power"]
        ),
        exact_distance_tolerance=float(
            neighbors["exact_distance_tolerance"]
        ),
        minimum_correction_factor=float(
            correction["minimum_factor"]
        ),
        maximum_correction_factor=float(
            correction["maximum_factor"]
        ),
        minimum_neighbors_for_reuse=int(
            applicability[
                "minimum_neighbors_for_reuse"
            ]
        ),
        require_target_preload_bracketing=bool(
            applicability[
                "require_target_preload_bracketing"
            ]
        ),
        maximum_correction_factor_relative_spread=float(
            applicability[
                "maximum_correction_factor_relative_spread"
            ]
        ),
    )

    if not policy.policy_id.strip():
        raise ValueError(
            "Warm-start policy_id must not be blank."
        )

    if policy.maximum_neighbors <= 0:
        raise ValueError(
            "maximum_neighbors must be positive."
        )

    if (
        policy.minimum_neighbors_for_reuse <= 0
        or policy.minimum_neighbors_for_reuse
        > policy.maximum_neighbors
    ):
        raise ValueError(
            "minimum_neighbors_for_reuse must be positive "
            "and no greater than maximum_neighbors."
        )

    for name, value in (
        (
            "maximum_reuse_distance",
            policy.maximum_reuse_distance,
        ),
        (
            "inverse_distance_power",
            policy.inverse_distance_power,
        ),
        (
            "exact_distance_tolerance",
            policy.exact_distance_tolerance,
        ),
        (
            "minimum_correction_factor",
            policy.minimum_correction_factor,
        ),
        (
            "maximum_correction_factor",
            policy.maximum_correction_factor,
        ),
        (
            "maximum_correction_factor_relative_spread",
            policy.maximum_correction_factor_relative_spread,
        ),
    ):
        _require_positive(name, value)

    if (
        policy.minimum_correction_factor
        >= policy.maximum_correction_factor
    ):
        raise ValueError(
            "Warm-start correction-factor bounds are invalid."
        )

    return policy


def build_fem_calibration_knowledge_record(
    *,
    resolved: ResolvedCase,
    seed: ThermalPreloadCalibrationSeed,
    geometry_identity: FemGeometryRealizationIdentity,
    execution_generation_id: str,
    accepted_run_id: str,
    accepted_delta_temperature_c: float,
    measured_mean_clamp_force_n: float,
) -> FemCalibrationKnowledgeRecord:
    """Create one reusable record from accepted FEM evidence."""

    if not execution_generation_id.strip():
        raise ValueError(
            "FEM execution generation ID must not be blank."
        )

    if not accepted_run_id.strip():
        raise ValueError(
            "Accepted FEM run ID must not be blank."
        )

    if (
        not math.isfinite(seed.predicted_delta_temperature_c)
        or seed.predicted_delta_temperature_c >= 0.0
    ):
        raise ValueError(
            "Analytical FEM preload seed must be thermal contraction."
        )

    if (
        not math.isfinite(accepted_delta_temperature_c)
        or accepted_delta_temperature_c >= 0.0
    ):
        raise ValueError(
            "Accepted FEM calibration must be thermal contraction."
        )

    _require_positive(
        "measured_mean_clamp_force_n",
        measured_mean_clamp_force_n,
    )

    record = FemCalibrationKnowledgeRecord(
        case_hash=resolved.case_hash,
        resolution_hash=resolved.resolution_hash,
        geometry_identity=geometry_identity,
        execution_generation_id=execution_generation_id,
        accepted_run_id=accepted_run_id,
        feature=build_fem_calibration_feature_vector(
            resolved,
            seed,
            geometry_identity,
            execution_generation_id,
        ),
        analytical_delta_temperature_c=(
            seed.predicted_delta_temperature_c
        ),
        accepted_delta_temperature_c=(
            accepted_delta_temperature_c
        ),
        target_force_n=seed.target_force_n,
        measured_mean_clamp_force_n=(
            measured_mean_clamp_force_n
        ),
    )

    _require_positive(
        "FEM correction factor",
        record.correction_factor,
    )

    return record


def predict_fem_warm_start(
    *,
    resolved: ResolvedCase,
    seed: ThermalPreloadCalibrationSeed,
    geometry_identity: FemGeometryRealizationIdentity,
    execution_generation_id: str,
    knowledge: tuple[
        FemCalibrationKnowledgeRecord,
        ...,
    ],
    policy: FemWarmStartPolicy,
) -> FemWarmStartPrediction:
    """Predict the first thermal FEM trial from accepted FEM history."""

    if not execution_generation_id.strip():
        raise ValueError(
            "FEM execution generation ID must not be blank."
        )

    target_feature = (
        build_fem_calibration_feature_vector(
            resolved,
            seed,
            geometry_identity,
            execution_generation_id,
        )
    )

    exact = tuple(
        record
        for record in knowledge
        if (
            record.case_hash == resolved.case_hash
            and record.resolution_hash == resolved.resolution_hash
            and record.geometry_identity == geometry_identity
            and record.execution_generation_id
            == execution_generation_id
        )
    )

    if len(exact) > 1:
        temperatures = {
            record.accepted_delta_temperature_c
            for record in exact
        }

        if len(temperatures) != 1:
            raise RuntimeError(
                "Conflicting exact-case FEM knowledge records exist."
            )

    if exact:
        record = exact[-1]

        return FemWarmStartPrediction(
            policy_id=policy.policy_id,
            source=FemWarmStartSource.EXACT_CASE,
            analytical_delta_temperature_c=(
                seed.predicted_delta_temperature_c
            ),
            predicted_delta_temperature_c=(
                record.accepted_delta_temperature_c
            ),
            correction_factor=(
                record.correction_factor
            ),
            reused_evidence_count=1,
            neighbor_case_hashes=(
                record.case_hash,
            ),
            nearest_distance=0.0,
            applicability=(
                FemWarmStartApplicability.EXACT_CASE
            ),
        )

    candidates: list[
        tuple[
            float,
            FemCalibrationKnowledgeRecord,
        ]
    ] = []

    for record in knowledge:
        distance = fem_calibration_feature_distance(
            target_feature,
            record.feature,
        )

        if distance is None:
            continue

        if (
            distance
            <= policy.maximum_reuse_distance
        ):
            candidates.append(
                (
                    distance,
                    record,
                )
            )

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1].case_hash,
            item[1].accepted_run_id,
        )
    )

    selected = tuple(
        candidates[
            : policy.maximum_neighbors
        ]
    )

    if not selected:
        return FemWarmStartPrediction(
            policy_id=policy.policy_id,
            source=(
                FemWarmStartSource.ANALYTICAL_FALLBACK
            ),
            analytical_delta_temperature_c=(
                seed.predicted_delta_temperature_c
            ),
            predicted_delta_temperature_c=(
                seed.predicted_delta_temperature_c
            ),
            correction_factor=1.0,
            reused_evidence_count=0,
            neighbor_case_hashes=(),
            nearest_distance=None,
            applicability=(
                FemWarmStartApplicability.NO_LOCAL_EVIDENCE
            ),
        )

    nearest_distance = selected[0][0]

    if (
        len(selected)
        < policy.minimum_neighbors_for_reuse
    ):
        return FemWarmStartPrediction(
            policy_id=policy.policy_id,
            source=FemWarmStartSource.ANALYTICAL_FALLBACK,
            analytical_delta_temperature_c=(
                seed.predicted_delta_temperature_c
            ),
            predicted_delta_temperature_c=(
                seed.predicted_delta_temperature_c
            ),
            correction_factor=1.0,
            reused_evidence_count=0,
            neighbor_case_hashes=(),
            nearest_distance=nearest_distance,
            applicability=(
                FemWarmStartApplicability.INSUFFICIENT_NEIGHBORS
            ),
        )

    if policy.require_target_preload_bracketing:
        preload_values = tuple(
            record.target_force_n
            for _, record in selected
        )

        preload_min = min(preload_values)
        preload_max = max(preload_values)

        target_preload = (
            target_feature.target_preload_n
        )

        if not (
            preload_min
            <= target_preload
            <= preload_max
        ):
            return FemWarmStartPrediction(
                policy_id=policy.policy_id,
                source=FemWarmStartSource.ANALYTICAL_FALLBACK,
                analytical_delta_temperature_c=(
                    seed.predicted_delta_temperature_c
                ),
                predicted_delta_temperature_c=(
                    seed.predicted_delta_temperature_c
                ),
                correction_factor=1.0,
                reused_evidence_count=0,
                neighbor_case_hashes=(),
                nearest_distance=nearest_distance,
                applicability=(
                    FemWarmStartApplicability.PRELOAD_EXTRAPOLATION
                ),
            )

    neighbor_factors = tuple(
        record.correction_factor
        for _, record in selected
    )

    factor_mean = (
        sum(neighbor_factors)
        / len(neighbor_factors)
    )

    factor_relative_spread = (
        max(neighbor_factors)
        - min(neighbor_factors)
    ) / factor_mean

    if (
        factor_relative_spread
        > policy.maximum_correction_factor_relative_spread
    ):
        return FemWarmStartPrediction(
            policy_id=policy.policy_id,
            source=FemWarmStartSource.ANALYTICAL_FALLBACK,
            analytical_delta_temperature_c=(
                seed.predicted_delta_temperature_c
            ),
            predicted_delta_temperature_c=(
                seed.predicted_delta_temperature_c
            ),
            correction_factor=1.0,
            reused_evidence_count=0,
            neighbor_case_hashes=(),
            nearest_distance=nearest_distance,
            applicability=(
                FemWarmStartApplicability.CORRECTION_FACTOR_DISAGREEMENT
            ),
        )

    tolerance = (
        policy.exact_distance_tolerance
    )

    zero_distance = tuple(
        item
        for item in selected
        if item[0] <= tolerance
    )

    if zero_distance:
        factors = tuple(
            record.correction_factor
            for _, record in zero_distance
        )

        correction_factor = (
            sum(factors) / len(factors)
        )
    else:
        weights = tuple(
            1.0
            / (
                distance
                ** policy.inverse_distance_power
            )
            for distance, _ in selected
        )

        weighted_factors = tuple(
            weight * record.correction_factor
            for weight, (_, record) in zip(
                weights,
                selected,
                strict=True,
            )
        )

        correction_factor = (
            sum(weighted_factors)
            / sum(weights)
        )

    correction_factor = min(
        policy.maximum_correction_factor,
        max(
            policy.minimum_correction_factor,
            correction_factor,
        ),
    )

    predicted = (
        seed.predicted_delta_temperature_c
        * correction_factor
    )

    return FemWarmStartPrediction(
        policy_id=policy.policy_id,
        source=FemWarmStartSource.FEM_NEIGHBORS,
        analytical_delta_temperature_c=(
            seed.predicted_delta_temperature_c
        ),
        predicted_delta_temperature_c=predicted,
        correction_factor=correction_factor,
        reused_evidence_count=len(selected),
        neighbor_case_hashes=tuple(
            record.case_hash
            for _, record in selected
        ),
        nearest_distance=selected[0][0],
        applicability=(
            FemWarmStartApplicability.INTERPOLATION
        ),
    )


def write_fem_calibration_knowledge(
    path: Path,
    records: tuple[
        FemCalibrationKnowledgeRecord,
        ...,
    ],
) -> None:
    """Persist accepted FEM calibration knowledge as deterministic JSON."""

    payload = {
        "schema_version": 2,
        "records": [
            asdict(record)
            for record in sorted(
                records,
                key=lambda item: (
                    item.case_hash,
                    item.accepted_run_id,
                ),
            )
        ],
    }

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

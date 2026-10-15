"""Trial-1 FEM preload predictor from governed calibration observations.

The predictor consumes the persistent solved-observation store introduced by
Pre-W03 Hardening Slice 2.

Safety contract:
- all valid solved observations may be retained in the store;
- same-case observations are collapsed to one case-level correction estimate;
- execution generation remains a strict compatibility boundary;
- geometry generation remains a strict compatibility boundary;
- fastener/material/contact categories remain strict;
- thread designation itself may vary, enabling interpolation across metric
  sizes when continuous geometry/load features are locally compatible;
- interpolation requires at least two neighbors and target-preload bracketing;
- disagreement or sparse evidence falls back to the analytical seed.
"""

from __future__ import annotations

import math
import re
import tomllib

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from threadrom.factory.fem_calibration_knowledge import (
    FemCalibrationFeatureVector,
)
from threadrom.factory.fem_calibration_observation_store import (
    FemCalibrationObservation,
)


class Trial1PredictionSource(str, Enum):
    EXACT_CASE = "exact_case"
    OBSERVATION_NEIGHBORS = "observation_neighbors"
    ANALYTICAL_FALLBACK = "analytical_fallback"


class Trial1PredictionApplicability(str, Enum):
    EXACT_CASE = "exact_case"
    INTERPOLATION = "interpolation"
    NO_COMPATIBLE_EVIDENCE = "no_compatible_evidence"
    INSUFFICIENT_NEIGHBORS = "insufficient_neighbors"
    PRELOAD_EXTRAPOLATION = "preload_extrapolation"
    CORRECTION_FACTOR_DISAGREEMENT = (
        "correction_factor_disagreement"
    )


@dataclass(frozen=True, slots=True)
class Trial1ObservationPredictorPolicy:
    policy_id: str
    maximum_neighbors: int
    maximum_distance: float
    inverse_distance_power: float
    minimum_neighbors_for_reuse: int
    require_target_preload_bracketing: bool
    maximum_correction_factor_relative_spread: float
    minimum_correction_factor: float
    maximum_correction_factor: float


@dataclass(frozen=True, slots=True)
class Trial1ObservationPrediction:
    policy_id: str
    source: Trial1PredictionSource
    applicability: Trial1PredictionApplicability

    analytical_delta_temperature_c: float
    predicted_delta_temperature_c: float
    correction_factor: float

    reused_case_count: int
    neighbor_case_ids: tuple[str, ...]
    neighbor_case_hashes: tuple[str, ...]
    nearest_distance: float | None


@dataclass(frozen=True, slots=True)
class _CaseEstimate:
    case_id: str
    case_hash: str
    resolution_hash: str
    feature: FemCalibrationFeatureVector
    correction_factor: float
    observation_count: int


def load_trial1_observation_predictor_policy(
    path: Path,
) -> Trial1ObservationPredictorPolicy:
    with path.open("rb") as stream:
        data = tomllib.load(stream)

    identity = data["identity"]
    neighbors = data["neighbors"]
    applicability = data["applicability"]
    correction = data["correction"]

    policy = Trial1ObservationPredictorPolicy(
        policy_id=str(
            identity["policy_id"]
        ),
        maximum_neighbors=int(
            neighbors["maximum_neighbors"]
        ),
        maximum_distance=float(
            neighbors["maximum_distance"]
        ),
        inverse_distance_power=float(
            neighbors["inverse_distance_power"]
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
        minimum_correction_factor=float(
            correction["minimum_factor"]
        ),
        maximum_correction_factor=float(
            correction["maximum_factor"]
        ),
    )

    if not policy.policy_id.strip():
        raise ValueError(
            "Trial-1 predictor policy_id must not be blank."
        )

    if (
        policy.maximum_neighbors <= 0
        or policy.minimum_neighbors_for_reuse <= 0
        or policy.minimum_neighbors_for_reuse
        > policy.maximum_neighbors
    ):
        raise ValueError(
            "Invalid Trial-1 predictor neighbor-count policy."
        )

    for name, value in (
        (
            "maximum_distance",
            policy.maximum_distance,
        ),
        (
            "inverse_distance_power",
            policy.inverse_distance_power,
        ),
        (
            "maximum_correction_factor_relative_spread",
            policy.maximum_correction_factor_relative_spread,
        ),
        (
            "minimum_correction_factor",
            policy.minimum_correction_factor,
        ),
        (
            "maximum_correction_factor",
            policy.maximum_correction_factor,
        ),
    ):
        if (
            not math.isfinite(value)
            or value <= 0.0
        ):
            raise ValueError(
                f"{name} must be finite and positive."
            )

    if (
        policy.minimum_correction_factor
        >= policy.maximum_correction_factor
    ):
        raise ValueError(
            "Invalid Trial-1 predictor correction-factor bounds."
        )

    return policy


def _metric_nominal_diameter(
    designation: str,
) -> float:
    match = re.fullmatch(
        r"M([0-9]+(?:\.[0-9]+)?)(?:x.+)?",
        designation,
        flags=re.IGNORECASE,
    )

    if match is None:
        raise ValueError(
            f"Unsupported metric thread designation: {designation!r}"
        )

    value = float(
        match.group(1)
    )

    if (
        not math.isfinite(value)
        or value <= 0.0
    ):
        raise ValueError(
            "Metric nominal diameter must be positive."
        )

    return value


def _strict_compatibility(
    target: FemCalibrationFeatureVector,
    evidence: FemCalibrationFeatureVector,
) -> bool:
    """Compatibility excluding only thread designation.

    Thread size is represented continuously in the distance metric. Everything
    that changes physics family or execution/model generation remains strict.
    """

    left = target.compatibility
    right = evidence.compatibility

    return (
        left.bolt_standard
        == right.bolt_standard
        and left.bolt_material_id
        == right.bolt_material_id
        and left.bolt_property_class
        == right.bolt_property_class
        and left.nut_standard
        == right.nut_standard
        and left.nut_material_id
        == right.nut_material_id
        and left.nut_property_class
        == right.nut_property_class
        and left.handedness
        == right.handedness
        and left.starts
        == right.starts
        and left.member_material_ids
        == right.member_material_ids
        and left.geometry_generation_id
        == right.geometry_generation_id
        and left.execution_generation_id
        == right.execution_generation_id
    )


def _relative_difference(
    left: float,
    right: float,
) -> float:
    scale = max(
        abs(left),
        abs(right),
        1.0e-12,
    )

    return abs(
        left - right
    ) / scale


def _feature_distance(
    target: FemCalibrationFeatureVector,
    evidence: FemCalibrationFeatureVector,
) -> float | None:
    if not _strict_compatibility(
        target,
        evidence,
    ):
        return None

    target_diameter = (
        _metric_nominal_diameter(
            target.compatibility.thread_designation
        )
    )

    evidence_diameter = (
        _metric_nominal_diameter(
            evidence.compatibility.thread_designation
        )
    )

    scalable = (
        (
            target_diameter,
            evidence_diameter,
        ),
        (
            target.target_preload_n,
            evidence.target_preload_n,
        ),
        (
            target.analytical_delta_temperature_abs_c,
            evidence.analytical_delta_temperature_abs_c,
        ),
        (
            target.bolt_length_mm,
            evidence.bolt_length_mm,
        ),
        (
            target.total_grip_length_mm,
            evidence.total_grip_length_mm,
        ),
    )

    # Dimensionless quantities are not all bounded fractions.
    #
    # Geometry ratios such as protrusion/pitch can legitimately be several
    # units large. Comparing them by raw absolute difference would therefore
    # dominate the distance metric solely because of their numerical scale.
    #
    # Scale-like ratios are compared relatively. Truly bounded fractions,
    # load ratios and friction coefficients retain absolute-difference
    # semantics.
    scalable_ratios = (
        (
            target.engagement_to_pitch,
            evidence.engagement_to_pitch,
        ),
        (
            target.protrusion_to_pitch,
            evidence.protrusion_to_pitch,
        ),
        (
            target.clearance_to_outer_diameter,
            evidence.clearance_to_outer_diameter,
        ),
        (
            target.outer_diameter_to_bolt_length,
            evidence.outer_diameter_to_bolt_length,
        ),
    )

    bounded_dimensionless = (
        (
            target.upper_grip_fraction,
            evidence.upper_grip_fraction,
        ),
        (
            target.external_axial_to_preload,
            evidence.external_axial_to_preload,
        ),
        (
            target.thread_friction,
            evidence.thread_friction,
        ),
        (
            target.head_bearing_friction,
            evidence.head_bearing_friction,
        ),
        (
            target.nut_bearing_friction,
            evidence.nut_bearing_friction,
        ),
        (
            target.member_interface_friction,
            evidence.member_interface_friction,
        ),
    )

    components = [
        _relative_difference(
            left,
            right,
        )
        for left, right in (
            *scalable,
            *scalable_ratios,
        )
    ]

    components.extend(
        abs(
            left - right
        )
        for left, right in bounded_dimensionless
    )

    return math.sqrt(
        sum(
            value * value
            for value in components
        )
        / len(components)
    )


def _case_estimates(
    observations: tuple[
        FemCalibrationObservation,
        ...,
    ],
) -> tuple[
    _CaseEstimate,
    ...,
]:
    grouped: dict[
        tuple[str, str],
        list[FemCalibrationObservation],
    ] = {}

    for observation in observations:
        if not observation.reusable_for_prediction:
            continue

        grouped.setdefault(
            (
                observation.case_hash,
                observation.resolution_hash,
            ),
            [],
        ).append(
            observation
        )

    result = []

    for (
        case_hash,
        resolution_hash,
    ), rows in sorted(
        grouped.items()
    ):
        rows = sorted(
            rows,
            key=lambda item: (
                item.trial_index,
                item.run_id,
            ),
        )

        feature = rows[0].feature
        case_id = rows[0].case_id

        if any(
            item.case_id != case_id
            or item.feature != feature
            for item in rows
        ):
            raise RuntimeError(
                f"{case_hash}: inconsistent observations inside one case."
            )

        factors = tuple(
            item.proportional_correction_factor
            for item in rows
        )

        factor = (
            sum(factors)
            / len(factors)
        )

        if (
            not math.isfinite(factor)
            or factor <= 0.0
        ):
            raise RuntimeError(
                f"{case_hash}: invalid case-level correction estimate."
            )

        result.append(
            _CaseEstimate(
                case_id=case_id,
                case_hash=case_hash,
                resolution_hash=resolution_hash,
                feature=feature,
                correction_factor=factor,
                observation_count=len(rows),
            )
        )

    return tuple(
        result
    )


def predict_trial1_from_observations(
    *,
    target_case_hash: str,
    target_resolution_hash: str,
    target_feature: FemCalibrationFeatureVector,
    analytical_delta_temperature_c: float,
    observations: tuple[
        FemCalibrationObservation,
        ...,
    ],
    policy: Trial1ObservationPredictorPolicy,
) -> Trial1ObservationPrediction:
    """Predict CAL_01 or return a governed analytical fallback."""

    if (
        not math.isfinite(
            analytical_delta_temperature_c
        )
        or analytical_delta_temperature_c >= 0.0
    ):
        raise ValueError(
            "Analytical Trial-1 seed must represent contraction."
        )

    estimates = _case_estimates(
        observations
    )

    exact = tuple(
        item
        for item in estimates
        if (
            item.case_hash
            == target_case_hash
            and item.resolution_hash
            == target_resolution_hash
            and _strict_compatibility(
                target_feature,
                item.feature,
            )
        )
    )

    if exact:
        if len(exact) != 1:
            raise RuntimeError(
                "Multiple exact calibration case estimates exist."
            )

        factor = min(
            policy.maximum_correction_factor,
            max(
                policy.minimum_correction_factor,
                exact[0].correction_factor,
            ),
        )

        return Trial1ObservationPrediction(
            policy_id=policy.policy_id,
            source=(
                Trial1PredictionSource.EXACT_CASE
            ),
            applicability=(
                Trial1PredictionApplicability.EXACT_CASE
            ),
            analytical_delta_temperature_c=(
                analytical_delta_temperature_c
            ),
            predicted_delta_temperature_c=(
                analytical_delta_temperature_c
                * factor
            ),
            correction_factor=factor,
            reused_case_count=1,
            neighbor_case_ids=(
                exact[0].case_id,
            ),
            neighbor_case_hashes=(
                exact[0].case_hash,
            ),
            nearest_distance=0.0,
        )

    candidates = []

    for estimate in estimates:
        distance = _feature_distance(
            target_feature,
            estimate.feature,
        )

        if distance is None:
            continue

        if (
            distance
            <= policy.maximum_distance
        ):
            candidates.append(
                (
                    distance,
                    estimate,
                )
            )

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1].case_hash,
            item[1].case_id,
        )
    )

    selected = tuple(
        candidates[
            : policy.maximum_neighbors
        ]
    )

    def fallback(
        applicability: Trial1PredictionApplicability,
        nearest: float | None,
    ) -> Trial1ObservationPrediction:
        return Trial1ObservationPrediction(
            policy_id=policy.policy_id,
            source=(
                Trial1PredictionSource.ANALYTICAL_FALLBACK
            ),
            applicability=applicability,
            analytical_delta_temperature_c=(
                analytical_delta_temperature_c
            ),
            predicted_delta_temperature_c=(
                analytical_delta_temperature_c
            ),
            correction_factor=1.0,
            reused_case_count=0,
            neighbor_case_ids=(),
            neighbor_case_hashes=(),
            nearest_distance=nearest,
        )

    if not selected:
        return fallback(
            Trial1PredictionApplicability.NO_COMPATIBLE_EVIDENCE,
            None,
        )

    nearest_distance = selected[0][0]

    if (
        len(selected)
        < policy.minimum_neighbors_for_reuse
    ):
        return fallback(
            Trial1PredictionApplicability.INSUFFICIENT_NEIGHBORS,
            nearest_distance,
        )

    if policy.require_target_preload_bracketing:
        preload_values = tuple(
            item.feature.target_preload_n
            for _, item in selected
        )

        target_preload = (
            target_feature.target_preload_n
        )

        if not (
            min(preload_values)
            <= target_preload
            <= max(preload_values)
        ):
            return fallback(
                Trial1PredictionApplicability.PRELOAD_EXTRAPOLATION,
                nearest_distance,
            )

    factors = tuple(
        item.correction_factor
        for _, item in selected
    )

    factor_mean = (
        sum(factors)
        / len(factors)
    )

    relative_spread = (
        max(factors)
        - min(factors)
    ) / factor_mean

    if (
        relative_spread
        > policy.maximum_correction_factor_relative_spread
    ):
        return fallback(
            Trial1PredictionApplicability.CORRECTION_FACTOR_DISAGREEMENT,
            nearest_distance,
        )

    zero = tuple(
        item
        for item in selected
        if item[0] <= 1.0e-12
    )

    if zero:
        correction_factor = (
            sum(
                estimate.correction_factor
                for _, estimate in zero
            )
            / len(zero)
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

        correction_factor = (
            sum(
                weight
                * estimate.correction_factor
                for weight, (_, estimate) in zip(
                    weights,
                    selected,
                    strict=True,
                )
            )
            / sum(weights)
        )

    correction_factor = min(
        policy.maximum_correction_factor,
        max(
            policy.minimum_correction_factor,
            correction_factor,
        ),
    )

    return Trial1ObservationPrediction(
        policy_id=policy.policy_id,
        source=(
            Trial1PredictionSource.OBSERVATION_NEIGHBORS
        ),
        applicability=(
            Trial1PredictionApplicability.INTERPOLATION
        ),
        analytical_delta_temperature_c=(
            analytical_delta_temperature_c
        ),
        predicted_delta_temperature_c=(
            analytical_delta_temperature_c
            * correction_factor
        ),
        correction_factor=correction_factor,
        reused_case_count=len(selected),
        neighbor_case_ids=tuple(
            estimate.case_id
            for _, estimate in selected
        ),
        neighbor_case_hashes=tuple(
            estimate.case_hash
            for _, estimate in selected
        ),
        nearest_distance=nearest_distance,
    )
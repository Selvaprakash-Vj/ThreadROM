"""Governed VV06-S1 matched-preload screening mathematics."""

from __future__ import annotations

import math
import tomllib

from itertools import pairwise

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Vv06S1PointVerdict(str, Enum):
    SUPPORT = "support"
    REJECT = "reject"
    INDETERMINATE = "indeterminate"


class Vv06S1Disposition(str, Enum):
    SUPPORTS_CONFIRMATION = "S1_SUPPORTS_CONFIRMATION"
    REJECTS_MEDIUM_FOR_P04 = "S1_REJECTS_MEDIUM_FOR_P04"
    INDETERMINATE = "S1_INDETERMINATE"


@dataclass(frozen=True, slots=True)
class Vv06S1ResponseTolerances:
    member_shortening_relative: float
    bolt_free_span_mean_szz_relative: float
    thread_normal_force_relative: float


@dataclass(frozen=True, slots=True)
class Vv06S1Policy:
    policy_id: str
    epsilon: float
    comparison_preload_kn: tuple[float, ...]
    governing_preload_kn: tuple[float, ...]
    require_strict_clamp_monotonicity: bool
    allow_extrapolation: bool
    response_tolerances: Vv06S1ResponseTolerances


@dataclass(frozen=True, slots=True)
class Vv06S1RelativeDifferenceBand:
    nominal_relative_difference: float
    lower_relative_difference: float
    upper_relative_difference: float


def load_vv06_s1_policy(
    path: Path,
) -> Vv06S1Policy:
    """Load and validate the frozen VV06-S1 screening policy."""

    with path.open("rb") as stream:
        data = tomllib.load(stream)

    tolerances = data["response_tolerances"]

    policy = Vv06S1Policy(
        policy_id=str(data["policy_id"]),
        epsilon=float(data["epsilon"]),
        comparison_preload_kn=tuple(
            float(value)
            for value in data["comparison_preload_kn"]
        ),
        governing_preload_kn=tuple(
            float(value)
            for value in data["governing_preload_kn"]
        ),
        require_strict_clamp_monotonicity=bool(
            data["require_strict_clamp_monotonicity"]
        ),
        allow_extrapolation=bool(
            data["allow_extrapolation"]
        ),
        response_tolerances=Vv06S1ResponseTolerances(
            member_shortening_relative=float(
                tolerances["member_shortening_relative"]
            ),
            bolt_free_span_mean_szz_relative=float(
                tolerances["bolt_free_span_mean_szz_relative"]
            ),
            thread_normal_force_relative=float(
                tolerances["thread_normal_force_relative"]
            ),
        ),
    )

    if not policy.policy_id.strip():
        raise ValueError("VV06-S1 policy_id must not be blank.")

    if (
        not math.isfinite(policy.epsilon)
        or policy.epsilon <= 0.0
    ):
        raise ValueError(
            "VV06-S1 epsilon must be finite and positive."
        )

    if not policy.comparison_preload_kn:
        raise ValueError(
            "VV06-S1 comparison preload list must not be empty."
        )

    if not policy.governing_preload_kn:
        raise ValueError(
            "VV06-S1 governing preload list must not be empty."
        )

    comparison_set = set(policy.comparison_preload_kn)

    if not set(policy.governing_preload_kn).issubset(
        comparison_set
    ):
        raise ValueError(
            "Every governing preload must also be a comparison preload."
        )

    if any(
        not math.isfinite(value) or value <= 0.0
        for value in policy.comparison_preload_kn
    ):
        raise ValueError(
            "VV06-S1 preload points must be finite and positive."
        )

    tolerance_values = (
        policy.response_tolerances.member_shortening_relative,
        policy.response_tolerances.bolt_free_span_mean_szz_relative,
        policy.response_tolerances.thread_normal_force_relative,
    )

    if any(
        not math.isfinite(value) or value <= 0.0
        for value in tolerance_values
    ):
        raise ValueError(
            "VV06-S1 response tolerances must be finite and positive."
        )

    return policy


def require_strictly_increasing(
    values: tuple[float, ...],
) -> None:
    """Require a finite strictly increasing realized-force history."""

    if len(values) < 2:
        raise ValueError(
            "At least two force states are required."
        )

    if any(
        not math.isfinite(value)
        for value in values
    ):
        raise ValueError(
            "Realized clamp-force history must be finite."
        )

    if any(
        right <= left
        for left, right in pairwise(values)
    ):
        raise ValueError(
            "Realized clamp-force history is not strictly increasing."
        )


def derive_relative_difference_band(
    *,
    medium_value: float,
    fine_value: float,
    medium_uncertainty: float,
    fine_uncertainty: float,
    epsilon: float,
) -> Vv06S1RelativeDifferenceBand:
    """Derive conservative matched-response relative-difference bounds."""

    inputs = (
        medium_value,
        fine_value,
        medium_uncertainty,
        fine_uncertainty,
        epsilon,
    )

    if any(
        not math.isfinite(value)
        for value in inputs
    ):
        raise ValueError(
            "VV06-S1 difference-band inputs must be finite."
        )

    if medium_uncertainty < 0.0 or fine_uncertainty < 0.0:
        raise ValueError(
            "Interpolation uncertainties must be non-negative."
        )

    if epsilon <= 0.0:
        raise ValueError(
            "epsilon must be positive."
        )

    difference = abs(
        fine_value - medium_value
    )

    combined_uncertainty = (
        medium_uncertainty
        + fine_uncertainty
    )

    medium_abs = abs(
        medium_value
    )

    nominal_denominator = max(
        medium_abs,
        epsilon,
    )

    nominal = (
        difference
        / nominal_denominator
    )

    lower = (
        max(
            0.0,
            difference - combined_uncertainty,
        )
        / (
            medium_abs
            + medium_uncertainty
        )
    )

    upper = (
        difference
        + combined_uncertainty
    ) / max(
        medium_abs - medium_uncertainty,
        epsilon,
    )

    return Vv06S1RelativeDifferenceBand(
        nominal_relative_difference=nominal,
        lower_relative_difference=lower,
        upper_relative_difference=upper,
    )


def classify_relative_difference_band(
    *,
    band: Vv06S1RelativeDifferenceBand,
    tolerance: float,
) -> Vv06S1PointVerdict:
    """Apply the pre-frozen three-way screening rule."""

    if (
        not math.isfinite(tolerance)
        or tolerance <= 0.0
    ):
        raise ValueError(
            "VV06-S1 tolerance must be finite and positive."
        )

    if band.upper_relative_difference <= tolerance:
        return Vv06S1PointVerdict.SUPPORT

    if band.lower_relative_difference > tolerance:
        return Vv06S1PointVerdict.REJECT

    return Vv06S1PointVerdict.INDETERMINATE


def derive_overall_disposition(
    verdicts: tuple[Vv06S1PointVerdict, ...],
) -> Vv06S1Disposition:
    """Apply frozen REJECT > INDETERMINATE > SUPPORT precedence."""

    if not verdicts:
        raise ValueError(
            "At least one VV06-S1 verdict is required."
        )

    if any(
        verdict is Vv06S1PointVerdict.REJECT
        for verdict in verdicts
    ):
        return Vv06S1Disposition.REJECTS_MEDIUM_FOR_P04

    if any(
        verdict is Vv06S1PointVerdict.INDETERMINATE
        for verdict in verdicts
    ):
        return Vv06S1Disposition.INDETERMINATE

    return Vv06S1Disposition.SUPPORTS_CONFIRMATION


# === VV06-S1 INTERPOLATION ENGINE ===


class Vv06S1InterpolationKind(str, Enum):
    DIRECT = "direct"
    INTERPOLATED = "interpolated"


@dataclass(frozen=True, slots=True)
class Vv06S1HistoryPoint:
    """One accepted FEM response state ordered by realized clamp force."""

    force_n: float
    response_value: float
    dataset_sequence: int
    step: int
    increment: int
    time: float


@dataclass(frozen=True, slots=True)
class Vv06S1InterpolationEstimate:
    """Matched-force response estimate with auditable interpolation provenance."""

    target_force_n: float
    kind: Vv06S1InterpolationKind

    value: float
    uncertainty: float

    linear_value: float
    quadratic_value: float | None

    lower_dataset_sequence: int
    upper_dataset_sequence: int

    lower_step: int
    upper_step: int

    lower_increment: int
    upper_increment: int

    lower_time: float
    upper_time: float

    lower_force_n: float
    upper_force_n: float

    interpolation_fraction: float

    quadratic_dataset_sequences: tuple[int, int, int] | None
    quadratic_increments: tuple[int, int, int] | None


def _validate_history_points(
    points: tuple[Vv06S1HistoryPoint, ...],
) -> None:
    if len(points) < 2:
        raise ValueError(
            "VV06-S1 interpolation requires at least two history points."
        )

    for point in points:
        values = (
            point.force_n,
            point.response_value,
            point.time,
        )

        if any(
            not math.isfinite(value)
            for value in values
        ):
            raise ValueError(
                "VV06-S1 history points must contain finite values."
            )

        if point.dataset_sequence <= 0:
            raise ValueError(
                "dataset_sequence must be positive."
            )

        if point.step <= 0 or point.increment <= 0:
            raise ValueError(
                "step and increment must be positive."
            )

    # IMPORTANT:
    # Do not sort here. The caller supplies accepted states in chronological
    # solver order. Sorting by force could conceal a genuine non-monotonic
    # response, which S1 explicitly forbids.
    require_strictly_increasing(
        tuple(
            point.force_n
            for point in points
        )
    )


def _linear_interpolate(
    *,
    lower: Vv06S1HistoryPoint,
    upper: Vv06S1HistoryPoint,
    target_force_n: float,
) -> tuple[float, float]:
    force_span = (
        upper.force_n
        - lower.force_n
    )

    if force_span <= 0.0:
        raise ValueError(
            "Linear interpolation requires an increasing force bracket."
        )

    fraction = (
        target_force_n
        - lower.force_n
    ) / force_span

    value = (
        lower.response_value
        + fraction
        * (
            upper.response_value
            - lower.response_value
        )
    )

    return float(value), float(fraction)


def _quadratic_interpolate(
    *,
    first: Vv06S1HistoryPoint,
    second: Vv06S1HistoryPoint,
    third: Vv06S1HistoryPoint,
    target_force_n: float,
) -> float:
    """Three-point Lagrange interpolation in realized clamp force."""

    x0 = first.force_n
    x1 = second.force_n
    x2 = third.force_n

    y0 = first.response_value
    y1 = second.response_value
    y2 = third.response_value

    if not (
        x0 < x1 < x2
    ):
        raise ValueError(
            "Quadratic interpolation forces must be strictly increasing."
        )

    if not (
        x0 <= target_force_n <= x2
    ):
        raise ValueError(
            "Quadratic VV06-S1 interpolation may not extrapolate."
        )

    l0 = (
        (target_force_n - x1)
        * (target_force_n - x2)
        / (
            (x0 - x1)
            * (x0 - x2)
        )
    )

    l1 = (
        (target_force_n - x0)
        * (target_force_n - x2)
        / (
            (x1 - x0)
            * (x1 - x2)
        )
    )

    l2 = (
        (target_force_n - x0)
        * (target_force_n - x1)
        / (
            (x2 - x0)
            * (x2 - x1)
        )
    )

    value = (
        y0 * l0
        + y1 * l1
        + y2 * l2
    )

    if not math.isfinite(value):
        raise ValueError(
            "Quadratic VV06-S1 interpolation produced a non-finite value."
        )

    return float(value)


def _select_local_quadratic_triplet(
    *,
    points: tuple[Vv06S1HistoryPoint, ...],
    lower_index: int,
    upper_index: int,
    target_force_n: float,
) -> tuple[
    Vv06S1HistoryPoint,
    Vv06S1HistoryPoint,
    Vv06S1HistoryPoint,
] | None:
    """Select a deterministic local three-point interpolation stencil.

    Candidate stencils must contain the target force and the linear bracket.
    If both left- and right-biased candidates exist, choose the candidate
    having the smallest total force-distance to the target. Ties are broken
    by the smaller force span and then by dataset-sequence tuple.
    """

    candidate_indices: list[tuple[int, int, int]] = []

    if lower_index > 0:
        candidate_indices.append(
            (
                lower_index - 1,
                lower_index,
                upper_index,
            )
        )

    if upper_index + 1 < len(points):
        candidate_indices.append(
            (
                lower_index,
                upper_index,
                upper_index + 1,
            )
        )

    candidates = []

    for indices in candidate_indices:
        triplet = tuple(
            points[index]
            for index in indices
        )

        forces = tuple(
            point.force_n
            for point in triplet
        )

        if not (
            forces[0]
            < forces[1]
            < forces[2]
        ):
            continue

        if not (
            forces[0]
            <= target_force_n
            <= forces[2]
        ):
            continue

        total_distance = sum(
            abs(
                force
                - target_force_n
            )
            for force in forces
        )

        force_span = (
            forces[2]
            - forces[0]
        )

        sequence_key = tuple(
            point.dataset_sequence
            for point in triplet
        )

        candidates.append(
            (
                total_distance,
                force_span,
                sequence_key,
                triplet,
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )

    return candidates[0][3]


def interpolate_response_at_force(
    *,
    points: tuple[Vv06S1HistoryPoint, ...],
    target_force_n: float,
    allow_extrapolation: bool = False,
) -> Vv06S1InterpolationEstimate:
    """Evaluate one response at a matched realized clamp force.

    DIRECT is used only for an exact force value already represented by an
    accepted FEM state. Otherwise two-point linear interpolation is primary.

    Interpolation uncertainty is:
      |quadratic - linear|
    when a valid local three-point quadratic cross-check exists.

    Otherwise the frozen conservative fallback is:
      |Q_upper - Q_lower|
    """

    _validate_history_points(
        points
    )

    if (
        not math.isfinite(target_force_n)
        or target_force_n <= 0.0
    ):
        raise ValueError(
            "Target preload must be finite and positive."
        )

    if allow_extrapolation:
        raise ValueError(
            "VV06-S1 extrapolation is prohibited by the frozen protocol."
        )

    first_force = points[0].force_n
    last_force = points[-1].force_n

    if (
        target_force_n < first_force
        or target_force_n > last_force
    ):
        raise ValueError(
            "Target preload lies outside the solved clamp-force history."
        )

    # Exact/direct accepted state only. No hidden numerical matching tolerance
    # is introduced into the frozen protocol.
    for point in points:
        if point.force_n == target_force_n:
            return Vv06S1InterpolationEstimate(
                target_force_n=target_force_n,
                kind=Vv06S1InterpolationKind.DIRECT,
                value=point.response_value,
                uncertainty=0.0,
                linear_value=point.response_value,
                quadratic_value=None,
                lower_dataset_sequence=point.dataset_sequence,
                upper_dataset_sequence=point.dataset_sequence,
                lower_step=point.step,
                upper_step=point.step,
                lower_increment=point.increment,
                upper_increment=point.increment,
                lower_time=point.time,
                upper_time=point.time,
                lower_force_n=point.force_n,
                upper_force_n=point.force_n,
                interpolation_fraction=0.0,
                quadratic_dataset_sequences=None,
                quadratic_increments=None,
            )

    lower_index: int | None = None

    for index in range(
        len(points) - 1
    ):
        lower = points[index]
        upper = points[index + 1]

        if (
            lower.force_n
            < target_force_n
            < upper.force_n
        ):
            lower_index = index
            break

    if lower_index is None:
        raise ValueError(
            "Could not derive an interpolation bracket for target preload."
        )

    upper_index = (
        lower_index + 1
    )

    lower = points[
        lower_index
    ]

    upper = points[
        upper_index
    ]

    linear_value, fraction = _linear_interpolate(
        lower=lower,
        upper=upper,
        target_force_n=target_force_n,
    )

    triplet = _select_local_quadratic_triplet(
        points=points,
        lower_index=lower_index,
        upper_index=upper_index,
        target_force_n=target_force_n,
    )

    if triplet is None:
        quadratic_value = None

        uncertainty = abs(
            upper.response_value
            - lower.response_value
        )

        quadratic_sequences = None
        quadratic_increments = None

    else:
        quadratic_value = _quadratic_interpolate(
            first=triplet[0],
            second=triplet[1],
            third=triplet[2],
            target_force_n=target_force_n,
        )

        uncertainty = abs(
            quadratic_value
            - linear_value
        )

        quadratic_sequences = tuple(
            point.dataset_sequence
            for point in triplet
        )

        quadratic_increments = tuple(
            point.increment
            for point in triplet
        )

    if (
        not math.isfinite(linear_value)
        or not math.isfinite(uncertainty)
        or uncertainty < 0.0
    ):
        raise ValueError(
            "VV06-S1 interpolation produced invalid evidence."
        )

    return Vv06S1InterpolationEstimate(
        target_force_n=target_force_n,
        kind=Vv06S1InterpolationKind.INTERPOLATED,
        value=linear_value,
        uncertainty=uncertainty,
        linear_value=linear_value,
        quadratic_value=quadratic_value,
        lower_dataset_sequence=lower.dataset_sequence,
        upper_dataset_sequence=upper.dataset_sequence,
        lower_step=lower.step,
        upper_step=upper.step,
        lower_increment=lower.increment,
        upper_increment=upper.increment,
        lower_time=lower.time,
        upper_time=upper.time,
        lower_force_n=lower.force_n,
        upper_force_n=upper.force_n,
        interpolation_fraction=fraction,
        quadratic_dataset_sequences=quadratic_sequences,
        quadratic_increments=quadratic_increments,
    )

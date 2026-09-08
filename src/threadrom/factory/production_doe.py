"""Governed Phase-3 CP8 Production DOE generation."""

from __future__ import annotations

import hashlib
import math
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path

from threadrom.case.contract import ThreadROMCase
from threadrom.case.reference_cases import (
    phase2_certification_case,
)
from threadrom.case.serialization import case_sha256
from threadrom.factory.pilot_doe import (
    build_phase3_cp7_pilot_doe,
)


@dataclass(frozen=True, slots=True)
class ProductionDoePointSpec:
    """One frozen normalized DOE point."""

    case_id: str
    normalized_coordinates: tuple[float, float, float]
    source_case_id: str | None = None

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError(
                "Production DOE case_id must not be blank."
            )

        if len(self.normalized_coordinates) != 3:
            raise ValueError(
                "Production DOE coordinates must be 3-dimensional."
            )

        if not all(
            math.isfinite(value)
            and 0.0 <= value <= 1.0
            for value in self.normalized_coordinates
        ):
            raise ValueError(
                "Production DOE normalized coordinates must lie in [0, 1]."
            )


@dataclass(frozen=True, slots=True)
class ProductionDoePolicy:
    """Frozen CP8 production-DOE definition."""

    policy_id: str
    policy_name: str
    status: str

    preload_min_n: float
    preload_max_n: float

    head_thickness_min_mm: float
    head_thickness_max_mm: float
    total_grip_mm: float

    radial_fraction_min: float
    radial_fraction_max: float
    outer_diameter_start_mm: float
    outer_diameter_end_mm: float
    clearance_hole_start_mm: float
    clearance_hole_end_mm: float

    design_rows_total: int
    existing_anchor_rows_planned: int
    new_design_rows_maximum: int
    blind_holdout_rows: int

    interior_space_filling_rows: int
    deterministic_seed: int
    candidate_pool_multiplier: int

    normalized_dimension_order: tuple[str, ...]

    existing_anchors: tuple[ProductionDoePointSpec, ...]
    mandatory_design_points: tuple[ProductionDoePointSpec, ...]
    holdout_points: tuple[ProductionDoePointSpec, ...]

    holdout_minimum_distance: float

    radial_variation_mesh_policy_name: str

    def __post_init__(self) -> None:
        if self.status != "frozen":
            raise ValueError(
                "Production DOE policy must be frozen before generation."
            )

        if self.policy_id != "TRM-PDOE-000001":
            raise ValueError(
                "Unexpected Production DOE policy identity."
            )

        if self.normalized_dimension_order != (
            "target_preload",
            "head_member_thickness",
            "radial_geometry_fraction",
        ):
            raise ValueError(
                "Unexpected Production DOE dimension order."
            )

        if self.design_rows_total != 24:
            raise ValueError(
                "Production DOE must contain 24 design rows."
            )

        if self.blind_holdout_rows != 6:
            raise ValueError(
                "Production DOE must contain 6 blind holdouts."
            )

        if (
            len(self.existing_anchors)
            != self.existing_anchor_rows_planned
        ):
            raise ValueError(
                "Existing-anchor count does not match policy."
            )

        if (
            len(self.holdout_points)
            != self.blind_holdout_rows
        ):
            raise ValueError(
                "Blind-holdout count does not match policy."
            )

        expected_design_rows = (
            len(self.existing_anchors)
            + len(self.mandatory_design_points)
            + self.interior_space_filling_rows
        )

        if expected_design_rows != self.design_rows_total:
            raise ValueError(
                "Configured DOE design-row accounting is inconsistent."
            )

        if (
            self.design_rows_total
            - self.existing_anchor_rows_planned
            > self.new_design_rows_maximum
        ):
            raise ValueError(
                "Configured DOE exceeds maximum new-design allowance."
            )

        if self.candidate_pool_multiplier <= 0:
            raise ValueError(
                "candidate_pool_multiplier must be positive."
            )

        if not (
            0.0
            < self.holdout_minimum_distance
            < math.sqrt(3.0)
        ):
            raise ValueError(
                "Invalid design-to-holdout distance requirement."
            )


@dataclass(frozen=True, slots=True)
class ProductionDoeCase:
    """One generated physical ThreadROM production-DOE case."""

    case_id: str
    role: str

    normalized_coordinates: tuple[float, float, float]

    case: ThreadROMCase
    case_hash: str

    mesh_policy_name: str

    source_case_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProductionDoeCampaign:
    """Complete deterministic CP8 Production DOE campaign."""

    policy_id: str
    design_cases: tuple[ProductionDoeCase, ...]
    holdout_cases: tuple[ProductionDoeCase, ...]

    selected_lhs_candidate_index: int
    selected_design_minimum_distance: float
    minimum_design_to_holdout_distance: float

    @property
    def all_cases(
        self,
    ) -> tuple[ProductionDoeCase, ...]:
        return (
            self.design_cases
            + self.holdout_cases
        )


def _point(
    raw: dict[str, object],
    *,
    source_case: bool,
) -> ProductionDoePointSpec:
    coordinates = tuple(
        float(value)
        for value in raw["normalized_coordinates"]
    )

    if len(coordinates) != 3:
        raise ValueError(
            "Production DOE coordinates must have length 3."
        )

    return ProductionDoePointSpec(
        case_id=str(
            raw.get(
                "anchor_id",
                raw.get("case_id", ""),
            )
        ),
        normalized_coordinates=(
            coordinates[0],
            coordinates[1],
            coordinates[2],
        ),
        source_case_id=(
            str(raw["source_case_id"])
            if source_case
            else None
        ),
    )


def load_phase3_production_doe_policy(
    path: Path,
) -> ProductionDoePolicy:
    """Load and validate the frozen CP8 Production DOE policy."""

    with path.open("rb") as stream:
        data = tomllib.load(stream)

    dimensions = {
        str(item["dimension_id"]): item
        for item in data["dimensions"]
    }

    preload = dimensions["target_preload"]
    head = dimensions["head_member_thickness"]
    radial = dimensions["radial_geometry_fraction"]

    anchors = tuple(
        _point(
            item,
            source_case=True,
        )
        for item in data["existing_anchors"]
    )

    mandatory = tuple(
        _point(
            item,
            source_case=False,
        )
        for item in data["mandatory_design_points"]
    )

    holdouts = tuple(
        _point(
            item,
            source_case=False,
        )
        for item in data["holdouts"]["points"]
    )

    design = data["design"]
    campaign = data["campaign"]
    member_stack = data["constraints"]["member_stack"]
    radial_path = data["constraints"]["radial_geometry_path"]

    return ProductionDoePolicy(
        policy_id=str(
            data["identity"]["policy_id"]
        ),
        policy_name=str(
            data["identity"]["policy_name"]
        ),
        status=str(
            data["identity"]["status"]
        ),
        preload_min_n=float(
            preload["minimum"]
        ),
        preload_max_n=float(
            preload["maximum"]
        ),
        head_thickness_min_mm=float(
            head["minimum"]
        ),
        head_thickness_max_mm=float(
            head["maximum"]
        ),
        total_grip_mm=float(
            member_stack["total_grip_mm"]
        ),
        radial_fraction_min=float(
            radial["minimum"]
        ),
        radial_fraction_max=float(
            radial["maximum"]
        ),
        outer_diameter_start_mm=float(
            radial_path["outer_diameter_start_mm"]
        ),
        outer_diameter_end_mm=float(
            radial_path["outer_diameter_end_mm"]
        ),
        clearance_hole_start_mm=float(
            radial_path["clearance_hole_start_mm"]
        ),
        clearance_hole_end_mm=float(
            radial_path["clearance_hole_end_mm"]
        ),
        design_rows_total=int(
            campaign["design_rows_total"]
        ),
        existing_anchor_rows_planned=int(
            campaign["existing_anchor_rows_planned"]
        ),
        new_design_rows_maximum=int(
            campaign["new_design_rows_maximum"]
        ),
        blind_holdout_rows=int(
            campaign["blind_holdout_rows"]
        ),
        interior_space_filling_rows=int(
            design["interior_space_filling_rows"]
        ),
        deterministic_seed=int(
            design["deterministic_seed"]
        ),
        candidate_pool_multiplier=int(
            design["candidate_pool_multiplier"]
        ),
        normalized_dimension_order=tuple(
            str(item)
            for item in design[
                "normalized_dimension_order"
            ]
        ),
        existing_anchors=anchors,
        mandatory_design_points=mandatory,
        holdout_points=holdouts,
        holdout_minimum_distance=float(
            data["holdouts"][
                "minimum_design_to_holdout_normalized_euclidean_distance"
            ]
        ),
        radial_variation_mesh_policy_name=str(
            data["mesh"][
                "radial_variation_mesh_policy_name"
            ]
        ),
    )


def _distance(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> float:
    return math.sqrt(
        sum(
            (a - b) ** 2
            for a, b in zip(
                left,
                right,
                strict=True,
            )
        )
    )


def _minimum_pairwise_distance(
    points: tuple[
        tuple[float, float, float],
        ...,
    ],
) -> float:
    if len(points) < 2:
        raise ValueError(
            "At least two points are required."
        )

    return min(
        _distance(
            points[left],
            points[right],
        )
        for left in range(len(points))
        for right in range(
            left + 1,
            len(points),
        )
    )


def _minimum_cross_distance(
    left: tuple[
        tuple[float, float, float],
        ...,
    ],
    right: tuple[
        tuple[float, float, float],
        ...,
    ],
) -> float:
    if not left or not right:
        raise ValueError(
            "Both point sets are required."
        )

    return min(
        _distance(a, b)
        for a in left
        for b in right
    )


def _hash_fraction(
    *,
    seed: int,
    candidate_index: int,
    dimension_index: int,
    row_index: int,
    purpose: str,
) -> float:
    payload = (
        f"{seed}|{candidate_index}|"
        f"{dimension_index}|{row_index}|{purpose}"
    ).encode("ascii")

    integer = int.from_bytes(
        hashlib.sha256(payload).digest(),
        byteorder="big",
        signed=False,
    )

    return (
        integer
        / float(1 << 256)
    )


def _lhs_candidate(
    *,
    rows: int,
    seed: int,
    candidate_index: int,
) -> tuple[
    tuple[float, float, float],
    ...,
]:
    """Create one cross-version deterministic 3-D Latin hypercube."""

    columns: list[list[float]] = []

    for dimension in range(3):
        strata = list(
            range(rows)
        )

        strata.sort(
            key=lambda stratum: (
                hashlib.sha256(
                    (
                        f"{seed}|{candidate_index}|"
                        f"{dimension}|{stratum}|perm"
                    ).encode("ascii")
                ).digest()
            )
        )

        column = []

        for row in range(rows):
            jitter = _hash_fraction(
                seed=seed,
                candidate_index=candidate_index,
                dimension_index=dimension,
                row_index=row,
                purpose="jitter",
            )

            column.append(
                (
                    strata[row]
                    + jitter
                )
                / rows
            )

        columns.append(
            column
        )

    return tuple(
        (
            columns[0][row],
            columns[1][row],
            columns[2][row],
        )
        for row in range(rows)
    )


def _select_maximin_lhs(
    *,
    policy: ProductionDoePolicy,
    fixed_design_points: tuple[
        tuple[float, float, float],
        ...,
    ],
) -> tuple[
    tuple[
        tuple[float, float, float],
        ...,
    ],
    int,
    float,
    float,
]:
    """Select deterministic maximin LHS subject to holdout separation."""

    holdouts = tuple(
        point.normalized_coordinates
        for point in policy.holdout_points
    )

    candidate_count = (
        policy.interior_space_filling_rows
        * policy.candidate_pool_multiplier
    )

    best_points = None
    best_index = None
    best_score = -math.inf
    best_holdout_distance = -math.inf

    for candidate_index in range(
        candidate_count
    ):
        interior = _lhs_candidate(
            rows=policy.interior_space_filling_rows,
            seed=policy.deterministic_seed,
            candidate_index=candidate_index,
        )

        design_points = (
            fixed_design_points
            + interior
        )

        design_to_holdout = (
            _minimum_cross_distance(
                design_points,
                holdouts,
            )
        )

        if (
            design_to_holdout
            + 1.0e-15
            < policy.holdout_minimum_distance
        ):
            continue

        score = (
            _minimum_pairwise_distance(
                design_points
            )
        )

        # Deterministic tie-breaking:
        # 1. larger design maximin distance
        # 2. larger design-to-holdout distance
        # 3. smaller candidate index
        better = (
            score > best_score
            or (
                math.isclose(
                    score,
                    best_score,
                    rel_tol=0.0,
                    abs_tol=1.0e-15,
                )
                and (
                    design_to_holdout
                    > best_holdout_distance
                )
            )
        )

        if better:
            best_points = interior
            best_index = candidate_index
            best_score = score
            best_holdout_distance = (
                design_to_holdout
            )

    if (
        best_points is None
        or best_index is None
    ):
        raise RuntimeError(
            "No deterministic LHS candidate satisfies "
            "the governed holdout-separation requirement."
        )

    return (
        best_points,
        best_index,
        best_score,
        best_holdout_distance,
    )


def _map_normalized_point_to_case(
    *,
    policy: ProductionDoePolicy,
    coordinates: tuple[
        float,
        float,
        float,
    ],
) -> ThreadROMCase:
    preload_x, grip_x, radial_x = (
        coordinates
    )

    preload_n = (
        policy.preload_min_n
        + (
            policy.preload_max_n
            - policy.preload_min_n
        )
        * preload_x
    )

    head_thickness_mm = (
        policy.head_thickness_min_mm
        + (
            policy.head_thickness_max_mm
            - policy.head_thickness_min_mm
        )
        * grip_x
    )

    nut_thickness_mm = (
        policy.total_grip_mm
        - head_thickness_mm
    )

    radial_fraction = (
        policy.radial_fraction_min
        + (
            policy.radial_fraction_max
            - policy.radial_fraction_min
        )
        * radial_x
    )

    outer_diameter_mm = (
        policy.outer_diameter_start_mm
        + (
            policy.outer_diameter_end_mm
            - policy.outer_diameter_start_mm
        )
        * radial_fraction
    )

    clearance_hole_mm = (
        policy.clearance_hole_start_mm
        + (
            policy.clearance_hole_end_mm
            - policy.clearance_hole_start_mm
        )
        * radial_fraction
    )

    baseline = (
        phase2_certification_case()
    )

    head_member, nut_member = (
        baseline.members.layers
    )

    return replace(
        baseline,
        loading=replace(
            baseline.loading,
            target_preload_n=preload_n,
        ),
        members=replace(
            baseline.members,
            layers=(
                replace(
                    head_member,
                    thickness_mm=(
                        head_thickness_mm
                    ),
                    outer_diameter_mm=(
                        outer_diameter_mm
                    ),
                    clearance_hole_diameter_mm=(
                        clearance_hole_mm
                    ),
                ),
                replace(
                    nut_member,
                    thickness_mm=(
                        nut_thickness_mm
                    ),
                    outer_diameter_mm=(
                        outer_diameter_mm
                    ),
                    clearance_hole_diameter_mm=(
                        clearance_hole_mm
                    ),
                ),
            ),
        ),
    )


def _mesh_policy_name(
    *,
    policy: ProductionDoePolicy,
    coordinates: tuple[
        float,
        float,
        float,
    ],
) -> str:
    radial_x = coordinates[2]

    if radial_x == 0.0:
        return "medium"

    return (
        policy.radial_variation_mesh_policy_name
    )


def _generated_case(
    *,
    policy: ProductionDoePolicy,
    case_id: str,
    role: str,
    coordinates: tuple[
        float,
        float,
        float,
    ],
    source_case_id: str | None = None,
) -> ProductionDoeCase:
    case = _map_normalized_point_to_case(
        policy=policy,
        coordinates=coordinates,
    )

    return ProductionDoeCase(
        case_id=case_id,
        role=role,
        normalized_coordinates=(
            coordinates
        ),
        case=case,
        case_hash=case_sha256(
            case
        ),
        mesh_policy_name=(
            _mesh_policy_name(
                policy=policy,
                coordinates=coordinates,
            )
        ),
        source_case_id=source_case_id,
    )


def build_phase3_production_doe(
    policy: ProductionDoePolicy,
) -> ProductionDoeCampaign:
    """Build the frozen deterministic CP8 production campaign."""

    fixed_specs = (
        policy.existing_anchors
        + policy.mandatory_design_points
    )

    fixed_coordinates = tuple(
        point.normalized_coordinates
        for point in fixed_specs
    )

    if len(
        set(fixed_coordinates)
    ) != len(fixed_coordinates):
        raise ValueError(
            "Fixed Production DOE coordinates must be unique."
        )

    interior, candidate_index, _, _ = (
        _select_maximin_lhs(
            policy=policy,
            fixed_design_points=(
                fixed_coordinates
            ),
        )
    )

    design_cases: list[
        ProductionDoeCase
    ] = []

    # Existing certified anchors.
    for point in policy.existing_anchors:
        design_cases.append(
            _generated_case(
                policy=policy,
                case_id=point.case_id,
                role="PRODUCTION_DESIGN",
                coordinates=(
                    point.normalized_coordinates
                ),
                source_case_id=(
                    point.source_case_id
                ),
            )
        )

    # Explicit missing cube corners.
    for point in (
        policy.mandatory_design_points
    ):
        design_cases.append(
            _generated_case(
                policy=policy,
                case_id=point.case_id,
                role=(
                    "PRODUCTION_DOMAIN_BOUNDARY_SENTINEL"
                ),
                coordinates=(
                    point.normalized_coordinates
                ),
            )
        )

    # Interior deterministic maximin-LHS rows.
    for index, coordinates in enumerate(
        interior,
        start=1,
    ):
        design_cases.append(
            _generated_case(
                policy=policy,
                case_id=(
                    f"D-INT-{index:03d}"
                ),
                role="PRODUCTION_DESIGN",
                coordinates=coordinates,
            )
        )

    holdout_cases = tuple(
        _generated_case(
            policy=policy,
            case_id=point.case_id,
            role="BLIND_HOLDOUT",
            coordinates=(
                point.normalized_coordinates
            ),
        )
        for point in policy.holdout_points
    )

    design_tuple = tuple(
        design_cases
    )

    if (
        len(design_tuple)
        != policy.design_rows_total
    ):
        raise RuntimeError(
            "Generated Production DOE design count "
            "does not match frozen policy."
        )

    if (
        len(holdout_cases)
        != policy.blind_holdout_rows
    ):
        raise RuntimeError(
            "Generated holdout count does not match "
            "frozen policy."
        )

    all_cases = (
        design_tuple
        + holdout_cases
    )

    all_hashes = tuple(
        case.case_hash
        for case in all_cases
    )

    if len(
        set(all_hashes)
    ) != len(all_hashes):
        raise RuntimeError(
            "Generated Production DOE contains duplicate "
            "canonical physical case hashes."
        )

    all_coordinates = tuple(
        case.normalized_coordinates
        for case in all_cases
    )

    if len(
        set(all_coordinates)
    ) != len(all_coordinates):
        raise RuntimeError(
            "Generated Production DOE contains duplicate "
            "normalized coordinates."
        )

    design_coordinates = tuple(
        case.normalized_coordinates
        for case in design_tuple
    )

    holdout_coordinates = tuple(
        case.normalized_coordinates
        for case in holdout_cases
    )

    design_minimum = (
        _minimum_pairwise_distance(
            design_coordinates
        )
    )

    holdout_minimum = (
        _minimum_cross_distance(
            design_coordinates,
            holdout_coordinates,
        )
    )

    if (
        holdout_minimum
        + 1.0e-15
        < policy.holdout_minimum_distance
    ):
        raise RuntimeError(
            "Generated Production DOE violates frozen "
            "design-to-holdout separation."
        )

    # Prove that the four declared reusable anchors map EXACTLY onto
    # their CP7 pilot physical case definitions.
    pilot_cases = {
        item.case_id.value: item.case
        for item in (
            build_phase3_cp7_pilot_doe().cases
        )
    }

    for generated in design_tuple:
        if generated.source_case_id is None:
            continue

        try:
            pilot = pilot_cases[
                generated.source_case_id
            ]
        except KeyError as exc:
            raise RuntimeError(
                "Reusable DOE anchor references an "
                "unknown CP7 pilot case: "
                f"{generated.source_case_id}"
            ) from exc

        if (
            generated.case_hash
            != case_sha256(pilot)
        ):
            raise RuntimeError(
                "Reusable DOE anchor does not reproduce "
                "its declared CP7 physical case exactly: "
                f"{generated.case_id}"
            )

    return ProductionDoeCampaign(
        policy_id=policy.policy_id,
        design_cases=design_tuple,
        holdout_cases=holdout_cases,
        selected_lhs_candidate_index=(
            candidate_index
        ),
        selected_design_minimum_distance=(
            design_minimum
        ),
        minimum_design_to_holdout_distance=(
            holdout_minimum
        ),
    )

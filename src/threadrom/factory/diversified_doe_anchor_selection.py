"""Deterministic M10 historical design-anchor selection.

Selects existing indexed design states only. Does not generate
holdouts, certify evidence, admit training rows or authorize FEM.
"""

import hashlib
import json
import math
from dataclasses import dataclass


MANDATORY_BOUNDARY_IDS = frozenset(
    f"D-BND-{number:03d}" for number in range(1, 5)
)

EXPECTED_INTERIOR_IDS = frozenset(
    f"D-INT-{number:03d}" for number in range(1, 17)
)

EXPECTED_M10_IDS = (
    MANDATORY_BOUNDARY_IDS | EXPECTED_INTERIOR_IDS
)


@dataclass(frozen=True, slots=True)
class HistoricalAnchorSelection:
    selected_case_ids: tuple[str, ...]
    selected_case_hashes: tuple[str, ...]
    selected_coordinates: tuple[tuple[float, float, float], ...]
    retained_unselected_ids: tuple[str, ...]
    minimum_selected_pairwise_distance: float
    evidence_admission_authorized: bool = False
    fem_execution_authorized: bool = False


def select_m10_historical_anchors(
    policy: dict,
    atlas_bytes: bytes,
) -> HistoricalAnchorSelection:
    """Select four registered boundary states and eight spread interiors."""
    if (
        policy["identity"]["status"] != "draft_not_authorized"
        or policy["governance"]["solver_launch_authorized"]
        or policy["governance"]["sealed_holdout_access_authorized"]
        or policy["governance"]["dataset_admission_authorized"]
        or policy["design_governance"]["candidate_generation_authorized"]
        or policy["design_governance"]["design_size_frozen"]
        or policy["design_governance"]["holdout_allocation_frozen"]
    ):
        raise RuntimeError(
            "Anchor selection requires the unapproved, fail-closed draft."
        )

    if (
        policy["provisional_allocation"]["status"]
        != "proposal_only_not_frozen"
        or policy["provisional_allocation"]["design_slots_per_cohort"]
        != 12
    ):
        raise RuntimeError("Unexpected provisional design allocation.")

    if hashlib.sha256(atlas_bytes).hexdigest() != (
        policy["provenance"]["baseline_atlas_sha256"]
    ):
        raise RuntimeError("Historical atlas differs from pinned baseline.")

    atlas = json.loads(atlas_bytes.decode("utf-8-sig"))
    cases = atlas["cases"]

    if (
        len(cases) != 22
        or atlas["acceptance_source_count"] != 22
        or len({row["case_id"] for row in cases}) != 22
        or len({row["case_hash"] for row in cases}) != 22
    ):
        raise RuntimeError("Unexpected historical atlas inventory.")

    selected_pool = {}

    for row in cases:
        inputs = row["engineering_inputs"]

        if inputs["thread_designation"] != "M10x1.5":
            continue

        case_id = row["case_id"]

        if case_id not in EXPECTED_M10_IDS:
            raise RuntimeError("Unexpected M10 design identity.")

        coords = inputs["normalized_coordinates"]

        if (
            inputs["configuration_status"]
            != "C01_POLICY_AND_CASE_COORDINATES_VERIFIED"
            or row["rom_admission_status"] != "NOT_EVALUATED"
            or row["dataset_partition"] is not None
            or not row["evidence"]
            or not isinstance(coords, list)
            or len(coords) != 3
            or any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value < 0.0
                or value > 1.0
                for value in coords
            )
        ):
            raise RuntimeError(
                f"Unverified or invalid historical M10 state: {case_id}"
            )

        selected_pool[case_id] = (
            row["case_hash"],
            tuple(float(value) for value in coords),
        )

    if set(selected_pool) != EXPECTED_M10_IDS:
        raise RuntimeError(
            "Expected exactly four registered boundary states "
            "and sixteen registered interior states."
        )

    chosen = sorted(MANDATORY_BOUNDARY_IDS)
    remaining = sorted(EXPECTED_INTERIOR_IDS)

    while len(chosen) < 12:
        def distance_to_selection(case_id):
            point = selected_pool[case_id][1]
            return min(
                math.dist(point, selected_pool[existing][1])
                for existing in chosen
            )

        next_id = min(
            remaining,
            key=lambda case_id: (
                -distance_to_selection(case_id),
                case_id,
            ),
        )
        chosen.append(next_id)
        remaining.remove(next_id)

    coordinates = tuple(
        selected_pool[case_id][1] for case_id in chosen
    )

    minimum_distance = min(
        math.dist(coordinates[i], coordinates[j])
        for i in range(len(coordinates))
        for j in range(i + 1, len(coordinates))
    )

    return HistoricalAnchorSelection(
        selected_case_ids=tuple(chosen),
        selected_case_hashes=tuple(
            selected_pool[case_id][0] for case_id in chosen
        ),
        selected_coordinates=coordinates,
        retained_unselected_ids=tuple(sorted(remaining)),
        minimum_selected_pairwise_distance=minimum_distance,
    )

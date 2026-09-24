"""Deterministic, design-only diversified DOE proposal generator.

No validation/holdout configurations, geometry, mesh, solver jobs,
acceptance records or dataset admissions are created by this module.
The proposal requires explicit candidate-generation authorization;
it never grants FEM execution authorization.
"""

import hashlib
import json
import math
from dataclasses import dataclass, replace
from itertools import product

from threadrom.case.reference_cases import phase2_certification_case
from threadrom.case.serialization import case_sha256
from threadrom.case.standards import resolve_metric_thread_standard
from threadrom.engineering.metric_thread import (
    calculate_metric_thread_basic_dimensions,
)


GRID = (0.0, 0.25, 0.5, 0.75, 1.0)
M10_BOUNDARY_IDS = frozenset(
    f"D-BND-{i:03d}" for i in range(1, 5)
)


@dataclass(frozen=True, slots=True)
class DoeDesignProposal:
    proposal_id: str
    thread_designation: str
    member_material_id: str
    normalized_coordinates: tuple[float, float, float]
    case_hash: str
    indexed_case_id: str | None
    product_case: object | None
    evidence_status: str
    fem_execution_authorized: bool = False
    dataset_admission_authorized: bool = False


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _stress_area(designation):
    standard = resolve_metric_thread_standard(designation)
    return calculate_metric_thread_basic_dimensions(
        standard.nominal_diameter_mm,
        standard.pitch_mm,
    ).tensile_stress_area_mm2


def _physical_signature(
    designation, member_material, preload, upper, lower, outer, hole
):
    """Conservative duplicate screen; not a substitute for case hashing."""
    return (
        designation,
        member_material,
        *(
            round(float(value), 8)
            for value in (preload, upper, lower, outer, hole)
        ),
    )


def _build_case(policy, size, member_material, point):
    x, y, z = point
    base = phase2_certification_case()
    geometry = policy["candidate_geometry"]
    preload_policy = policy["candidate_preload"]

    d = float(size["nominal_diameter_mm"])
    grip = float(size["total_grip_mm"])

    head_fraction = (
        geometry["head_member_grip_fraction_min"]
        + y * (
            geometry["head_member_grip_fraction_max"]
            - geometry["head_member_grip_fraction_min"]
        )
    )

    head_thickness = grip * head_fraction
    nut_thickness = grip - head_thickness

    outer_ratio = (
        geometry["member_outer_diameter_over_nominal_diameter_min"]
        + z * (
            geometry["member_outer_diameter_over_nominal_diameter_max"]
            - geometry["member_outer_diameter_over_nominal_diameter_min"]
        )
    )

    hole_ratio = (
        geometry["clearance_hole_over_nominal_diameter_min"]
        + z * (
            geometry["clearance_hole_over_nominal_diameter_max"]
            - geometry["clearance_hole_over_nominal_diameter_min"]
        )
    )

    reference_stress = (
        preload_policy["reference_preload_n"]
        / _stress_area(
            preload_policy["reference_thread_designation"]
        )
    )

    nominal_stress_ratio = (
        preload_policy["ratio_min"]
        + x * (
            preload_policy["ratio_max"]
            - preload_policy["ratio_min"]
        )
    )

    requested_preload = (
        reference_stress
        * _stress_area(size["designation"])
        * nominal_stress_ratio
    )

    upper, lower = base.members.layers

    candidate = replace(
        base,
        fastener=replace(
            base.fastener,
            thread_designation=size["designation"],
            bolt_length_mm=float(size["bolt_length_mm"]),
        ),
        members=replace(
            base.members,
            layers=(
                replace(
                    upper,
                    thickness_mm=head_thickness,
                    outer_diameter_mm=d * outer_ratio,
                    clearance_hole_diameter_mm=d * hole_ratio,
                    material_id=member_material,
                ),
                replace(
                    lower,
                    thickness_mm=nut_thickness,
                    outer_diameter_mm=d * outer_ratio,
                    clearance_hole_diameter_mm=d * hole_ratio,
                    material_id=member_material,
                ),
            ),
        ),
        loading=replace(
            base.loading,
            target_preload_n=requested_preload,
            external_axial_load_n=0.0,
        ),
        metadata=replace(
            base.metadata,
            name="Phase 3 diversified DOE design proposal",
            notes=(
                "Unsealed design proposal; no FEM authorization "
                "or physics certification."
            ),
        ),
    )

    signature = _physical_signature(
        size["designation"],
        member_material,
        requested_preload,
        head_thickness,
        nut_thickness,
        d * outer_ratio,
        d * hole_ratio,
    )

    return candidate, signature


def _select_points(existing, count):
    """Deterministic maximin selection on a declared 5-level design grid."""
    chosen = list(existing)
    pool = [
        tuple(float(value) for value in point)
        for point in product(GRID, repeat=3)
        if tuple(float(value) for value in point) not in chosen
    ]

    while len(chosen) < count:
        if not chosen:
            next_point = (0.0, 0.0, 0.0)
        else:
            next_point = min(
                pool,
                key=lambda point: (
                    -min(
                        math.dist(point, prior)
                        for prior in chosen
                    ),
                    point,
                ),
            )

        chosen.append(next_point)
        pool.remove(next_point)

    return tuple(chosen)


def propose_diversified_design(
    policy,
    atlas_bytes,
    *,
    m10_anchor_selection,
):
    """Return 72 design proposals only, with no persistent side effects."""
    governance = policy["governance"]
    design = policy["design_governance"]
    allocation = policy["provisional_allocation"]

    _require(
        policy["identity"]["status"] == "draft_not_authorized"
        and design["candidate_generation_authorized"] is True
        and allocation["status"] == "proposal_only_not_frozen",
        "Explicit design-generation authorization is required.",
    )

    _require(
        not any((
            governance["solver_launch_authorized"],
            governance["geometry_or_mesh_execution_authorized"],
            governance["dataset_admission_authorized"],
            governance["sealed_holdout_access_authorized"],
            design["design_size_frozen"],
            design["holdout_allocation_frozen"],
            policy["candidate_member_material"][
                "solver_launch_authorized"
            ],
        )),
        "Unexpected FEM, dataset, holdout or design-freeze authorization.",
    )

    _require(
        hashlib.sha256(atlas_bytes).hexdigest()
        == policy["provenance"]["baseline_atlas_sha256"],
        "Atlas differs from the pinned historical baseline.",
    )

    atlas = json.loads(atlas_bytes.decode("utf-8-sig"))
    rows = atlas["cases"]

    _require(
        len(rows) == atlas["acceptance_source_count"] == 22
        and len({row["case_id"] for row in rows}) == 22
        and len({row["case_hash"] for row in rows}) == 22,
        "Unexpected historical atlas inventory.",
    )

    by_id = {row["case_id"]: row for row in rows}
    selected_ids = m10_anchor_selection.selected_case_ids
    selected_hashes = m10_anchor_selection.selected_case_hashes
    selected_coords = m10_anchor_selection.selected_coordinates

    _require(
        len(selected_ids) == len(set(selected_ids)) == 12
        and M10_BOUNDARY_IDS.issubset(selected_ids)
        and len(selected_hashes) == len(selected_coords) == 12
        and not m10_anchor_selection.evidence_admission_authorized
        and not m10_anchor_selection.fem_execution_authorized,
        "M10 historical anchor selection is invalid.",
    )

    for case_id, case_hash, coords in zip(
        selected_ids, selected_hashes, selected_coords
    ):
        row = by_id.get(case_id)
        _require(
            row is not None
            and row["case_hash"] == case_hash
            and tuple(row["engineering_inputs"]["normalized_coordinates"])
            == coords,
            f"Historical anchor differs from pinned atlas: {case_id}",
        )

    sizes = tuple(policy["size_candidates"])
    _require(
        [size["designation"] for size in sizes]
        == ["M8x1.25", "M10x1.5", "M12x1.75"],
        "Unexpected size policy.",
    )

    member_ids = (
        policy["baseline_materials"]["member_material_id"],
        policy["candidate_member_material"]["material_id"],
    )

    _require(
        member_ids == (
            "steel_member",
            "member_aluminium_en_aw_6082_t6",
        )
        and allocation["design_slots_per_cohort"] == 12,
        "Unexpected provisional cohort allocation.",
    )

    historical_signatures = set()

    for row in rows:
        inputs = row["engineering_inputs"]
        historical_signatures.add(
            _physical_signature(
                inputs["thread_designation"],
                inputs["head_member_material_id"],
                inputs["target_preload_n"],
                inputs["head_member_thickness_mm"],
                inputs["nut_member_thickness_mm"],
                inputs["member_outer_diameter_mm"],
                inputs["member_clearance_hole_diameter_mm"],
            )
        )

    sentinel_points = {
        "M8x1.25": ("TRM-XFEM-M8-001", (1.0, 1.0, 0.0)),
        "M12x1.75": ("TRM-XFEM-M12-001", (1.0, 1.0, 0.0)),
    }

    proposals = []
    seen_hashes = set()
    seen_signatures = set()

    for size in sizes:
        designation = size["designation"]

        for member_id in member_ids:
            cohort_name = (
                designation.replace(".", "_").replace("x", "x")
                + "__"
                + member_id
            )

            anchored = []
            points = ()

            if designation == "M10x1.5" and member_id == "steel_member":
                points = tuple(selected_coords)
                anchored = list(selected_ids)

            elif member_id == "steel_member":
                sentinel_id, sentinel_point = sentinel_points[designation]
                sentinel = by_id[sentinel_id]

                _require(
                    sentinel["engineering_inputs"]["thread_designation"]
                    == designation
                    and sentinel["engineering_inputs"][
                        "head_member_material_id"
                    ] == "steel_member",
                    "Cross-size anchor differs from its expected cohort.",
                )

                points = _select_points(
                    (sentinel_point,),
                    12,
                )
                anchored = [sentinel_id]

            else:
                points = _select_points((), 12)

            _require(
                len(points) == len(set(points)) == 12,
                "Design cohort contains duplicate coordinates.",
            )

            for index, point in enumerate(points):
                case_id = (
                    f"TRM-DDOE-D-{cohort_name}-{index + 1:02d}"
                )

                anchor_id = (
                    anchored[index]
                    if index < len(anchored)
                    else None
                )

                if anchor_id is not None:
                    record = by_id[anchor_id]
                    case_hash = record["case_hash"]
                    product_case = None
                    status = "EXACT_HISTORICAL_ANCHOR_ADMISSION_PENDING"

                else:
                    product_case, signature = _build_case(
                        policy, size, member_id, point
                    )
                    case_hash = case_sha256(product_case)

                    _require(
                        signature not in historical_signatures,
                        "New proposal reproduces historical physical inputs; "
                        "reuse must be resolved before FEM.",
                    )

                    _require(
                        signature not in seen_signatures,
                        "Duplicate proposed physical configuration.",
                    )

                    _require(
                        case_hash not in {
                            row["case_hash"] for row in rows
                        },
                        "New proposal has an existing canonical case hash.",
                    )

                    seen_signatures.add(signature)
                    status = "NEW_EVIDENCE_REQUIRED_NO_EXECUTION_AUTHORITY"

                _require(
                    case_hash not in seen_hashes,
                    "Duplicate canonical case hash in design proposal.",
                )

                seen_hashes.add(case_hash)

                proposals.append(
                    DoeDesignProposal(
                        proposal_id=case_id,
                        thread_designation=designation,
                        member_material_id=member_id,
                        normalized_coordinates=point,
                        case_hash=case_hash,
                        indexed_case_id=anchor_id,
                        product_case=product_case,
                        evidence_status=status,
                    )
                )

    _require(
        len(proposals) == 72
        and sum(
            row.indexed_case_id is not None
            for row in proposals
        ) == 14
        and sum(
            row.product_case is not None
            for row in proposals
        ) == 58,
        "Design proposal counts differ from the expected allocation.",
    )

    return tuple(proposals)

"""Read-only, fail-closed diversified DOE candidate/atlas comparison.

An indexed case is NOT automatically admitted to the new DOE dataset.
A new case is NOT automatically authorized for FEM execution.
No DOE generation, holdout access, solver or filesystem writes occur here.
"""

import hashlib
import json
import math
from dataclasses import dataclass

from threadrom.case.serialization import case_sha256
from threadrom.case.standards import resolve_metric_thread_standard
from threadrom.engineering.metric_thread import (
    calculate_metric_thread_basic_dimensions,
)


@dataclass(frozen=True, slots=True)
class DoeReusePreview:
    case_hash: str
    thread_designation: str
    member_material_id: str
    indexed_case_id: str | None
    evidence_status: str
    dataset_admission_status: str
    fem_execution_authorized: bool


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _close(actual, expected, *, tolerance=1e-8):
    return math.isfinite(actual) and math.isclose(
        actual,
        expected,
        rel_tol=0.0,
        abs_tol=tolerance,
    )


def _stress_area(designation):
    standard = resolve_metric_thread_standard(designation)
    dimensions = calculate_metric_thread_basic_dimensions(
        standard.nominal_diameter_mm,
        standard.pitch_mm,
    )
    return dimensions.tensile_stress_area_mm2


def preview_case_against_baseline_atlas(
    case,
    *,
    policy,
    atlas_bytes: bytes,
) -> DoeReusePreview:
    """Classify one supplied, unsealed product case without authorizing it."""
    _require(
        policy["identity"]["status"] == "draft_not_authorized",
        "Expected the unapproved diversified DOE draft.",
    )

    governance = policy["governance"]
    design = policy["design_governance"]

    _require(
        not any((
            governance["solver_launch_authorized"],
            governance["geometry_or_mesh_execution_authorized"],
            governance["dataset_admission_authorized"],
            governance["sealed_holdout_access_authorized"],
            design["candidate_generation_authorized"],
            design["design_size_frozen"],
            design["holdout_allocation_frozen"],
        )),
        "Unexpected DOE generation, freeze or execution authorization.",
    )

    _require(
        hashlib.sha256(atlas_bytes).hexdigest()
        == policy["provenance"]["baseline_atlas_sha256"],
        "Atlas does not match the policy-pinned historical baseline.",
    )

    atlas = json.loads(atlas_bytes.decode("utf-8-sig"))
    atlas_cases = atlas["cases"]

    _require(
        len(atlas_cases) == 22
        and atlas["acceptance_source_count"] == 22
        and len({row["case_hash"] for row in atlas_cases}) == 22
        and len({row["case_id"] for row in atlas_cases}) == 22,
        "Unexpected historical atlas inventory.",
    )

    fastener = case.fastener
    layers = tuple(case.members.layers)
    loading = case.loading
    interfaces = case.interfaces

    _require(len(layers) == 2, "Exactly two clamped members required.")
    upper, lower = layers

    baseline = policy["baseline_materials"]
    candidate_member = policy["candidate_member_material"]
    cohort = policy["baseline_cohort"]

    designation = fastener.thread_designation

    _require(
        designation in cohort["thread_designations"],
        "Thread designation is outside the proposed size cohort.",
    )

    _require(
        fastener.bolt_material_id
        == fastener.nut_material_id
        == baseline["fastener_material_id"],
        "Unsupported fastener material pairing.",
    )

    _require(
        fastener.bolt_property_class == baseline["bolt_property_class"]
        and fastener.nut_property_class == baseline["nut_property_class"],
        "Unsupported fastener property-class pairing.",
    )

    _require(
        upper.material_id == lower.material_id
        and upper.material_id in {
            baseline["member_material_id"],
            candidate_member["material_id"],
        },
        "Unsupported or unequal clamped-member materials.",
    )

    _require(
        loading.external_axial_load_n
        == cohort["fixed_external_axial_load_n"],
        "Nonzero external axial load is not qualified for this cohort.",
    )

    friction = (
        interfaces.thread_friction_coefficient,
        interfaces.head_bearing_friction_coefficient,
        interfaces.nut_bearing_friction_coefficient,
        interfaces.member_interface_friction_coefficient,
    )

    _require(
        all(
            _close(value, 0.15, tolerance=1e-12)
            for value in friction
        ),
        "Only common friction 0.15 is in the proposed cohort.",
    )

    sizes = {
        row["designation"]: row
        for row in policy["size_candidates"]
    }

    _require(
        len(sizes) == 3 and designation in sizes,
        "Unexpected size-candidate policy.",
    )

    size = sizes[designation]
    diameter = size["nominal_diameter_mm"]
    geometry = policy["candidate_geometry"]

    _require(
        _close(fastener.bolt_length_mm, size["bolt_length_mm"]),
        "Unsupported candidate bolt length.",
    )

    _require(
        upper.layer_id == "head_side_member"
        and lower.layer_id == "nut_side_member",
        "Unexpected member-stack identities.",
    )

    _require(
        _close(
            upper.thickness_mm + lower.thickness_mm,
            size["total_grip_mm"],
        ),
        "Candidate total grip differs from the proposed size policy.",
    )

    head_fraction = (
        upper.thickness_mm / size["total_grip_mm"]
    )

    _require(
        geometry["head_member_grip_fraction_min"] - 1e-10
        <= head_fraction
        <= geometry["head_member_grip_fraction_max"] + 1e-10,
        "Head-side grip fraction outside proposed bounds.",
    )

    _require(
        _close(
            upper.outer_diameter_mm,
            lower.outer_diameter_mm,
        )
        and _close(
            upper.clearance_hole_diameter_mm,
            lower.clearance_hole_diameter_mm,
        ),
        "The proposed cohort requires shared member radial geometry.",
    )

    outer_ratio = upper.outer_diameter_mm / diameter
    hole_ratio = upper.clearance_hole_diameter_mm / diameter

    _require(
        geometry["member_outer_diameter_over_nominal_diameter_min"]
        - 1e-10
        <= outer_ratio
        <= geometry["member_outer_diameter_over_nominal_diameter_max"]
        + 1e-10,
        "Member outer diameter outside proposed bounds.",
    )

    _require(
        geometry["clearance_hole_over_nominal_diameter_min"]
        - 1e-10
        <= hole_ratio
        <= geometry["clearance_hole_over_nominal_diameter_max"]
        + 1e-10,
        "Clearance-hole diameter outside proposed bounds.",
    )

    outer_fraction = (
        outer_ratio
        - geometry["member_outer_diameter_over_nominal_diameter_min"]
    ) / (
        geometry["member_outer_diameter_over_nominal_diameter_max"]
        - geometry["member_outer_diameter_over_nominal_diameter_min"]
    )

    hole_fraction = (
        hole_ratio
        - geometry["clearance_hole_over_nominal_diameter_min"]
    ) / (
        geometry["clearance_hole_over_nominal_diameter_max"]
        - geometry["clearance_hole_over_nominal_diameter_min"]
    )

    _require(
        _close(outer_fraction, hole_fraction, tolerance=1e-7),
        "Outer diameter and clearance hole do not share "
        "the proposed radial coordinate.",
    )

    preload_policy = policy["candidate_preload"]

    reference_stress = (
        preload_policy["reference_preload_n"]
        / _stress_area(
            preload_policy["reference_thread_designation"]
        )
    )

    requested_stress = (
        loading.target_preload_n / _stress_area(designation)
    )

    preload_ratio = requested_stress / reference_stress

    _require(
        math.isfinite(preload_ratio)
        and preload_policy["ratio_min"] - 1e-10
        <= preload_ratio
        <= preload_policy["ratio_max"] + 1e-10,
        "Requested preload outside the proposed stress-ratio bounds.",
    )

    candidate_hash = case_sha256(case)

    matches = [
        row for row in atlas_cases
        if row["case_hash"] == candidate_hash
    ]

    _require(
        len(matches) <= 1,
        "Duplicate historical canonical case hash.",
    )

    if matches:
        match = matches[0]

        _require(
            match["engineering_inputs"]["configuration_status"]
            in {
                "C01_POLICY_AND_CASE_COORDINATES_VERIFIED",
                "CROSS_SIZE_CANONICAL_CASE_HASH_VERIFIED",
            }
            and match["rom_admission_status"] == "NOT_EVALUATED"
            and match["dataset_partition"] is None
            and bool(match["evidence"]),
            "Exact atlas identity lacks the expected baseline "
            "configuration/evidence status.",
        )

        indexed_id = match["case_id"]
        status = "EXACT_HASH_INDEXED_ADMISSION_PENDING"
    else:
        indexed_id = None
        status = "NO_EXACT_HASH_MATCH_NEW_EVIDENCE_REQUIRED"

    return DoeReusePreview(
        case_hash=candidate_hash,
        thread_designation=designation,
        member_material_id=upper.material_id,
        indexed_case_id=indexed_id,
        evidence_status=status,
        dataset_admission_status="NOT_EVALUATED",
        fem_execution_authorized=False,
    )

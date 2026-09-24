"""Planning-only allocation for the Phase-3 diversified DOE.

This module counts proposed slots and historical atlas metadata.
It does NOT generate physical cases, assign holdout configurations,
admit historical evidence, authorize execution, or freeze a design.
"""

from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DoeCohortBudget:
    thread_designation: str
    member_material_id: str
    design_slots: int
    sealed_validation_slots: int
    indexed_historical_states: int
    potential_reuse_ceiling: int


@dataclass(frozen=True, slots=True)
class DoePlanningPreview:
    cohorts: tuple[DoeCohortBudget, ...]
    design_slots: int
    sealed_validation_slots: int
    total_proposed_states: int
    indexed_historical_states: int
    potential_reuse_ceiling: int
    new_state_floor_if_all_reuse_qualifies: int
    new_state_ceiling_without_reuse: int


def preview_diversified_doe_allocation(policy, atlas):
    """Return a NON-EXECUTABLE planning budget, without case generation."""
    identity = policy["identity"]
    governance = policy["governance"]
    design = policy["design_governance"]
    allocation = policy["provisional_allocation"]

    if identity["status"] != "draft_not_authorized":
        raise RuntimeError("Expected an unapproved DOE planning draft.")

    if any((
        governance["solver_launch_authorized"],
        governance["geometry_or_mesh_execution_authorized"],
        governance["dataset_admission_authorized"],
        governance["sealed_holdout_access_authorized"],
        design["candidate_generation_authorized"],
        design["design_size_frozen"],
        design["holdout_allocation_frozen"],
    )):
        raise RuntimeError(
            "Planning preview requires all execution, generation, "
            "admission and design-freeze gates to remain closed."
        )

    if allocation["status"] != "proposal_only_not_frozen":
        raise RuntimeError("Unexpected DOE allocation status.")

    design_per_cohort = allocation["design_slots_per_cohort"]
    validation_per_cohort = allocation[
        "sealed_validation_slots_per_cohort"
    ]

    if (
        not isinstance(design_per_cohort, int)
        or isinstance(design_per_cohort, bool)
        or design_per_cohort < 1
        or not isinstance(validation_per_cohort, int)
        or isinstance(validation_per_cohort, bool)
        or validation_per_cohort < 1
    ):
        raise RuntimeError("Invalid proposed cohort allocation.")

    sizes = tuple(
        policy["baseline_cohort"]["thread_designations"]
    )
    members = (
        policy["baseline_materials"]["member_material_id"],
        policy["candidate_member_material"]["material_id"],
    )

    if (
        sizes != ("M8x1.25", "M10x1.5", "M12x1.75")
        or len(set(members)) != 2
        or members[1] != "member_aluminium_en_aw_6082_t6"
        or policy["candidate_member_material"]["status"]
        != "source_backed_not_fem_certified"
    ):
        raise RuntimeError("Unexpected candidate cohort definitions.")

    if any((
        policy["candidate_member_material"][
            "solver_launch_authorized"
        ],
        policy["material_expansion"]["solver_launch_authorized"],
        policy["external_load_expansion"]["solver_launch_authorized"],
        policy["friction_expansion"]["solver_launch_authorized"],
    )):
        raise RuntimeError(
            "An unqualified expansion has been authorized."
        )

    cases = atlas["cases"]

    if (
        len(cases) != 22
        or atlas["acceptance_source_count"] != 22
        or len({case["case_hash"] for case in cases}) != 22
    ):
        raise RuntimeError("Unexpected historical atlas inventory.")

    counts = Counter()
    baseline_fastener = policy["baseline_materials"][
        "fastener_material_id"
    ]

    verified_statuses = {
        "C01_POLICY_AND_CASE_COORDINATES_VERIFIED",
        "CROSS_SIZE_CANONICAL_CASE_HASH_VERIFIED",
    }

    for case in cases:
        inputs = case["engineering_inputs"]

        if (
            inputs["configuration_status"] not in verified_statuses
            or case["rom_admission_status"] != "NOT_EVALUATED"
            or case["dataset_partition"] is not None
            or not case["evidence"]
        ):
            raise RuntimeError(
                "Historical evidence has unexpected configuration "
                "or dataset-admission status."
            )

        thread = inputs["thread_designation"]
        upper_material = inputs["head_member_material_id"]
        lower_material = inputs["nut_member_material_id"]

        if (
            thread not in sizes
            or inputs["bolt_material_id"] != baseline_fastener
            or inputs["nut_material_id"] != baseline_fastener
            or upper_material != lower_material
            or upper_material != members[0]
            or inputs["external_axial_load_n"] != 0.0
        ):
            raise RuntimeError(
                "Historical case differs from the expected "
                "steel/zero-external-load baseline."
            )

        for key in (
            "thread_friction_coefficient",
            "head_bearing_friction_coefficient",
            "nut_bearing_friction_coefficient",
            "member_interface_friction_coefficient",
        ):
            if inputs[key] != 0.15:
                raise RuntimeError(
                    "Unexpected historical friction configuration."
                )

        counts[(thread, upper_material)] += 1

    cohorts = tuple(
        DoeCohortBudget(
            thread_designation=thread,
            member_material_id=member_material,
            design_slots=design_per_cohort,
            sealed_validation_slots=validation_per_cohort,
            indexed_historical_states=counts[
                (thread, member_material)
            ],
            potential_reuse_ceiling=min(
                design_per_cohort,
                counts[(thread, member_material)],
            ),
        )
        for thread in sizes
        for member_material in members
    )

    if len(cohorts) != 6:
        raise RuntimeError("Expected six size/material cohorts.")

    design_total = sum(row.design_slots for row in cohorts)
    validation_total = sum(
        row.sealed_validation_slots for row in cohorts
    )
    total = design_total + validation_total
    potential_reuse = sum(
        row.potential_reuse_ceiling for row in cohorts
    )

    if (
        total != allocation["proposed_total_distinct_states"]
        or sum(row.indexed_historical_states for row in cohorts)
        != 22
    ):
        raise RuntimeError("DOE allocation or baseline count drift.")

    return DoePlanningPreview(
        cohorts=cohorts,
        design_slots=design_total,
        sealed_validation_slots=validation_total,
        total_proposed_states=total,
        indexed_historical_states=22,
        potential_reuse_ceiling=potential_reuse,
        new_state_floor_if_all_reuse_qualifies=(
            total - potential_reuse
        ),
        new_state_ceiling_without_reuse=total,
    )

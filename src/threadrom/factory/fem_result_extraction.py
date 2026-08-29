"""Generic governed extraction of FEM physics evidence."""

from __future__ import annotations

import gc
import json
import math
import tomllib

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

from threadrom.factory.fem_preload_calibration_measurement import (
    CalibrationContactPair,
    extract_clamp_force_measurement_from_dat,
)
from threadrom.postprocessing.calculix_frd_displacement import (
    read_targeted_frd_displacement_datasets,
    read_targeted_frd_stress_datasets,
)
from threadrom.postprocessing.calculix_nonlinear_progress import (
    AcceptedIncrement,
    parse_status_increments,
)
from threadrom.postprocessing.calculix_semantic_mechanics import (
    CompleteJointAxialStressState,
    CompleteJointDeformationState,
    derive_bolt_free_span_stress_region,
    summarize_complete_joint_axial_state,
    summarize_complete_joint_deformation,
)
from threadrom.postprocessing.calculix_thread_flank import (
    ThreadFlankStressState,
    summarize_engaged_bolt_thread_flanks,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    CompleteJointCalculixMeshData,
)


@dataclass(frozen=True, slots=True)
class FemResultExtractionPolicy:
    """Governed semantic regions used for FEM result interpretation."""

    policy_id: str

    bolt_component: str
    head_side_member_component: str
    nut_side_member_component: str

    bolt_free_span_band_start_fraction: float
    bolt_free_span_band_end_fraction: float

    under_head_surface: str
    head_member_bearing_surface: str
    nut_member_bearing_surface: str
    nut_thread_surface: str
    bolt_thread_surface: str

    def __post_init__(self) -> None:
        text_values = (
            self.policy_id,
            self.bolt_component,
            self.head_side_member_component,
            self.nut_side_member_component,
            self.under_head_surface,
            self.head_member_bearing_surface,
            self.nut_member_bearing_surface,
            self.nut_thread_surface,
            self.bolt_thread_surface,
        )

        if any(not value.strip() for value in text_values):
            raise ValueError(
                "FEM result-extraction semantic names must not be blank."
            )

        start = self.bolt_free_span_band_start_fraction
        end = self.bolt_free_span_band_end_fraction

        if (
            not math.isfinite(start)
            or not math.isfinite(end)
            or not 0.0 <= start < end <= 1.0
        ):
            raise ValueError(
                "Bolt free-span diagnostic fractions must satisfy "
                "0 <= start < end <= 1."
            )


@dataclass(frozen=True, slots=True)
class FemPhysicsResultEvidence:
    """Generic physics evidence extracted from one completed FEM solve."""

    extraction_policy_id: str

    final_step: int
    final_increment: int
    final_time: float

    thread_normal_force_n: float

    axial_state: CompleteJointAxialStressState
    deformation_state: CompleteJointDeformationState
    thread_flank_state: ThreadFlankStressState

    accepted_increments: tuple[AcceptedIncrement, ...]

    return_code: int | None
    stdout: str

    displacement_target_node_count: int
    stress_target_node_count: int


def _section(
    data: Mapping[str, object],
    name: str,
) -> Mapping[str, object]:
    value = data.get(name)

    if not isinstance(value, dict):
        raise TypeError(
            f"Missing or invalid FEM result-extraction section: {name}"
        )

    return value


def _string(
    data: Mapping[str, object],
    key: str,
) -> str:
    value = data.get(key)

    if not isinstance(value, str) or not value.strip():
        raise TypeError(
            f"Missing or invalid string value: {key}"
        )

    return value


def _number(
    data: Mapping[str, object],
    key: str,
) -> float:
    value = data.get(key)

    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise TypeError(
            f"Missing or invalid numeric value: {key}"
        )

    result = float(value)

    if not math.isfinite(result):
        raise ValueError(
            f"Non-finite numeric value: {key}"
        )

    return result


def load_fem_result_extraction_policy(
    path: Path,
) -> FemResultExtractionPolicy:
    """Load generic FEM semantic-result extraction configuration."""

    with path.open("rb") as stream:
        data = tomllib.load(stream)

    identity = _section(data, "identity")
    axial = _section(data, "axial_stress")
    surfaces = _section(data, "surfaces")

    return FemResultExtractionPolicy(
        policy_id=_string(
            identity,
            "policy_id",
        ),
        bolt_component=_string(
            axial,
            "bolt_component",
        ),
        head_side_member_component=_string(
            axial,
            "head_side_member_component",
        ),
        nut_side_member_component=_string(
            axial,
            "nut_side_member_component",
        ),
        bolt_free_span_band_start_fraction=_number(
            axial,
            "bolt_free_span_band_start_fraction",
        ),
        bolt_free_span_band_end_fraction=_number(
            axial,
            "bolt_free_span_band_end_fraction",
        ),
        under_head_surface=_string(
            surfaces,
            "under_head",
        ),
        head_member_bearing_surface=_string(
            surfaces,
            "head_member_bearing",
        ),
        nut_member_bearing_surface=_string(
            surfaces,
            "nut_member_bearing",
        ),
        nut_thread_surface=_string(
            surfaces,
            "nut_thread",
        ),
        bolt_thread_surface=_string(
            surfaces,
            "bolt_thread",
        ),
    )


def _required_component(
    mesh_data: CompleteJointCalculixMeshData,
    name: str,
):
    try:
        value = mesh_data.component_tetrahedra[name]
    except KeyError as error:
        raise RuntimeError(
            f"Required FEM volume component is absent: {name}"
        ) from error

    if value.ndim != 2 or value.shape[1] != 4 or len(value) == 0:
        raise RuntimeError(
            f"Invalid tetrahedral FEM component: {name}"
        )

    return value


def _required_surface(
    mesh_data: CompleteJointCalculixMeshData,
    name: str,
):
    try:
        value = mesh_data.boundary_triangles[name]
    except KeyError as error:
        raise RuntimeError(
            f"Required FEM semantic surface is absent: {name}"
        ) from error

    if value.ndim != 2 or value.shape[1] != 3 or len(value) == 0:
        raise RuntimeError(
            f"Invalid triangular FEM semantic surface: {name}"
        )

    return value


def _one_based_node_ids(
    *arrays,
) -> frozenset[int]:
    """Convert zero-based mesh connectivity to CalculiX node IDs."""

    if not arrays:
        raise ValueError(
            "At least one connectivity array is required."
        )

    return frozenset(
        int(node_index) + 1
        for array in arrays
        for node_index in np.unique(
            array.reshape(-1)
        )
    )


def _select_final_dataset(
    datasets,
    *,
    step: int,
    increment: int,
    kind: str,
):
    matches = tuple(
        dataset
        for dataset in datasets
        if (
            dataset.step == step
            and dataset.increment == increment
        )
    )

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one final {kind} dataset for "
            f"Step {step}, Increment {increment}; "
            f"found {len(matches)}."
        )

    return matches[0]


def _load_manifest_return_code(
    manifest_path: Path,
) -> int | None:
    data = json.loads(
        manifest_path.read_text(
            encoding="utf-8",
        )
    )

    value = data.get("return_code")

    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(
            "FEM manifest return_code must be an integer or null."
        )

    return value


def extract_fem_physics_result_evidence(
    *,
    mesh_data: CompleteJointCalculixMeshData,
    policy: FemResultExtractionPolicy,
    frd_path: Path,
    sta_path: Path,
    dat_path: Path,
    stdout_path: Path,
    manifest_path: Path,
    contact_pairs: tuple[CalibrationContactPair, ...],
    thermal_expansion_coefficient_per_c: float,
    equivalent_delta_temperature_c: float,
) -> FemPhysicsResultEvidence:
    """Extract generic physics states from one completed CalculiX run."""

    required_paths = (
        frd_path,
        sta_path,
        dat_path,
        stdout_path,
        manifest_path,
    )

    for path in required_paths:
        if not path.exists() or path.stat().st_size <= 0:
            raise FileNotFoundError(
                f"Required completed FEM artifact is absent or empty: {path}"
            )

    bolt_tetrahedra = _required_component(
        mesh_data,
        policy.bolt_component,
    )

    head_tetrahedra = _required_component(
        mesh_data,
        policy.head_side_member_component,
    )

    nut_tetrahedra = _required_component(
        mesh_data,
        policy.nut_side_member_component,
    )

    under_head = _required_surface(
        mesh_data,
        policy.under_head_surface,
    )

    head_bearing = _required_surface(
        mesh_data,
        policy.head_member_bearing_surface,
    )

    nut_bearing = _required_surface(
        mesh_data,
        policy.nut_member_bearing_surface,
    )

    nut_thread = _required_surface(
        mesh_data,
        policy.nut_thread_surface,
    )

    bolt_thread = _required_surface(
        mesh_data,
        policy.bolt_thread_surface,
    )

    accepted_increments = parse_status_increments(
        sta_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    )

    if not accepted_increments:
        raise RuntimeError(
            "Completed FEM result contains no accepted increments."
        )

    final = accepted_increments[-1]

    # --------------------------------------------------------------
    # Displacement evidence
    # --------------------------------------------------------------

    displacement_target_ids = _one_based_node_ids(
        under_head,
        head_bearing,
        nut_bearing,
        nut_thread,
        bolt_thread,
    )

    displacement_datasets = (
        read_targeted_frd_displacement_datasets(
            frd_path,
            target_node_ids=displacement_target_ids,
        )
    )

    final_displacement = _select_final_dataset(
        displacement_datasets,
        step=final.step,
        increment=final.increment,
        kind="displacement",
    )

    if not math.isclose(
        final_displacement.time,
        final.total_time,
        rel_tol=0.0,
        abs_tol=1.0e-9,
    ):
        raise RuntimeError(
            "Final FRD displacement time does not match the final "
            "accepted STA increment."
        )

    nodal_uz_mm = {
        record.node_id - 1: record.d3_mm
        for record in final_displacement.records
    }

    deformation_state = summarize_complete_joint_deformation(
        points_mm=mesh_data.points_mm,
        under_head_triangles=under_head,
        head_member_bearing_triangles=head_bearing,
        nut_member_bearing_triangles=nut_bearing,
        nut_thread_triangles=nut_thread,
        bolt_thread_triangles=bolt_thread,
        nodal_uz_mm=nodal_uz_mm,
        thermal_expansion_coefficient_per_c=(
            thermal_expansion_coefficient_per_c
        ),
        equivalent_delta_temperature_c=(
            equivalent_delta_temperature_c
        ),
    )

    del displacement_datasets
    del final_displacement
    del nodal_uz_mm
    gc.collect()

    # --------------------------------------------------------------
    # Stress evidence
    #
    # The bolt free-span selection is geometry-derived before FRD
    # extraction, so only the governed diagnostic region plus required
    # member/thread nodes are retained.
    # --------------------------------------------------------------

    bolt_region = derive_bolt_free_span_stress_region(
        points_mm=mesh_data.points_mm,
        bolt_tetrahedra=bolt_tetrahedra,
        under_head_triangles=under_head,
        nut_thread_triangles=nut_thread,
        band_start_fraction=(
            policy.bolt_free_span_band_start_fraction
        ),
        band_end_fraction=(
            policy.bolt_free_span_band_end_fraction
        ),
    )

    selected_bolt_tetrahedra = bolt_tetrahedra[
        np.asarray(
            bolt_region.selected_element_indices,
            dtype=np.int64,
        )
    ]

    stress_target_ids = _one_based_node_ids(
        selected_bolt_tetrahedra,
        head_tetrahedra,
        nut_tetrahedra,
        bolt_thread,
        nut_thread,
    )

    stress_datasets = read_targeted_frd_stress_datasets(
        frd_path,
        target_node_ids=stress_target_ids,
    )

    final_stress = _select_final_dataset(
        stress_datasets,
        step=final.step,
        increment=final.increment,
        kind="stress",
    )

    if not math.isclose(
        final_stress.time,
        final.total_time,
        rel_tol=0.0,
        abs_tol=1.0e-9,
    ):
        raise RuntimeError(
            "Final FRD stress time does not match the final "
            "accepted STA increment."
        )

    nodal_szz_mpa = {
        record.node_id - 1: record.szz_mpa
        for record in final_stress.records
    }

    nodal_stress_mpa = {
        record.node_id - 1: (
            record.sxx_mpa,
            record.syy_mpa,
            record.szz_mpa,
            record.sxy_mpa,
            record.syz_mpa,
            record.szx_mpa,
        )
        for record in final_stress.records
    }

    axial_state = summarize_complete_joint_axial_state(
        points_mm=mesh_data.points_mm,
        bolt_tetrahedra=bolt_tetrahedra,
        head_side_member_tetrahedra=head_tetrahedra,
        nut_side_member_tetrahedra=nut_tetrahedra,
        under_head_triangles=under_head,
        nut_thread_triangles=nut_thread,
        band_start_fraction=(
            policy.bolt_free_span_band_start_fraction
        ),
        band_end_fraction=(
            policy.bolt_free_span_band_end_fraction
        ),
        nodal_szz_mpa=nodal_szz_mpa,
    )

    thread_flank_state = summarize_engaged_bolt_thread_flanks(
        points_mm=mesh_data.points_mm,
        bolt_thread_triangles=bolt_thread,
        nut_thread_triangles=nut_thread,
        nodal_stress_mpa=nodal_stress_mpa,
    )

    del stress_datasets
    del final_stress
    del nodal_szz_mpa
    del nodal_stress_mpa
    gc.collect()

    contact = extract_clamp_force_measurement_from_dat(
        dat_path=dat_path,
        contact_pairs=contact_pairs,
    )

    if not math.isclose(
        contact.time,
        final.total_time,
        rel_tol=0.0,
        abs_tol=1.0e-9,
    ):
        raise RuntimeError(
            "Final DAT contact time does not match the final "
            "accepted STA increment."
        )

    stdout = stdout_path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    return FemPhysicsResultEvidence(
        extraction_policy_id=policy.policy_id,
        final_step=final.step,
        final_increment=final.increment,
        final_time=final.total_time,
        thread_normal_force_n=contact.thread_normal_force_n,
        axial_state=axial_state,
        deformation_state=deformation_state,
        thread_flank_state=thread_flank_state,
        accepted_increments=accepted_increments,
        return_code=_load_manifest_return_code(
            manifest_path
        ),
        stdout=stdout,
        displacement_target_node_count=len(
            displacement_target_ids
        ),
        stress_target_node_count=len(
            stress_target_ids
        ),
    )

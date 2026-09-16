"""Execution-generation-safe FEM calibration reuse contracts."""

from threadrom.factory.fem_calibration_knowledge import (
    FemWarmStartApplicability,
    FemWarmStartSource,
    build_fem_calibration_knowledge_record,
    predict_fem_warm_start,
)
from threadrom.factory.pilot_doe import (
    PilotDoeCaseId,
)
from tests.unit.test_phase3_fem_calibration_knowledge import (
    _geometry_identity,
    _pilot,
    _policy,
)


LEGACY_EXECUTION = "legacy_single_step_unversioned"

CHECKPOINTED_EXECUTION = (
    "phase3_cp8_thermal_calibration_restart_v2_windows_nonoverlay"
)


def test_record_preserves_execution_generation() -> None:
    resolved, seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    record = build_fem_calibration_knowledge_record(
        resolved=resolved,
        seed=seed,
        geometry_identity=_geometry_identity(resolved),
        execution_generation_id=CHECKPOINTED_EXECUTION,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    assert (
        record.feature.compatibility.execution_generation_id
        == CHECKPOINTED_EXECUTION
    )


def test_exact_reuse_rejects_different_execution_generation() -> None:
    resolved, seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    record = build_fem_calibration_knowledge_record(
        resolved=resolved,
        seed=seed,
        geometry_identity=_geometry_identity(resolved),
        execution_generation_id=LEGACY_EXECUTION,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    prediction = predict_fem_warm_start(
        resolved=resolved,
        seed=seed,
        geometry_identity=_geometry_identity(resolved),
        execution_generation_id=CHECKPOINTED_EXECUTION,
        knowledge=(record,),
        policy=_policy(),
    )

    assert prediction.source is FemWarmStartSource.ANALYTICAL_FALLBACK
    assert (
        prediction.applicability
        is FemWarmStartApplicability.NO_LOCAL_EVIDENCE
    )
    assert prediction.reused_evidence_count == 0


def test_neighbor_reuse_rejects_different_execution_generation() -> None:
    baseline, baseline_seed = _pilot(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    asymmetric, asymmetric_seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    radial, radial_seed = _pilot(
        PilotDoeCaseId.RADIAL_GEOMETRY
    )

    baseline_record = build_fem_calibration_knowledge_record(
        resolved=baseline,
        seed=baseline_seed,
        geometry_identity=_geometry_identity(baseline),
        execution_generation_id=LEGACY_EXECUTION,
        accepted_run_id="accepted-baseline",
        accepted_delta_temperature_c=-243.2744971,
        measured_mean_clamp_force_n=20063.5,
    )

    asymmetric_record = build_fem_calibration_knowledge_record(
        resolved=asymmetric,
        seed=asymmetric_seed,
        geometry_identity=_geometry_identity(asymmetric),
        execution_generation_id=LEGACY_EXECUTION,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    prediction = predict_fem_warm_start(
        resolved=radial,
        seed=radial_seed,
        geometry_identity=_geometry_identity(radial),
        execution_generation_id=CHECKPOINTED_EXECUTION,
        knowledge=(
            baseline_record,
            asymmetric_record,
        ),
        policy=_policy(),
    )

    assert prediction.source is FemWarmStartSource.ANALYTICAL_FALLBACK
    assert (
        prediction.applicability
        is FemWarmStartApplicability.NO_LOCAL_EVIDENCE
    )
    assert prediction.reused_evidence_count == 0


def test_same_execution_generation_preserves_neighbor_reuse() -> None:
    baseline, baseline_seed = _pilot(
        PilotDoeCaseId.BASELINE_CONTROL
    )

    asymmetric, asymmetric_seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    radial, radial_seed = _pilot(
        PilotDoeCaseId.RADIAL_GEOMETRY
    )

    baseline_record = build_fem_calibration_knowledge_record(
        resolved=baseline,
        seed=baseline_seed,
        geometry_identity=_geometry_identity(baseline),
        execution_generation_id=CHECKPOINTED_EXECUTION,
        accepted_run_id="accepted-baseline",
        accepted_delta_temperature_c=-243.2744971,
        measured_mean_clamp_force_n=20063.5,
    )

    asymmetric_record = build_fem_calibration_knowledge_record(
        resolved=asymmetric,
        seed=asymmetric_seed,
        geometry_identity=_geometry_identity(asymmetric),
        execution_generation_id=CHECKPOINTED_EXECUTION,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    prediction = predict_fem_warm_start(
        resolved=radial,
        seed=radial_seed,
        geometry_identity=_geometry_identity(radial),
        execution_generation_id=CHECKPOINTED_EXECUTION,
        knowledge=(
            baseline_record,
            asymmetric_record,
        ),
        policy=_policy(),
    )

    assert prediction.source is FemWarmStartSource.FEM_NEIGHBORS
    assert prediction.reused_evidence_count == 2

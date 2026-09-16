"""Geometry-realization-safe FEM calibration reuse contracts."""

from threadrom.factory.fem_calibration_knowledge import (
    LEGACY_UNVERSIONED_GEOMETRY_GENERATION_ID,
    FemGeometryRealizationIdentity,
    build_legacy_fem_geometry_identity,
    FemWarmStartApplicability,
    FemWarmStartSource,
    build_fem_calibration_knowledge_record,
    predict_fem_warm_start,
)
from threadrom.factory.pilot_doe import (
    PilotDoeCaseId,
)
from tests.unit.test_phase3_fem_calibration_knowledge import (
    _TEST_EXECUTION_GENERATION_ID,
    _pilot,
    _policy,
)


LEGACY_GENERATION = "legacy_unversioned"

CURRENT_GENERATION = (
    "canonical_additive_external_thread_v2_physical_minor_core"
)


def _identity(
    generation: str,
    realization: str,
) -> FemGeometryRealizationIdentity:
    return FemGeometryRealizationIdentity(
        generation_id=generation,
        realization_id=realization,
    )


def test_calibration_record_preserves_geometry_realization_identity() -> None:
    resolved, seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    identity = _identity(
        CURRENT_GENERATION,
        "joint-geometry-current-p03",
    )

    record = build_fem_calibration_knowledge_record(
        resolved=resolved,
        seed=seed,
        geometry_identity=identity,
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    assert record.geometry_identity == identity

    assert (
        record.feature.compatibility.geometry_generation_id
        == CURRENT_GENERATION
    )


def test_exact_reuse_rejects_different_geometry_generation() -> None:
    resolved, seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    legacy_identity = _identity(
        LEGACY_GENERATION,
        "legacy-artifacts-p03",
    )

    current_identity = _identity(
        CURRENT_GENERATION,
        "joint-geometry-current-p03",
    )

    record = build_fem_calibration_knowledge_record(
        resolved=resolved,
        seed=seed,
        geometry_identity=legacy_identity,
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    prediction = predict_fem_warm_start(
        resolved=resolved,
        seed=seed,
        geometry_identity=current_identity,
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        knowledge=(record,),
        policy=_policy(),
    )

    assert prediction.source is not FemWarmStartSource.EXACT_CASE

    assert (
        prediction.source
        is FemWarmStartSource.ANALYTICAL_FALLBACK
    )

    assert (
        prediction.applicability
        is FemWarmStartApplicability.NO_LOCAL_EVIDENCE
    )

    assert prediction.reused_evidence_count == 0


def test_exact_reuse_rejects_different_realization_same_generation() -> None:
    resolved, seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    record_identity = _identity(
        CURRENT_GENERATION,
        "joint-geometry-realization-a",
    )

    target_identity = _identity(
        CURRENT_GENERATION,
        "joint-geometry-realization-b",
    )

    record = build_fem_calibration_knowledge_record(
        resolved=resolved,
        seed=seed,
        geometry_identity=record_identity,
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    prediction = predict_fem_warm_start(
        resolved=resolved,
        seed=seed,
        geometry_identity=target_identity,
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        knowledge=(record,),
        policy=_policy(),
    )

    assert prediction.source is not FemWarmStartSource.EXACT_CASE


def test_neighbor_reuse_rejects_different_geometry_generation() -> None:
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
        geometry_identity=_identity(
            LEGACY_GENERATION,
            "legacy-baseline",
        ),
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        accepted_run_id="accepted-baseline",
        accepted_delta_temperature_c=-243.2744971,
        measured_mean_clamp_force_n=20063.5,
    )

    asymmetric_record = build_fem_calibration_knowledge_record(
        resolved=asymmetric,
        seed=asymmetric_seed,
        geometry_identity=_identity(
            LEGACY_GENERATION,
            "legacy-asymmetric",
        ),
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    prediction = predict_fem_warm_start(
        resolved=radial,
        seed=radial_seed,
        geometry_identity=_identity(
            CURRENT_GENERATION,
            "joint-geometry-current-radial",
        ),
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        knowledge=(
            baseline_record,
            asymmetric_record,
        ),
        policy=_policy(),
    )

    assert (
        prediction.source
        is FemWarmStartSource.ANALYTICAL_FALLBACK
    )

    assert (
        prediction.applicability
        is FemWarmStartApplicability.NO_LOCAL_EVIDENCE
    )

    assert prediction.reused_evidence_count == 0


def test_same_generation_allows_neighbor_reuse_across_realizations() -> None:
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
        geometry_identity=_identity(
            CURRENT_GENERATION,
            "joint-geometry-baseline",
        ),
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        accepted_run_id="accepted-baseline",
        accepted_delta_temperature_c=-243.2744971,
        measured_mean_clamp_force_n=20063.5,
    )

    asymmetric_record = build_fem_calibration_knowledge_record(
        resolved=asymmetric,
        seed=asymmetric_seed,
        geometry_identity=_identity(
            CURRENT_GENERATION,
            "joint-geometry-asymmetric",
        ),
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    prediction = predict_fem_warm_start(
        resolved=radial,
        seed=radial_seed,
        geometry_identity=_identity(
            CURRENT_GENERATION,
            "joint-geometry-radial",
        ),
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        knowledge=(
            baseline_record,
            asymmetric_record,
        ),
        policy=_policy(),
    )

    assert prediction.source is FemWarmStartSource.FEM_NEIGHBORS
    assert prediction.reused_evidence_count == 2


def test_matching_geometry_identity_remains_exact_reuse() -> None:
    resolved, seed = _pilot(
        PilotDoeCaseId.ASYMMETRIC_GRIP
    )

    identity = _identity(
        CURRENT_GENERATION,
        "joint-geometry-current-p03",
    )

    record = build_fem_calibration_knowledge_record(
        resolved=resolved,
        seed=seed,
        geometry_identity=identity,
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        accepted_run_id="accepted-p03",
        accepted_delta_temperature_c=-263.562942251128,
        measured_mean_clamp_force_n=19820.576667,
    )

    prediction = predict_fem_warm_start(
        resolved=resolved,
        seed=seed,
        geometry_identity=identity,
        execution_generation_id=_TEST_EXECUTION_GENERATION_ID,
        knowledge=(record,),
        policy=_policy(),
    )

    assert prediction.source is FemWarmStartSource.EXACT_CASE


def test_legacy_identity_is_bound_to_certified_mesh_sha256() -> None:
    mesh_sha = (
        "32c81d6fafb871840b55a99e85abf179"
        "edb20db5eb330603facdf81df968ea2a"
    )

    identity = build_legacy_fem_geometry_identity(
        mesh_sha256=mesh_sha,
    )

    assert (
        identity.generation_id
        == LEGACY_UNVERSIONED_GEOMETRY_GENERATION_ID
    )

    assert (
        identity.realization_id
        == f"legacy_mesh_sha256:{mesh_sha}"
    )


def test_legacy_identity_is_deterministic_for_same_mesh() -> None:
    mesh_sha = (
        "21022f69b866f95da500b821153c5c6d"
        "bb7b6269a9f6d91b7047716f20a4971e"
    )

    first = build_legacy_fem_geometry_identity(
        mesh_sha256=mesh_sha,
    )

    second = build_legacy_fem_geometry_identity(
        mesh_sha256=mesh_sha,
    )

    assert first == second


def test_legacy_identity_changes_when_mesh_changes() -> None:
    first = build_legacy_fem_geometry_identity(
        mesh_sha256="a" * 64,
    )

    second = build_legacy_fem_geometry_identity(
        mesh_sha256="b" * 64,
    )

    assert first != second


def test_legacy_identity_rejects_invalid_sha256() -> None:
    import pytest

    for bad_value in (
        "",
        "abc",
        "g" * 64,
        "A" * 64,
        "a" * 63,
        "a" * 65,
    ):
        with pytest.raises(ValueError):
            build_legacy_fem_geometry_identity(
                mesh_sha256=bad_value,
            )

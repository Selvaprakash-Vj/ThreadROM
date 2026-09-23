"""Isolated tests for reusable governed CAD/mesh preparation."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import threadrom.factory.governed_fem_physical_preparation as prep


CASE_HASH = "a" * 64
RUN_ID = "trm_fem_" + CASE_HASH[:12]


def run_synthetic_preparation(
    tmp_path,
    monkeypatch,
    *,
    case_hash=CASE_HASH,
    run_id=RUN_ID,
    mesh_variant="medium",
    expected_mesh_variant="medium",
    geometry_bytes=b"synthetic-step",
    mesh_bytes=b"synthetic-mesh",
):
    step_path = tmp_path / "synthetic.step"
    msh_path = tmp_path / "synthetic.msh"

    step_path.write_bytes(geometry_bytes)
    msh_path.write_bytes(mesh_bytes)

    resolved = SimpleNamespace(case_hash=CASE_HASH)
    geometry = object()

    geometry_artifact = SimpleNamespace(
        case_hash=case_hash,
        run_id=run_id,
        step_path=step_path,
        geometry=geometry,
    )

    mesh_artifact = SimpleNamespace(
        case_hash=case_hash,
        run_id=run_id,
        msh_path=msh_path,
        sizes=SimpleNamespace(level_name=mesh_variant),
        local_refinement=None,
    )

    calls = []

    def synthetic_geometry_builder(
        case,
        *,
        artifact_root,
        validation_policy,
    ):
        assert case is resolved
        assert artifact_root == tmp_path
        assert validation_policy == "synthetic-validation"

        calls.append("geometry")
        return geometry_artifact

    def synthetic_mesh_builder(
        case,
        built_geometry,
        **kwargs,
    ):
        assert case is resolved
        assert built_geometry is geometry
        assert kwargs["step_path"] == step_path
        assert kwargs["artifact_root"] == tmp_path

        calls.append("mesh")
        return mesh_artifact

    monkeypatch.setattr(
        prep,
        "build_fem_case_geometry",
        synthetic_geometry_builder,
    )

    monkeypatch.setattr(
        prep,
        "generate_fem_case_grouped_mesh",
        synthetic_mesh_builder,
    )

    def execute():
        return prep.prepare_governed_fem_geometry_mesh(
            resolved_case=resolved,
            expected_case_hash=CASE_HASH,
            expected_run_id=RUN_ID,
            expected_mesh_policy_name=expected_mesh_variant,
            artifact_root=tmp_path,
            validation_policy="synthetic-validation",
            mesh_template="synthetic-mesh-template",
            joint_classification_template="synthetic-joint",
            bolt_classification_template="synthetic-bolt",
            nut_classification_template="synthetic-nut",
            bolt_mesh_level_policy="synthetic-bolt-level",
            nut_mesh_level_policy="synthetic-nut-level",
            local_refinement_policy=None,
        )

    return execute, calls, geometry_artifact, mesh_artifact


@pytest.mark.parametrize(
    "case_label",
    ("SYNTHETIC-M8", "SYNTHETIC-M10", "SYNTHETIC-M12"),
)
def test_same_preparation_path_for_different_case_labels(
    tmp_path,
    monkeypatch,
    case_label,
):
    execute, calls, geometry, mesh = (
        run_synthetic_preparation(tmp_path, monkeypatch)
    )

    result = execute()

    assert result.geometry_artifact is geometry
    assert result.mesh_artifact is mesh
    assert result.step_path.is_file()
    assert result.msh_path.is_file()
    assert calls == ["geometry", "mesh"]


def test_geometry_case_hash_mismatch_blocks_meshing(
    tmp_path,
    monkeypatch,
):
    execute, calls, _, _ = run_synthetic_preparation(
        tmp_path,
        monkeypatch,
        case_hash="b" * 64,
    )

    with pytest.raises(
        RuntimeError,
        match="Geometry artifact case hash mismatch",
    ):
        execute()

    assert calls == ["geometry"]


def test_geometry_run_id_mismatch_blocks_meshing(
    tmp_path,
    monkeypatch,
):
    execute, calls, _, _ = run_synthetic_preparation(
        tmp_path,
        monkeypatch,
        run_id="incorrect-run-id",
    )

    with pytest.raises(
        RuntimeError,
        match="Geometry artifact run ID mismatch",
    ):
        execute()

    assert calls == ["geometry"]


def test_missing_geometry_artifact_blocks_meshing(
    tmp_path,
    monkeypatch,
):
    execute, calls, _, _ = run_synthetic_preparation(
        tmp_path,
        monkeypatch,
        geometry_bytes=b"",
    )

    with pytest.raises(
        RuntimeError,
        match="Validated STEP artifact was not produced",
    ):
        execute()

    assert calls == ["geometry"]


def test_mesh_policy_mismatch_fails_closed(
    tmp_path,
    monkeypatch,
):
    execute, calls, _, _ = run_synthetic_preparation(
        tmp_path,
        monkeypatch,
        mesh_variant="unexpected-mesh",
    )

    with pytest.raises(
        RuntimeError,
        match="governed mesh policy",
    ):
        execute()

    assert calls == ["geometry", "mesh"]


def test_missing_grouped_mesh_fails_closed(
    tmp_path,
    monkeypatch,
):
    execute, calls, _, _ = run_synthetic_preparation(
        tmp_path,
        monkeypatch,
        mesh_bytes=b"",
    )

    with pytest.raises(
        RuntimeError,
        match="Governed grouped mesh was not produced",
    ):
        execute()

    assert calls == ["geometry", "mesh"]

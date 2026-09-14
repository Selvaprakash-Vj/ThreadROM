from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import threadrom.factory.fem_case_mesh as module

from threadrom.meshing.complete_joint_local_refinement import (
    load_complete_joint_local_refinement_policy,
)


ROOT = Path(__file__).resolve().parents[2]


def _install_factory_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    captured: dict[str, object],
) -> None:
    preparation = SimpleNamespace(
        identity=SimpleNamespace(
            run_id="trm_fem_test_case",
        )
    )

    definitions = SimpleNamespace(
        mesh=object(),
        joint_classification=object(),
        bolt_classification=object(),
        nut_classification=object(),
    )

    sizes = SimpleNamespace(
        level_name="medium",
        mesh_size_max_mm=1.005,
    )

    monkeypatch.setattr(
        module,
        "derive_fem_case_preparation",
        lambda resolved: preparation,
    )

    monkeypatch.setattr(
        module,
        "build_fem_case_mesh_definitions",
        lambda *args, **kwargs: definitions,
    )

    monkeypatch.setattr(
        module,
        "bind_fem_case_mesh_identity",
        lambda definitions, *args, **kwargs: definitions,
    )

    monkeypatch.setattr(
        module,
        "resolve_mesh_levels",
        lambda *args, **kwargs: (),
    )

    monkeypatch.setattr(
        module,
        "resolve_complete_joint_mesh_sizes",
        lambda *args, **kwargs: sizes,
    )

    def fake_generate(
        *args: object,
        **kwargs: object,
    ) -> object:
        captured["msh_path"] = args[1]
        captured["local_refinement"] = kwargs.get(
            "local_refinement"
        )

        return SimpleNamespace(
            local_refinement_policy_id=(
                None
                if kwargs.get("local_refinement") is None
                else kwargs["local_refinement"].policy_id
            )
        )

    monkeypatch.setattr(
        module,
        "generate_grouped_complete_joint_mesh",
        fake_generate,
    )


def _common_inputs(
    tmp_path: Path,
) -> dict[str, object]:
    step_path = tmp_path / "case.step"
    step_path.write_text(
        "STEP",
        encoding="utf-8",
    )

    resolved = SimpleNamespace(
        case_hash="case_hash",
        assembly=object(),
    )

    geometry = SimpleNamespace(
        bolt_blank=object(),
        nut_blank=object(),
        external_thread=object(),
        internal_thread=object(),
    )

    return {
        "resolved": resolved,
        "geometry": geometry,
        "step_path": step_path,
        "artifact_root": tmp_path / "artifacts",
        "mesh_template": object(),
        "joint_classification_template": object(),
        "bolt_classification_template": object(),
        "nut_classification_template": object(),
        "bolt_mesh_level_policy": object(),
        "nut_mesh_level_policy": object(),
    }


def test_factory_base_medium_path_remains_unmodified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    _install_factory_stubs(
        monkeypatch,
        captured=captured,
    )

    artifact = module.generate_fem_case_grouped_mesh(
        **_common_inputs(tmp_path),
    )

    assert artifact.local_refinement is None

    assert captured["local_refinement"] is None

    assert Path(
        captured["msh_path"]
    ).name == (
        "complete_joint_grouped_medium_first_order.msh"
    )


def test_factory_medium_plus_is_explicit_and_provenanced(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    _install_factory_stubs(
        monkeypatch,
        captured=captured,
    )

    policy = load_complete_joint_local_refinement_policy(
        ROOT
        / "config"
        / "complete_joint_local_refinement.toml"
    )

    artifact = module.generate_fem_case_grouped_mesh(
        **_common_inputs(tmp_path),
        local_refinement_policy=policy,
    )

    assert artifact.local_refinement is not None

    assert artifact.local_refinement.policy_id == (
        "TRM-LRP-000001"
    )

    assert artifact.local_refinement.policy_name == (
        "medium_plus_v1"
    )

    assert artifact.local_refinement.local_size_mm == pytest.approx(
        0.5025
    )

    assert (
        artifact.local_refinement.transition_distance_mm
        == pytest.approx(0.15075)
    )

    assert captured["local_refinement"] is artifact.local_refinement

    assert Path(
        captured["msh_path"]
    ).name == (
        "complete_joint_grouped_medium_plus_v1_first_order.msh"
    )

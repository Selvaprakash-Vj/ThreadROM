from pathlib import Path
from types import SimpleNamespace

import pytest

import threadrom.factory.fem_case_mesh as mesh_module


def test_fem_case_mesh_quality_rejection_propagates_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    mesh_path = tmp_path / "generated.msh"
    mesh_path.write_text("synthetic mesh placeholder", encoding="utf-8")

    artifact = SimpleNamespace(msh_path=mesh_path)
    definition = SimpleNamespace()

    def reject_mesh(*args: object, **kwargs: object) -> None:
        raise RuntimeError(
            "Minimum mean-ratio quality violates "
            "the controlled safety threshold."
        )

    monkeypatch.setattr(
        mesh_module,
        "analyze_tetrahedral_mesh_quality",
        reject_mesh,
    )

    with pytest.raises(
        RuntimeError,
        match="Minimum mean-ratio quality violates",
    ):
        mesh_module.validate_fem_case_grouped_mesh_quality(
            artifact,
            definition,
        )


def test_production_doe_preparation_wires_fail_closed_mesh_quality() -> None:
    source = Path(
        "scripts/prepare_phase3_production_doe_case.py"
    ).read_text(encoding="utf-8-sig")

    required_fragments = (
        "complete_joint_mesh_quality.toml",
        "load_mesh_quality_definition",
        "validate_fem_case_grouped_mesh_quality",
        '"mesh_quality_validation"',
        '"policy_sha256"',
        '"minimum_mean_ratio"',
        '"maximum_edge_ratio"',
        '"degenerate_count"',
        '"mixed_orientation"',
    )

    missing = [
        fragment
        for fragment in required_fragments
        if fragment not in source
    ]

    assert not missing, (
        "Production DOE mesh-quality enforcement drifted; "
        f"missing fragments: {missing}"
    )

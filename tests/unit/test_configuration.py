"""Tests for the ThreadROM configuration architecture."""

from pathlib import Path

from threadrom.configuration import (
    load_project_config,
    resolve_calculix_executable,
)


def test_project_configuration_loads() -> None:
    """The controlled project configuration loads correctly."""

    project_root = Path(__file__).resolve().parents[2]
    config_path = project_root / "config" / "threadrom.toml"

    config = load_project_config(config_path)

    assert config.name == "ThreadROM"
    assert config.phase == 1
    assert config.work_package == "WP1"
    assert config.canonical_length_unit == "m"
    assert config.canonical_force_unit == "N"
    assert config.axial_axis == "Z"
    assert config.coordinate_handedness == "right"
    assert config.geometry.backend == "CadQuery"
    assert config.mesher.backend == "Gmsh"
    assert config.solver.version == "2.23"

    expected_solver = (
        project_root
        / "tools"
        / "calculix"
        / "2.23.0"
        / "CalculiX-2.23.0-win-x64"
        / "bin"
        / "ccx.exe"
    )

    assert resolve_calculix_executable(
        config,
        project_root,
    ) == expected_solver
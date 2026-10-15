from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

HOOK = (
    ROOT
    / "scripts"
    / "run_phase3_governed_wave_post_fem_rom_hook_v1.py"
)


def load_hook():
    spec = importlib.util.spec_from_file_location(
        "threadrom_post_fem_rom_hook_test",
        HOOK,
    )

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


def test_hook_is_generic_and_wave_parameterized() -> None:

    module = load_hook()

    command = module.build_command(
        wave_id="W99",
        expected_atlas_sha256="a" * 64,
        expected_count=4,
    )

    assert "--wave-id" in command
    assert "W99" in command
    assert "--expected-atlas-sha256" in command
    assert "a" * 64 in command
    assert "--expected-count" in command
    assert "4" in command


def test_hook_targets_generic_rom_adapter() -> None:

    module = load_hook()

    assert (
        module.ROM_ADAPTER.name
        == "evaluate_phase3_governed_wave_rom_admission_v1.py"
    )


def test_hook_contains_no_w05_or_w06_branch() -> None:

    source = HOOK.read_text(
        encoding="utf-8"
    )

    assert 'if wave_id == "W05"' not in source
    assert 'if wave_id == "W06"' not in source
    assert "case_id ==" not in source

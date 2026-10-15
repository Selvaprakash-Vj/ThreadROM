from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SCRIPT = (
    ROOT
    / "scripts"
    / "run_phase3_governed_wave_post_wave_transaction_v1.py"
)


def load_module():

    spec = importlib.util.spec_from_file_location(
        "threadrom_post_wave_transaction_test",
        SCRIPT,
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


def synthetic_plan(
    module,
):
    return {
        "schema_version": 1,
        "record_status": "FINAL",
        "wave_id": "TRM-DDOE-001-W99",
        "stages": {
            name: {
                "script_sha256": (
                    module.sha256(
                        module.STAGE_SCRIPTS[
                            name
                        ]
                    )
                ),
                "args": [
                    "--synthetic",
                    name,
                ],
            }
            for name in module.STAGE_ORDER
        },
    }


def test_stage_order_is_frozen() -> None:

    module = load_module()

    assert module.STAGE_ORDER == (
        "geometry_mesh",
        "calibration_knowledge",
        "fem_evidence",
        "rom_candidate",
    )


def test_all_four_generic_components_exist() -> None:

    module = load_module()

    assert set(
        module.STAGE_SCRIPTS
    ) == set(
        module.STAGE_ORDER
    )

    assert all(
        path.is_file()
        for path in module.STAGE_SCRIPTS.values()
    )


def test_transaction_is_parameterized_by_plan() -> None:

    module = load_module()

    plan = synthetic_plan(
        module
    )

    commands = (
        module.build_transaction_commands(
            plan
        )
    )

    assert len(
        commands
    ) == 4

    assert tuple(
        name
        for name, _ in commands
    ) == module.STAGE_ORDER


def test_each_command_uses_its_generic_stage_script() -> None:

    module = load_module()

    plan = synthetic_plan(
        module
    )

    commands = dict(
        module.build_transaction_commands(
            plan
        )
    )

    for stage_name in module.STAGE_ORDER:

        command = commands[
            stage_name
        ]

        assert (
            Path(
                command[
                    2
                ]
            )
            == module.STAGE_SCRIPTS[
                stage_name
            ]
        )


def test_no_wave_specific_branch_exists() -> None:

    source = SCRIPT.read_text(
        encoding="utf-8"
    )

    assert '== "W05"' not in source
    assert '== "W06"' not in source
    assert '== "TRM-DDOE-001-W05"' not in source
    assert '== "TRM-DDOE-001-W06"' not in source
    assert "case_id ==" not in source


def test_authority_verification_accepts_current_generic_scripts() -> None:

    module = load_module()

    plan = synthetic_plan(
        module
    )

    module.verify_stage_authorities(
        plan
    )

"""Tests for governed CalculiX pretension-force direction."""

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.solver.complete_joint_physical_pretension import (
    _render_preload_checkpoint_steps,
)
from threadrom.solver.complete_joint_pretension import (
    load_complete_joint_pretension_definition,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BASE_CONFIG = PROJECT_ROOT / "config" / "complete_joint_pretension.toml"


def test_legacy_config_defaults_to_positive_reference_sign() -> None:
    """Existing configurations preserve their historical sign."""

    definition = load_complete_joint_pretension_definition(BASE_CONFIG)

    assert definition.preload_force_n == 20000.0
    assert definition.reference_force_sign == 1
    assert definition.signed_preload_force_n == 20000.0


def test_negative_reference_sign_renders_negative_cload() -> None:
    """The governed sign controls only the CalculiX reference force."""

    definition = load_complete_joint_pretension_definition(BASE_CONFIG)

    corrected = replace(
        definition,
        reference_force_sign=-1,
    )

    text = "\n".join(
        _render_preload_checkpoint_steps(
            corrected,
            reference_node_id=76066,
        )
    )

    assert corrected.preload_force_n == 20000.0
    assert corrected.signed_preload_force_n == -20000.0

    assert "76066, 1, -1.000000000000e+03" in text

    assert "76066, 1, -2.000000000000e+04" in text


def test_invalid_reference_force_sign_is_rejected(
    tmp_path: Path,
) -> None:
    """Only the two physical force directions are accepted."""

    content = BASE_CONFIG.read_text(encoding="utf-8")

    content = content.replace(
        "reference_force_sign = 1",
        "reference_force_sign = 0",
        1,
    )

    config_path = tmp_path / "invalid_pretension_direction.toml"

    config_path.write_text(
        content,
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(
        ValueError,
        match=("reference-force sign must be -1 or \\+1"),
    ):
        load_complete_joint_pretension_definition(config_path)

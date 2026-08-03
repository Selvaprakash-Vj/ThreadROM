"""Tests for governed compression-cone method inputs."""

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_input import (
    AnalyticalMethodSelection,
    BoltComplianceMethod,
    ExternalLoadMethod,
    MemberCompressionMethod,
    ThreadLoadDistributionMethod,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)


def _method_selection() -> AnalyticalMethodSelection:
    """Create one valid analytical method selection."""

    return AnalyticalMethodSelection(
        bolt_compliance=(BoltComplianceMethod.SEGMENTED),
        member_compression=(MemberCompressionMethod.COMPRESSION_CONE),
        external_load=(ExternalLoadMethod.BASIC_SPRING_RATIO),
        thread_load_distribution=(ThreadLoadDistributionMethod.DISCRETE_SPRING),
        head_participation_factor=0.5,
        nut_participation_factor=0.5,
    )


def test_compression_cone_angle_has_governed_default() -> None:
    """Direct construction retains the 30-degree default."""

    methods = _method_selection()

    assert methods.compression_cone_half_angle_deg == pytest.approx(30.0)


def test_explicit_compression_cone_angle_is_retained() -> None:
    """A valid explicit cone angle is accepted."""

    methods = replace(
        _method_selection(),
        compression_cone_half_angle_deg=45.0,
    )

    assert methods.compression_cone_half_angle_deg == pytest.approx(45.0)


@pytest.mark.parametrize(
    "angle_deg",
    [
        -1.0,
        0.0,
        90.0,
        91.0,
    ],
)
def test_invalid_compression_cone_angles_are_rejected(
    angle_deg: float,
) -> None:
    """Nonphysical cone half-angles are rejected."""

    with pytest.raises(
        ValueError,
        match="Compression-cone half-angle",
    ):
        replace(
            _method_selection(),
            compression_cone_half_angle_deg=(angle_deg),
        )


def test_governed_config_loads_explicit_cone_angle() -> None:
    """The benchmark exposes its cone-angle assumption."""

    project_root = Path(__file__).resolve().parents[2]

    joint = load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")

    assert joint.methods.compression_cone_half_angle_deg == pytest.approx(30.0)


def test_loader_defaults_angle_for_legacy_config(
    tmp_path: Path,
) -> None:
    """Legacy configurations retain backward compatibility."""

    project_root = Path(__file__).resolve().parents[2]

    source_path = project_root / "config" / "analytical_m10_5kn.toml"

    config_text = source_path.read_text(encoding="utf-8")

    setting = "compression_cone_half_angle_deg = 30.0\n"

    assert setting in config_text

    legacy_path = tmp_path / "legacy_analytical_joint.toml"

    legacy_path.write_text(
        config_text.replace(
            setting,
            "",
            1,
        ),
        encoding="utf-8",
        newline="\n",
    )

    joint = load_analytical_joint_input(legacy_path)

    assert joint.methods.compression_cone_half_angle_deg == pytest.approx(30.0)

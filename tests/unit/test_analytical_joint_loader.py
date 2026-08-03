"""Tests for the canonical analytical joint TOML loader."""

from pathlib import Path

import pytest

from threadrom.engineering.analytical_inputs import (
    BoltSegmentKind,
)
from threadrom.engineering.analytical_joint_input import (
    BoltComplianceMethod,
    MemberCompressionMethod,
    ThreadLoadDistributionMethod,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)


def test_m10_5kn_benchmark_loads_from_governed_toml() -> None:
    """The first analytical benchmark loads from its governed input."""

    project_root = Path(__file__).resolve().parents[2]

    joint = load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")

    assert joint.joint_id == "TRM-ANL-000001"
    assert joint.thread.nominal_diameter_mm == pytest.approx(10.0)
    assert joint.thread.pitch_mm == pytest.approx(1.5)
    assert joint.loading.preload_n == pytest.approx(5000.0)
    assert joint.loading.external_axial_load_n == pytest.approx(0.0)
    assert joint.grip_length_mm == pytest.approx(20.0)
    assert joint.engaged_thread_count == pytest.approx(8.0 / 1.5)
    assert len(joint.materials) == 3
    assert len(joint.member_layers) == 2
    assert len(joint.bolt.axial_segments) == 1

    assert joint.bolt.axial_segments[0].kind is BoltSegmentKind.THREADED

    assert joint.methods.bolt_compliance is BoltComplianceMethod.SEGMENTED

    assert joint.methods.member_compression is MemberCompressionMethod.UNIFORM_ANNULAR_CYLINDER

    assert joint.methods.thread_load_distribution is ThreadLoadDistributionMethod.DISCRETE_SPRING


def test_loader_rejects_invalid_enum_value(
    tmp_path: Path,
) -> None:
    """Unsupported analytical method names are rejected."""

    config = tmp_path / "invalid.toml"

    source = Path(__file__).resolve().parents[2] / "config" / "analytical_m10_5kn.toml"

    text = source.read_text(
        encoding="utf-8-sig",
    ).replace(
        'bolt_compliance = "segmented"',
        'bolt_compliance = "unknown_method"',
    )

    config.write_text(
        text,
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported value for bolt_compliance",
    ):
        load_analytical_joint_input(config)

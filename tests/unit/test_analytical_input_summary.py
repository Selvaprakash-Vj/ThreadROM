"""Tests for analytical input-summary rendering."""

from pathlib import Path

from threadrom.engineering.analytical_input_summary import (
    render_analytical_input_summary,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)


def test_m10_input_summary_contains_governed_values() -> None:
    """The summary reports resolved canonical benchmark inputs."""

    project_root = Path(__file__).resolve().parents[2]

    joint = load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")

    report = render_analytical_input_summary(joint)

    assert "# ThreadROM Analytical Joint Input Summary" in report
    assert "TRM-ANL-000001" in report
    assert "| Nominal diameter | 10.000000 mm |" in report
    assert "| Pitch | 1.500000 mm |" in report
    assert "- Total grip length: 20.000000 mm" in report
    assert "- Preload: 5000.000000 N" in report
    assert "- Bolt compliance: segmented" in report
    assert "- Thread-load distribution: discrete_spring" in report
    assert "It does not yet contain calculated" in report

"""Tests for governed compression-cone member reporting."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_input import (
    MemberCompressionMethod,
)
from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_member_result import (
    evaluate_analytical_member,
    render_analytical_member_report,
)


def _cone_result():
    """Evaluate the benchmark using compression-cone mechanics."""

    project_root = Path(__file__).resolve().parents[2]

    joint = load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")

    cone_joint = replace(
        joint,
        methods=replace(
            joint.methods,
            member_compression=(MemberCompressionMethod.COMPRESSION_CONE),
        ),
    )

    return evaluate_analytical_member(cone_joint)


def test_cone_result_is_governed_and_validated() -> None:
    """The cone model passes the common member validator."""

    result = _cone_result()

    assert result.mechanics.method == "compression_cone"

    assert result.mechanics.compression_cone_half_angle_deg == pytest.approx(30.0)

    assert result.validation.passed
    assert result.validation.failed_check_ids == ()


def test_cone_json_preserves_method_specific_fields() -> None:
    """Machine-readable output includes cone slice evidence."""

    payload = json.loads(_cone_result().to_json())

    mechanics = payload["mechanics"]

    assert mechanics["method"] == "compression_cone"

    assert mechanics["compression_cone_half_angle_deg"] == pytest.approx(30.0)

    assert mechanics["layers"][0]["compression_model"] == ("compression_cone_slice")

    assert mechanics["layers"][0]["cone_side"] == ("head_side")

    assert (
        mechanics["layers"][0]["end_compression_area_mm2"]
        > mechanics["layers"][0]["compression_area_mm2"]
    )


def test_cone_report_uses_method_appropriate_scope() -> None:
    """The cone report does not claim spreading is excluded."""

    report = render_analytical_member_report(_cone_result())

    normalized_report = " ".join(report.split())

    assert "- Compression-cone half-angle: 30.000000000 deg" in report

    assert (
        "Compression spreading follows ideal opposed "
        "annular frustums meeting at the stack midpoint." in normalized_report
    )

    assert (
        "Each cone is capped by the configured outer "
        "diameter of its current member layer." in normalized_report
    )

    assert "Compression spreading and cone interaction are excluded." not in normalized_report

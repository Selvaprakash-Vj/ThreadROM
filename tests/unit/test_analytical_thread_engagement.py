"""Tests for governed engaged-thread discretization."""

from dataclasses import replace
from pathlib import Path

import pytest

from threadrom.engineering.analytical_joint_loader import (
    load_analytical_joint_input,
)
from threadrom.engineering.analytical_thread_engagement import (
    discretize_thread_engagement,
)


def _benchmark_joint():
    """Load the governed M10 analytical benchmark."""

    project_root = Path(__file__).resolve().parents[2]

    return load_analytical_joint_input(project_root / "config" / "analytical_m10_5kn.toml")


def test_m10_engagement_resolves_full_and_partial_turns() -> None:
    """Eight millimetres resolves to five full plus one partial turn."""

    result = discretize_thread_engagement(_benchmark_joint())

    assert result.method == "axial_pitch_cells_v1"
    assert result.axial_origin == "nut_bearing_face"

    assert result.numbering_direction == ("bearing_face_to_nut_free_end")

    assert result.pitch_mm == pytest.approx(1.5)

    assert result.total_engagement_length_mm == pytest.approx(8.0)

    assert result.nominal_engaged_pitch_count == pytest.approx(8.0 / 1.5)

    assert result.active_turn_count == 6
    assert result.complete_turn_count == 5

    assert result.partial_turn_fraction == pytest.approx(1.0 / 3.0)

    assert [turn.turn_number for turn in result.turns] == [
        1,
        2,
        3,
        4,
        5,
        6,
    ]


def test_first_turn_begins_at_nut_bearing_face() -> None:
    """Turn one is the first loaded turn at the bearing face."""

    result = discretize_thread_engagement(_benchmark_joint())

    first = result.turns[0]

    assert first.turn_number == 1
    assert first.axial_start_mm == pytest.approx(0.0)

    assert first.axial_end_mm == pytest.approx(1.5)

    assert first.axial_centroid_mm == pytest.approx(0.75)

    assert first.engagement_fraction == pytest.approx(1.0)

    assert not first.is_partial


def test_final_partial_turn_ends_at_engagement_limit() -> None:
    """The final partial cell terminates at the nut free end."""

    result = discretize_thread_engagement(_benchmark_joint())

    final = result.turns[-1]

    assert final.turn_number == 6

    assert final.axial_start_mm == pytest.approx(7.5)

    assert final.axial_end_mm == pytest.approx(8.0)

    assert final.axial_centroid_mm == pytest.approx(7.75)

    assert final.engagement_length_mm == pytest.approx(0.5)

    assert final.engagement_fraction == pytest.approx(1.0 / 3.0)

    assert final.is_partial


def test_turn_lengths_and_fractions_are_conservative() -> None:
    """Resolved cells conserve engagement length and pitch count."""

    result = discretize_thread_engagement(_benchmark_joint())

    assert sum(turn.engagement_length_mm for turn in result.turns) == pytest.approx(
        result.total_engagement_length_mm
    )

    assert sum(turn.engagement_fraction for turn in result.turns) == pytest.approx(
        result.nominal_engaged_pitch_count
    )


def test_exact_pitch_multiple_has_no_partial_turn() -> None:
    """An exact engagement multiple creates complete turns only."""

    joint = _benchmark_joint()

    modified = replace(
        joint,
        nut=replace(
            joint.nut,
            thread_engagement_length_mm=7.5,
        ),
    )

    result = discretize_thread_engagement(modified)

    assert result.active_turn_count == 5
    assert result.complete_turn_count == 5
    assert result.partial_turn_fraction == pytest.approx(0.0)

    assert all(not turn.is_partial for turn in result.turns)


def test_sub_pitch_engagement_creates_one_partial_turn() -> None:
    """A short engagement still resolves one active partial cell."""

    joint = _benchmark_joint()

    modified = replace(
        joint,
        nut=replace(
            joint.nut,
            thread_engagement_length_mm=0.75,
        ),
    )

    result = discretize_thread_engagement(modified)

    assert result.active_turn_count == 1
    assert result.complete_turn_count == 0
    assert result.partial_turn_fraction == pytest.approx(0.5)

    assert result.turns[0].engagement_fraction == pytest.approx(0.5)

    assert result.turns[0].is_partial


def test_multistart_threads_are_explicitly_out_of_scope() -> None:
    """The V1 discretization rejects unsupported multistart threads."""

    joint = _benchmark_joint()

    modified = replace(
        joint,
        thread=replace(
            joint.thread,
            starts=2,
        ),
    )

    with pytest.raises(
        NotImplementedError,
        match="single-start threads",
    ):
        discretize_thread_engagement(modified)

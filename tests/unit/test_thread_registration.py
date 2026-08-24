"""Tests for canonical bolt-nut thread registration."""

from __future__ import annotations

import pytest

from threadrom.geometry.canonical_screw_geometry import (
    screw_rotation_deg,
)
from threadrom.geometry.thread_registration import (
    calculate_thread_pair_registration,
)


def test_baseline_registration_is_canonical_120_deg() -> None:
    """M10x1.5 at z=20 mm derives one-third-turn registration."""

    result = calculate_thread_pair_registration(
        nut_translation_z_mm=20.0,
        external_pitch_mm=1.5,
        internal_pitch_mm=1.5,
        external_handedness="right",
        internal_handedness="right",
        thread_boolean_overlap_mm=0.03,
    )

    expected = screw_rotation_deg(
        20.0,
        1.5,
        "right",
    )

    assert expected == pytest.approx(
        120.0,
        abs=1.0e-10,
    )

    assert result.nut_rotation_deg == pytest.approx(
        expected,
        abs=1.0e-10,
    )

    assert result.translation_z_mm == pytest.approx(
        20.0
    )

    assert result.pitch_mm == pytest.approx(
        1.5
    )

    assert result.handedness == "right"


def test_registration_scales_parametrically() -> None:
    """Changing pitch and translation follows the same screw law."""

    result = calculate_thread_pair_registration(
        nut_translation_z_mm=25.0,
        external_pitch_mm=2.0,
        internal_pitch_mm=2.0,
        external_handedness="right",
        internal_handedness="right",
        thread_boolean_overlap_mm=0.04,
    )

    assert result.nut_rotation_deg == pytest.approx(
        180.0,
        abs=1.0e-10,
    )


def test_boolean_overlap_cannot_change_physical_registration() -> None:
    """CAD construction overlap is independent of physical screw phase."""

    no_overlap = calculate_thread_pair_registration(
        nut_translation_z_mm=20.0,
        external_pitch_mm=1.5,
        internal_pitch_mm=1.5,
        external_handedness="right",
        internal_handedness="right",
        thread_boolean_overlap_mm=0.0,
    )

    baseline_overlap = calculate_thread_pair_registration(
        nut_translation_z_mm=20.0,
        external_pitch_mm=1.5,
        internal_pitch_mm=1.5,
        external_handedness="right",
        internal_handedness="right",
        thread_boolean_overlap_mm=0.03,
    )

    large_overlap = calculate_thread_pair_registration(
        nut_translation_z_mm=20.0,
        external_pitch_mm=1.5,
        internal_pitch_mm=1.5,
        external_handedness="right",
        internal_handedness="right",
        thread_boolean_overlap_mm=0.20,
    )

    assert no_overlap.nut_rotation_deg == pytest.approx(
        baseline_overlap.nut_rotation_deg,
        abs=1.0e-12,
    )

    assert large_overlap.nut_rotation_deg == pytest.approx(
        baseline_overlap.nut_rotation_deg,
        abs=1.0e-12,
    )


def test_left_hand_registration_reverses_phase_direction() -> None:
    """Left-hand screw registration reverses the angular direction."""

    right = calculate_thread_pair_registration(
        nut_translation_z_mm=20.0,
        external_pitch_mm=1.5,
        internal_pitch_mm=1.5,
        external_handedness="right",
        internal_handedness="right",
        thread_boolean_overlap_mm=0.03,
    )

    left = calculate_thread_pair_registration(
        nut_translation_z_mm=20.0,
        external_pitch_mm=1.5,
        internal_pitch_mm=1.5,
        external_handedness="left",
        internal_handedness="left",
        thread_boolean_overlap_mm=0.03,
    )

    assert right.nut_rotation_deg == pytest.approx(
        120.0,
        abs=1.0e-10,
    )

    assert left.nut_rotation_deg == pytest.approx(
        240.0,
        abs=1.0e-10,
    )

    assert left.nut_rotation_deg == pytest.approx(
        (-right.nut_rotation_deg) % 360.0,
        abs=1.0e-10,
    )


def test_registration_rejects_pitch_mismatch() -> None:
    """Different bolt and nut pitches fail closed."""

    with pytest.raises(
        ValueError,
        match="pitches must match",
    ):
        calculate_thread_pair_registration(
            nut_translation_z_mm=20.0,
            external_pitch_mm=1.5,
            internal_pitch_mm=1.75,
            external_handedness="right",
            internal_handedness="right",
            thread_boolean_overlap_mm=0.03,
        )


def test_registration_rejects_handedness_mismatch() -> None:
    """Opposite-handed bolt and nut definitions fail closed."""

    with pytest.raises(
        ValueError,
        match="handedness must match",
    ):
        calculate_thread_pair_registration(
            nut_translation_z_mm=20.0,
            external_pitch_mm=1.5,
            internal_pitch_mm=1.5,
            external_handedness="right",
            internal_handedness="left",
            thread_boolean_overlap_mm=0.03,
        )


def test_registration_rejects_negative_boolean_overlap() -> None:
    """Compatibility overlap input still fails closed when invalid."""

    with pytest.raises(
        ValueError,
        match="overlap must be non-negative",
    ):
        calculate_thread_pair_registration(
            nut_translation_z_mm=20.0,
            external_pitch_mm=1.5,
            internal_pitch_mm=1.5,
            external_handedness="right",
            internal_handedness="right",
            thread_boolean_overlap_mm=-0.01,
        )
"""Canonical geometry contract for conjugate metric screw threads."""

from __future__ import annotations

import math

THREAD_FLANK_ANGLE_DEG = 60.0

_PITCH_TOLERANCE_MM = 1.0e-12


def _require_positive(value: float, name: str) -> float:
    if value <= 0.0:
        raise ValueError(f"{name} must be positive.")
    return value


def normalized_handedness(handedness: str) -> str:
    """Return validated lower-case thread handedness."""

    value = handedness.lower()

    if value not in {"right", "left"}:
        raise ValueError(
            "Thread handedness must be 'right' or 'left'."
        )

    return value


def fundamental_height_mm(pitch_mm: float) -> float:
    """Return the ISO basic-profile fundamental triangle height H."""

    pitch = _require_positive(
        pitch_mm,
        "Thread pitch",
    )

    return (
        math.sqrt(3.0)
        / 2.0
        * pitch
    )


def basic_pitch_diameter_mm(
    nominal_diameter_mm: float,
    pitch_mm: float,
) -> float:
    """Return the zero-line basic pitch diameter d2/D2."""

    nominal = _require_positive(
        nominal_diameter_mm,
        "Nominal diameter",
    )

    height = fundamental_height_mm(
        pitch_mm
    )

    diameter = (
        nominal
        - 3.0 * height / 4.0
    )

    if diameter <= 0.0:
        raise ValueError(
            "Basic pitch diameter must remain positive."
        )

    return diameter


def basic_pitch_radius_mm(
    nominal_diameter_mm: float,
    pitch_mm: float,
) -> float:
    """Return the zero-line basic pitch-cylinder radius."""

    return (
        basic_pitch_diameter_mm(
            nominal_diameter_mm,
            pitch_mm,
        )
        / 2.0
    )


def basic_internal_minor_diameter_mm(
    nominal_diameter_mm: float,
    pitch_mm: float,
) -> float:
    """Return basic internal-thread minor diameter D1."""

    nominal = _require_positive(
        nominal_diameter_mm,
        "Nominal diameter",
    )

    height = fundamental_height_mm(
        pitch_mm
    )

    diameter = (
        nominal
        - 5.0 * height / 4.0
    )

    if diameter <= 0.0:
        raise ValueError(
            "Basic internal minor diameter must remain positive."
        )

    return diameter


def basic_internal_minor_radius_mm(
    nominal_diameter_mm: float,
    pitch_mm: float,
) -> float:
    """Return basic internal-thread minor radius D1/2."""

    return (
        basic_internal_minor_diameter_mm(
            nominal_diameter_mm,
            pitch_mm,
        )
        / 2.0
    )


def canonical_flank_half_width_mm(
    radius_mm: float,
    nominal_diameter_mm: float,
    pitch_mm: float,
) -> float:
    """Return axial half-width of the canonical 60-degree flank.

    The physical flank is anchored at +/- P/4 on the pitch
    cylinder. Male and female material occupy opposite sides
    of this same geometric boundary.
    """

    radius = _require_positive(
        radius_mm,
        "Thread radius",
    )

    pitch = _require_positive(
        pitch_mm,
        "Thread pitch",
    )

    pitch_radius = basic_pitch_radius_mm(
        nominal_diameter_mm,
        pitch,
    )

    return (
        pitch / 4.0
        + (
            pitch_radius - radius
        )
        / math.tan(
            math.radians(
                THREAD_FLANK_ANGLE_DEG
            )
        )
    )


def wrap_thread_phase_mm(
    axial_phase_mm: float,
    pitch_mm: float,
) -> float:
    """Wrap an axial screw phase into [-P/2, +P/2)."""

    pitch = _require_positive(
        pitch_mm,
        "Thread pitch",
    )

    return (
        (
            axial_phase_mm
            + 0.5 * pitch
        )
        % pitch
    ) - 0.5 * pitch


def canonical_internal_radius_from_phase_mm(
    axial_phase_mm: float,
    nominal_diameter_mm: float,
    pitch_mm: float,
) -> float:
    """Return radius of the canonical zero-line internal profile."""

    pitch = _require_positive(
        pitch_mm,
        "Thread pitch",
    )

    major_radius = (
        _require_positive(
            nominal_diameter_mm,
            "Nominal diameter",
        )
        / 2.0
    )

    pitch_radius = basic_pitch_radius_mm(
        nominal_diameter_mm,
        pitch,
    )

    minor_radius = (
        basic_internal_minor_radius_mm(
            nominal_diameter_mm,
            pitch,
        )
    )

    phase = abs(
        wrap_thread_phase_mm(
            axial_phase_mm,
            pitch,
        )
    )

    if phase <= pitch / 16.0:
        return major_radius

    if phase < 3.0 * pitch / 8.0:
        return (
            pitch_radius
            + math.tan(
                math.radians(
                    THREAD_FLANK_ANGLE_DEG
                )
            )
            * (
                pitch / 4.0
                - phase
            )
        )

    return minor_radius


def screw_rotation_deg(
    translation_z_mm: float,
    pitch_mm: float,
    handedness: str,
) -> float:
    """Return rotation preserving the common rigid screw datum."""

    if translation_z_mm < 0.0:
        raise ValueError(
            "Thread translation must be non-negative."
        )

    pitch = _require_positive(
        pitch_mm,
        "Thread pitch",
    )

    hand = normalized_handedness(
        handedness
    )

    phase_sign = (
        -1.0
        if hand == "left"
        else 1.0
    )

    fractional_turn = (
        translation_z_mm / pitch
    ) % 1.0

    return (
        phase_sign
        * 360.0
        * fractional_turn
    ) % 360.0


def screw_point_xyz(
    radius_mm: float,
    axial_offset_mm: float,
    theta_rad: float,
    pitch_mm: float,
    handedness: str,
) -> tuple[float, float, float]:
    """Map a profile point through the canonical rigid screw motion."""

    radius = _require_positive(
        radius_mm,
        "Thread radius",
    )

    pitch = _require_positive(
        pitch_mm,
        "Thread pitch",
    )

    hand = normalized_handedness(
        handedness
    )

    phase_sign = (
        -1.0
        if hand == "left"
        else 1.0
    )

    return (
        radius * math.cos(theta_rad),
        radius * math.sin(theta_rad),
        axial_offset_mm
        + phase_sign
        * pitch
        * theta_rad
        / (2.0 * math.pi),
    )


def validate_basic_internal_minor_diameter(
    actual_minor_diameter_mm: float,
    nominal_diameter_mm: float,
    pitch_mm: float,
    tolerance_mm: float = _PITCH_TOLERANCE_MM,
) -> None:
    """Fail closed unless D1 matches the canonical zero-line datum."""

    if tolerance_mm < 0.0:
        raise ValueError(
            "Diameter tolerance must be non-negative."
        )

    expected = (
        basic_internal_minor_diameter_mm(
            nominal_diameter_mm,
            pitch_mm,
        )
    )

    if abs(
        actual_minor_diameter_mm
        - expected
    ) > tolerance_mm:
        raise ValueError(
            "Internal minor diameter does not match "
            "the canonical zero-line basic profile."
        )
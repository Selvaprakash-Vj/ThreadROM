"""Canonical screw registration of mating external and internal threads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from threadrom.geometry.canonical_screw_geometry import (
    normalized_handedness,
    screw_rotation_deg,
)

_PITCH_TOLERANCE_MM = 1.0e-9


class ExternalThreadRegistrationDefinition(Protocol):
    """External-thread data required for mating registration."""

    pitch_mm: float
    handedness: str


class InternalThreadRegistrationDefinition(Protocol):
    """Internal-thread data required for mating registration."""

    pitch_mm: float
    handedness: str


@dataclass(frozen=True)
class ThreadPairRegistration:
    """Canonical rigid-screw registration of a mating thread pair."""

    translation_z_mm: float
    pitch_mm: float
    handedness: str
    nut_rotation_deg: float


def calculate_thread_pair_registration(
    *,
    nut_translation_z_mm: float,
    external_pitch_mm: float,
    internal_pitch_mm: float,
    external_handedness: str,
    internal_handedness: str,
    thread_boolean_overlap_mm: float,
) -> ThreadPairRegistration:
    """Return nut rotation from the common rigid screw datum.

    Physical registration depends only on axial translation, pitch,
    and handedness. Boolean construction overlap is accepted here
    temporarily for API compatibility, but it cannot alter the
    physical thread phase.
    """

    if nut_translation_z_mm < 0.0:
        raise ValueError(
            "Nut translation must be non-negative."
        )

    if external_pitch_mm <= 0.0:
        raise ValueError(
            "External thread pitch must be positive."
        )

    if internal_pitch_mm <= 0.0:
        raise ValueError(
            "Internal thread pitch must be positive."
        )

    if (
        abs(
            external_pitch_mm
            - internal_pitch_mm
        )
        > _PITCH_TOLERANCE_MM
    ):
        raise ValueError(
            "External and internal thread pitches must match."
        )

    external_hand = normalized_handedness(
        external_handedness
    )

    internal_hand = normalized_handedness(
        internal_handedness
    )

    if external_hand != internal_hand:
        raise ValueError(
            "External and internal thread handedness must match."
        )

    if thread_boolean_overlap_mm < 0.0:
        raise ValueError(
            "Thread Boolean overlap must be non-negative."
        )

    nut_rotation_deg = screw_rotation_deg(
        nut_translation_z_mm,
        external_pitch_mm,
        external_hand,
    )

    return ThreadPairRegistration(
        translation_z_mm=nut_translation_z_mm,
        pitch_mm=external_pitch_mm,
        handedness=external_hand,
        nut_rotation_deg=nut_rotation_deg,
    )


def calculate_thread_pair_registration_from_definitions(
    *,
    nut_translation_z_mm: float,
    external: ExternalThreadRegistrationDefinition,
    internal: InternalThreadRegistrationDefinition,
    thread_boolean_overlap_mm: float,
) -> ThreadPairRegistration:
    """Return canonical mating registration from thread definitions."""

    return calculate_thread_pair_registration(
        nut_translation_z_mm=nut_translation_z_mm,
        external_pitch_mm=external.pitch_mm,
        internal_pitch_mm=internal.pitch_mm,
        external_handedness=external.handedness,
        internal_handedness=internal.handedness,
        thread_boolean_overlap_mm=thread_boolean_overlap_mm,
    )
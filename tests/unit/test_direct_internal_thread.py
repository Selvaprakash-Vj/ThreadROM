"""Tests for the compact production internal-thread geometry."""

from __future__ import annotations

import math
from pathlib import Path

import cadquery as cq
import pytest

from threadrom.geometry.canonical_screw_geometry import (
    canonical_internal_radius_from_phase_mm,
)
from threadrom.geometry.complete_nut import (
    load_complete_nut_definitions,
)
from threadrom.geometry.direct_internal_thread import (
    _inner_profile_wire,
    build_direct_internal_thread_sleeve,
    direct_internal_thread_join_radii_mm,
    direct_internal_thread_twist_angle_deg,
    measure_direct_internal_thread_sleeve,
)
from threadrom.geometry.geometry_quality import (
    load_geometry_quality_policy,
)
from threadrom.geometry.internal_thread_cutter import (
    InternalThreadCutterDefinition,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

QUALITY = load_geometry_quality_policy(
    PROJECT_ROOT
    / "config"
    / "geometry_quality.toml"
)


@pytest.fixture(scope="module")
def thread_definition() -> InternalThreadCutterDefinition:
    """Load the governed baseline internal-thread definition once."""

    _, definition = load_complete_nut_definitions(
        PROJECT_ROOT
    )

    return definition


@pytest.fixture(scope="module")
def threaded_sleeve(
    thread_definition: InternalThreadCutterDefinition,
) -> cq.Shape:
    """Build the expensive governed sleeve once for this module."""

    return build_direct_internal_thread_sleeve(
        thread_definition,
        QUALITY.thread_boolean_overlap_mm,
    )


def test_baseline_join_radii_are_outside_physical_thread(
    thread_definition: InternalThreadCutterDefinition,
) -> None:
    """Construction overlap stays outside the physical major radius."""

    shell_radius, sleeve_radius = (
        direct_internal_thread_join_radii_mm(
            thread_definition,
            QUALITY.thread_boolean_overlap_mm,
        )
    )

    assert shell_radius == pytest.approx(
        5.03,
        abs=1.0e-12,
    )

    assert sleeve_radius == pytest.approx(
        5.06,
        abs=1.0e-12,
    )

    assert (
        thread_definition.major_radius_mm
        < shell_radius
        < sleeve_radius
    )


def test_baseline_total_twist_is_derived(
    thread_definition: InternalThreadCutterDefinition,
) -> None:
    """The baseline 1920 degrees is derived, never stored as geometry."""

    assert thread_definition.thread_length_mm == pytest.approx(
        8.0
    )

    assert direct_internal_thread_twist_angle_deg(
        thread_definition
    ) == pytest.approx(
        1920.0,
        abs=1.0e-12,
    )


def test_compact_profile_has_four_valid_edges(
    thread_definition: InternalThreadCutterDefinition,
) -> None:
    """The canonical female section uses compact CAD topology."""

    wire = _inner_profile_wire(
        thread_definition
    )

    assert wire.IsClosed()
    assert wire.isValid()
    assert len(wire.Edges()) == 4


def test_full_length_compact_internal_thread_is_valid(
    threaded_sleeve: cq.Shape,
    thread_definition: InternalThreadCutterDefinition,
) -> None:
    """The full governed thread is one valid compact solid."""

    measurements = (
        measure_direct_internal_thread_sleeve(
            threaded_sleeve,
            thread_definition,
            QUALITY.thread_boolean_overlap_mm,
        )
    )

    assert measurements.solid_count == 1
    assert measurements.is_valid
    assert measurements.volume_mm3 > 0.0

    assert measurements.profile_edge_count == 4
    assert measurements.thread_segment_count == 6

    assert measurements.z_min_mm == pytest.approx(
        0.0,
        abs=2.0e-7,
    )

    assert measurements.z_max_mm == pytest.approx(
        thread_definition.thread_length_mm,
        abs=2.0e-7,
    )


def test_full_length_thread_tracks_canonical_oracle(
    threaded_sleeve: cq.Shape,
    thread_definition: InternalThreadCutterDefinition,
) -> None:
    """Both material sides follow the canonical screw boundary."""

    hand_sign = (
        -1.0
        if thread_definition.is_left_hand
        else 1.0
    )

    phases = (
        0.000,
        +0.150,
        -0.150,
        +0.300,
        -0.300,
        +0.450,
        -0.450,
    )

    sample_z = (
        0.75,
        2.00,
        4.00,
        6.00,
        7.25,
    )

    boundary_errors: list[float] = []

    material_passes = 0
    void_passes = 0
    sample_count = 0

    epsilon_mm = 0.010

    for phase_fraction in phases:
        phase_mm = (
            phase_fraction
            * thread_definition.pitch_mm
        )

        radius_mm = (
            canonical_internal_radius_from_phase_mm(
                phase_mm,
                thread_definition.nominal_diameter_mm,
                thread_definition.pitch_mm,
            )
        )

        for z_mm in sample_z:
            theta_rad = (
                hand_sign
                * 2.0
                * math.pi
                * (
                    z_mm - phase_mm
                )
                / thread_definition.pitch_mm
            )

            cos_theta = math.cos(
                theta_rad
            )

            sin_theta = math.sin(
                theta_rad
            )

            boundary = cq.Vertex.makeVertex(
                radius_mm * cos_theta,
                radius_mm * sin_theta,
                z_mm,
            )

            boundary_errors.append(
                float(
                    threaded_sleeve.distance(
                        boundary
                    )
                )
            )

            material = cq.Vector(
                (
                    radius_mm
                    + epsilon_mm
                )
                * cos_theta,
                (
                    radius_mm
                    + epsilon_mm
                )
                * sin_theta,
                z_mm,
            )

            void = cq.Vector(
                (
                    radius_mm
                    - epsilon_mm
                )
                * cos_theta,
                (
                    radius_mm
                    - epsilon_mm
                )
                * sin_theta,
                z_mm,
            )

            if threaded_sleeve.isInside(
                material,
                1.0e-7,
            ):
                material_passes += 1

            if not threaded_sleeve.isInside(
                void,
                1.0e-7,
            ):
                void_passes += 1

            sample_count += 1

    assert max(boundary_errors) <= 1.0e-3
    assert material_passes == sample_count
    assert void_passes == sample_count


def test_segment_interfaces_preserve_thread_material(
    threaded_sleeve: cq.Shape,
    thread_definition: InternalThreadCutterDefinition,
) -> None:
    """Pitch-cell interfaces contain no thread topology gaps."""

    hand_sign = (
        -1.0
        if thread_definition.is_left_hand
        else 1.0
    )

    joint_z = (
        1.5,
        3.0,
        4.5,
        6.0,
        7.5,
    )

    offsets = (
        -0.002,
        -0.0002,
        +0.0002,
        +0.002,
    )

    radius_mm = (
        canonical_internal_radius_from_phase_mm(
            0.0,
            thread_definition.nominal_diameter_mm,
            thread_definition.pitch_mm,
        )
    )

    for seam_z_mm in joint_z:
        for offset_mm in offsets:
            z_mm = (
                seam_z_mm
                + offset_mm
            )

            theta_rad = (
                hand_sign
                * 2.0
                * math.pi
                * z_mm
                / thread_definition.pitch_mm
            )

            cos_theta = math.cos(
                theta_rad
            )

            sin_theta = math.sin(
                theta_rad
            )

            material = cq.Vector(
                (
                    radius_mm
                    + 0.010
                )
                * cos_theta,
                (
                    radius_mm
                    + 0.010
                )
                * sin_theta,
                z_mm,
            )

            void = cq.Vector(
                (
                    radius_mm
                    - 0.010
                )
                * cos_theta,
                (
                    radius_mm
                    - 0.010
                )
                * sin_theta,
                z_mm,
            )

            assert threaded_sleeve.isInside(
                material,
                1.0e-7,
            )

            assert not threaded_sleeve.isInside(
                void,
                1.0e-7,
            )
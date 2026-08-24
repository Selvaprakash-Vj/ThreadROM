"""Tests for the complete canonical internally threaded nut."""

from __future__ import annotations

import math
from pathlib import Path

import cadquery as cq
import pytest

from threadrom.geometry.canonical_screw_geometry import (
    canonical_internal_radius_from_phase_mm,
)
from threadrom.geometry.complete_nut import (
    CompleteNutBuild,
    build_complete_nut,
    load_complete_nut_definitions,
    measure_complete_nut,
)
from threadrom.geometry.geometry_quality import (
    load_geometry_quality_policy,
)
from threadrom.geometry.internal_thread_cutter import (
    InternalThreadCutterDefinition,
)
from threadrom.geometry.nut_blank import (
    NutBlankDefinition,
    measure_nut_blank,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

GEOMETRY_QUALITY_POLICY = load_geometry_quality_policy(
    PROJECT_ROOT
    / "config"
    / "geometry_quality.toml"
)


@pytest.fixture(scope="module")
def definitions() -> tuple[
    NutBlankDefinition,
    InternalThreadCutterDefinition,
]:
    """Load the governed nut definitions once."""

    return load_complete_nut_definitions(
        PROJECT_ROOT
    )


@pytest.fixture(scope="module")
def complete_nut_build(
    definitions: tuple[
        NutBlankDefinition,
        InternalThreadCutterDefinition,
    ],
) -> CompleteNutBuild:
    """Build the governed canonical nut once for this module."""

    nut_definition, thread_definition = definitions

    return build_complete_nut(
        nut_definition,
        thread_definition,
        GEOMETRY_QUALITY_POLICY,
    )


def test_complete_nut_definitions_are_consistent(
    definitions: tuple[
        NutBlankDefinition,
        InternalThreadCutterDefinition,
    ],
) -> None:
    """The governed nut and internal-thread definitions agree."""

    nut_definition, thread_definition = definitions

    assert nut_definition.geometry_id == "TRM-GEO-000001"
    assert nut_definition.assembly_id == "TRM-ASM-000001"

    assert nut_definition.nominal_diameter_mm == pytest.approx(
        thread_definition.nominal_diameter_mm
    )

    assert nut_definition.pitch_mm == pytest.approx(
        thread_definition.pitch_mm
    )

    assert nut_definition.bore_diameter_mm == pytest.approx(
        thread_definition.minor_diameter_mm
    )

    assert nut_definition.thickness_mm == pytest.approx(
        thread_definition.thread_length_mm
    )


def test_complete_threaded_nut_is_valid(
    complete_nut_build: CompleteNutBuild,
) -> None:
    """The compact canonical construction produces one valid nut."""

    measurements = measure_complete_nut(
        complete_nut_build
    )

    assert measurements.solid_count == 1
    assert measurements.is_valid

    assert measurements.complete_volume_mm3 > 0.0

    assert (
        measurements.construction_shell_volume_mm3
        < measurements.complete_volume_mm3
        < measurements.blank_volume_mm3
    )

    assert measurements.added_thread_material_mm3 > 1.0
    assert measurements.removed_thread_volume_mm3 > 1.0

    assert measurements.thread_segment_count == 6

    assert (
        measurements.thread_construction_volume_mm3
        > measurements.added_thread_material_mm3
    )


def test_internal_thread_preserves_outer_nut_envelope(
    complete_nut_build: CompleteNutBuild,
    definitions: tuple[
        NutBlankDefinition,
        InternalThreadCutterDefinition,
    ],
) -> None:
    """Canonical thread construction preserves the governed hex envelope."""

    nut_definition, _ = definitions

    blank_measurements = measure_nut_blank(
        complete_nut_build.nut_blank
    )

    complete_measurements = measure_complete_nut(
        complete_nut_build
    )

    assert complete_measurements.x_length_mm == pytest.approx(
        blank_measurements.x_length_mm
    )

    assert complete_measurements.y_length_mm == pytest.approx(
        blank_measurements.y_length_mm
    )

    assert complete_measurements.z_min_mm == pytest.approx(
        0.0,
        abs=2.0e-7,
    )

    assert complete_measurements.z_max_mm == pytest.approx(
        nut_definition.thickness_mm,
        abs=2.0e-7,
    )

    assert (
        complete_nut_build.complete_nut.Area()
        > complete_nut_build.nut_blank.Area()
    )


def test_complete_nut_tracks_canonical_internal_thread(
    complete_nut_build: CompleteNutBuild,
    definitions: tuple[
        NutBlankDefinition,
        InternalThreadCutterDefinition,
    ],
) -> None:
    """The actual production nut follows the canonical screw oracle."""

    _, thread_definition = definitions

    nut = complete_nut_build.complete_nut

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
                    z_mm
                    - phase_mm
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
                    nut.distance(
                        boundary
                    )
                )
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

            if nut.isInside(
                material,
                1.0e-7,
            ):
                material_passes += 1

            if not nut.isInside(
                void,
                1.0e-7,
            ):
                void_passes += 1

            sample_count += 1

    assert max(boundary_errors) <= 1.0e-3
    assert material_passes == sample_count
    assert void_passes == sample_count
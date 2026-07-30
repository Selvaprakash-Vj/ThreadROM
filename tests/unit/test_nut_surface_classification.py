"""Tests for geometry-driven nut-surface classification."""

from pathlib import Path

from threadrom.geometry.nut_blank import (
    NutBlankDefinition,
    load_nut_blank_definition,
)
from threadrom.meshing.nut_surface_classification import (
    INTERNAL_THREAD,
    LOWER_BEARING,
    OUTER_HEX,
    UPPER_BEARING,
    NutSurfaceClassificationDefinition,
    classify_nut_surface_region,
    load_nut_surface_classification_definition,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_definitions() -> tuple[
    NutBlankDefinition,
    NutSurfaceClassificationDefinition,
]:
    """Load governed nut and classification definitions."""

    nut_definition = load_nut_blank_definition(
        PROJECT_ROOT / "config" / "nut_geometry.toml",
        PROJECT_ROOT / "config" / "baseline_fastener.toml",
        PROJECT_ROOT / "config" / "baseline_assembly.toml",
    )

    classification_definition = (
        load_nut_surface_classification_definition(
            PROJECT_ROOT
            / "config"
            / "nut_surface_classification.toml"
        )
    )

    return nut_definition, classification_definition


def test_nut_surface_classification_definition() -> None:
    """The governed classification names load correctly."""

    _, definition = load_definitions()

    assert definition.mesh_id == "TRM-MSH-000004"
    assert definition.geometry_id == "TRM-GEO-000001"
    assert definition.lower_bearing_name == (
        "nut_lower_bearing"
    )
    assert definition.upper_bearing_name == (
        "nut_upper_bearing"
    )
    assert definition.outer_hex_name == "nut_outer_hex"
    assert definition.internal_thread_name == (
        "nut_internal_thread"
    )


def test_nut_bearing_faces_are_classified_by_plane() -> None:
    """Lower and upper planar faces receive bearing names."""

    nut, definition = load_definitions()

    lower = classify_nut_surface_region(
        x_min_mm=-9.0,
        x_max_mm=9.0,
        y_min_mm=-8.0,
        y_max_mm=8.0,
        z_min_mm=0.0,
        z_max_mm=0.0,
        nut_definition=nut,
        definition=definition,
    )

    upper = classify_nut_surface_region(
        x_min_mm=-9.0,
        x_max_mm=9.0,
        y_min_mm=-8.0,
        y_max_mm=8.0,
        z_min_mm=8.0,
        z_max_mm=8.0,
        nut_definition=nut,
        definition=definition,
    )

    assert lower == LOWER_BEARING
    assert upper == UPPER_BEARING


def test_nut_radial_regions_are_distinguished() -> None:
    """Internal thread and outer hex surfaces remain distinct."""

    nut, definition = load_definitions()

    internal = classify_nut_surface_region(
        x_min_mm=-5.0,
        x_max_mm=5.0,
        y_min_mm=-5.0,
        y_max_mm=5.0,
        z_min_mm=0.0,
        z_max_mm=8.0,
        nut_definition=nut,
        definition=definition,
    )

    external = classify_nut_surface_region(
        x_min_mm=4.6,
        x_max_mm=9.24,
        y_min_mm=0.0,
        y_max_mm=8.0,
        z_min_mm=0.0,
        z_max_mm=8.0,
        nut_definition=nut,
        definition=definition,
    )

    assert internal == INTERNAL_THREAD
    assert external == OUTER_HEX


def test_helical_thread_bounds_may_cross_nut_planes() -> None:
    """Swept thread faces are governed by sampled radial position."""

    nut, definition = load_definitions()

    region = classify_nut_surface_region(
        x_min_mm=-6.48,
        x_max_mm=6.48,
        y_min_mm=-6.48,
        y_max_mm=6.48,
        z_min_mm=-0.1875,
        z_max_mm=8.1875,
        sampled_radial_max_mm=5.030002,
        nut_definition=nut,
        definition=definition,
    )

    assert region == INTERNAL_THREAD

"""Integration tests for parametric bolt-surface classification."""

from pathlib import Path

from threadrom.geometry.complete_bolt import (
    build_complete_bolt,
    export_and_reimport_step,
)
from threadrom.geometry.geometry_quality import (
    load_geometry_quality_policy,
)
from threadrom.geometry.threaded_shank import (
    load_threaded_shank_definitions,
)
from threadrom.meshing.surface_classification import (
    BOLT_TIP,
    HEAD_SIDES,
    HEAD_TOP,
    REGION_ORDER,
    THREAD_SURFACES,
    UNDER_HEAD_BEARING,
    classify_step_surfaces,
    load_surface_classification_definition,
)


def test_surface_classification_definition_loads() -> None:
    """The controlled surface-classification policy is valid."""

    project_root = Path(__file__).resolve().parents[2]

    definition = load_surface_classification_definition(
        project_root / "config" / "surface_classification.toml"
    )

    assert definition.mesh_id == "TRM-MSH-000001"
    assert definition.geometry_id == "TRM-GEO-000001"
    assert definition.plane_tolerance_mm > 0.0

    assert definition.minimum_head_side_surface_count >= 6


def test_complete_bolt_surfaces_are_classified(
    tmp_path: Path,
) -> None:
    """Every complete-bolt surface enters one engineering region."""

    project_root = Path(__file__).resolve().parents[2]

    blank_definition, thread_definition = load_threaded_shank_definitions(project_root)

    quality_policy = load_geometry_quality_policy(project_root / "config" / "geometry_quality.toml")

    classification_definition = load_surface_classification_definition(
        project_root / "config" / "surface_classification.toml"
    )

    bolt_build = build_complete_bolt(
        blank_definition,
        thread_definition,
        quality_policy,
    )

    step_path = tmp_path / "complete_bolt.step"

    export_and_reimport_step(
        bolt_build.complete_bolt,
        step_path,
    )

    result = classify_step_surfaces(
        step_path,
        blank_definition,
        classification_definition,
    )

    assert result.imported_volume_count == 1
    assert result.surface_count > 0

    assert result.count_for(HEAD_TOP) >= 1
    assert result.count_for(UNDER_HEAD_BEARING) >= 1
    assert result.count_for(HEAD_SIDES) >= 6
    assert result.count_for(THREAD_SURFACES) >= 1
    assert result.count_for(BOLT_TIP) >= 1

    classified_tags = [surface.tag for surface in result.surfaces]

    assert len(classified_tags) == len(set(classified_tags))

    assert all(surface.area_mm2 > 0.0 for surface in result.surfaces)

    registered_regions = {group.region for group in result.physical_groups}

    expected_regions = {region for region in REGION_ORDER if result.count_for(region) > 0}

    assert registered_regions == expected_regions

    for group in result.physical_groups:
        assert group.entity_count == result.count_for(group.region)

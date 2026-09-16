"""Physical-root contract for the production external thread."""

from pathlib import Path

import cadquery as cq

from threadrom.geometry.geometry_quality import (
    load_geometry_quality_policy,
)
from threadrom.geometry.threaded_shank import (
    build_threaded_shank,
    load_threaded_shank_definitions,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_boolean_overlap_does_not_fill_above_external_minor_radius() -> None:
    """Boolean overlap must stay buried below the physical root datum."""

    blank, thread = load_threaded_shank_definitions(
        PROJECT_ROOT
    )

    policy = load_geometry_quality_policy(
        PROJECT_ROOT / "config" / "geometry_quality.toml"
    )

    build = build_threaded_shank(
        blank,
        thread,
        policy,
    )

    overlap = policy.thread_boolean_overlap_mm

    # At theta=0, choose the centre of a thread-root interval well
    # inside the finite threaded length:
    #
    #   crest centres: z = k*P
    #   root centres : z = (k + 1/2)*P
    #
    root_z_mm = 5.5 * thread.pitch_mm

    # This point lies radially ABOVE the governed external minor/root
    # radius but BELOW the currently enlarged construction-core radius.
    #
    # It therefore must be void in the finished physical thread if
    # Boolean overlap is truly only a buried construction aid.
    probe_radius_mm = (
        thread.minor_radius_mm
        + 0.5 * overlap
    )

    probe = cq.Vector(
        probe_radius_mm,
        0.0,
        root_z_mm,
    )

    assert not build.threaded_shank.isInside(
        probe,
        1.0e-7,
    )

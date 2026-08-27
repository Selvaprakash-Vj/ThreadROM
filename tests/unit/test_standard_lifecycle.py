"""Tests for ISO lifecycle resolution."""

import pytest

from threadrom.case.standard_catalog import (
    StandardLifecycle,
    resolve_standard_lifecycle,
)


@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        (None, StandardLifecycle.UNKNOWN),
        (98, StandardLifecycle.UNDER_DEVELOPMENT),
        (1098, StandardLifecycle.UNDER_DEVELOPMENT),
        (2098, StandardLifecycle.UNDER_DEVELOPMENT),
        (3020, StandardLifecycle.UNDER_DEVELOPMENT),
        (3098, StandardLifecycle.UNDER_DEVELOPMENT),
        (4020, StandardLifecycle.UNDER_DEVELOPMENT),
        (4098, StandardLifecycle.UNDER_DEVELOPMENT),
        (5098, StandardLifecycle.UNDER_DEVELOPMENT),
        (6060, StandardLifecycle.PUBLISHED),
        (9020, StandardLifecycle.PUBLISHED),
        (9092, StandardLifecycle.PUBLISHED),
        (9093, StandardLifecycle.PUBLISHED),
        (9500, StandardLifecycle.WITHDRAWN),
        (9599, StandardLifecycle.WITHDRAWN),
    ],
)
def test_iso_stage_resolves_to_expected_lifecycle(
    stage: int | None,
    expected: StandardLifecycle,
) -> None:
    """Representative ISO harmonized stages resolve deterministically."""

    assert resolve_standard_lifecycle(stage) is expected


def test_negative_iso_stage_is_rejected() -> None:
    """Invalid negative ISO lifecycle stages fail immediately."""

    with pytest.raises(ValueError):
        resolve_standard_lifecycle(-1)

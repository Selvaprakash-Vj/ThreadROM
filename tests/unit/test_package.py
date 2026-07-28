"""Smoke tests for the ThreadROM package."""

import threadrom


def test_package_version() -> None:
    """Verify that the package exposes its current version."""
    assert threadrom.__version__ == "0.1.0"
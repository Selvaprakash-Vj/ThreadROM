"""Unit tests for tetrahedral quality mathematics."""

import math

import numpy as np
import pytest

from threadrom.meshing.tetrahedral_quality import (
    calculate_tetrahedron_quality,
)


def test_equilateral_tetrahedron_has_ideal_quality() -> None:
    """An equilateral tetrahedron has mean and edge ratios of one."""

    points = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.5, math.sqrt(3.0) / 2.0, 0.0],
            [
                0.5,
                math.sqrt(3.0) / 6.0,
                math.sqrt(2.0 / 3.0),
            ],
        ],
        dtype=np.float64,
    )

    tetrahedra = np.asarray(
        [[0, 1, 2, 3]],
        dtype=np.int64,
    )

    quality = calculate_tetrahedron_quality(
        points,
        tetrahedra,
    )

    assert quality.absolute_volumes_mm3[0] == pytest.approx(math.sqrt(2.0) / 12.0)

    assert quality.mean_ratios[0] == pytest.approx(1.0)
    assert quality.edge_ratios[0] == pytest.approx(1.0)


def test_coplanar_tetrahedron_is_degenerate() -> None:
    """A coplanar tetrahedron has zero volume and zero mean ratio."""

    points = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [1.0, 1.0, 0.0],
        ],
        dtype=np.float64,
    )

    tetrahedra = np.asarray(
        [[0, 1, 2, 3]],
        dtype=np.int64,
    )

    quality = calculate_tetrahedron_quality(
        points,
        tetrahedra,
    )

    assert quality.absolute_volumes_mm3[0] == pytest.approx(0.0)
    assert quality.mean_ratios[0] == pytest.approx(0.0)

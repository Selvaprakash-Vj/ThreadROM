"""Integration test for the CalculiX solver adapter."""

from pathlib import Path

import pytest

from threadrom.solver.calculix import resolve_ccx, run_smoke_test


def test_calculix_linear_elastic_smoke_case() -> None:
    """CalculiX reproduces the expected mean axial stress."""

    ccx_path = resolve_ccx()

    if not Path(ccx_path).is_file():
        pytest.skip("CalculiX is not installed in the configured location.")

    result = run_smoke_test()

    assert result.exit_code == 0
    assert result.relative_stress_error < 0.02
    assert result.mean_loaded_displacement_m > 0.0
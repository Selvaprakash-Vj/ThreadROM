"""Unit tests for Gmsh-to-CalculiX mesh transfer."""

from pathlib import Path

import meshio  # type: ignore[import-untyped]
import numpy as np
import pytest

from threadrom.solver.calculix_mesh_transfer import (
    CalculixTransferDefinition,
    evaluate_calculix_force_balance,
    read_grouped_mesh_for_calculix,
    write_calculix_transfer_deck,
)


def _definition() -> CalculixTransferDefinition:
    """Return a controlled synthetic transfer definition."""

    return CalculixTransferDefinition(
        simulation_id="TRM-SIM-TEST",
        mesh_id="TRM-MSH-TEST",
        geometry_id="TRM-GEO-TEST",
        mesh_level="coarse",
        executable_relative_path=Path("ccx.exe"),
        job_name="synthetic_transfer",
        timeout_seconds=30,
        volume_group="BOLT",
        fixed_node_group="BOLT_TIP",
        loaded_node_group="BOLT_HEAD_TOP",
        element_type="C3D4",
        material_name="BOLT_STEEL",
        youngs_modulus_mpa=210000.0,
        poissons_ratio=0.3,
        total_axial_force_n=-1000.0,
        minimum_node_count=4,
        minimum_element_count=1,
        force_balance_tolerance_n=0.1,
        required_boundary_groups=(
            "BOLT_HEAD_TOP",
            "BOLT_TIP",
        ),
    )


def _write_synthetic_grouped_mesh(
    path: Path,
) -> None:
    """Write one tetrahedron with two named boundary groups."""

    points = np.asarray(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )

    tetrahedra = np.asarray(
        [[0, 1, 2, 3]],
        dtype=np.int64,
    )

    triangles = np.asarray(
        [
            [0, 1, 2],
            [0, 1, 3],
        ],
        dtype=np.int64,
    )

    mesh = meshio.Mesh(
        points=points,
        cells=[
            ("tetra", tetrahedra),
            ("triangle", triangles),
        ],
        cell_data={
            "gmsh:physical": [
                np.asarray(
                    [1],
                    dtype=np.int32,
                ),
                np.asarray(
                    [2, 3],
                    dtype=np.int32,
                ),
            ],
            "gmsh:geometrical": [
                np.asarray(
                    [1],
                    dtype=np.int32,
                ),
                np.asarray(
                    [2, 3],
                    dtype=np.int32,
                ),
            ],
        },
        field_data={
            "BOLT": np.asarray(
                [1, 3],
                dtype=np.int32,
            ),
            "BOLT_HEAD_TOP": np.asarray(
                [2, 2],
                dtype=np.int32,
            ),
            "BOLT_TIP": np.asarray(
                [3, 2],
                dtype=np.int32,
            ),
        },
    )

    meshio.write(
        path,
        mesh,
        file_format="gmsh22",
        binary=False,
    )


def test_grouped_mesh_converts_to_calculix_data(
    tmp_path: Path,
) -> None:
    """Named Gmsh groups become CalculiX boundary node sets."""

    msh_path = tmp_path / "synthetic.msh"

    _write_synthetic_grouped_mesh(msh_path)

    mesh_data = read_grouped_mesh_for_calculix(
        msh_path,
        _definition(),
    )

    assert mesh_data.node_count == 4
    assert mesh_data.element_count == 1
    assert mesh_data.volume_group_name == "BOLT"

    assert mesh_data.boundary_node_sets["BOLT_HEAD_TOP"] == (1, 2, 3)

    assert mesh_data.boundary_node_sets["BOLT_TIP"] == (1, 2, 4)


def test_calculix_deck_preserves_sets_and_force(
    tmp_path: Path,
) -> None:
    """The generated input deck preserves sets and force balance."""

    msh_path = tmp_path / "synthetic.msh"
    input_path = tmp_path / "synthetic_transfer.inp"

    _write_synthetic_grouped_mesh(msh_path)

    definition = _definition()

    mesh_data = read_grouped_mesh_for_calculix(
        msh_path,
        definition,
    )

    with pytest.raises(
        RuntimeError,
        match="share nodes",
    ):
        write_calculix_transfer_deck(
            mesh_data,
            definition,
            input_path,
        )


def test_calculix_total_force_is_balanced(
    tmp_path: Path,
) -> None:
    """The fixed-support reaction balances the applied axial load."""

    dat_path = tmp_path / "synthetic_transfer.dat"

    dat_path.write_text(
        (
            " total force (fx,fy,fz) for set BOLT_TIP "
            "and time  0.1000000E+01\n"
            "\n"
            "        5.666245E-12 "
            "-5.234979E-12  1.000000E+03\n"
        ),
        encoding="utf-8",
        newline="\n",
    )

    result = evaluate_calculix_force_balance(
        dat_path,
        _definition(),
    )

    assert result.reaction_x_n == pytest.approx(5.666245e-12)

    assert result.reaction_y_n == pytest.approx(-5.234979e-12)

    assert result.reaction_z_n == pytest.approx(1000.0)

    assert result.applied_z_n == pytest.approx(-1000.0)

    assert result.residual_z_n == pytest.approx(0.0)

    assert result.maximum_absolute_residual_n < 0.1

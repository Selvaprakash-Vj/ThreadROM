"""Tests for the reduced complete-joint settling diagnostics."""

from pathlib import Path

import pytest

from threadrom.solver.complete_joint_boundary_regions import (
    load_complete_joint_boundary_region_definition,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    load_complete_joint_calculix_transfer_definition,
    read_grouped_complete_joint_mesh,
)
from threadrom.solver.complete_joint_contact import (
    load_complete_joint_contact_definition,
)
from threadrom.solver.complete_joint_pretension import (
    load_complete_joint_pretension_definition,
)
from threadrom.solver.complete_joint_settling_diagnostic import (
    SETTLING_DIAGNOSTIC_CASES,
    CompleteJointSettlingDiagnosticCase,
    settling_diagnostic_case,
    write_complete_joint_settling_diagnostic_deck,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_settling_diagnostic_case_matrix_is_governed() -> None:
    """A0-A3 and A0T resolve to the approved section and force matrix."""

    expected = {
        "A0": (False, 0.0, ()),
        "A0T": (False, 0.0, ("thread",)),
        "A1": (True, 0.0, ()),
        "A2": (True, 1.0, ()),
        "A3": (True, -1.0, ()),
    }

    assert tuple(case.case_id for case in SETTLING_DIAGNOSTIC_CASES) == tuple(expected)

    for case_id, governed_values in expected.items():
        case = settling_diagnostic_case(case_id.lower())

        assert (
            case.include_pretension_section,
            case.reference_force_n,
            case.excluded_contact_pair_names,
        ) == governed_values


def test_settling_diagnostic_case_rejects_invalid_definition() -> None:
    """Case identifiers cannot be assigned ungoverned behavior."""

    with pytest.raises(
        ValueError,
        match="does not match its governed definition",
    ):
        CompleteJointSettlingDiagnosticCase(
            case_id="A2",
            include_pretension_section=True,
            reference_force_n=2.0,
        )

    with pytest.raises(
        ValueError,
        match="Unknown settling diagnostic case",
    ):
        CompleteJointSettlingDiagnosticCase(
            case_id="A4",
            include_pretension_section=True,
            reference_force_n=1.0,
        )

    with pytest.raises(
        KeyError,
        match="Unknown settling diagnostic case",
    ):
        settling_diagnostic_case("A4")


def test_write_complete_joint_settling_diagnostic_decks(
    tmp_path: Path,
) -> None:
    """A0-A3 and A0T differ only through governed pretension controls."""

    config = PROJECT_ROOT / "config"

    transfer = load_complete_joint_calculix_transfer_definition(
        config / ("complete_joint_pretension_calculix_transfer_c3d4_coarse_diagnostic.toml")
    )

    contact = load_complete_joint_contact_definition(
        config / "complete_joint_pretension_contact_c3d4_coarse_diagnostic.toml"
    )

    boundary = load_complete_joint_boundary_region_definition(
        config / ("complete_joint_pretension_boundary_regions_c3d4_coarse_diagnostic.toml")
    )

    pretension = load_complete_joint_pretension_definition(
        config / "complete_joint_pretension_c3d4_coarse_diagnostic.toml"
    )

    mesh = read_grouped_complete_joint_mesh(
        (
            PROJECT_ROOT
            / "simulations"
            / "staging"
            / transfer.mesh_id
            / "mesh"
            / transfer.source_mesh_name
        ),
        transfer,
    )

    reference_node_id = mesh.node_count + 1

    expected = {
        "A0": {
            "pretension_count": 0,
            "cload_count": 0,
            "reference_node_id": None,
            "reference_force_n": 0.0,
        },
        "A0T": {
            "pretension_count": 0,
            "cload_count": 0,
            "reference_node_id": None,
            "reference_force_n": 0.0,
        },
        "A1": {
            "pretension_count": 1,
            "cload_count": 0,
            "reference_node_id": reference_node_id,
            "reference_force_n": 0.0,
        },
        "A2": {
            "pretension_count": 1,
            "cload_count": 1,
            "reference_node_id": reference_node_id,
            "reference_force_n": 1.0,
        },
        "A3": {
            "pretension_count": 1,
            "cload_count": 1,
            "reference_node_id": reference_node_id,
            "reference_force_n": -1.0,
        },
    }

    excluded_face_counts: set[int] = set()

    for case in SETTLING_DIAGNOSTIC_CASES:
        input_path = tmp_path / f"{case.case_id.lower()}.inp"

        summary = write_complete_joint_settling_diagnostic_deck(
            mesh,
            transfer,
            contact,
            boundary,
            pretension,
            case,
            input_path,
        )

        text = input_path.read_text(encoding="utf-8")
        governed = expected[case.case_id]

        assert summary.case_id == case.case_id
        assert summary.pretension_section_count == governed["pretension_count"]
        assert summary.cload_count == governed["cload_count"]
        assert summary.reference_node_id == governed["reference_node_id"]
        assert summary.applied_reference_force_n == governed["reference_force_n"]

        expected_contact_pair_count = 4 - len(case.excluded_contact_pair_names)

        assert summary.contact_pair_count == expected_contact_pair_count
        assert summary.excluded_contact_pair_names == case.excluded_contact_pair_names
        assert summary.interaction_count == 1
        assert summary.step_count == 1
        assert summary.restart_write_count == 0

        assert summary.boundary_region_count == 2
        assert summary.boundary_region_node_count == 367

        assert summary.guidance_reference_node_count == 8
        assert summary.guidance_sample_node_count == 240
        assert summary.distributing_coupling_count == 3
        assert summary.mean_rotation_mpc_count == 5

        assert summary.excluded_thread_contact_face_count == 271
        assert summary.input_file_size_bytes > 8_000_000

        assert text.count("*CONTACT PAIR,") == expected_contact_pair_count
        assert text.count("*SURFACE INTERACTION,") == 1

        thread_pair = "SURF_NUT_INTERNAL_THREAD, SURF_BOLT_THREAD_SURFACES"

        if case.case_id == "A0T":
            assert "** Contact pair: thread" not in text
            assert thread_pair not in text
        else:
            assert "** Contact pair: thread" in text
            assert thread_pair in text
        assert text.count("*STEP,") == 1
        assert text.count("*END STEP") == 1
        assert text.count("*ELEMENT, TYPE=DCOUP3D") == 3
        assert text.count("*DISTRIBUTING COUPLING,") == 3
        assert text.count("MEANROT,") == 5

        assert "HEAD_MEMBER_SUPPORT_BAND, 1, 3, 0.0" in text
        assert "ALL_NODES, 1, 3, 0.0" not in text
        assert "*RESTART,WRITE" not in text

        if not case.include_pretension_section:
            assert "*PRE-TENSION SECTION," not in text
            assert "BOLT_PRETENSION_REFERENCE" not in text
            assert "*CLOAD" not in text
        else:
            assert text.count("*PRE-TENSION SECTION,") == 1
            assert "BOLT_PRETENSION_REFERENCE" in text

        if case.case_id == "A2":
            assert (f"{reference_node_id}, 1, 1.000000000000e+00") in text

        if case.case_id == "A3":
            assert (f"{reference_node_id}, 1, -1.000000000000e+00") in text

        excluded_face_counts.add(summary.excluded_thread_contact_face_count)

    assert excluded_face_counts == {271}

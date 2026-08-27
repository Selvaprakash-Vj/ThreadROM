"""Tests for the governed ThreadROM product-level case contract."""

from dataclasses import FrozenInstanceError

import pytest

from threadrom.case import AnalysisFidelity, CalculationMode
from threadrom.case.contract import (
    AnalysisSelection,
    FastenerSelection,
    InterfacesSelection,
    LoadingSelection,
    MemberLayerSelection,
    MembersSelection,
    ThreadROMCase,
)
from threadrom.engineering.analytical_inputs import ThreadHandedness


def _baseline_case() -> ThreadROMCase:
    """Return a Phase-2-shaped case using only authoritative inputs."""

    members = MembersSelection(
        layers=(
            MemberLayerSelection(
                layer_id="upper_member",
                thickness_mm=10.0,
                material_id="steel_member",
                outer_diameter_mm=30.0,
                clearance_hole_diameter_mm=11.0,
            ),
            MemberLayerSelection(
                layer_id="lower_member",
                thickness_mm=10.0,
                material_id="steel_member",
                outer_diameter_mm=30.0,
                clearance_hole_diameter_mm=11.0,
            ),
        )
    )

    return ThreadROMCase(
        fastener=FastenerSelection(
            bolt_standard="ISO 4017:2022",
            thread_designation="M10x1.5",
            bolt_length_mm=30.0,
            bolt_material_id="fastener_steel",
            bolt_property_class="8.8",
            nut_standard="ISO 4032:2023",
            nut_material_id="fastener_steel",
            nut_property_class="8",
            handedness=ThreadHandedness.RIGHT,
            starts=1,
        ),
        members=members,
        interfaces=InterfacesSelection(
            thread_friction_coefficient=0.15,
            head_bearing_friction_coefficient=0.15,
            nut_bearing_friction_coefficient=0.15,
            member_interface_friction_coefficient=0.15,
        ),
        loading=LoadingSelection(
            target_preload_n=20_000.0,
            external_axial_load_n=0.0,
        ),
        analysis=AnalysisSelection(
            calculation_mode=CalculationMode.FEM,
            fidelity=AnalysisFidelity.CERTIFICATION,
        ),
    )


def test_case_contract_represents_certified_baseline_shape() -> None:
    """The certified joint family is representable without derived inputs."""

    case = _baseline_case()

    assert case.fastener.thread_designation == "M10x1.5"
    assert case.fastener.bolt_length_mm == pytest.approx(30.0)
    assert case.members.member_count == 2
    assert case.members.total_grip_length_mm == pytest.approx(20.0)
    assert case.loading.target_preload_n == pytest.approx(20_000.0)
    assert case.loading.external_axial_load_n == pytest.approx(0.0)


def test_case_contract_is_immutable() -> None:
    """Authoritative case inputs cannot mutate after construction."""

    case = _baseline_case()

    with pytest.raises(FrozenInstanceError):
        case.loading.target_preload_n = 10_000.0


def test_duplicate_member_layer_ids_are_rejected() -> None:
    """Member identities must remain unique within one case."""

    layer = MemberLayerSelection(
        layer_id="member",
        thickness_mm=10.0,
        material_id="steel",
        outer_diameter_mm=30.0,
        clearance_hole_diameter_mm=11.0,
    )

    with pytest.raises(ValueError):
        MembersSelection(
            layers=(layer, layer),
        )


@pytest.mark.parametrize(
    ("outer_diameter_mm", "hole_diameter_mm"),
    [
        (11.0, 11.0),
        (10.0, 11.0),
        (0.0, 11.0),
        (30.0, 0.0),
    ],
)
def test_invalid_member_geometry_is_rejected(
    outer_diameter_mm: float,
    hole_diameter_mm: float,
) -> None:
    """Impossible or non-positive member dimensions are rejected."""

    with pytest.raises(ValueError):
        MemberLayerSelection(
            layer_id="member",
            thickness_mm=10.0,
            material_id="steel",
            outer_diameter_mm=outer_diameter_mm,
            clearance_hole_diameter_mm=hole_diameter_mm,
        )


@pytest.mark.parametrize(
    "friction_coefficient",
    [-0.01, 1.01],
)
def test_invalid_interface_friction_is_rejected(
    friction_coefficient: float,
) -> None:
    """Interface friction coefficients remain bounded."""

    with pytest.raises(ValueError):
        InterfacesSelection(
            thread_friction_coefficient=friction_coefficient,
            head_bearing_friction_coefficient=0.15,
            nut_bearing_friction_coefficient=0.15,
            member_interface_friction_coefficient=0.15,
        )


@pytest.mark.parametrize(
    ("bolt_length_mm", "starts"),
    [
        (0.0, 1),
        (-30.0, 1),
        (30.0, 0),
    ],
)
def test_invalid_fastener_selections_are_rejected(
    bolt_length_mm: float,
    starts: int,
) -> None:
    """Structurally invalid fastener selections are rejected."""

    with pytest.raises(ValueError):
        FastenerSelection(
            bolt_standard="ISO 4017:2022",
            thread_designation="M10x1.5",
            bolt_length_mm=bolt_length_mm,
            bolt_material_id="fastener_steel",
            bolt_property_class="8.8",
            nut_standard="ISO 4032:2023",
            nut_material_id="fastener_steel",
            nut_property_class="8",
            starts=starts,
        )


def test_zero_external_load_is_valid() -> None:
    """Preload-only cases are valid product-level requests."""

    loading = LoadingSelection(
        target_preload_n=20_000.0,
        external_axial_load_n=0.0,
    )

    assert loading.external_axial_load_n == pytest.approx(0.0)



def test_case_schema_version_defaults_to_current_version() -> None:
    """New cases use the current governed schema version."""

    case = _baseline_case()

    assert case.schema_version == 1


def test_unsupported_case_schema_version_is_rejected() -> None:
    """Unknown persisted case schemas fail rather than being misread."""

    case = _baseline_case()

    with pytest.raises(ValueError):
        ThreadROMCase(
            fastener=case.fastener,
            members=case.members,
            interfaces=case.interfaces,
            loading=case.loading,
            schema_version=999,
            analysis=case.analysis,
            metadata=case.metadata,
        )

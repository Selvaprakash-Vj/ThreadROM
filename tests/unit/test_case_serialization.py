"""Tests for deterministic ThreadROM case serialization."""

from dataclasses import replace

from threadrom.case import AnalysisFidelity, CalculationMode
from threadrom.case.contract import (
    AnalysisSelection,
    CaseMetadata,
    FastenerSelection,
    InterfacesSelection,
    LoadingSelection,
    MemberLayerSelection,
    MembersSelection,
    ThreadROMCase,
)
from threadrom.case.serialization import (
    canonical_case_json,
    case_sha256,
)
from threadrom.engineering.analytical_inputs import ThreadHandedness


def _case() -> ThreadROMCase:
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
        members=MembersSelection(
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
        ),
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
        metadata=CaseMetadata(
            name="baseline",
            notes="certified reference",
        ),
    )


def test_case_serialization_is_deterministic() -> None:
    """Repeated serialization and hashing produce identical output."""

    case = _case()

    assert canonical_case_json(case) == canonical_case_json(case)
    assert case_sha256(case) == case_sha256(case)
    assert len(case_sha256(case)) == 64


def test_metadata_does_not_change_engineering_fingerprint() -> None:
    """Human-facing labels do not create a different engineering case."""

    case = _case()

    renamed = replace(
        case,
        metadata=CaseMetadata(
            name="renamed case",
            notes="different human notes",
        ),
    )

    assert case_sha256(renamed) == case_sha256(case)


def test_physical_change_changes_engineering_fingerprint() -> None:
    """A physical input change creates a different engineering case."""

    case = _case()

    changed = replace(
        case,
        loading=replace(
            case.loading,
            target_preload_n=19_000.0,
        ),
    )

    assert case_sha256(changed) != case_sha256(case)


def test_analysis_request_changes_engineering_fingerprint() -> None:
    """Calculation mode and fidelity are part of case identity."""

    case = _case()

    changed = replace(
        case,
        analysis=AnalysisSelection(
            calculation_mode=CalculationMode.ANALYTICAL,
            fidelity=AnalysisFidelity.SCREENING,
        ),
    )

    assert case_sha256(changed) != case_sha256(case)


def test_member_stack_order_changes_engineering_fingerprint() -> None:
    """Member order remains physically meaningful."""

    case = _case()

    reversed_members = replace(
        case,
        members=MembersSelection(
            layers=tuple(reversed(case.members.layers))
        ),
    )

    assert case_sha256(reversed_members) != case_sha256(case)


def test_equivalent_integer_and_float_inputs_hash_identically() -> None:
    """Equivalent numeric values canonicalize to one engineering identity."""

    case = _case()

    equivalent = replace(
        case,
        loading=LoadingSelection(
            target_preload_n=20_000,
            external_axial_load_n=0,
        ),
    )

    assert canonical_case_json(equivalent) == canonical_case_json(case)
    assert case_sha256(equivalent) == case_sha256(case)

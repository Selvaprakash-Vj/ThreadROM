from __future__ import annotations

import pytest

from threadrom.factory.production_doe_reaction_observable_revision import (
    REACTION_OBSERVABLE_REVISION_TAG,
    bridge_bundle_to_frozen_production_doe_identity,
    certify_named_reaction_observability,
    derive_reaction_observable_revision_identity,
)


def test_revision_identity_preserves_trial_one_semantics():
    identity = derive_reaction_observable_revision_identity(
        case_run_id="trm_fem_d667bb1aca27",
    )

    assert identity.trial_index == 1
    assert (
        identity.source_trial_run_id
        == "trm_fem_d667bb1aca27_cal_01_wsv21"
    )
    assert (
        identity.revision_trial_run_id
        == "trm_fem_d667bb1aca27_cal_01_wsv21_rfobs1"
    )
    assert (
        identity.revision_tag
        == REACTION_OBSERVABLE_REVISION_TAG
    )


def test_revision_identity_rejects_invalid_case_run_id():
    with pytest.raises(
        ValueError,
        match="governed",
    ):
        derive_reaction_observable_revision_identity(
            case_run_id="D-INT-012",
        )


def test_complete_named_reaction_system_is_observable():
    result = certify_named_reaction_observability(
        constrained_reaction_sets=(
            "HEAD_MEMBER_SUPPORT_BAND",
            "BOLT_HEAD_GUIDANCE_REFERENCE",
            "NUT_TRANSLATION_GUIDANCE_REFERENCE",
        ),
        observable_reaction_sets=(
            "HEAD_MEMBER_SUPPORT_BAND",
            "BOLT_HEAD_GUIDANCE_REFERENCE",
            "NUT_TRANSLATION_GUIDANCE_REFERENCE",
        ),
    )

    assert result.fully_observable
    assert result.missing_reaction_sets == ()


def test_missing_named_reaction_carrier_is_rejected():
    with pytest.raises(
        ValueError,
        match="NUT_TRANSLATION_GUIDANCE_REFERENCE",
    ):
        certify_named_reaction_observability(
            constrained_reaction_sets=(
                "HEAD_MEMBER_SUPPORT_BAND",
                "BOLT_HEAD_GUIDANCE_REFERENCE",
                "NUT_TRANSLATION_GUIDANCE_REFERENCE",
            ),
            observable_reaction_sets=(
                "HEAD_MEMBER_SUPPORT_BAND",
                "BOLT_HEAD_GUIDANCE_REFERENCE",
            ),
        )


def test_extra_nonconstrained_output_does_not_reduce_coverage():
    result = certify_named_reaction_observability(
        constrained_reaction_sets=(
            "HEAD_MEMBER_SUPPORT_BAND",
            "BOLT_HEAD_GUIDANCE_REFERENCE",
        ),
        observable_reaction_sets=(
            "HEAD_MEMBER_SUPPORT_BAND",
            "BOLT_HEAD_GUIDANCE_REFERENCE",
            "BOLT_PRETENSION_REFERENCE",
        ),
    )

    assert result.fully_observable
    assert (
        "BOLT_PRETENSION_REFERENCE"
        in result.observable_reaction_sets
    )



def test_frozen_lineage_bridge_rebinds_only_identity_fields():
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Identity:
        case_hash: str
        resolution_hash: str
        run_id: str
        job_name: str

    @dataclass(frozen=True)
    class Preparation:
        identity: Identity
        physics: str

    @dataclass(frozen=True)
    class Transfer:
        simulation_id: str
        job_name: str
        payload: str

    @dataclass(frozen=True)
    class Contact:
        simulation_id: str
        solver_job_name: str
        payload: str

    @dataclass(frozen=True)
    class Boundary:
        simulation_id: str
        payload: str

    @dataclass(frozen=True)
    class Bundle:
        preparation: Preparation
        transfer: Transfer
        contact: Contact
        boundary: Boundary
        guidance_geometry: str
        calibration_seed: str
        calibration_policy: str

    case_hash = (
        "d667bb1aca2720b10e8a80dbcfba700b"
        "042b45a20289927feb5e97a33f3b244c"
    )

    resolution_hash = (
        "675d7450e87b5114f64884ca6c042354"
        "be9d8b0a28b91bdb6f7acf34cf6d1472"
    )

    current = "trm_fem_675d7450e87b"
    frozen = "trm_fem_d667bb1aca27"

    bundle = Bundle(
        preparation=Preparation(
            identity=Identity(
                case_hash=case_hash,
                resolution_hash=resolution_hash,
                run_id=current,
                job_name=current,
            ),
            physics="physics",
        ),
        transfer=Transfer(
            simulation_id=current,
            job_name=current,
            payload="transfer",
        ),
        contact=Contact(
            simulation_id=current,
            solver_job_name=current,
            payload="contact",
        ),
        boundary=Boundary(
            simulation_id=current,
            payload="boundary",
        ),
        guidance_geometry="guidance",
        calibration_seed="seed",
        calibration_policy="policy",
    )

    bridged = (
        bridge_bundle_to_frozen_production_doe_identity(
            bundle=bundle,
            case_hash=case_hash,
            resolution_hash=resolution_hash,
            frozen_case_run_id=frozen,
        )
    )

    assert (
        bridged.preparation.identity.run_id
        == frozen
    )
    assert (
        bridged.preparation.identity.job_name
        == frozen
    )
    assert (
        bridged.preparation.identity.case_hash
        == case_hash
    )
    assert (
        bridged.preparation.identity.resolution_hash
        == resolution_hash
    )

    assert (
        bridged.transfer.simulation_id
        == frozen
    )
    assert (
        bridged.transfer.job_name
        == frozen
    )
    assert (
        bridged.contact.simulation_id
        == frozen
    )
    assert (
        bridged.contact.solver_job_name
        == frozen
    )
    assert (
        bridged.boundary.simulation_id
        == frozen
    )

    assert (
        bridged.preparation.physics
        == bundle.preparation.physics
    )
    assert (
        bridged.transfer.payload
        == bundle.transfer.payload
    )
    assert (
        bridged.contact.payload
        == bundle.contact.payload
    )
    assert (
        bridged.boundary.payload
        == bundle.boundary.payload
    )
    assert (
        bridged.guidance_geometry
        == bundle.guidance_geometry
    )
    assert (
        bridged.calibration_seed
        == bundle.calibration_seed
    )
    assert (
        bridged.calibration_policy
        == bundle.calibration_policy
    )


def test_frozen_lineage_bridge_rejects_wrong_frozen_id():
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class Identity:
        case_hash: str
        resolution_hash: str
        run_id: str
        job_name: str

    @dataclass(frozen=True)
    class Preparation:
        identity: Identity

    @dataclass(frozen=True)
    class Transfer:
        simulation_id: str
        job_name: str

    @dataclass(frozen=True)
    class Contact:
        simulation_id: str
        solver_job_name: str

    @dataclass(frozen=True)
    class Boundary:
        simulation_id: str

    @dataclass(frozen=True)
    class Bundle:
        preparation: Preparation
        transfer: Transfer
        contact: Contact
        boundary: Boundary

    case_hash = "a" * 64
    resolution_hash = "b" * 64
    current = "trm_fem_" + ("b" * 12)

    bundle = Bundle(
        preparation=Preparation(
            identity=Identity(
                case_hash=case_hash,
                resolution_hash=resolution_hash,
                run_id=current,
                job_name=current,
            )
        ),
        transfer=Transfer(
            simulation_id=current,
            job_name=current,
        ),
        contact=Contact(
            simulation_id=current,
            solver_job_name=current,
        ),
        boundary=Boundary(
            simulation_id=current,
        ),
    )

    with pytest.raises(
        ValueError,
        match="governed case hash",
    ):
        bridge_bundle_to_frozen_production_doe_identity(
            bundle=bundle,
            case_hash=case_hash,
            resolution_hash=resolution_hash,
            frozen_case_run_id="trm_fem_wrong",
        )

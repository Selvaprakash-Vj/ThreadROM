from __future__ import annotations

from threadrom.factory.production_doe_equilibrium_applicability import (
    ProductionDoeEquilibriumApplicability,
    classify_production_doe_equilibrium_applicability,
)


def test_support_only_legacy_doe_contract_is_diagnostic_only() -> None:
    result = classify_production_doe_equilibrium_applicability(
        constrained_reaction_sets=(
            "HEAD_MEMBER_SUPPORT_BAND",
            "BOLT_HEAD_GUIDANCE_REFERENCE",
            "BOLT_HEAD_ROTATION_X_REFERENCE",
            "BOLT_HEAD_ROTATION_Y_REFERENCE",
            "NUT_MEMBER_GUIDANCE_REFERENCE",
            "NUT_ROTATION_GUIDANCE_REFERENCE",
            "NUT_ROTATION_X_REFERENCE",
            "NUT_ROTATION_Y_REFERENCE",
            "NUT_TRANSLATION_GUIDANCE_REFERENCE",
        ),
        reaction_observable_sets=(
            "HEAD_MEMBER_SUPPORT_BAND",
        ),
    )

    assert (
        result.applicability
        is ProductionDoeEquilibriumApplicability
        .DIAGNOSTIC_ONLY_INCOMPLETE_REACTION_SYSTEM
    )

    assert result.support_only_result_is_diagnostic
    assert not result.full_system_pass_claimed
    assert not result.tolerance_changed
    assert not result.additional_fem_authorized_by_classifier

    assert result.missing_reaction_sets == (
        "BOLT_HEAD_GUIDANCE_REFERENCE",
        "BOLT_HEAD_ROTATION_X_REFERENCE",
        "BOLT_HEAD_ROTATION_Y_REFERENCE",
        "NUT_MEMBER_GUIDANCE_REFERENCE",
        "NUT_ROTATION_GUIDANCE_REFERENCE",
        "NUT_ROTATION_X_REFERENCE",
        "NUT_ROTATION_Y_REFERENCE",
        "NUT_TRANSLATION_GUIDANCE_REFERENCE",
    )


def test_complete_reaction_contract_is_not_support_only_diagnostic() -> None:
    constrained = (
        "HEAD_MEMBER_SUPPORT_BAND",
        "BOLT_HEAD_GUIDANCE_REFERENCE",
        "NUT_MEMBER_GUIDANCE_REFERENCE",
    )

    result = classify_production_doe_equilibrium_applicability(
        constrained_reaction_sets=constrained,
        reaction_observable_sets=constrained,
    )

    assert (
        result.applicability
        is ProductionDoeEquilibriumApplicability
        .FULL_SYSTEM_OBSERVABLE
    )

    assert not result.support_only_result_is_diagnostic

    # Applicability alone must never manufacture an equilibrium PASS.
    assert not result.full_system_pass_claimed

    # The existing numerical tolerance is never changed here.
    assert not result.tolerance_changed

    assert result.missing_reaction_sets == ()


def test_classifier_fails_closed_without_constrained_system() -> None:
    try:
        classify_production_doe_equilibrium_applicability(
            constrained_reaction_sets=(),
            reaction_observable_sets=(),
        )
    except ValueError as exc:
        assert (
            str(exc)
            == "At least one constrained reaction set is required."
        )
    else:
        raise AssertionError(
            "Empty constrained reaction system must fail closed."
        )


def test_case_and_whitespace_do_not_change_contract_identity() -> None:
    result = classify_production_doe_equilibrium_applicability(
        constrained_reaction_sets=(
            " head_member_support_band ",
            "Nut_Member_Guidance_Reference",
        ),
        reaction_observable_sets=(
            "HEAD_MEMBER_SUPPORT_BAND",
        ),
    )

    assert result.missing_reaction_sets == (
        "NUT_MEMBER_GUIDANCE_REFERENCE",
    )

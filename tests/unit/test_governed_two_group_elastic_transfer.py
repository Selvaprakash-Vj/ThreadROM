"""Two-group FEM material identity and real deck-card emission."""

from types import SimpleNamespace as NS

import pytest

from threadrom.factory.fem_case_preparation import (
    derive_two_group_elastic_properties,
)
from threadrom.solver.complete_joint_calculix_transfer import (
    render_governed_elastic_material_cards,
)


def material(modulus, ratio):
    return NS(
        youngs_modulus_mpa=modulus,
        poissons_ratio=ratio,
    )


def resolved(
    *,
    bolt_id="fastener_steel",
    nut_id="fastener_steel",
    upper_id="steel_member",
    lower_id="steel_member",
    bolt_e=210000.0,
    nut_e=210000.0,
    upper_e=70000.0,
    lower_e=70000.0,
    bolt_nu=0.30,
    nut_nu=0.30,
    upper_nu=0.33,
    lower_nu=0.33,
):
    return NS(
        source_case=NS(
            fastener=NS(
                bolt_material_id=bolt_id,
                nut_material_id=nut_id,
            ),
            members=NS(
                layers=(
                    NS(material_id=upper_id),
                    NS(material_id=lower_id),
                )
            ),
        ),
        bolt_material=material(bolt_e, bolt_nu),
        nut_material=material(nut_e, nut_nu),
        member_materials=(
            material(upper_e, upper_nu),
            material(lower_e, lower_nu),
        ),
    )


def definition(member_e=None, member_nu=None):
    return NS(
        bolt_material_name="BOLT_STEEL",
        nut_material_name="NUT_STEEL",
        member_material_name="MEMBER_STEEL",
        youngs_modulus_mpa=210000.0,
        poissons_ratio=0.30,
        member_youngs_modulus_mpa=member_e,
        member_poissons_ratio=member_nu,
    )


def test_two_groups_may_have_different_elastic_properties():
    assert derive_two_group_elastic_properties(resolved()) == (
        210000.0, 0.30, 70000.0, 0.33,
    )


@pytest.mark.parametrize(
    "change",
    (
        {"nut_id": "different_fastener"},
        {"lower_id": "different_member"},
        {"nut_e": 205000.0},
        {"lower_e": 72000.0},
        {"nut_nu": 0.31},
        {"lower_nu": 0.32},
    ),
)
def test_within_group_mismatch_fails_closed(change):
    with pytest.raises(ValueError):
        derive_two_group_elastic_properties(
            resolved(**change)
        )


def test_real_renderer_assigns_distinct_group_cards():
    cards = render_governed_elastic_material_cards(
        definition(70000.0, 0.33)
    )
    assert cards["BOLT_STEEL"][2] == (
        "2.100000000000e+05, 3.000000000000e-01"
    )
    assert cards["NUT_STEEL"][2] == cards["BOLT_STEEL"][2]
    assert cards["MEMBER_STEEL"][2] == (
        "7.000000000000e+04, 3.300000000000e-01"
    )


def test_historical_equal_property_cards_are_unchanged():
    cards = render_governed_elastic_material_cards(
        definition()
    )
    assert all(
        card[2] == (
            "2.100000000000e+05, 3.000000000000e-01"
        )
        for card in cards.values()
    )


@pytest.mark.parametrize(
    "member_e,member_nu",
    (
        (70000.0, None),
        (None, 0.33),
        (-1.0, 0.33),
        (70000.0, 0.5),
    ),
)
def test_incomplete_or_invalid_member_group_rejected(
    member_e, member_nu,
):
    with pytest.raises(ValueError):
        render_governed_elastic_material_cards(
            definition(member_e, member_nu)
        )


def test_different_groups_cannot_share_one_material_name():
    item = definition(70000.0, 0.33)
    item.member_material_name = "BOLT_STEEL"
    with pytest.raises(ValueError):
        render_governed_elastic_material_cards(item)

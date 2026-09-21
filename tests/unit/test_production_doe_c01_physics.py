"""Safety tests for the complete nine-set C01 equilibrium witness."""
from pathlib import Path

import pytest

from threadrom.factory.production_doe_c01_physics import (
    complete_reaction_equilibrium,
)

from threadrom.factory.production_doe_c01_physics import (
    C01_PHYSICAL_FORCE_SETS,
    C01_MEANROT_REFERENCE_SETS,
)

SETS = C01_PHYSICAL_FORCE_SETS + C01_MEANROT_REFERENCE_SETS


def evidence(tmp_path: Path, *, physical_force: str = '0',
             meanrot_force: str = '0') -> dict:
    deck_path = tmp_path / 'test.inp'
    deck_path.write_text(
        '*NSET,NSET=HEAD_MEMBER_SUPPORT_BAND\n1,2,3\n'
        + ''.join(
            f'*NODE,NSET={name}\n{i + 10},0,0,0\n'
            for i, name in enumerate(SETS[1:])
        )
        + '*MPC\n'
        + ''.join(
            f'MEANROT, 1, 2, 3, {SETS.index(name) + 9}\n'
            for name in C01_MEANROT_REFERENCE_SETS
        )
        + '*BOUNDARY\n'
        + ''.join(f'{name}, 1, 1, 0.0\n'
                  for name in C01_MEANROT_REFERENCE_SETS),
        encoding='ascii',
    )
    sta = '\n'.join(
        f'1 {i} 1 3 {i * .05:.9E} {i * .05:.9E} 0.050000E+00'
        for i in range(1, 21)
    )
    dat = '\n'.join(
        f'total force (fx,fy,fz) for set {name} and time {i * .05:.9E}\n'
        f'{physical_force if name == SETS[0] else meanrot_force if name in C01_MEANROT_REFERENCE_SETS else 0} 0 0'
        for i in range(1, 21) for name in SETS
    )
    return dict(
        dat_text=dat, sta_text=sta, deck_path=deck_path,
        constrained_sets=SETS, observable_sets=SETS,
    )


def test_complete_nine_set_witness_uses_existing_tolerance(tmp_path):
    result = complete_reaction_equilibrium(**evidence(tmp_path))
    assert result['overall_status'] == 'pass'
    assert result['accepted_increment_count'] == 20
    assert result['maximum_absolute_resultant_n'] == 0.0
    assert result['tolerances']['force_absolute_n'] == 1.0e-3


def test_excess_resultant_is_fail_not_physics_pass(tmp_path):
    result = complete_reaction_equilibrium(**evidence(tmp_path, physical_force='0.002'))
    assert result['overall_status'] == 'fail'
    assert result['maximum_absolute_resultant_n'] == 0.002


def test_missing_named_reactions_cannot_be_summed(tmp_path):
    data = evidence(tmp_path)
    data['dat_text'] = data['dat_text'].replace(
        f'total force (fx,fy,fz) for set {SETS[1]} and time',
        'total force (fx,fy,fz) for set UNRELATED and time',
    )
    with pytest.raises(RuntimeError, match='Incomplete reaction witness'):
        complete_reaction_equilibrium(**data)


def test_overlapping_reaction_sets_cannot_be_double_counted(tmp_path):
    data = evidence(tmp_path)
    with data['deck_path'].open('a', encoding='ascii') as stream:
        stream.write(f'*NODE,NSET={SETS[1]}\n1,0,0,0\n')
    with pytest.raises(RuntimeError, match='Overlapping constrained reaction NSET'):
        complete_reaction_equilibrium(**data)


def test_missing_observable_carrier_is_rejected(tmp_path):
    data = evidence(tmp_path)
    data['observable_sets'] = SETS[:-1]
    with pytest.raises(RuntimeError, match='reaction contract drift'):
        complete_reaction_equilibrium(**data)


def test_meanrot_generalized_reference_is_not_cartesian_force(tmp_path):
    result = complete_reaction_equilibrium(
        **evidence(tmp_path, meanrot_force='662.40921')
    )
    assert result['overall_status'] == 'pass'
    assert result['maximum_absolute_resultant_n'] == 0.0
    assert result['maximum_absolute_generalized_reference_component_n'] == 662.40921
    assert result['rotational_moment_equilibrium_status'] == 'not_assessed'
    assert result['force_balance_is_not_moment_balance'] is True
    assert len(result['constrained_reaction_sets']) == 9


def test_missing_meanrot_provenance_fails_closed(tmp_path):
    data = evidence(tmp_path)
    deck = data['deck_path']
    deck.write_text(deck.read_text().replace('MEANROT,', 'UNVERIFIED,', 1))
    with pytest.raises(RuntimeError, match='MEANROT-reference provenance'):
        complete_reaction_equilibrium(**data)


def test_missing_meanrot_dof1_constraint_fails_closed(tmp_path):
    data = evidence(tmp_path)
    deck = data['deck_path']
    name = C01_MEANROT_REFERENCE_SETS[0]
    deck.write_text(deck.read_text().replace(f'{name}, 1, 1, 0.0',
                                                  f'{name}, 2, 2, 0.0'))
    with pytest.raises(RuntimeError, match='DOF-1 constraint drift'):
        complete_reaction_equilibrium(**data)

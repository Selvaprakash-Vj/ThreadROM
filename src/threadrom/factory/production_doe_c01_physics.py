"""Read-only governed physics assessment of an existing C01 completed trial.

This adapter shares the standard ThreadROM result extractor, calibration
controller, full-physics evaluator and nonlinear equilibrium validator.
It does not create a solver job, certify evidence or retire restart artifacts.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from threadrom.case.resolver import resolve_case
from threadrom.factory.adaptive_fem_physics_assessment import (
    assess_verified_completed_fem,
)
from threadrom.factory.fem_acceptance_policy import (
    derive_complete_joint_physics_acceptance_policy,
)
from threadrom.factory.fem_case_definition_bundle import (
    build_generic_fem_definition_bundle,
)
from threadrom.factory.fem_preload_calibration_measurement import (
    extract_clamp_force_measurement_from_dat,
)
from threadrom.factory.fem_result_extraction import (
    load_fem_result_extraction_policy,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationDisposition,
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
    evaluate_preload_calibration_trial,
)
from threadrom.factory.production_doe import (
    build_phase3_production_doe,
    load_phase3_production_doe_policy,
)
from threadrom.factory.production_doe_adaptive_history_planner import (
    plan_from_verified_history,
)
from threadrom.factory.production_doe_case_registry import (
    resolve_governed_c01_case,
)
from threadrom.factory.production_doe_gate0_evidence import (
    GATE0_CASE_IDS,
    inspect_gate0_trial1,
)
from threadrom.factory.production_doe_reaction_observable_revision import (
    bridge_bundle_to_frozen_production_doe_identity,
)
from threadrom.postprocessing.calculix_external_equilibrium import (
    validate_external_equilibrium,
)
from threadrom.postprocessing.calculix_nonlinear_progress import (
    parse_status_increments,
)
from threadrom.postprocessing.calculix_total_force_dat import (
    parse_total_force_records,
)
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
from threadrom.solver.complete_joint_preload import (
    load_complete_joint_preload_definition,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _frozen_file(root: Path, relative: str, digest: str) -> Path:
    if not isinstance(relative, str) or not isinstance(digest, str):
        raise RuntimeError('Invalid frozen evidence path or hash.')
    candidate = (root / relative).resolve(strict=True)
    if not candidate.is_relative_to(root) or sha256(candidate) != digest:
        raise RuntimeError(f'Frozen FEM evidence drift: {relative}')
    return candidate


def _check_reaction_set_independence(deck_path: Path, names: tuple[str, ...]) -> None:
    """Avoid summing overlapping node sets or unresolved symbolic NSETs."""
    target = {name.upper(): set() for name in names}
    active = None
    generate = False
    definition = None
    with deck_path.open('r', encoding='utf-8', errors='replace') as stream:
        for raw in stream:
            line = raw.strip()
            if line.startswith('**') or not line:
                continue
            if line.startswith('*'):
                active = None
                generate = False
                definition = None
                fields = [piece.strip() for piece in line[1:].split(',')]
                keyword = fields[0].upper()
                if keyword not in ('NSET', 'NODE'):
                    continue
                attrs = dict(
                    (a.strip().upper(), b.strip().upper())
                    for field in fields[1:]
                    if '=' in field
                    for a, b in [field.split('=', 1)]
                )
                active = attrs.get('NSET')
                if active not in target:
                    active = None
                else:
                    definition = keyword
                    generate = (keyword == 'NSET' and
                                any(f.upper() == 'GENERATE' for f in fields[1:]))
                continue
            if active is None:
                continue
            if definition == 'NODE':
                token = line.split(',', 1)[0].strip()
                if not token.isdecimal() or int(token) < 1:
                    raise RuntimeError(f'Malformed reaction reference NODE: {active}')
                target[active].add(int(token))
                continue
            tokens = [token.strip() for token in line.split(',') if token.strip()]
            if not all(token.isdecimal() for token in tokens):
                raise RuntimeError(f'Symbolic or malformed reaction NSET: {active}')
            values = tuple(int(token) for token in tokens)
            if generate:
                if len(values) not in (2, 3):
                    raise RuntimeError(f'Invalid NSET GENERATE: {active}')
                first, last = values[:2]
                step = values[2] if len(values) == 3 else 1
                if first < 1 or step < 1 or last < first:
                    raise RuntimeError(f'Invalid reaction NSET range: {active}')
                target[active].update(range(first, last + 1, step))
            else:
                target[active].update(values)
    if any(not nodes for nodes in target.values()):
        raise RuntimeError('Reaction NSET absent or empty in the certified input deck.')
    seen: set[int] = set()
    for name, nodes in target.items():
        if seen.intersection(nodes):
            raise RuntimeError(f'Overlapping constrained reaction NSET: {name}')
        seen.update(nodes)


# C01's four translation-support reaction sets carry net physical forces.
# The other five references are the scalar generalized DOFs of CalculiX
# MEANROT MPCs; their RF1 values cannot be added as Cartesian FX forces.
C01_PHYSICAL_FORCE_SETS = (
    'HEAD_MEMBER_SUPPORT_BAND',
    'BOLT_HEAD_GUIDANCE_REFERENCE',
    'NUT_MEMBER_GUIDANCE_REFERENCE',
    'NUT_TRANSLATION_GUIDANCE_REFERENCE',
)
C01_MEANROT_REFERENCE_SETS = (
    'BOLT_HEAD_ROTATION_X_REFERENCE',
    'BOLT_HEAD_ROTATION_Y_REFERENCE',
    'NUT_ROTATION_GUIDANCE_REFERENCE',
    'NUT_ROTATION_X_REFERENCE',
    'NUT_ROTATION_Y_REFERENCE',
)


def _verify_meanrot_reaction_roles(deck_path: Path) -> None:
    """Prove, from the solved deck, which reference RFs are generalized.

    Do not exclude a named reaction based merely on its spelling. Every
    excluded reference must have its own MEANROT MPC and an imposed scalar
    DOF-1 boundary in the frozen input deck. The four included sets must
    not be MEANROT-reference carriers.
    """
    reference_names = (
        set(C01_MEANROT_REFERENCE_SETS)
        | set(C01_PHYSICAL_FORCE_SETS[1:])
    )
    node_ids: dict[str, set[int]] = {name: set() for name in reference_names}
    boundary_dofs: dict[str, set[tuple[int, int]]] = {
        name: set() for name in C01_MEANROT_REFERENCE_SETS
    }
    meanrot_refs: list[int] = []
    active_keyword = ''
    active_node_set = ''
    current_mpc: list[str] = []

    def flush_mpc() -> None:
        if not current_mpc:
            return
        parts = [piece.strip() for piece in ','.join(current_mpc).split(',')
                 if piece.strip()]
        if parts[0].upper() != 'MEANROT':
            return
        if len(parts) < 3 or not all(part.isdecimal() for part in parts[1:]):
            raise RuntimeError('Malformed MEANROT reference contract in input deck.')
        meanrot_refs.append(int(parts[-1]))
        current_mpc.clear()

    with deck_path.open('r', encoding='utf-8', errors='replace') as stream:
        for raw in stream:
            line = raw.strip()
            if not line or line.startswith('**'):
                continue
            if line.startswith('*'):
                if active_keyword == 'MPC':
                    flush_mpc()
                head = [part.strip() for part in line[1:].split(',')]
                active_keyword = head[0].upper()
                active_node_set = ''
                if active_keyword == 'NODE':
                    for part in head[1:]:
                        if part.upper().startswith('NSET='):
                            active_node_set = part.split('=', 1)[1].strip().upper()
                continue
            if active_keyword == 'NODE' and active_node_set in node_ids:
                token = line.split(',', 1)[0].strip()
                if not token.isdecimal():
                    raise RuntimeError('Malformed named reference node in input deck.')
                node_ids[active_node_set].add(int(token))
            elif active_keyword == 'BOUNDARY':
                items = [item.strip() for item in line.split(',')]
                name = items[0].upper()
                if name in boundary_dofs:
                    if len(items) < 3 or not all(v.isdecimal() for v in items[1:3]):
                        raise RuntimeError('Malformed rotation-reference boundary DOF.')
                    boundary_dofs[name].add((int(items[1]), int(items[2])))
            elif active_keyword == 'MPC':
                if line.split(',', 1)[0].strip().upper() == 'MEANROT':
                    flush_mpc()
                    current_mpc.append(line)
                elif current_mpc:
                    current_mpc.append(line)
        if active_keyword == 'MPC':
            flush_mpc()

    if any(len(nodes) != 1 for nodes in node_ids.values()):
        raise RuntimeError('Missing or ambiguous reference-node identity in deck.')
    expected_generalized = {
        next(iter(node_ids[name])) for name in C01_MEANROT_REFERENCE_SETS
    }
    actual_generalized = set(meanrot_refs)
    if (len(meanrot_refs) != 5 or len(actual_generalized) != 5
            or actual_generalized != expected_generalized):
        raise RuntimeError(
            'MEANROT-reference provenance unverified; force witness blocked.'
        )
    if any(dofs != {(1, 1)} for dofs in boundary_dofs.values()):
        raise RuntimeError('MEANROT generalized reference DOF-1 constraint drift.')
    if actual_generalized.intersection(
        next(iter(node_ids[name])) for name in C01_PHYSICAL_FORCE_SETS[1:]
    ):
        raise RuntimeError('Physical force carrier is a MEANROT reference.')


def complete_reaction_equilibrium(
    *, dat_text: str, sta_text: str, deck_path: Path,
    constrained_sets: tuple[str, ...], observable_sets: tuple[str, ...],
) -> dict[str, object]:
    """Validate physical-force balance, retaining all nine reaction records.

    Four translation supports enter Cartesian force equilibrium. Five MEANROT
    reference RF1 outputs represent generalized rotation constraint reactions;
    those five are preserved as diagnostics, not summed as Cartesian forces.
    This validates force equilibrium only; it does not certify moment balance.
    """
    expected = tuple(name.strip().upper() for name in constrained_sets)
    governed = set(C01_PHYSICAL_FORCE_SETS) | set(C01_MEANROT_REFERENCE_SETS)
    if (len(expected) != 9 or set(expected) != governed
            or set(expected) != {name.strip().upper() for name in observable_sets}):
        raise RuntimeError('Certified nine-set constrained reaction contract drift.')
    _check_reaction_set_independence(deck_path, expected)
    _verify_meanrot_reaction_roles(deck_path)
    accepted = parse_status_increments(sta_text)
    if len(accepted) != 20 or accepted[-1].total_time != 1.0:
        raise RuntimeError('Incomplete governed 20-increment preload history.')
    records = parse_total_force_records(dat_text, set_names=expected)
    if len(records) != len(accepted) * len(expected):
        raise RuntimeError(
            f'Incomplete reaction witness: {len(records)} / '
            f'{len(accepted) * len(expected)} required set-increment records.'
        )
    aggregate = []
    generalized_maximum_n = 0.0
    for step in accepted:
        by_name = {}
        for record in records:
            if (math.isclose(record.time, step.total_time, rel_tol=0.0, abs_tol=1.e-9)
                and (record.increment is None or record.increment == step.increment)
                and (record.step is None or record.step == step.step)):
                name = record.set_name.upper()
                if name in by_name:
                    raise RuntimeError(f'Duplicate reaction record {name} at {step.total_time}.')
                by_name[name] = record
        if set(by_name) != set(expected):
            raise RuntimeError(f'Missing constrained reactions at t={step.total_time}.')
        # An MPC's generalized rotation-reference RF1 is NOT a Cartesian
        # FX resultant. Its physical interpretation requires MPC geometry
        # and moment accounting; retaining the raw values avoids losing it.
        generalized_maximum_n = max(
            generalized_maximum_n,
            *(abs(value) for name in C01_MEANROT_REFERENCE_SETS
              for value in by_name[name].force_components_n),
        )
        components = [
            math.fsum(by_name[name].force_components_n[axis]
                      for name in C01_PHYSICAL_FORCE_SETS)
            for axis in range(3)
        ]
        aggregate.append({
            'step': step.step, 'increment': step.increment,
            'set_name': 'C01_PHYSICAL_TRANSLATIONAL_FORCE_REACTIONS',
            'time': step.total_time, 'force_components_n': components,
        })
    result = validate_external_equilibrium(
        {'accepted_increments': [asdict(step) for step in accepted]},
        {'records': aggregate},
        support_set_name='C01_PHYSICAL_TRANSLATIONAL_FORCE_REACTIONS',
    )
    result['witness_scope'] = 'four_physical_force_sets_plus_five_meanrot_diagnostics'
    result['physical_force_reaction_sets'] = list(C01_PHYSICAL_FORCE_SETS)
    result['generalized_rotation_reference_sets'] = list(C01_MEANROT_REFERENCE_SETS)
    result['maximum_absolute_generalized_reference_component_n'] = generalized_maximum_n
    result['rotational_moment_equilibrium_status'] = 'not_assessed'
    result['force_balance_is_not_moment_balance'] = True
    result['constrained_reaction_sets'] = list(expected)
    result['maximum_absolute_resultant_n'] = max(
        abs(value) for row in aggregate for value in row['force_components_n']
    )
    result['source'] = 'existing solved DAT and certified INP/STA; no new FEM'
    return result


def assess_c01_saved_trial(*, repo_root: Path, case_id: str) -> dict[str, object]:
    """Read-only full-physics gate report; no certificate is issued."""
    root = repo_root.resolve(strict=True)
    if case_id not in GATE0_CASE_IDS or case_id == 'D-INT-012':
        raise RuntimeError('Only completed C01 Gate-0 Trial-1 013–016 are in this batch.')
    governed = resolve_governed_c01_case(repo_root=root, requested_case_id=case_id)
    gate0 = inspect_gate0_trial1(repo_root=root, requested_case_id=case_id)
    if gate0.completion_status != 'COMPLETED_INPUT_EVIDENCE_VERIFIED':
        raise RuntimeError('The original completed Trial-1 input evidence is not verified.')
    plan = plan_from_verified_history(repo_root=root, case_id=case_id)
    if (plan.state != 'CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS'
            or plan.completed_trial_count != 1 or plan.last_completed_run_id != gate0.run_id):
        raise RuntimeError('Trial-1 governed preload calibration is not accepted.')
    case_run_id, run_id = governed.case_run_id, gate0.run_id
    case_root = root / 'simulations/staging/phase3_cp8_production_doe/TRM-PDOE-C01'
    run_dir = case_root / 'solver_preparation' / case_run_id / run_id
    prep = json.loads((run_dir / 'production_doe_reaction_observable_revision_record.json')
                      .read_text(encoding='utf-8-sig'))
    cert = json.loads((case_root / 'production_doe_gate0_execution_certification.json')
                      .read_text(encoding='utf-8-sig'))
    matches = [row for row in cert['certified_gate0_cases'] if row['case_id'] == case_id]
    if len(matches) != 1:
        raise RuntimeError('Missing/ambiguous frozen Gate-0 case.')
    frozen = matches[0]
    mesh = prep['certified_prepared_artifacts']
    if mesh['mesh_sha256'] != frozen['mesh_sha256']:
        raise RuntimeError('Gate-0 certified mesh differs from preparation.')
    mesh_path = _frozen_file(root, mesh['mesh_relative_path'], mesh['mesh_sha256'])
    cfg = root / 'config'
    doe_policy = load_phase3_production_doe_policy(cfg / 'phase3_production_doe.toml')
    matches = [row for row in build_phase3_production_doe(doe_policy).design_cases
               if row.case_id == case_id]
    if len(matches) != 1 or matches[0].case_hash != governed.case_hash:
        raise RuntimeError('Frozen DOE case identity drift.')
    resolved = resolve_case(matches[0].case)
    if resolved.case_hash != governed.case_hash:
        raise RuntimeError('Frozen resolved-case drift.')
    contact = load_complete_joint_contact_definition(cfg / 'complete_joint_contact.toml')
    preload = load_complete_joint_preload_definition(cfg / 'complete_joint_preload.toml')
    trial_raw = prep['trial']
    trial = PreloadCalibrationTrial(
        trial_index=1, run_id=run_id,
        delta_temperature_c=float(trial_raw['delta_temperature_c']),
        source=PreloadCalibrationTrialSource(trial_raw['source']),
    )
    dat_path = run_dir / f'{run_id}.dat'
    measurement = extract_clamp_force_measurement_from_dat(
        dat_path=dat_path, contact_pairs=contact.contact_pairs,
    ).measurement
    calibration = evaluate_preload_calibration_trial(
        case_run_id=case_run_id,
        target_force_n=resolved.source_case.loading.target_preload_n,
        target_relative_tolerance=preload.target_relative_tolerance,
        spread_relative_tolerance=preload.interface_spread_relative_tolerance,
        current_trial=trial, measurement=measurement,
    )
    if (calibration.decision.disposition is not PreloadCalibrationDisposition.ACCEPT
            or calibration.next_trial is not None):
        raise RuntimeError('Independent Trial-1 calibration replay did not ACCEPT.')
    # The original nine-set contract is pinned by inspect_gate0_trial1().
    reaction = prep['reaction_observability']
    if reaction['fully_observable'] is not True or reaction['missing_reaction_sets']:
        raise RuntimeError('C01 frozen constrained-reaction observability drift.')
    equilibrium = None
    equilibrium_error = None
    try:
        equilibrium = complete_reaction_equilibrium(
            dat_text=dat_path.read_text(encoding='utf-8', errors='replace'),
            sta_text=(run_dir / f'{run_id}.sta').read_text(
                encoding='utf-8', errors='replace'),
            deck_path=run_dir / f'{run_id}.inp',
            constrained_sets=tuple(reaction['constrained_reaction_sets']),
            observable_sets=tuple(reaction['observable_reaction_sets']),
        )
    except (ValueError, RuntimeError, KeyError) as exc:
        equilibrium_error = str(exc)
    token = governed.case_hash[:16]
    bundle = build_generic_fem_definition_bundle(
        resolved, mesh_id=f'mesh-{token}', geometry_id=f'geometry-{token}',
        classification_id=f'classification-{token}', source_mesh_name=mesh_path.name,
        transfer_template=load_complete_joint_calculix_transfer_definition(
            cfg / 'complete_joint_calculix_transfer.toml'),
        contact_template=contact,
        boundary_template=load_complete_joint_boundary_region_definition(
            cfg / 'complete_joint_boundary_regions.toml'),
    )
    bundle = bridge_bundle_to_frozen_production_doe_identity(
        bundle=bundle, case_hash=governed.case_hash,
        resolution_hash=resolved.resolution_hash, frozen_case_run_id=case_run_id,
    )
    mesh_data = read_grouped_complete_joint_mesh(mesh_path, bundle.transfer)
    assessment = assess_verified_completed_fem(
        repo_root=root, manifest_path=run_dir / 'fem_run_manifest.json',
        expected_run_id=run_id, expected_case_hash=governed.case_hash,
        expected_deck_sha256=gate0.deck_sha256,
        frd_path=run_dir / f'{run_id}.frd', sta_path=run_dir / f'{run_id}.sta',
        stdout_path=run_dir / f'{run_id}.stdout.log', mesh_data=mesh_data,
        extraction_policy=load_fem_result_extraction_policy(
            cfg / 'fem_result_extraction.toml'),
        contact_pairs=bundle.contact.contact_pairs,
        thermal_expansion_coefficient_per_c=(
            bundle.preparation.physics.bolt_thermal_expansion_per_c),
        equivalent_delta_temperature_c=trial.delta_temperature_c,
        physics_policy=derive_complete_joint_physics_acceptance_policy(resolved.assembly),
        preload_decision=calibration.decision,
        external_equilibrium_payload=equilibrium,
    )
    checks = [
        {'name': check.name, 'kind': check.kind.value, 'passed': check.passed,
         'measured': check.measured, 'expected': check.expected,
         'tolerance': check.tolerance}
        for check in assessment.acceptance_result.checks
    ]
    return {
        'case_id': case_id, 'run_id': run_id,
        'calibration': 'ACCEPTED_TRIAL_1',
        'equilibrium_status': (equilibrium or {}).get('overall_status', 'unavailable'),
        'equilibrium_error': equilibrium_error,
        'equilibrium_max_resultant_n': (equilibrium or {}).get('maximum_absolute_resultant_n'),
        'force_balance_scope': (equilibrium or {}).get('witness_scope'),
        'generalized_rotation_reference_max_n': (
            (equilibrium or {}).get('maximum_absolute_generalized_reference_component_n')),
        'rotational_moment_equilibrium_status': (
            (equilibrium or {}).get('rotational_moment_equilibrium_status', 'not_assessed')),
        'equilibrium_tolerance_n': (equilibrium or {}).get('tolerances', {}).get('force_absolute_n'),
        'physics_checks': checks,
        'failed_governed_checks': list(assessment.failed_governed_checks),
        'physics_gates': ('PASS_PENDING_INDEPENDENT_CERTIFICATION'
                          if not assessment.failed_governed_checks else 'REVIEW_REQUIRED'),
        'final_physics_certified': False,
        'new_fem_authorized': False,
        'rout_retirement_authorized': False,
    }

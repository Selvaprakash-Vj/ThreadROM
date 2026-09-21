"""Assess four solved C01 Trial-1 cases; read-only, no CalculiX or cleanup."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from threadrom.factory.production_doe_c01_physics import assess_c01_saved_trial

ROOT = Path(__file__).resolve().parents[1]
CASE_IDS = tuple(f'D-INT-{i:03d}' for i in (13, 14, 15, 16))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case-id', choices=CASE_IDS, action='append')
    args = parser.parse_args()
    failed = False
    for case_id in args.case_id or CASE_IDS:
        print(f'\n=== {case_id}: VERIFIED TRIAL-1 FULL-PHYSICS GATES ===', flush=True)
        try:
            result = assess_c01_saved_trial(repo_root=ROOT, case_id=case_id)
        except Exception as exc:
            failed = True
            print(f'{case_id}: ASSESSMENT_BLOCKED: {type(exc).__name__}: {exc}', flush=True)
            continue
        print('Calibration:', result['calibration'], flush=True)
        print('PHYSICAL TRANSLATIONAL FORCE EQUILIBRIUM:', result['equilibrium_status'],
              'max |FX,FY,FZ| N:', result['equilibrium_max_resultant_n'],
              'governed limit N:', result['equilibrium_tolerance_n'], flush=True)
        print('Reaction witness:', result['force_balance_scope'], flush=True)
        print('MEANROT generalized reference RF maximum N-equivalent (diagnostic, NOT FX):',
              result['generalized_rotation_reference_max_n'], flush=True)
        print('Rotational moment equilibrium:',
              result['rotational_moment_equilibrium_status'],
              '(not inferred from the force-equilibrium PASS)', flush=True)
        if result['equilibrium_error']:
            print('Equilibrium evidence limitation:', result['equilibrium_error'], flush=True)
        for check in result['physics_checks']:
            status = 'PASS' if check['passed'] else 'FAIL'
            print(f"  [{status}] {check['kind']}: {check['name']} | "
                  f"measured={check['measured']} expected={check['expected']} "
                  f"limit={check['tolerance']}", flush=True)
        print('GOVERNED PHYSICS:', result['physics_gates'], flush=True)
        print('FULL PHYSICS CERTIFIED: NO (independent certification separate)', flush=True)
        print('FURTHER FEM / .rout DELETION: NOT AUTHORIZED', flush=True)
        if result['failed_governed_checks']:
            failed = True
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

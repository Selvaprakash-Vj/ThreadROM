from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threadrom.factory.fem_factory_registry import FemFactoryJobState, FemFactoryPriority, FemFactoryRegistry
from threadrom.factory.diversified_calculix_worker_adapter import GovernedCalculixExecutionSpec
from threadrom.factory import fem_case_definition_bundle as bundle_mod
from threadrom.solver.calculix_job import CalculixJobDefinition
from threadrom.solver.complete_joint_calculix_transfer import load_complete_joint_calculix_transfer_definition
ROOT = Path('D:\\ThreadROM').resolve()
CONFIG = ROOT / 'config'
CAMPAIGN_ID = 'TRM-DDOE-001'
WAVE_ID = 'TRM-DDOE-001-W04'
WAVE_TOKEN = 'W04'
AUTHORIZED_CASE_COUNT = 4
AUTHORIZED_TRIAL_INDEX = 1
MAXIMUM_CONCURRENT_CCX = 4

def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)

def sha256(path: Path) -> str:
    require(path.is_file(), f'Required file missing: {path}')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def canonical_json_bytes(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + '\n').encode('utf-8')

def write_immutable_json(path: Path, payload: dict) -> str:
    encoded = canonical_json_bytes(payload)
    digest = hashlib.sha256(encoded).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        require(path.read_bytes() == encoded, f'Immutable JSON conflict: {path}')
        return digest
    path.write_bytes(encoded)
    return digest

def repository_path(relative_path: str) -> Path:
    candidate = (ROOT / relative_path).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError(f'Repository path escape: {relative_path}') from exc
    return candidate

def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected-wave-sha', required=True)
    parser.add_argument('--expected-trial-preparation-auth-sha', required=True)
    parser.add_argument('--expected-geometry-auth-sha', required=True)
    parser.add_argument('--expected-preparation-sha', required=True)
    parser.add_argument('--expected-registry-sha', required=True)
    parser.add_argument('--approved-by', required=True)
    return parser.parse_args()
args = parse_args()
wave_root = ROOT / 'docs' / 'phase3_diversified_doe' / 'waves' / WAVE_ID
wave_path = wave_root / 'wave_plan.json'
trial_prep_auth_path = wave_root / 'trial1_owner_authorization.json'
geometry_auth_path = wave_root / 'geometry_mesh_owner_authorization.json'
trial1_execution_auth_path = wave_root / 'trial1_execution_owner_authorization.json'
trial1_preflight_path = wave_root / 'trial1_execution_preflight.json'
adaptive_auth_path = wave_root / 'adaptive_campaign_owner_authorization.json'
adaptive_preflight_path = wave_root / 'governed_execution_preflight.json'
campaign_root = ROOT / 'simulations' / 'staging' / 'phase3_diversified_doe' / CAMPAIGN_ID / WAVE_TOKEN
preparation_path = campaign_root / 'w04_trial1_preparation.json'
registry_path = campaign_root / 'factory' / 'w04_trial1_factory.sqlite3'
adaptive_lock_path = campaign_root / 'factory' / 'w04_adaptive_parallel_admission.lock'
print()
print('=== W04 CAL_01 EXECUTION-BOUNDARY PINS ===')
pins = (('Wave plan', wave_path, args.expected_wave_sha), ('Trial-1 preparation authorization', trial_prep_auth_path, args.expected_trial_preparation_auth_sha), ('Geometry/mesh authorization', geometry_auth_path, args.expected_geometry_auth_sha), ('Trial-1 preparation', preparation_path, args.expected_preparation_sha), ('Factory registry', registry_path, args.expected_registry_sha))
for label, path, expected in pins:
    actual = sha256(path)
    require(actual == expected, f'{label} SHA drift.\nexpected={expected}\nactual={actual}')
    print('PASS:', label, actual)
require(not adaptive_auth_path.exists(), 'Adaptive campaign authorization still exists. The failed Step 2E rollback was not clean.')
require(not adaptive_preflight_path.exists(), 'Adaptive execution preflight unexpectedly exists.')
require(not adaptive_lock_path.exists(), 'Adaptive parallel-admission lock unexpectedly exists.')
print()
print('PASS: failed adaptive authorization is fully rolled back.')
wave = load_json(wave_path)
preparation = load_json(preparation_path)
require(wave['wave_id'] == WAVE_ID, 'Wave identity drift.')
require(preparation['wave_id'] == WAVE_ID, 'Preparation wave identity drift.')
require(preparation['prepared_trial_count'] == AUTHORIZED_CASE_COUNT, 'Expected exactly four prepared CAL_01 trials.')
require(preparation['factory_ready'] is True, 'Preparation is not factory-ready.')
require(preparation['solver_launched'] is False, 'Preparation claims solver launch.')
require(preparation['adaptive_continuation_authorized'] is False, 'Preparation grants adaptive continuation.')
require(preparation['holdouts_accessed'] is False, 'Preparation claims holdout access.')
for key in ('fem_execution_authorized', 'adaptive_continuation_authorized', 'full_physics_certification_authorized', 'dataset_admission_authorized', 'holdout_access_authorized', 'artifact_retirement_authorized'):
    require(wave[key] is False, f'Frozen wave-plan authority drift: {key}')
registry = FemFactoryRegistry(registry_path)
jobs = registry.list_jobs()
require(len(jobs) == AUTHORIZED_CASE_COUNT, f'Expected exactly four registry jobs; found {len(jobs)}.')
prepared_rows = {row['case_hash']: row for row in preparation['prepared_trials']}
require(len(prepared_rows) == AUTHORIZED_CASE_COUNT, 'Duplicate prepared case hashes.')
for job in jobs:
    require(job.case_hash in prepared_rows, 'Registry contains case outside frozen W04 preparation.')
    row = prepared_rows[job.case_hash]
    require(job.case_id == row['case_id'], f'{job.case_id}: case identity drift.')
    require(job.trial_index == AUTHORIZED_TRIAL_INDEX, f'{job.case_id}: only CAL_01 is authorized.')
    require(job.run_id == row['trial_run_id'], f'{job.case_id}: Trial-1 run identity drift.')
    require(job.priority is FemFactoryPriority.HIGH_INFORMATION_DOE, f'{job.case_id}: priority drift.')
    require(job.state is FemFactoryJobState.PREPARED, f'{job.case_id}: expected PREPARED, found {job.state.value}.')
    require(job.preparation_record == row['preparation_record'], f'{job.case_id}: preparation-record binding drift.')
    require(job.manifest_path is None, f'{job.case_id}: manifest already registered.')
    require(job.acceptance_record is None, f'{job.case_id}: acceptance evidence already exists.')
    require(job.failure_category is None and job.failure_message is None, f'{job.case_id}: failure metadata exists.')
    require(job.lease_owner is None, f'{job.case_id}: job already leased.')
    require(job.lease_expires_at_utc is None, f'{job.case_id}: lease expiry exists.')
    require(job.lease_generation == 0, f'{job.case_id}: lease generation is non-zero.')
print()
print('PASS: 4/4 registry jobs are pristine PREPARED CAL_01.')
transfer = load_complete_joint_calculix_transfer_definition(CONFIG / 'complete_joint_calculix_transfer.toml')
backend = bundle_mod.PHASE2_CERTIFIED_FEM_PROFILE.backend
require(bool(transfer.executable_relative_path), 'Certified CalculiX executable path is blank.')
require(bool(backend.policy_id) and bool(backend.solver_name) and bool(backend.solver_version), 'Certified backend identity is incomplete.')
print()
print('=== CERTIFIED SOLVER BACKEND ===')
print('Executable     :', transfer.executable_relative_path)
print('Backend policy :', backend.policy_id)
print('Solver         :', backend.solver_name)
print('Version        :', backend.solver_version)
authorized_trials = []
specs = {}
for row in sorted(preparation['prepared_trials'], key=lambda item: item['wave_order']):
    case_id = row['case_id']
    run_id = row['trial_run_id']
    prep_record_path = repository_path(row['preparation_record'])
    require(sha256(prep_record_path) == row['preparation_record_sha256'], f'{case_id}: preparation-record SHA drift.')
    prep_record = load_json(prep_record_path)
    require(prep_record['solve_authorization']['calculix_invoked'] is False, f'{case_id}: preparation claims prior execution.')
    require(prep_record['solve_authorization']['trial1_execution_authority_exists'] is False, f'{case_id}: preparation record itself must not grant execution authority.')
    deck_path = repository_path(prep_record['deck']['relative_path'])
    deck_sha = sha256(deck_path)
    require(deck_sha == row['deck_sha256'] == prep_record['deck']['sha256'], f'{case_id}: CAL_01 deck SHA drift.')
    run_dir = deck_path.parent
    require(deck_path.name == f'{run_id}.inp', f'{case_id}: deck filename / run identity drift.')
    for suffix in ('.dat', '.frd', '.sta', '.cvg', '.rout'):
        require(not (run_dir / f'{run_id}{suffix}').exists(), f'{case_id}: {suffix} already exists; refusing CAL_01 duplicate execution.')
    manifest_path = run_dir / 'fem_run_manifest.json'
    require(not manifest_path.exists(), f'{case_id}: FEM manifest already exists; refusing CAL_01 duplicate execution.')
    definition = CalculixJobDefinition(executable_relative_path=transfer.executable_relative_path, job_name=run_id, timeout_seconds=None)
    spec = GovernedCalculixExecutionSpec(project_root=ROOT, input_path=deck_path, definition=definition, backend_policy_id=backend.policy_id, solver_name=backend.solver_name, solver_version=backend.solver_version, manifest_path=manifest_path)
    require(spec.definition.job_name == run_id, f'{case_id}: execution-spec identity drift.')
    specs[run_id] = spec
    authorized_trials.append({'wave_order': row['wave_order'], 'case_id': case_id, 'case_hash': row['case_hash'], 'case_run_id': row['case_run_id'], 'trial_index': 1, 'trial_run_id': run_id, 'preparation_record': row['preparation_record'], 'preparation_record_sha256': row['preparation_record_sha256'], 'deck_path': relative(deck_path), 'deck_sha256': deck_sha, 'manifest_path': relative(manifest_path)})
require(len(specs) == AUTHORIZED_CASE_COUNT, 'Execution-spec count drift.')
authorization_created_now = False
if trial1_execution_auth_path.exists():
    auth_bytes = trial1_execution_auth_path.read_bytes()
    auth = json.loads(auth_bytes.decode('utf-8'))
    auth_sha = hashlib.sha256(auth_bytes).hexdigest()
else:
    auth = {'schema': 'threadrom.phase3_governed_wave_trial1_execution_authorization.v1', 'record_status': 'FINAL', 'authorization_type': 'OWNER_WAVE_CAL_01_ONLY_EXECUTION_AUTHORIZATION', 'approval_status': 'OWNER_APPROVED', 'approved_by': args.approved_by, 'approved_at_utc': datetime.now(timezone.utc).isoformat(timespec='microseconds'), 'campaign_id': CAMPAIGN_ID, 'wave_id': WAVE_ID, 'bound_artifacts': {'wave_plan_sha256': args.expected_wave_sha, 'trial1_preparation_authorization_sha256': args.expected_trial_preparation_auth_sha, 'geometry_mesh_authorization_sha256': args.expected_geometry_auth_sha, 'trial1_preparation_sha256': args.expected_preparation_sha, 'factory_registry_sha256': args.expected_registry_sha}, 'execution_contract': {'authorized_trial_index': 1, 'authorized_case_count': AUTHORIZED_CASE_COUNT, 'maximum_concurrent_calculix': MAXIMUM_CONCURRENT_CCX, 'duplicate_solver_execution_forbidden': True, 'registry_claim_required': True, 'durable_lease_required': True, 'certified_solver_backend_required': True, 'adaptive_cal_02_plus_authorized': False, 'additional_trials_authorized': False, 'full_physics_certification_authorized': False}, 'scope': {'additional_doe_cases_authorized': False, 'additional_waves_authorized': False, 'dataset_admission_authorized': False, 'holdout_access_authorized': False, 'surrogate_training_authorized': False, 'artifact_retirement_authorized': False}, 'authorized_trials': authorized_trials}
    auth_bytes = canonical_json_bytes(auth)
    auth_sha = hashlib.sha256(auth_bytes).hexdigest()
require(auth['schema'] == 'threadrom.phase3_governed_wave_trial1_execution_authorization.v1', 'Trial-1 execution authorization schema drift.')
require(auth['record_status'] == 'FINAL', 'Trial-1 execution authorization not FINAL.')
require(auth['authorization_type'] == 'OWNER_WAVE_CAL_01_ONLY_EXECUTION_AUTHORIZATION', 'Authorization type drift.')
require(auth['approval_status'] == 'OWNER_APPROVED', 'Trial-1 execution is not owner-approved.')
require(auth['campaign_id'] == CAMPAIGN_ID and auth['wave_id'] == WAVE_ID, 'Authorization campaign/wave drift.')
bound = auth['bound_artifacts']
require(bound['wave_plan_sha256'] == args.expected_wave_sha, 'Authorization wave SHA drift.')
require(bound['trial1_preparation_authorization_sha256'] == args.expected_trial_preparation_auth_sha, 'Authorization preparation-authority SHA drift.')
require(bound['geometry_mesh_authorization_sha256'] == args.expected_geometry_auth_sha, 'Authorization geometry-authority SHA drift.')
require(bound['trial1_preparation_sha256'] == args.expected_preparation_sha, 'Authorization preparation SHA drift.')
require(bound['factory_registry_sha256'] == args.expected_registry_sha, 'Authorization registry SHA drift.')
contract = auth['execution_contract']
require(contract['authorized_trial_index'] == 1, 'Authorization broadened beyond CAL_01.')
require(contract['authorized_case_count'] == 4, 'Authorization case count drift.')
require(contract['maximum_concurrent_calculix'] == 4, 'Authorization concurrency drift.')
require(contract['duplicate_solver_execution_forbidden'] is True, 'Duplicate-execution protection missing.')
require(contract['registry_claim_required'] is True, 'Durable registry claim is not required.')
require(contract['durable_lease_required'] is True, 'Durable lease is not required.')
require(contract['certified_solver_backend_required'] is True, 'Certified backend requirement missing.')
for forbidden in ('adaptive_cal_02_plus_authorized', 'additional_trials_authorized', 'full_physics_certification_authorized'):
    require(contract[forbidden] is False, f'CAL_01 authorization scope broadened: {forbidden}')
scope = auth['scope']
require(all((scope[key] is False for key in ('additional_doe_cases_authorized', 'additional_waves_authorized', 'dataset_admission_authorized', 'holdout_access_authorized', 'surrogate_training_authorized', 'artifact_retirement_authorized'))), 'CAL_01 execution scope broadened.')
auth_trials = auth['authorized_trials']
require(auth_trials == authorized_trials, 'Authorized CAL_01 trial inventory differs from current frozen preparation.')
if not trial1_execution_auth_path.exists():
    trial1_execution_auth_path.write_bytes(auth_bytes)
    authorization_created_now = True
require(sha256(trial1_execution_auth_path) == auth_sha, 'Published Trial-1 authorization SHA drift.')
print()
print('=== CAL_01 OWNER AUTHORIZATION ===')
print('Authorization SHA :', auth_sha)
print('Cases             : 4')
print('Trial             : CAL_01 ONLY')
print('Max concurrent ccx:', MAXIMUM_CONCURRENT_CCX)
print('Adaptive CAL_02+  : BLOCKED')
print('Holdouts          : SEALED')
print('Dataset admission : BLOCKED')
registry_sha_before = sha256(registry_path)
try:
    fresh_jobs = registry.list_jobs()
    require(len(fresh_jobs) == 4, 'Registry changed during authorization.')
    for job in fresh_jobs:
        require(job.state is FemFactoryJobState.PREPARED, f'{job.case_id}: no longer PREPARED.')
        require(job.trial_index == 1, f'{job.case_id}: non-CAL_01 job present.')
        require(job.run_id in specs, f'{job.case_id}: no pinned execution spec.')
        require(job.lease_generation == 0, f'{job.case_id}: lease generation changed.')
        require(job.lease_owner is None, f'{job.case_id}: job was unexpectedly claimed.')
        spec = specs[job.run_id]
        require(sha256(spec.input_path) == prepared_rows[job.case_hash]['deck_sha256'], f'{job.case_id}: deck changed after authorization.')
        require(not spec.manifest_path.exists(), f'{job.case_id}: manifest appeared during preflight.')
        for suffix in ('.dat', '.frd', '.sta', '.cvg', '.rout'):
            require(not (spec.input_path.parent / f'{job.run_id}{suffix}').exists(), f'{job.case_id}: solver evidence appeared during preflight.')
    registry_sha_after = sha256(registry_path)
    require(registry_sha_after == registry_sha_before == args.expected_registry_sha, 'Registry mutated during CAL_01 preflight.')
except Exception:
    if authorization_created_now:
        trial1_execution_auth_path.unlink(missing_ok=True)
        print()
        print('ROLLBACK: newly-created CAL_01 execution authorization removed because preflight failed.')
    raise
preflight = {'schema': 'threadrom.phase3_governed_wave_trial1_execution_preflight.v1', 'record_status': 'FINAL', 'campaign_id': CAMPAIGN_ID, 'wave_id': WAVE_ID, 'bound_artifacts': {'wave_plan_sha256': args.expected_wave_sha, 'trial1_preparation_sha256': args.expected_preparation_sha, 'factory_registry_sha256': args.expected_registry_sha, 'trial1_execution_authorization_sha256': auth_sha}, 'execution_scope': {'authorized_case_count': 4, 'authorized_trial_index': 1, 'maximum_concurrent_calculix': 4, 'adaptive_cal_02_plus_authorized': False}, 'backend': {'executable_relative_path': str(transfer.executable_relative_path), 'backend_policy_id': backend.policy_id, 'solver_name': backend.solver_name, 'solver_version': backend.solver_version}, 'registry_state': {'jobs': 4, 'prepared': 4, 'running': 0, 'lease_generation_zero': True, 'registry_mutated': False}, 'duplicate_execution_evidence': {'existing_manifests': 0, 'existing_dat': 0, 'existing_frd': 0, 'existing_sta': 0, 'existing_cvg': 0, 'existing_rout': 0}, 'safety': {'jobs_claimed': False, 'calculix_launched': False, 'adaptive_continuation': False, 'holdouts_accessed': False, 'dataset_admission': False}, 'authorized_trials': authorized_trials, 'overall_disposition': 'W04_CAL_01_EXECUTION_PREFLIGHT_PASS_LAUNCH_NOT_PERFORMED'}
preflight_sha = write_immutable_json(trial1_preflight_path, preflight)
print()
print('=' * 108)
print('W04 CAL_01 EXECUTION PREFLIGHT PASS')
print('=' * 108)
print('Owner authorization SHA :', auth_sha)
print('Preflight evidence SHA  :', preflight_sha)
print('Registry SHA            :', args.expected_registry_sha)
print('Jobs                     : 4/4 PREPARED')
print('Trial                    : CAL_01 ONLY')
print('Pinned execution specs   :', len(specs))
print('Jobs claimed             : NO')
print('Lease generation         : 0 / ALL')
print('Adaptive CAL_02+         : BLOCKED')
print('CalculiX launched        : NO')
print('Holdouts                 : SEALED')
print('ROM dataset              : UNTOUCHED')
print('=' * 108)

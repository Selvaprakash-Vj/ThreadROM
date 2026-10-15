from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from threadrom.factory.fem_factory_registry import FemFactoryJobState, FemFactoryPriority, FemFactoryRegistry
from threadrom.factory.governed_wave_contract import build_governed_wave_execution_contract
from threadrom.factory.governed_wave_owner_authorization import load_and_verify_wave_owner_authorization, verify_owner_authorization_payload
from threadrom.factory.governed_wave_runtime import run_governed_wave_entrypoint
ROOT = Path('D:\\ThreadROM').resolve()

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

def repository_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wave-id', required=True)
    parser.add_argument('--expected-wave-sha', required=True)
    parser.add_argument('--expected-trial-auth-sha', required=True)
    parser.add_argument('--expected-artifact-auth-sha', required=True)
    parser.add_argument('--expected-preparation-sha', required=True)
    parser.add_argument('--expected-registry-sha', required=True)
    parser.add_argument('--approved-by', required=True)
    return parser.parse_args()
args = parse_args()
WAVE_ID = args.wave_id
require(WAVE_ID == 'TRM-DDOE-001-W04', 'This commissioning invocation is bound specifically to W04.')
CAMPAIGN_ID = 'TRM-DDOE-001'
WAVE_TOKEN = 'W04'
MAXIMUM_CONCURRENT_SOLVER_SLOTS = 4
MAXIMUM_TRIAL_INDEX = 6
AUTHORIZED_CASE_COUNT = 4
wave_root = ROOT / 'docs' / 'phase3_diversified_doe' / 'waves' / WAVE_ID
wave_path = wave_root / 'wave_plan.json'
trial_auth_path = wave_root / 'trial1_owner_authorization.json'
artifact_auth_path = wave_root / 'geometry_mesh_owner_authorization.json'
execution_auth_path = wave_root / 'adaptive_campaign_owner_authorization.json'
campaign_root = ROOT / 'simulations' / 'staging' / 'phase3_diversified_doe' / CAMPAIGN_ID / WAVE_TOKEN
preparation_path = campaign_root / 'w04_trial1_preparation.json'
factory_root = campaign_root / 'factory'
registry_path = factory_root / 'w04_trial1_factory.sqlite3'
admission_lock_path = factory_root / 'w04_adaptive_parallel_admission.lock'
preflight_record_path = wave_root / 'governed_execution_preflight.json'
print()
print('=== FROZEN W04 EXECUTION-BOUNDARY PINS ===')
pins = (('Wave plan', wave_path, args.expected_wave_sha), ('Trial-1 preparation authorization', trial_auth_path, args.expected_trial_auth_sha), ('Geometry/mesh authorization', artifact_auth_path, args.expected_artifact_auth_sha), ('Trial-1 preparation index', preparation_path, args.expected_preparation_sha), ('Factory registry', registry_path, args.expected_registry_sha))
for label, path, expected in pins:
    actual = sha256(path)
    require(actual == expected, f'{label} SHA drift.\nexpected={expected}\nactual={actual}')
    print('PASS:', label, actual)
wave = load_json(wave_path)
preparation = load_json(preparation_path)
require(wave['wave_id'] == WAVE_ID, 'Wave identity drift.')
require(preparation['wave_id'] == WAVE_ID, 'Preparation identity drift.')
require(preparation['wave_plan_sha256'] == args.expected_wave_sha, 'Preparation / wave binding drift.')
require(preparation['factory_ready'] is True, 'Preparation is not factory-ready.')
require(preparation['solver_launched'] is False, 'Preparation claims solver launch.')
require(preparation['adaptive_continuation_authorized'] is False, 'Preparation itself grants adaptive continuation.')
require(preparation['holdouts_accessed'] is False, 'Preparation claims holdout access.')
for key in ('fem_execution_authorized', 'adaptive_continuation_authorized', 'full_physics_certification_authorized', 'dataset_admission_authorized', 'holdout_access_authorized', 'artifact_retirement_authorized'):
    require(wave[key] is False, f'Frozen wave-plan authority drift: {key}')
print()
print('=== PRE-AUTHORIZATION REGISTRY GATE ===')
registry = FemFactoryRegistry(registry_path)
jobs = registry.list_jobs()
require(len(jobs) == 4, f'Expected exactly four W04 registry jobs; found {len(jobs)}.')
prepared_rows = {row['case_hash']: row for row in preparation['prepared_trials']}
require(len(prepared_rows) == 4, 'Preparation contains duplicate case hashes.')
for job in jobs:
    require(job.case_hash in prepared_rows, 'Registry contains a case outside the frozen W04 preparation.')
    expected = prepared_rows[job.case_hash]
    require(job.case_id == expected['case_id'], f'{job.case_id}: case identity drift.')
    require(job.trial_index == 1, f'{job.case_id}: trial index is not CAL_01.')
    require(job.run_id == expected['trial_run_id'], f'{job.case_id}: run identity drift.')
    require(job.priority is FemFactoryPriority.HIGH_INFORMATION_DOE, f'{job.case_id}: priority drift.')
    require(job.state is FemFactoryJobState.PREPARED, f'{job.case_id}: expected PREPARED, found {job.state.value}.')
    require(job.preparation_record == expected['preparation_record'], f'{job.case_id}: preparation-record binding drift.')
    require(job.manifest_path is None, f'{job.case_id}: manifest already exists.')
    require(job.acceptance_record is None, f'{job.case_id}: acceptance record already exists.')
    require(job.lease_owner is None, f'{job.case_id}: lease owner already exists.')
    require(job.lease_expires_at_utc is None, f'{job.case_id}: lease already exists.')
    require(job.lease_generation == 0, f'{job.case_id}: lease generation is non-zero.')
print('PASS: 4/4 registry jobs PREPARED.')
print('PASS: zero leases / zero manifests / zero acceptance records.')
solver_evidence_suffixes = {'.dat', '.frd', '.sta', '.cvg', '.rout'}
solver_evidence = tuple((path for path in (campaign_root / 'solver_preparation').rglob('*') if path.is_file() and (path.suffix.lower() in solver_evidence_suffixes or path.name == 'fem_run_manifest.json')))
require(not solver_evidence, 'Solver evidence exists before governed launch:\n' + '\n'.join((str(path) for path in solver_evidence)))
require(not admission_lock_path.exists(), 'Parallel admission lock already exists.')
authorization_created_now = False
if execution_auth_path.exists():
    print()
    print('=== VERIFY EXISTING EXECUTION AUTHORIZATION ===')
    authorization_bytes = execution_auth_path.read_bytes()
    authorization_sha = hashlib.sha256(authorization_bytes).hexdigest()
    authorization_payload = json.loads(authorization_bytes.decode('utf-8'))
else:
    print()
    print('=== BUILD CANDIDATE EXECUTION AUTHORIZATION ===')
    authorization_payload = {'schema_version': 1, 'authorization_type': 'OWNER_BOUNDED_ADAPTIVE_WAVE_CAMPAIGN_AUTHORIZATION', 'approval_status': 'OWNER_APPROVED', 'approved_by': args.approved_by, 'approved_at_utc': datetime.now(timezone.utc).isoformat(timespec='microseconds'), 'campaign_id': CAMPAIGN_ID, 'wave_id': WAVE_ID, 'engineering_intent': 'One owner launch authorizes the hardened generic ThreadROM governed-wave stack to execute and adapt only the four frozen W04 cases from CAL_01 through governed full-physics acceptance or a defined terminal condition. No manual approval is required between bounded CAL_n trials inside this authorization.', 'bound_artifacts': {'wave_plan_sha256': args.expected_wave_sha, 'trial1_owner_authorization_sha256': args.expected_trial_auth_sha, 'geometry_mesh_owner_authorization_sha256': args.expected_artifact_auth_sha, 'w04_trial1_preparation_sha256': args.expected_preparation_sha}, 'execution_contract': {'automatic_governed_adaptation': True, 'continue_until_physics_acceptance': True, 'duplicate_solver_execution_forbidden': True, 'full_physics_certification': True, 'maximum_concurrent_calculix': MAXIMUM_CONCURRENT_SOLVER_SLOTS, 'maximum_trial_index_per_case': MAXIMUM_TRIAL_INDEX, 'preload_calibration_continuation': True, 'preserve_all_valid_realized_trials': True, 'reuse_existing_valid_trials': True, 'stop_on_governed_terminal_condition': True, 'stop_on_non_monotonic_response': True, 'stop_on_provenance_or_identity_failure': True, 'stop_on_unrecoverable_solver_failure': True}, 'required_completion_state': 'GOVERNED_FULL_PHYSICS_ACCEPTED', 'scope': {'authorized_case_count': AUTHORIZED_CASE_COUNT, 'additional_doe_cases_authorized': False, 'additional_waves_authorized': False, 'artifact_retirement_authorized': False, 'dataset_admission_authorized': False, 'holdout_access_authorized': False, 'independent_human_review_claimed': False, 'surrogate_training_authorized': False}}
    authorization_bytes = canonical_json_bytes(authorization_payload)
    authorization_sha = hashlib.sha256(authorization_bytes).hexdigest()
contract = build_governed_wave_execution_contract(campaign_id=CAMPAIGN_ID, wave_token=WAVE_TOKEN, expected_owner_authorization_sha256=authorization_sha, expected_preparation_index_sha256=args.expected_preparation_sha, authorized_case_count=AUTHORIZED_CASE_COUNT, maximum_concurrent_solver_slots=MAXIMUM_CONCURRENT_SOLVER_SLOTS, maximum_trial_index=MAXIMUM_TRIAL_INDEX)
print()
print('=== HARDENED AUTHORIZATION PAYLOAD VERIFICATION ===')
verified_candidate = verify_owner_authorization_payload(payload=authorization_payload, contract=contract, authorization_sha256=authorization_sha)
require(verified_candidate.campaign_id == CAMPAIGN_ID, 'Verified authorization campaign drift.')
require(verified_candidate.wave_id == WAVE_ID, 'Verified authorization wave drift.')
require(verified_candidate.authorized_case_count == AUTHORIZED_CASE_COUNT, 'Verified authorization case-count drift.')
require(verified_candidate.maximum_trial_index == MAXIMUM_TRIAL_INDEX, 'Verified authorization trial ceiling drift.')
require(verified_candidate.maximum_concurrent_solver_slots == MAXIMUM_CONCURRENT_SOLVER_SLOTS, 'Verified authorization concurrency drift.')
print('PASS: hardened generic verifier accepted candidate.')
print('Duplicate-execution guard:', verified_candidate.duplicate_execution_guard_field)
if not execution_auth_path.exists():
    execution_auth_path.write_bytes(authorization_bytes)
    authorization_created_now = True
    print('PASS: W04 execution authorization frozen.')
else:
    require(execution_auth_path.read_bytes() == authorization_bytes, 'Existing authorization bytes changed unexpectedly.')
    print('PASS: existing W04 execution authorization verified.')
require(sha256(execution_auth_path) == authorization_sha, 'Published authorization SHA drift.')
print('Authorization SHA:', authorization_sha)
loaded_authorization = load_and_verify_wave_owner_authorization(repository_root=ROOT, contract=contract)
require(loaded_authorization.authorization_sha256 == authorization_sha, 'Canonical authorization loader SHA drift.')
print('PASS: canonical generic authorization loader verified W04.')
registry_sha_before = sha256(registry_path)
print()
print('====================================================================================================')
print('HARDENED GENERIC RUNTIME PREFLIGHT')
print('execute=False')
print('====================================================================================================')
try:
    runtime_status = run_governed_wave_entrypoint(repository_root=ROOT, contract=contract, execute=False)
except Exception:
    if authorization_created_now:
        execution_auth_path.unlink(missing_ok=True)
        print()
        print('ROLLBACK: newly-created execution authorization removed because generic preflight failed.')
    raise
require(runtime_status == 0, f'Generic runtime preflight returned non-zero status: {runtime_status}')
registry_sha_after = sha256(registry_path)
require(registry_sha_after == registry_sha_before == args.expected_registry_sha, f'Registry changed during execute=False preflight.\nbefore={registry_sha_before}\nafter ={registry_sha_after}')
require(not admission_lock_path.exists(), 'execute=False preflight created a parallel-admission lock.')
jobs_after = registry.list_jobs()
require(len(jobs_after) == 4, 'Registry job count changed during preflight.')
for job in jobs_after:
    require(job.state is FemFactoryJobState.PREPARED, f'{job.case_id}: preflight changed state to {job.state.value}.')
    require(job.lease_owner is None, f'{job.case_id}: preflight claimed a lease.')
    require(job.lease_expires_at_utc is None, f'{job.case_id}: preflight created a lease.')
    require(job.lease_generation == 0, f'{job.case_id}: preflight changed lease generation.')
    require(job.manifest_path is None, f'{job.case_id}: preflight created manifest binding.')
solver_evidence_after = tuple((path for path in (campaign_root / 'solver_preparation').rglob('*') if path.is_file() and (path.suffix.lower() in solver_evidence_suffixes or path.name == 'fem_run_manifest.json')))
require(not solver_evidence_after, 'Solver evidence appeared during execute=False preflight.')
preflight_record = {'schema': 'threadrom.phase3_governed_wave_execution_preflight.v1', 'record_status': 'FINAL', 'campaign_id': CAMPAIGN_ID, 'wave_id': WAVE_ID, 'wave_token': WAVE_TOKEN, 'execution_contract': {'expected_owner_authorization_sha256': authorization_sha, 'expected_preparation_index_sha256': args.expected_preparation_sha, 'authorized_case_count': AUTHORIZED_CASE_COUNT, 'maximum_concurrent_solver_slots': MAXIMUM_CONCURRENT_SOLVER_SLOTS, 'maximum_trial_index': MAXIMUM_TRIAL_INDEX}, 'bound_artifacts': {'wave_plan_sha256': args.expected_wave_sha, 'trial1_owner_authorization_sha256': args.expected_trial_auth_sha, 'geometry_mesh_owner_authorization_sha256': args.expected_artifact_auth_sha, 'trial1_preparation_sha256': args.expected_preparation_sha, 'factory_registry_sha256': args.expected_registry_sha, 'adaptive_campaign_owner_authorization_sha256': authorization_sha}, 'registry_state': {'job_count': 4, 'prepared': 4, 'running': 0, 'solved': 0, 'accepted': 0, 'all_lease_generation_zero': True}, 'runtime': {'entrypoint': 'run_governed_wave_entrypoint', 'execute': False, 'status': runtime_status, 'registry_mutated': False, 'admission_lock_created': False, 'solver_evidence_created': False}, 'safety': {'calculix_launched': False, 'holdouts_accessed': False, 'dataset_admission_authorized': False, 'artifact_retirement_authorized': False, 'surrogate_training_authorized': False}, 'overall_disposition': 'W04_GOVERNED_EXECUTION_PREFLIGHT_PASS_LAUNCH_NOT_PERFORMED'}
preflight_sha = write_immutable_json(preflight_record_path, preflight_record)
print()
print('====================================================================================================')
print('W04 GOVERNED EXECUTION PREFLIGHT PASS')
print('====================================================================================================')
print('Execution authorization SHA :', authorization_sha)
print('Preparation SHA             :', args.expected_preparation_sha)
print('Factory registry SHA        :', args.expected_registry_sha)
print('Preflight evidence SHA      :', preflight_sha)
print('Cases                       : 4/4 PREPARED')
print('Maximum concurrent ccx      :', MAXIMUM_CONCURRENT_SOLVER_SLOTS)
print('Maximum trial index         :', MAXIMUM_TRIAL_INDEX)
print('Generic runtime status      :', runtime_status)
print('execute                     : FALSE')
print('Registry mutated            : NO')
print('Admission lock              : NONE')
print('Solver evidence             : NONE')
print('CalculiX launched           : NO')
print('Holdouts                    : SEALED')
print('ROM dataset                 : UNTOUCHED')
print('====================================================================================================')

# ThreadROM — Engineering Documentation Index

**Purpose:** Fast navigation across the Phase-3 engineering knowledge factory, current DA08 numerical-certification campaign, and Phase-4 handoff.

> This index is a navigation layer. Canonical authority always remains with the governed JSON records, closures, certificates, source contracts and SHA256 sidecars.

---

## Start here

### Human-readable master overview

Add this file to the repository as:

`docs/THREADROM_PHASE3_MASTER_STATUS_AND_PHASE4_ROADMAP.md`

It should explain:

- current Phase-3 status;
- why DA08 exists;
- W06 closure;
- current architecture;
- roadmap to Phase-3 closure;
- Phase-4 ROM plan;
- universality / new-M-standard expansion strategy;
- important authorities, scripts and modules.

---

## Core engineering knowledge

### FEM Atlas

- `docs/phase3_fem_atlas/INDEX.md`
- `docs/phase3_fem_atlas/atlas.json`
- `docs/phase3_fem_atlas/cases.csv`
- `docs/phase3_fem_atlas/historical_baselines/`

Use for:

- accepted FEM population;
- human-readable FEM inventory;
- evidence navigation;
- historical Atlas authority.

### Geometry / Mesh Atlas

- `docs/phase3_geometry_mesh_atlas/atlas.json`
- `docs/phase3_geometry_mesh_atlas/slice1_closure.json`

Use for:

- geometry/mesh reuse knowledge;
- governed mesh provenance;
- reuse decisions.

### Calibration knowledge

- `docs/phase3_calibration_knowledge/observations_v1.json`
- `docs/phase3_calibration_knowledge/slice2_closure.json`
- `docs/phase3_calibration_knowledge/trial1_predictor_v1_validation.json`

Use for:

- solved calibration-observation knowledge;
- trial-1 warm-start learning;
- predictor validation.

---

## Governed waves

### Wave authorities

Root:

`docs/phase3_diversified_doe/waves/`

Current wave directories:

- `TRM-DDOE-001-W01`
- `TRM-DDOE-001-W02`
- `TRM-DDOE-001-W03`
- `TRM-DDOE-001-W04`
- `TRM-DDOE-001-W05`
- `TRM-DDOE-001-W06`

Typical contents include:

- `wave_plan.json`
- `geometry_mesh_owner_authorization.json`
- `trial1_owner_authorization.json`
- `trial1_execution_owner_authorization.json`
- `trial1_execution_preflight.json`
- `governed_execution_preflight.json`
- `adaptive_campaign_owner_authorization.json`

### Wave closure

Root:

`docs/phase3_governed_wave_closure/`

Key files:

- `TRM-DDOE-001-W03.wave_closure.json`
- `TRM-DDOE-001-W04.wave_closure.json`
- `TRM-DDOE-001-W05.wave_closure.json`
- `TRM-DDOE-001-W06.wave_closure.json`
- `historical_replay/`
- `slice5_closure.json`
- `status_snapshot_v1.json`

Current W06 canonical closure SHA:

`1b4ea393fdd3c22646199e1a691e395c16952989d0e98eccfaac2d62c6983a57`

---

## ROM target / bridge

### Target authority

- `docs/phase3_rom_targets/member_shortening_v1.target_contract.json`

### Bridge closures

Root:

`docs/phase3_rom_dataset_bridge/`

Sequence:

1. `member_shortening_v1.t0_w06_launch_ready_closure.json`
2. `member_shortening_v1.t1_w06_preparation_authorization_closure.json`
3. `member_shortening_v1.t2_w06_wave_contract_closure.json`
4. `member_shortening_v1.t3_w06_readiness_closure.json`
5. `member_shortening_v1.t4_post_wave_transaction_closure.json`
6. `member_shortening_v1.t5_post_fem_hook_closure.json`
7. `member_shortening_v1.t6_governed_wave_admission_closure.json`
8. `member_shortening_v1.t7_target_bridge_closure.json`

Use this sequence to understand the FEM → target → ROM-admission bridge.

---

## ROM dataset admission

Root:

`docs/phase3_rom_dataset_admission/`

### Core contract

- `member_shortening_v1.admission_contract.json`

### DA08

- `member_shortening_v1.da08_exact_case_recovery.json`
- `member_shortening_v1.da08_fine_reference_campaign.json`
- `member_shortening_v1.da08_fine_reference_solver_launch_authorization.json`
- `member_shortening_v1.da08_holdout_clearance.json`
- `member_shortening_v1.da08_mesh_provenance_disposition.json`
- `member_shortening_v1.da08_sentinel_protocol.json`
- `member_shortening_v1.numerical_certification_authority.json`

### DA10

- `member_shortening_v1.supported_domain.json`
- `member_shortening_v1.da10_applicability_closure.json`

---

## DA08 execution navigation

### Preparation

- `scripts/prepare_phase3_da08_fine_reference_meshes_v2.py`
- `scripts/prepare_phase3_da08_fine_reference_decks_v3.py`

### Authorization

- `scripts/authorize_phase3_da08_fine_reference_execution_v2.py`

### Current execution

- `scripts/run_phase3_da08_fine_reference_campaign_v2.py`

### Generic solver reservation

- `src/threadrom/factory/governed_solver_launch_reservation.py`

### Historical diagnostic runner

- `scripts/run_phase3_da08_fine_reference_campaign_v1.py`

Do **not** use V1 as the current entrypoint. It intentionally remains evidence of the calibration-specific launch-fence mismatch.

---

## Numerical-certification implementation

- `config/fem_vv06_s1.toml`
- `src/threadrom/factory/fem_vv06_s1.py`
- `src/threadrom/factory/fem_result_extraction.py`
- `src/threadrom/factory/rom_dataset_numerical_certification.py`

Use after DA08 fine solves finish.

---

## Generic governed-wave source

- `src/threadrom/factory/governed_wave_contract.py`
- `src/threadrom/factory/governed_wave_owner_authorization.py`
- `src/threadrom/factory/governed_wave_runner.py`
- `src/threadrom/factory/governed_wave_runtime.py`
- `src/threadrom/factory/governed_wave_state_machine.py`
- `src/threadrom/factory/governed_wave_closure.py`
- `src/threadrom/factory/governed_stale_run_recovery.py`

---

## FEM factory / execution source

- `src/threadrom/factory/diversified_doe_adaptive_live_port.py`
- `src/threadrom/factory/diversified_factory_worker.py`
- `src/threadrom/factory/diversified_parallel_admission.py`
- `src/threadrom/factory/diversified_calculix_worker_adapter.py`
- `src/threadrom/factory/fem_factory_registry.py`
- `src/threadrom/factory/fem_solver_orchestrator.py`
- `src/threadrom/factory/production_doe_launch_fence.py`
- `src/threadrom/factory/governed_solver_launch_reservation.py`

---

## FEM definition / deck source

- `src/threadrom/factory/fem_case_definition_bundle.py`
- `src/threadrom/factory/fem_production_deck.py`
- `src/threadrom/solver/complete_joint_calculix_transfer.py`

---

## ROM admission source

- `src/threadrom/factory/rom_dataset_input_resolution.py`
- `src/threadrom/factory/rom_dataset_holdout_protection.py`
- `src/threadrom/factory/rom_dataset_applicability.py`
- `src/threadrom/factory/rom_dataset_admission.py`

---

## Post-wave transaction scripts

- `scripts/admit_phase3_governed_wave_geometry_mesh_v1.py`
- `scripts/admit_phase3_governed_wave_calibration_knowledge_v1.py`
- `scripts/admit_phase3_governed_wave_fem_evidence_v1.py`
- `scripts/run_phase3_governed_wave_post_fem_rom_hook_v1.py`
- `scripts/run_phase3_governed_wave_post_wave_transaction_v1.py`
- `scripts/evaluate_phase3_governed_wave_rom_admission_v1.py`

---

## Factory hardening / closure history

- `docs/phase3_generic_factory_hardening/`
- `docs/phase3_pre_w03_hardening/`
- `docs/phase3_production_baseline/`
- `docs/phase3_governed_wave_runner/`
- `docs/phase3_governed_wave_state_machine/`

Use these when tracing why a generic execution or governance rule exists.

---

## Current Git milestone

```text
Branch:
main

Commit:
d16ca7212445609bdfa328b502a997df1b8e5849

Message:
phase3: close W06 and freeze DA08 fine-reference boundary
```

This commit is the clean restore point immediately before the new generic solver-reservation + DA08 V2 execution proof.

---

## Phase-3 remaining path

```text
DA08 19/19 fine FEM
        ↓
fine-history extraction
        ↓
VV06-S1
        ↓
numerical certification authority
        ↓
DA08 closure
        ↓
W06 post-wave admission
        ↓
dataset/model lifecycle contracts
        ↓
final Phase-3 closure
        ↓
Phase 4 ROM
```

---

## Phase-4 entry point

Phase 4 should begin only from a **frozen governed dataset snapshot**.

Initial Phase-4 focus:

1. dataset snapshot/version contract;
2. feature/target assembly;
3. baseline ROM;
4. training provenance;
5. validation;
6. uncertainty/applicability;
7. model registry;
8. candidate-vs-incumbent comparison;
9. promotion/rollback policy;
10. retraining lifecycle when new FEM knowledge is admitted.

---

## Expansion rule for new thread standards

For future M14/M16/M20/etc.:

```text
add engineering definition
        ↓
build governed cases
        ↓
same CAD / mesh / FEM factory
        ↓
bounded domain-extension certification
        ↓
admit qualified evidence
        ↓
expand supported domain
        ↓
retrain/version ROM
```

The architecture should not require a new M-specific solver pipeline.

---

## One-line project principle

> **Phase 3 builds the trusted engineering teacher; Phase 4 builds and continuously improves the fast ROM student.**

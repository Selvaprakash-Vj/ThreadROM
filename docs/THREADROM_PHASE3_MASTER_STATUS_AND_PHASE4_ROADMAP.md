# ThreadROM — Phase 3 Master Status, Architecture & Phase 4 Roadmap

**Status snapshot:** 2026-10-15  
**Repository:** `D:\ThreadROM`  
**Branch:** `main`  
**Last pushed checkpoint:** `d16ca7212445609bdfa328b502a997df1b8e5849`  
**Checkpoint message:** `phase3: close W06 and freeze DA08 fine-reference boundary`

> **Document role**
>
> This file is a human-readable master guide. It does **not** replace immutable JSON authorities, SHA256 sidecars, FEM certificates, wave closures, Atlas records, or source-level contracts.  
> Where a discrepancy exists, the corresponding governed authority / closure / certificate is canonical.

---

## 1. Executive summary

ThreadROM Phase 3 is no longer primarily about “running FEM cases”. It is about completing and certifying a **generic engineering knowledge factory** that can turn arbitrary valid ThreadROM bolted-joint cases into governed FEM evidence and, where permitted, ROM-learning data.

The intended product architecture is:

```text
ThreadROMCase
    ↓
canonical engineering coordinates
    ↓
CAD / geometry generation
    ↓
geometry provenance / Geometry-Mesh Atlas
    ↓
governed mesh generation
    ↓
mesh provenance
    ↓
FEM definition
    ↓
adaptive preload calibration when required
    ↓
governed solver execution
    ↓
physics acceptance
    ↓
FEM Atlas
    ↓
target extraction
    ↓
ROM applicability + numerical-certification gates
    ↓
governed ROM dataset
    ↓
Phase 4 ROM training / validation / versioning
```

### Current headline status

- W03–W06 governed-wave closure machinery is operational.
- W06 reached **4/4 governed full-physics acceptance** and has a canonical final closure.
- FEM Atlas currently contains **43 accepted FEM cases** at the frozen DA08 baseline.
- `member_shortening` target bridge is complete.
- DA10 supported-domain/applicability closure is complete.
- DA08 fine-reference campaign was frozen at **19 exact sentinel/reference cases**.
- DA08 true global-fine meshes: **19/19 prepared**.
- DA08 deterministic production fine decks: **19/19 prepared**.
- DA08 solver-launch authorization: **frozen**.
- A new generic solver-reservation seam has been built and unit-tested to remove calibration-run-name assumptions.
- DA08 V2 execution has crossed the former launch barrier and the first true-fine solve has been launched.
- The 19 DA08 fine references run **serially, one at a time** and require no manual intervention between successful cases.
- W06 post-wave learning-sink admission is intentionally deferred until DA08 closes, so the frozen 43-case FEM Atlas authority remains unchanged during numerical certification.

---

## 2. What Phase 3 is actually trying to prove

Phase 3 is the **engineering-knowledge-factory phase**.

Its job is to prove that ThreadROM can reliably and generically perform the following:

1. represent engineering cases canonically;
2. generate/reuse CAD and mesh evidence;
3. create governed FEM definitions;
4. calibrate preload adaptively when needed;
5. execute CalculiX safely and reproducibly;
6. accept/reject physics through explicit evidence;
7. store qualified evidence in the FEM Atlas;
8. extract ROM targets deterministically;
9. reject cases outside the certified ROM domain;
10. prove numerical fidelity of the FEM teacher;
11. admit only qualified cases to the ROM dataset;
12. preserve lineage from engineering case → FEM → target → dataset → future model.

The desired Phase-3 closure condition is therefore **not** “we have enough FEM cases forever”.

It is:

> The architecture is complete, governed, generic, auditable and capable of continuing to accumulate high-quality FEM knowledge without reopening core architecture.

Diversified DOE waves can then continue as **data accumulation**, not as unfinished architecture.

---

## 3. Why the 19 DA08 fine FEM simulations exist

The DA08 campaign is a **numerical-certification campaign**, not primarily a training-data campaign.

The core question is:

> Can the accepted production FEM evidence be trusted as the numerical teacher for `member_shortening`?

The comparison route is:

```text
accepted production FEM state
        ↓
same physical / accepted calibration state
        ↓
true global-fine FEM
        ↓
fine nonlinear history
        ↓
match by realized clamp force
        ↓
compare member_shortening
        ↓
VV06-S1
        ↓
relative error ≤ 2%
        ↓
numerical certification
```

### Frozen DA08 design

- Target: `member_shortening`
- Exact fine-reference cases: **19**
- Cohorts represented: **11**
- Current production/reference Atlas baseline: **43 FEM cases**
- DA10-eligible domain at current baseline: **35**
- Numerical tolerance: **2%**
- Fine-reference comparison method: **VV06-S1**
- No extrapolation outside fine-history clamp-force support
- 15 cases are direct-certification references
- M10 steel contains the baseline + radial sentinels required for the frozen transfer decision
- If frozen M10-steel transfer conditions pass, the certification burden can extend to the remaining eligible population without brute-force fine-solving every historical case

### Important interpretation

These 19 simulations are **not** the adaptive preload-calibration loop.

The preload/calibration state has already been accepted and is reused. The DA08 campaign changes the numerical resolution while preserving the physical state.

---

## 4. Current DA08 execution state

### Pre-solve closure

All pre-solve work is complete:

```text
Exact cases              : 19/19
True global-fine meshes  : 19/19
Fine mesh quality        : 19/19 PASS
Accepted source states   : 19/19
Production fine decks    : 19/19
Deterministic decks      : 19/19
Solver authorization     : FROZEN
```

### Generic execution repair

The first DA08 runner attempted to reuse:

`reserve_adaptive_trial_launch(...)`

That fence correctly rejected the DA08 run identity because it is historically coupled to bounded calibration-style identities such as `_cal_01`.

The repair was **not** to fake calibration naming.

A new generic execution reservation layer was created:

`src/threadrom/factory/governed_solver_launch_reservation.py`

Current local SHA256:

`2066a5f82f542d85c76cc7237c8360274d047309878a04124514e5e8815b3531`

Properties:

- calibration-agnostic run identity;
- repository-global solver-slot reservation;
- campaign-local concurrency reservation;
- per-run duplicate-active protection;
- Windows OS-backed byte-range locks;
- live global CalculiX count remains authoritative;
- global ThreadROM limit remains **4**;
- DA08 local campaign limit remains **1**;
- historical `production_doe_launch_fence.py` is unchanged.

Unit test result:

```text
13 passed
```

DA08 V2 runner:

`scripts/run_phase3_da08_fine_reference_campaign_v2.py`

Current local SHA256:

`f9c4a0880d062fa71f2c55fff52cc431e6c1b318358ab95f2208d0d3e30dedd9`

### Current live boundary

The first DA08 true-fine case crossed the previously blocked reservation boundary:

```text
DA08 TRUE-FINE FEM 01/19
Run ID       : trm_fem_0f92f7fbf611_da08_fine_ref_01
Execution    : LAUNCH
ccx before   : 0
Global slot  : 0
Campaign slot: 0
```

The runner is designed to continue automatically:

```text
01/19 → solve → verify → persist evidence
02/19 → solve → verify → persist evidence
...
19/19 → campaign certificate
```

No manual action is required between successful cases.

---

## 5. W06 closure status

W06 was the latest governed adaptive wave and is an important validation of the generic adaptive FEM factory.

### Final accepted cases

| Case | Final accepted trial |
|---|---|
| M10 × 1.5, Al 6082-T6 | CAL_02 |
| M12 × 1.75, Al 6082-T6 | CAL_02 |
| M12 × 1.75, steel member | CAL_01 |
| M8 × 1.25, Al 6082-T6 | CAL_02 |

### Meaning

- one case accepted directly at CAL_01;
- three cases solved a valid CAL_01 miss;
- the adaptive factory automatically generated CAL_02;
- all four physical cases reached governed full-physics acceptance;
- solved misses were retained as useful calibration-learning evidence;
- no historical solved evidence was mutated or rerun.

### Canonical closure

File:

`docs/phase3_governed_wave_closure/TRM-DDOE-001-W06.wave_closure.json`

SHA256:

`1b4ea393fdd3c22646199e1a691e395c16952989d0e98eccfaac2d62c6983a57`

Disposition:

`GOVERNED_WAVE_FULL_PHYSICS_CLOSED`

Authorized cases: `4`  
Accepted cases: `4`

---

## 6. Why W06 post-wave admission is temporarily parked

The DA08 protocol was frozen against the existing FEM Atlas authority:

`docs/phase3_fem_atlas/atlas.json`

Frozen SHA256:

`2f491e19c248c13986c195a0161d00ab69c787f34998cb57c2e1b2d172d19515`

Therefore W06 physics is closed, but its downstream learning-sink admission is intentionally deferred until DA08 closes.

Correct ordering:

```text
W06 physics accepted
    ↓
W06 canonical closure
    ↓
DA08 frozen against unchanged 43-case FEM Atlas
    ↓
DA08 fine solves
    ↓
VV06-S1 numerical certification
    ↓
DA08 closure
    ↓
W06 post-wave transaction / learning-sink admission
```

This avoids silently changing the authority beneath an active numerical-certification protocol.

---

## 7. Current Phase-3 progress map

### Closed / substantially complete

#### Geometry / Mesh
- generic CAD generation path;
- geometry identity/provenance;
- generic mesh generation;
- Geometry/Mesh Atlas;
- governed geometry/mesh reuse;
- DA08 true global-fine mesh preparation.

#### FEM execution
- governed FEM preparation;
- production deck generation;
- CalculiX orchestration;
- adaptive preload calibration;
- factory job registry;
- parallel/governed wave execution;
- stale-run recovery;
- governed wave closure;
- generic non-calibration solver reservation now established locally.

#### FEM knowledge
- adaptive solved-miss retention;
- calibration observation store;
- warm-start predictor;
- accepted FEM evidence registration;
- FEM Atlas.

#### ROM bridge
- T0–T7 bridge/closure sequence;
- target contract for `member_shortening`;
- deterministic target extraction bridge;
- generic post-FEM ROM hook;
- generic post-wave transaction;
- generic post-target dataset-admission engine.

#### Dataset admission
- DA01–DA07 substantially closed;
- DA09 closed;
- DA10 supported-domain/applicability closed;
- DA11 holdout clearance closed;
- DA12 closed;
- DA08 is the remaining numerical-certification bottleneck.

### Current open architectural/numerical items

1. finish all 19 DA08 fine solves;
2. extract fine histories;
3. run VV06-S1 matched-force certification;
4. update/freeze numerical-certification authority;
5. prove runtime admission on the frozen Atlas;
6. close DA08 immutably;
7. admit W06 through generic post-wave sinks;
8. freeze dataset snapshot/version/model-registry/retraining lifecycle contracts;
9. final non-DOE Phase-3 readiness/closure audit.

---

## 8. Phase-3 closure roadmap

### Gate A — DA08 fine execution

Target result:

```text
Authorized cases       : 19
Successful fine solves : 19/19
Final running ccx      : 0
W06 registry           : UNCHANGED
FEM Atlas              : UNCHANGED
Holdouts               : SEALED
```

### Gate B — fine-history extraction

For each fine reference:

- recover accepted nonlinear history;
- recover realized clamp-force coordinate;
- recover `member_shortening`;
- bind result provenance to source case and exact fine deck;
- preserve deterministic hashes.

Relevant implementation:

`src/threadrom/factory/fem_result_extraction.py`

### Gate C — VV06-S1

Frozen configuration:

`config/fem_vv06_s1.toml`

Frozen comparison rules:

- screening points: `[5, 10, 15, 18, 19, 19.5]`
- governing points: `[18, 19, 19.5]`
- x-axis: realized clamp force
- no extrapolation
- tolerance: `0.02`
- primary: two-point linear interpolation
- cross-check: three-point quadratic interpolation
- worst-case additive uncertainty
- support if `d_high <= tol`
- reject if `d_low > tol`
- otherwise indeterminate

Implementation:

`src/threadrom/factory/fem_vv06_s1.py`

### Gate D — DA08 authority

Update/freeze:

`docs/phase3_rom_dataset_admission/member_shortening_v1.numerical_certification_authority.json`

Desired effect:

DA08 ceases to be the active blocker for all cases supported by the frozen direct/transfer rules.

### Gate E — runtime admission proof

Use the generic post-target admission engine to demonstrate that eligible cases no longer remain DA08-deferred where certification is available.

### Gate F — W06 post-wave admission

Only after DA08 closes:

- geometry/mesh knowledge;
- calibration knowledge;
- accepted FEM evidence;
- FEM Atlas;
- target bridge;
- ROM-admission evaluation.

Use the generic post-wave transaction rather than wave-specific code.

### Gate G — learning lifecycle contracts

Freeze:

- dataset snapshot identity;
- dataset versioning;
- model versioning;
- training provenance;
- evaluation provenance;
- retraining trigger semantics;
- old-vs-new model comparison;
- rollback/reference-model policy.

### Gate H — Phase-3 closure

The final Phase-3 closure should explicitly state:

> Diversified DOE accumulation remains open as an intentional data-growth track. Core Phase-3 architecture is closed and no longer blocked on continued FEM accumulation.

---

## 9. What Phase 4 should become

Phase 4 is the **ROM learning-product phase**.

It should consume governed Phase-3 outputs rather than rebuild FEM infrastructure.

Target architecture:

```text
frozen admitted dataset snapshot
        ↓
feature / target preparation
        ↓
train candidate ROM
        ↓
validation
        ↓
uncertainty / applicability
        ↓
model registry
        ↓
production prediction
```

And the long-term loop:

```text
new engineering case
        ↓
ROM applicability check
     ↙       ↘
 inside     outside / uncertain
 domain
   ↓              ↓
ROM predict     FEM factory
                  ↓
            accepted FEM
                  ↓
             FEM Atlas
                  ↓
            ROM admission
                  ↓
          dataset snapshot N+1
                  ↓
              retrain
                  ↓
              ROM N+1
```

FEM therefore becomes the **teacher**.

The ROM becomes the fast surrogate.

---

## 10. Architecture universality

ThreadROM is not intended to be “universal mechanical engineering software”.

The realistic universality target is:

> A generic, governed architecture for supported metric threaded bolted-joint structural cases where thread, material, geometry, preload, mesh, boundary conditions and targets are engineering coordinates rather than hard-coded execution branches.

### What should *not* exist

```python
if case_id == "special_case_17":
    ...
```

```python
if wave == "W06":
    use_special_physics()
```

```python
if thread == "M14":
    run_m14_pipeline()
```

### What should exist instead

Canonical coordinates such as:

```text
thread designation
pitch
nominal diameter
member material
fastener material
geometry ratios
preload
contact/friction policy
mesh policy
boundary conditions
target definitions
```

The architecture then interprets those coordinates generically.

### Current architectural confidence

At the present state:

- generic engineering/factory architecture: approximately **97%**;
- after DA08 numerical closure: approximately **98–99%**;
- after final lifecycle + closure contracts: architecture can reasonably be considered **Phase-3 complete**.

Those percentages are engineering-progress estimates, not governed certificate fields.

---

## 11. Adding new M standards later

A future new standard such as `M14 × 2` should ideally require:

1. add/validate the new thread engineering definition/catalog data;
2. construct governed `ThreadROMCase` inputs;
3. run existing CAD/mesh/factory machinery;
4. execute a bounded domain-extension certification set;
5. admit qualified cases;
6. expand the supported ROM domain;
7. retrain/version the ROM.

It should **not** require:

```text
build_m14_cad.py
mesh_m14.py
run_m14_solver.py
extract_m14.py
```

### Example expansion

```text
Current:
M8 + M10 + M12

Next:
+ M14

Later:
+ M16
+ M20
+ additional supported materials
+ broader preload region
+ broader geometry region
```

A genuinely new engineering domain may still require **new sentinel/fine-reference certification**.

That is healthy.

Universality means the **pipeline remains the same**; it does not mean evidence requirements disappear.

---

## 12. How product robustness improves over time

Every new qualified FEM campaign can improve ThreadROM through several knowledge layers:

### Geometry/Mesh knowledge
New cases improve reuse coverage and demonstrate broader geometric robustness.

### Calibration knowledge
Valid solved misses and accepted calibration trials improve the observation store and warm-start predictor.

### FEM Atlas
The accepted FEM population becomes broader and more representative.

### Numerical-certification domain
New fine-reference sentinels can certify additional engineering regions.

### ROM dataset
More qualified cases improve interpolation density and robustness.

### ROM model
New dataset snapshots can produce better models, provided validation proves an actual improvement.

The expected product cycle is:

```text
more governed FEM
    ↓
more qualified engineering knowledge
    ↓
broader certified ROM dataset
    ↓
retraining
    ↓
compare candidate vs incumbent ROM
    ↓
promote only if evidence supports promotion
```

---

## 13. Important current authorities and SHAs

> These are snapshot references for navigation. Always verify the live file/sidecar before using them as execution authority.

| Authority / component | Current reference |
|---|---|
| Pushed repository checkpoint | `d16ca7212445609bdfa328b502a997df1b8e5849` |
| Frozen FEM Atlas | `2f491e19c248c13986c195a0161d00ab69c787f34998cb57c2e1b2d172d19515` |
| W06 closure | `1b4ea393fdd3c22646199e1a691e395c16952989d0e98eccfaac2d62c6983a57` |
| DA08 exact-case recovery | `61a84b602e654a867945b130110b81ed5bd75bc1d1187676543d0da544f42637` |
| DA08 fine mesh preparation cert | `d22f971212ed8e367b6aea0c06a4c4d64df67bbdeeb9a40bb47858ab8b60f0ec` |
| DA08 fine deck preparation cert | `0db68e52e84dd74cf40b5c6e47db772aa670b7618f50dc45299c65739345e576` |
| DA08 solver authorization | `ec95fa65dab101c30d477b01eb8310638b3898f34f910c91fe099ad027346e41` |
| DA08 sentinel protocol | `540e4ec8087bb11a622322ef9733e03a65cbcfc8ea4b62d228eaba5524b12d54` |
| DA08 holdout clearance | `04e719c61f842ecfc50fcc33330eb11d4562aa977802dcb03d24a8084e84f308` |
| DA08 mesh provenance disposition | `d8db133f45f7fdcbdc98a022ddb4bd4a239e1be0364f87f7f86bad5066f53290` |
| DA10 supported-domain definition | `8e299508dd12f92fce4fcae59a2bf034eb91dbffcf0b46db3646a6e0ccfbd6` |
| DA10 closure | `0603722f6c3558808f55b19e2b29d695412c00f75565333a22c3491a9871c30d` |
| `member_shortening` target contract | `b8fcf7519e1fe805f5093b9f3a0d01f53b64ba705b118e4d271677895e47a2bf` |
| ROM admission contract | `5d7b127345b89327624db560cf03c49fa40346a01491188540ffc797b44f5c11` |
| T7 target bridge closure | `7e604c14146e5bae902ffa107288328044bae0c3e926bfa51e85b61e5da8f1` |
| Generic ROM admission module | `3e5ae43faeb676d399e5cb99233aa71582ff2cbf67ff81eb37c3ed124ec82d13` |
| DA10 applicability module | `7ae9aaafe2efa8ebcca4cd7ec3dafe19fef7f7e1224a82593f87334e8d401d82` |
| Generic post-FEM ROM hook | `6a717bcde381e405017b90bcd93ed88a77f3aed4e3f0268c418e37faeab82fb2` |
| Generic post-wave transaction | `8a0b69e9db6804fb7772ee3320b22c8e758eaece75f2fd70c07def6cee6292f0` |
| VV06-S1 config | `8db299508dd12f92fce4fcae59a2bf034eb91dbffcf0b46db3646a6e0ccfbd6` |
| VV06-S1 implementation | `b06023a67b35d546c36f9b288ed4c2cb06f668cd4245049e4a549fa2a8c48e90` |
| FEM result extraction | `657debfbb41a9fdee75d72f03250ca01f4c6f9fdf73224c79d1e58a0f3158b37` |
| Solver orchestrator | `c9bfdc251681387ccde0e64937ace083491c13b159a8e32a81341592bca37040` |
| Generic solver reservation (local current) | `2066a5f82f542d85c76cc7237c8360274d047309878a04124514e5e8815b3531` |
| DA08 V2 runner (local current) | `f9c4a0880d062fa71f2c55fff52cc431e6c1b318358ab95f2208d0d3e30dedd9` |

### Note on VV06-S1 config hash

The live repository file and its `.sha256` sidecar are canonical. If this document’s snapshot reference differs from the actual sidecar, use the sidecar.

---

## 14. Important file map

### FEM Atlas

```text
docs/phase3_fem_atlas/
├── INDEX.md
├── atlas.json
├── cases.csv
└── historical_baselines/
```

### Geometry/Mesh Atlas

```text
docs/phase3_geometry_mesh_atlas/
├── atlas.json
└── slice1_closure.json
```

### Governed wave authorities

```text
docs/phase3_diversified_doe/waves/
├── TRM-DDOE-001-W01/
├── TRM-DDOE-001-W02/
├── TRM-DDOE-001-W03/
├── TRM-DDOE-001-W04/
├── TRM-DDOE-001-W05/
└── TRM-DDOE-001-W06/
```

### Wave closures

```text
docs/phase3_governed_wave_closure/
├── TRM-DDOE-001-W03.wave_closure.json
├── TRM-DDOE-001-W04.wave_closure.json
├── TRM-DDOE-001-W05.wave_closure.json
├── TRM-DDOE-001-W06.wave_closure.json
├── historical_replay/
├── slice5_closure.json
└── status_snapshot_v1.json
```

### ROM / dataset admission

```text
docs/phase3_rom_dataset_admission/
├── member_shortening_v1.admission_contract.json
├── member_shortening_v1.da08_exact_case_recovery.json
├── member_shortening_v1.da08_fine_reference_campaign.json
├── member_shortening_v1.da08_fine_reference_solver_launch_authorization.json
├── member_shortening_v1.da08_holdout_clearance.json
├── member_shortening_v1.da08_mesh_provenance_disposition.json
├── member_shortening_v1.da08_sentinel_protocol.json
├── member_shortening_v1.da10_applicability_closure.json
├── member_shortening_v1.numerical_certification_authority.json
└── member_shortening_v1.supported_domain.json
```

### ROM bridge

```text
docs/phase3_rom_dataset_bridge/
├── member_shortening_v1.t0_w06_launch_ready_closure.json
├── member_shortening_v1.t1_w06_preparation_authorization_closure.json
├── member_shortening_v1.t2_w06_wave_contract_closure.json
├── member_shortening_v1.t3_w06_readiness_closure.json
├── member_shortening_v1.t4_post_wave_transaction_closure.json
├── member_shortening_v1.t5_post_fem_hook_closure.json
├── member_shortening_v1.t6_governed_wave_admission_closure.json
└── member_shortening_v1.t7_target_bridge_closure.json
```

### ROM target

```text
docs/phase3_rom_targets/
└── member_shortening_v1.target_contract.json
```

### Calibration knowledge

```text
docs/phase3_calibration_knowledge/
├── observations_v1.json
├── slice2_closure.json
└── trial1_predictor_v1_validation.json
```

---

## 15. Important source modules

### Generic governed-wave machinery

```text
src/threadrom/factory/governed_wave_contract.py
src/threadrom/factory/governed_wave_owner_authorization.py
src/threadrom/factory/governed_wave_runner.py
src/threadrom/factory/governed_wave_runtime.py
src/threadrom/factory/governed_wave_state_machine.py
src/threadrom/factory/governed_wave_closure.py
src/threadrom/factory/governed_stale_run_recovery.py
```

### Adaptive FEM factory / execution

```text
src/threadrom/factory/diversified_doe_adaptive_live_port.py
src/threadrom/factory/diversified_factory_worker.py
src/threadrom/factory/diversified_parallel_admission.py
src/threadrom/factory/diversified_calculix_worker_adapter.py
src/threadrom/factory/fem_factory_registry.py
src/threadrom/factory/fem_solver_orchestrator.py
src/threadrom/factory/production_doe_launch_fence.py
src/threadrom/factory/governed_solver_launch_reservation.py   # new generic non-calibration reservation
```

### Calibration learning

```text
src/threadrom/factory/fem_calibration_observation_store.py
src/threadrom/factory/fem_calibration_trial1_predictor.py
src/threadrom/factory/governed_calibration_history.py
src/threadrom/factory/governed_trial_history.py
```

### FEM preparation / deck

```text
src/threadrom/factory/fem_case_definition_bundle.py
src/threadrom/factory/fem_production_deck.py
src/threadrom/solver/complete_joint_calculix_transfer.py
```

### FEM extraction / numerical certification

```text
src/threadrom/factory/fem_result_extraction.py
src/threadrom/factory/fem_vv06_s1.py
src/threadrom/factory/rom_dataset_numerical_certification.py
```

### ROM admission

```text
src/threadrom/factory/rom_dataset_input_resolution.py
src/threadrom/factory/rom_dataset_holdout_protection.py
src/threadrom/factory/rom_dataset_applicability.py
src/threadrom/factory/rom_dataset_admission.py
```

---

## 16. Important scripts

### Governed wave preparation / execution / closure

```text
scripts/build_phase3_next_governed_wave_v1.py
scripts/authorize_phase3_governed_wave_preparation_v1.py
scripts/prepare_phase3_governed_wave_trial1_v1.py
scripts/initialize_phase3_governed_wave_factory_v1.py
scripts/start_phase3_governed_wave_v1.py
scripts/launch_phase3_governed_wave_trial1_v1.py
scripts/close_current_phase3_governed_wave_v2.py
```

### Post-wave knowledge admission

```text
scripts/admit_phase3_governed_wave_geometry_mesh_v1.py
scripts/admit_phase3_governed_wave_calibration_knowledge_v1.py
scripts/admit_phase3_governed_wave_fem_evidence_v1.py
scripts/run_phase3_governed_wave_post_fem_rom_hook_v1.py
scripts/run_phase3_governed_wave_post_wave_transaction_v1.py
scripts/evaluate_phase3_governed_wave_rom_admission_v1.py
```

### DA08

```text
scripts/prepare_phase3_da08_fine_reference_meshes_v2.py
scripts/prepare_phase3_da08_fine_reference_decks_v3.py
scripts/authorize_phase3_da08_fine_reference_execution_v2.py
scripts/run_phase3_da08_fine_reference_campaign_v2.py
```

Historical/failed DA08 runner:

```text
scripts/run_phase3_da08_fine_reference_campaign_v1.py
```

Do not treat V1 as the current execution entrypoint. It is retained as diagnostic/history evidence for the calibration-specific reservation mismatch.

---

## 17. Git milestone

Current pushed checkpoint:

```text
Commit:
d16ca7212445609bdfa328b502a997df1b8e5849

Message:
phase3: close W06 and freeze DA08 fine-reference boundary
```

Meaning of this checkpoint:

```text
W06 physics   : 4/4 ACCEPTED
W06 closure   : FINAL
DA08 meshes   : 19/19
DA08 decks    : 19/19
DA08 auth     : FROZEN
DA08 FEM      : NOT YET PART OF THAT COMMIT
```

The generic solver reservation + DA08 V2 execution runner were created after this checkpoint and should receive their own clean commit after execution behavior is proven.

---

## 18. Operating rules that should remain true

1. Do not access or expose holdout identities/coordinates/targets.
2. Do not admit unqualified FEM evidence into ROM-learning data.
3. Do not infer mesh identity solely from engineering regime.
4. Do not silently extrapolate numerical certification.
5. Do not mutate historical accepted/solved evidence to “clean up” a registry.
6. Preserve valid solved misses as calibration-learning knowledge.
7. Do not introduce wave-specific physics hacks.
8. Do not introduce case-ID hacks.
9. Keep immutable authorities + SHA sidecars as canonical evidence.
10. Separate:
   - physics acceptance,
   - numerical certification,
   - ROM applicability,
   - dataset admission.
11. A passing FEM case is not automatically a ROM-training case.
12. A supported ROM domain must expand only with engineering evidence.
13. New standards should expand data/catalog/domain definitions before architecture.
14. Historical execution fences should not be weakened merely to support a new campaign; create/promote generic seams instead.
15. Phase 4 model promotion must be evidence-based, versioned and reversible.

---

## 19. Definition of success for the product

The intended future user experience is:

```text
Engineer defines supported bolted-joint case
        ↓
ThreadROM resolves canonical case
        ↓
If inside certified ROM domain:
        → fast ROM prediction

If outside / uncertain:
        → governed FEM factory
        → evidence
        → optional domain extension
        → future ROM improvement
```

The product becomes stronger through use:

```text
new standards
+ new materials
+ new geometry regions
+ new preload regions
+ governed FEM evidence
        ↓
broader certified dataset
        ↓
better ROM
        ↓
broader robust product scope
```

That is the long-term ThreadROM architecture.

---

## 20. Immediate next actions

### While DA08 V2 runs

No manual intervention between successful cases.

Observe only for:

- solver failure;
- non-success manifest;
- missing output;
- unexpected persistent `ccx`;
- W06/FEM-Atlas mutation guard;
- reservation error.

### After 19/19 succeeds

1. freeze DA08 execution campaign certificate;
2. extract fine histories;
3. apply VV06-S1;
4. create exact direct-certification results;
5. evaluate frozen M10-steel transfer rule;
6. update numerical-certification authority;
7. rerun ROM admission;
8. close DA08;
9. admit W06 post-wave knowledge;
10. close remaining Phase-3 lifecycle architecture;
11. create final Phase-3 closure;
12. start Phase 4 ROM.

---

# Final perspective

Phase 3 is building a **trusted engineering teacher**.

Phase 4 will build the **fast learning surrogate** from that teacher.

The key long-term promise is not simply that ThreadROM can solve M8/M10/M12 today.

It is that adding M14, M16, M20, broader materials and broader design regions should primarily mean:

```text
add engineering scope
→ certify the extension
→ run the same factory
→ admit qualified knowledge
→ retrain/version the ROM
```

—not rebuild the software architecture.

That is the standard by which ThreadROM’s universality and product robustness should continue to be judged.

# ThreadROM — Phase 3 Factory, Engineering Scope and ROM Roadmap

**Status date:** 2026-09-23
**Project:** ThreadROM
**Document type:** Engineering status, architectural reference and future-work handover
**Status:** Six bounded factory-qualification gates closed; Phase 3 dataset completion pending; Phase 4 ROM not started.

> This document records the project state established through 2026-09-23.
> It is not a substitute for the authoritative repository, frozen campaign
> configuration, case-specific evidence, solver outputs or physics certificates.
> If a later run or committed change supersedes an item, update this document
> with the exact evidence and date rather than silently rewriting history.

---

## 1. Executive summary

ThreadROM is developing a parametric, governed engineering workflow for
bolted-joint analysis and subsequent reduced-order modelling (ROM).

The long-term ambition is a diversified family of fastener-joint ROMs supported
by reusable analytical, CAD, FEM, validation and data-governance infrastructure.

The near-term product scope is intentionally narrower:

1. Complete Phase 3 using the explicitly governed and documented DOE envelope.
2. Verify and freeze a physically defensible training/evaluation dataset.
3. Begin the first bounded ROM in Phase 4.
4. Expand size, material, geometry, loading and ROM capabilities through
   separate, evidence-backed qualification campaigns.

**Current milestone:** The six agreed factory software and bounded-C01
preparation-qualification gates are closed. The latest full repository
regression passed **1,157 tests** on 2026-09-23.

**Not yet achieved:** Full DOE physics certification, complete training-dataset
freeze, an operating first ROM, or universally qualified metric-fastener FEM.

The C01 DOE has already accumulated physical solver evidence. The six-gate
qualification was therefore a qualification of the reusable factory for
continued governed work, not a claim that no DOE FEM had previously run.

---

## 2. Governing engineering principles

### 2.1 Physics before predictions

An accepted solver run is not automatically an accepted engineering sample.
Simulation completion, numerical convergence, preload acceptance, equilibrium,
contact behaviour, mesh adequacy and case-specific physics criteria are
different evidence requirements.

ROM training must consume samples admitted by the appropriate governed
engineering and dataset criteria. Missing evidence must not be inferred from
the presence of a deck, run manifest or apparently successful solver exit.

### 2.2 Evidence conservation and computational efficiency

- Reuse existing, certified engineering evidence wherever its applicability
  and provenance support reuse.
- Do not repeat FEM merely because a new script or inventory cannot locate
  an expected file.
- Preserve valid realised states, including failed and rejected trials, with
  explicit dispositions and failure reasons.
- Use governed analytical/FEM-informed warm starts and the reusable calibration
  machinery to reduce unnecessary nonlinear iterations and repeat solves.
- Treat expensive compute and energy consumption as engineering constraints.
- A justified long-running FEM job must not be interrupted by an arbitrary
  short timeout solely for convenience.

### 2.3 Fail-closed governance

- A frozen design-case inventory is not a solver-launch authorization.
- New Trial-1 launches require independent, exact-case, exact-trial, pinned
  owner authorization through the governed launch mechanism.
- Recovery must not fabricate a missing record or infer a physics certificate.
- Uncertain or partially written evidence leads to review rather than
  automatic deletion, preparation or relaunch.
- Concurrency, capacity, durable claims and output ownership are controlled
  through the shared launch fence.
- Sealed holdouts are not opened or repurposed during training-data preparation.

### 2.4 Configuration and provenance

Case parameters, materials, mesh policies, loads, calibration choices and
acceptance rules must originate from governed configuration and resolved
engineering metadata.

Avoid one-off hard-coded preload values, element/node IDs, temperatures,
stress-seeding areas, contact assumptions or case-specific manual solver edits.

Every reusable sample should retain its originating case, geometry, mesh,
deck, solver, calibration, extraction and validation provenance.

---

## 3. Current physical and material scope

### 3.1 Frozen C01 campaign

The frozen campaign examined in the September 2026 qualification is
`TRM-PDOE-C01`, defined by:

- `config/phase3_production_doe.toml`
- `simulations/staging/phase3_cp8_production_doe/TRM-PDOE-C01/`
- `production_doe_campaign_manifest.json` within that campaign directory.

The observed inventory contains **24 design cases and six sealed holdout
cases**. The holdouts were not inspected during the six-gate checks.

The documented C01 fastener designation is **M10×1.5**.

The verified C01 radial-geometry path couples the two clamped members:

| Radial fraction | Member outer diameter | Clearance-hole diameter |
|---|---:|---:|
| 0 | 30 mm | 11 mm |
| 1 | 36 mm | 12 mm |

Within this path:

- Outer diameter = `30.0 + 6.0 × radial_geometry_fraction`.
- Clearance-hole diameter = `11.0 + radial_geometry_fraction`.
- Both clamped members receive the same radial-geometry values.
- Intermediate design-case coordinates are governed by the frozen manifest.
- The baseline mesh policy is `medium`; the radial-variation policy includes
  `medium_plus_v1`.

Do not confuse *parametric CAD capability* with *physically qualified FEM or
ROM applicability*.

The frozen C01 geometry qualification does not establish end-to-end
certification for M8, M12, all metric pitches, arbitrary thread families,
independent hole/outer-diameter variation or arbitrary joint geometry.

### 3.2 The two-group material rule

The intended bounded material model is:

- Bolt and nut: one common material identity and matching elastic properties.
- Upper and lower clamped members: one common material identity and matching
  elastic properties.
- The fastener group and member group may have different elastic properties.

A matching base material does not require the bolt and nut to have identical
fastener property-class designations. Do not conflate the material identity
with the fastener-class and strength-validation contracts.

The current software path supports two distinct isotropic elastic-property
pairs. The actual production-deck integration test verified:

| Component group | Young's modulus | Poisson's ratio |
|---|---:|---:|
| Bolt and nut | 210,000 MPa | 0.30 |
| Both members | 70,000 MPa | 0.33 |

The test also checked all four actual section assignments, historical
equal-property cards, preparation-field serialization and rejection of
within-group mismatches.

**Qualification boundary:** This establishes the two-group *software transfer
path*. It does not certify mixed-material FEM physics or authorize material
variation within the frozen C01 campaign. The examined frozen policy explicitly
recorded `material_variation_certified = false`.

### 3.3 Other explicitly unqualified variations

The examined C01 policy did not establish certification for independent
member outer-diameter variation, independent clearance-hole variation,
friction variation, external axial-load variation or thread-family variation.

A future expansion must define a new governed envelope and obtain the
appropriate software, geometric, mesh, solver and physical evidence.

---

## 4. Architectural layers — implemented foundations

The present ThreadROM code separates major responsibilities across:

1. **Case and materials:** canonical case definitions, standards,
   material catalogues, case resolution, capability and preflight checks.
2. **Engineering:** analytical bolt, member, thread, joint and
   compression-cone calculations and validation.
3. **Geometry:** parametric fastener, nut and complete-joint assembly creation.
4. **Meshing and classification:** grouped mesh generation, mesh identity,
   physical-surface classification and mesh-policy enforcement.
5. **FEM preparation and solver:** case-derived physical inputs, transfer
   definitions, CalculiX deck generation, contact, boundary conditions,
   bolt-only thermal-eigenstrain preload and nonlinear solution machinery.
6. **Factory and governance:** campaign resolution, preparation,
   launch authorization, durable reservation, calibration, adaptive
   continuation, trial history, evidence recovery and supervisor decisions.
7. **Evidence and validation:** case/run identities, hashes, preparation
   records, calibration and physics verification, and governed dispositions.

These boundaries form a reusable engineering foundation. They do not imply
that every public interface is already stable or that a universal ROM
training/prediction subsystem exists today.

### 4.1 Relevant current implementation locations

Examples of source files involved in the verified factory milestone:

- `src/threadrom/factory/fem_case_preparation.py`
- `src/threadrom/factory/fem_case_definition_bundle.py`
- `src/threadrom/solver/complete_joint_calculix_transfer.py`
- `src/threadrom/factory/fem_production_deck.py`
- `src/threadrom/factory/governed_fem_initial_launch_authorization.py`
- `src/threadrom/factory/governed_fem_initial_live_port.py`
- `src/threadrom/factory/production_doe_launch_fence.py`
- `src/threadrom/factory/production_doe_trial_history.py`

Do not treat this illustrative list as the complete execution dependency
graph. Consult the actual source and tests before changing an interface.

---

## 5. Six-gate factory qualification — CLOSED

**Qualification date:** 2026-09-23.
**Scope:** Governed factory software and the bounded frozen-C01 preparation
path. These gates do not constitute full DOE physics certification.

### Gate 1 — Initial Trial-1 admission and launch safety

**Closed.**

Independent, exact-case and exact-deck authorization was connected to the
Trial-1 runner and the shared durable launch fence. Default launch behaviour
remains conservative. An empty approval-pin registry does not authorize a
launch.

### Gate 2 — New-case port and evidence-safe recovery

**Closed.**

The governed initial live port can distinguish fresh and prepared states,
route an authorized Trial-1 request through the secured runner and recover
existing trial evidence. Uncertain states stop for review.

The existing D-BND-001 Trial-1 and Trial-2 evidence was recovered without
running either trial again.

### Gate 3 — Supervisor lifecycle dry run

**Closed.**

The real supervisor was exercised with mocked preparation and solver
execution. A focused run reported **27 passing tests** across the selected
gate-related suites.

The real D-BND-001 recovery returned `ENGINEERING_REVIEW`, with zero
preparation actions, zero launch actions and no inferred physics certificate.

### Gate 4 — Two-group elastic material software path

**Closed.**

Case resolution/preparation, the immutable definition bundle and the actual
CalculiX material-card emission now carry separate fastener-group and
member-group elastic properties.

A production-deck integration test passed with distinct group properties.
The accompanying selected material-path regression reported **47 passes**.

This gate does not certify material variation across the DOE.

### Gate 5 — Frozen C01 geometry/mesh qualification

**Closed within the bounded C01 scope.**

A read-only verification established:

- 24/24 design cases satisfy the frozen radial-geometry relationship.
- 19/19 case-local preparation records report PASS for the four checked
  geometry and mesh gates.
- All 19 corresponding STEP/mesh pairs matched the recorded SHA256 hashes.
- D-BND-004 Trial-1 and Trial-2 solver preparation correctly referenced
  D-BND-002's verified STEP/mesh evidence.

A00–A03 remain designated for separate governed binding to existing evidence.

**Not established by Gate 5:** M8/M12 physical qualification, certification
of arbitrary geometries, or independent physics acceptance of all cases.

### Gate 6 — Full regression and reconciled frozen inventory

**Closed for the factory software/preparation milestone.**

Full repository regression on 2026-09-23:

`1157 passed in 555.92s (0:09:15)`

The initial inventory script incorrectly treated every trial directory as a
completed run. The subsequent read-only reconciliation distinguished run
manifests from preparation-only directories.

No new FEM solve, holdout access or evidence modification was needed to
resolve that inventory-count discrepancy.

**Six-gate result: 6/6 CLOSED.**

**Still required:** case-specific physics disposition, justified remaining
DOE execution, training-data certification and dataset freeze.

---

## 6. Frozen C01 inventory — observed 2026-09-23

The reconciled *filesystem-level* inventory is:

| Item | Observed count |
|---|---:|
| Frozen design cases | 24 |
| Sealed holdout cases | 6 |
| Cases with case-local preparation records | 19 |
| Cases with a run manifest at a checked trial-directory path | 11 |
| Run manifests at checked trial-directory paths | 16 |
| Trial directories with preparation/deck but no local run manifest | 15 |
| Total inspected trial directories | 31 |
| Design cases awaiting governed existing-evidence binding | 4 |
| Frozen manifest per-case solver-launch flags set to true | 0 |

**Interpretation rules:**

- A trial directory is not a completed FEM run.
- A missing `fem_run_manifest.json` at one expected location does not prove
  that no solver execution or other authoritative evidence exists elsewhere.
- A run manifest is not, by itself, a full physics certificate.
- A frozen manifest's `PLANNED_UNEXECUTED` field may reflect the original
  planning snapshot rather than current execution reality.
- Reconcile final status through the authoritative governed trial-history,
  solver outputs, acceptance records and physics-verification machinery.
- Never regenerate or rerun a case solely to repair an inventory label.

### 6.1 A00–A03

`A00`, `A01`, `A02` and `A03` are marked for governed binding to existing
evidence. They have no case-local solver run manifests in their newly derived
case-run directories.

Their next action is **evidence-binding review**, not an automatic new solve.

### 6.2 D-BND-001

The observed preparation and trial records include two previously existing
trials. Both were recovered through the governed recovery path without a
new FEM execution.

The lifecycle dry run intentionally stopped at engineering review. That
stop must not be relabelled as an independent complete-physics certificate.

### 6.3 D-BND-004

D-BND-004 has no preparation record at its own expected case-local path, but
its two solver-preparation records reference D-BND-002's existing STEP/mesh
artifacts and matching SHA256 values.

That is a documented geometry/mesh reuse route, not evidence that D-BND-004
needs geometry regeneration or another solver run.

### 6.4 Preparation-only Trial-1 directories

The 15 examined directories lacking a local run manifest contained
solver-preparation JSON, its SHA256 sidecar and an `.inp` deck. They did not
contain a conventional run manifest at the checked path.

They must retain their existing identity and contents. Do not conclude
that their underlying case has never been solved elsewhere or that a
replacement trial should be launched.

### 6.5 Historical accepted evidence

Existing certified/accepted case evidence must be reused under its actual
governed provenance and applicability. Previously recorded C01 milestones
include accepted D-INT-012 evidence and completed trial evidence for
D-INT-013 through D-INT-016.

Those historical dispositions are not overwritten by the narrower
trial-directory file inventory above. Reconcile the authoritative
records before reporting any per-case final physics or dataset status.

---

## 7. Current robustness and limits

### 7.1 Parametric

**Substantially implemented at the engineering/software level.**

CAD, analytical engineering, governed case resolution and FEM preparation
support parameter-driven workflows.

**Qualified to date:** the bounded frozen C01 M10×1.5 geometry/preparation
path described above. Do not advertise full metric-fastener FEM validation
solely because the CAD supports more sizes.

### 7.2 Adaptive

**Implemented as governed, bounded adaptation.**

The factory includes reusable calibration, warm-start knowledge, continuation
logic, trial recovery and lifecycle supervision.

It has not been demonstrated to handle every physically valid geometry,
material, friction or load combination without engineering review.

### 7.3 Universal

**A long-term engineering goal, not a current certification claim.**

Universal metric-fastener capability would require separately qualified
cross-size, cross-material, geometry, mesh, solver and physical coverage.

The ROM's applicable domain can never be inferred from the set of CAD
parameters alone; it must be supported by its certified dataset and
independent model evaluation.

### 7.4 Foolproof

**Not a supportable engineering claim.**

The factory has implemented and tested important fail-closed boundaries.
Remaining risks include untested real-world interruptions, unsupported
physical configurations, numerical/contact/mesh failure modes, provenance
gaps and model out-of-domain use.

A correct operational state may be `ENGINEERING_REVIEW`, not automatic
continuation.

---

## 8. Immediate Phase 3 roadmap

The six factory-qualification gates are complete. The next workflow is
**governed evidence disposition and DOE completion**.

### P3-R1 — Preserve the verified source checkpoint

- Review the current working-tree diff and untracked files.
- Separate intended source/tests/documentation from generated reports and
  unrelated or temporary files.
- Preserve all existing FEM and certification evidence without alteration.
- Record the verified test baseline, scope and known limitations.
- Create a reviewed Git commit and push only after the exact file selection
  and expected source state are confirmed.

As observed on 2026-09-23, the working tree contained multiple modified
and untracked files. The full regression passed, but a clean committed
checkpoint was **not established** by that test output.

### P3-R2 — Reconcile and bind existing evidence

- Resolve the authoritative current trial status for every design case.
- Bind A00–A03 to eligible historical evidence under the governed identity
  and provenance rules.
- Preserve D-BND-004's verified geometry/mesh reuse.
- Recover valid realised trials and retain rejected/failed states with
  accurate failure reasons.
- Do not equate file absence at one expected path with lost physics evidence.

### P3-R3 — Establish case-level engineering dispositions

For each case, determine whether the existing evidence satisfies the
required calibration, solver, global-equilibrium, contact, mesh and physics
acceptance checks.

Record verified accepted evidence separately from prepared-only, running,
rejected, incomplete and engineering-review states.

Do not use a previously passing generic unit test as proof of a specific
FEM case's physical validity.

### P3-R4 — Identify and run only genuinely necessary FEM

For each gap:

1. Prove existing certified evidence cannot satisfy the requirement.
2. Establish the exact governed case/trial and requested physics question.
3. Reuse validated warm starts and current preparation where applicable.
4. Obtain independent exact-case launch authorization.
5. Apply the shared capacity/claim/output fence.
6. Run and certify the result; preserve failures and partial evidence.

No blanket solver launch is authorized by this document or by the six-gate
qualification.

### P3-R5 — Freeze the ROM-ready dataset

Before Phase 4:

- Confirm documented parameter-space coverage and remaining limitations.
- Establish consistent features, labels, units and extraction conventions.
- Admit only samples passing the required engineering quality checks.
- Preserve authoritative source hashes and traceable case/run lineage.
- Define training, validation and sealed independent evaluation partitions.
- Declare acceptance criteria before model training; do not adjust them
  retrospectively to fit the outcome.
- Freeze the dataset version, supported domain and exclusions.

Phase 3 is complete only when its governed dataset requirements have been
met. It is not complete merely because all factory software tests pass.

---

## 9. Phase 4 — first ROM and future diversification

**Phase 4 has not started.** The following is the proposed architecture,
not a claim that these ROM interfaces are already implemented.

### 9.1 Protect the factory/ROM boundary

The first ROM should consume a versioned, **certified engineering dataset
contract** rather than being tightly coupled to:

- CalculiX `.inp`, `.frd`, `.dat` or `.rout` formats;
- C01-specific campaign paths;
- mesh node/element numbering;
- a particular calibration-trial sequence; or
- direct access to mutable FEM staging folders.

Proposed data flow:

`Governed case → analytical/CAD/FEM factory → certified engineering sample
→ ROM-specific target extraction → training/evaluation → registered model
→ guarded prediction`

### 9.2 Proposed canonical engineering sample

A versioned sample should include:

- Canonical case and resolved parameter identities.
- Geometry, materials, interfaces, loads, boundary conditions and units.
- Applicable configuration and physics-model versions.
- Certified source evidence and all relevant hashes.
- Solver and extraction provenance.
- Explicit engineering-acceptance and dataset-admission status.
- Target values and extraction definitions, with validity metadata.
- Dataset partition identity and leakage/independence safeguards.

This is a Phase-4 design contract to implement and test, not an assertion
that the existing data schema already contains every field above.

### 9.3 Proposed independent ROM specifications

Each ROM should declare its own:

- Prediction target and target-extraction method.
- Input features, units and preprocessing.
- Supported physical and parametric domain.
- Permitted model family and model version.
- Training-data and evaluation-data requirements.
- Predeclared accuracy, physical-consistency and uncertainty criteria.
- Out-of-domain rejection or escalation behaviour.
- Training dataset identity and independent evaluation certificate.

Do not force every prediction target into one model architecture.

### 9.4 Diversification tiers

**Tier 1 — Same certified fastener-joint cases, different outputs**

Potential targets include clamp force, joint stiffness, load sharing,
selected displacements, contact quantities and stress responses.

A single certified FEM case may supply several legitimate labels if
each extraction and target-specific acceptance rule is verified.

**Tier 2 — Expanded metric-fastener/joint domain**

Potential future axes include fastener diameter/pitch/length, grip and
radial geometry, friction, material groups and loading variations.

Each expansion requires its own DOE coverage, solver/physical
qualification and model applicability checks. The existing frozen C01
dataset does not establish generalization to these configurations.

**Tier 3 — Different engineering physics**

Modal, thermal, thermomechanical, fatigue, fluid or other multiphysics
ROMs may reuse selected orchestration, provenance, data and evaluation
infrastructure.

Their governing equations, FEM/solver interfaces, target definitions and
physics-certification rules require domain-specific implementations.

### 9.5 Spatial-field ROM caution

Scalar output ROMs can often consume mesh-independent case-level labels.

Full stress, displacement or contact-field ROMs need a defensible strategy
for changing geometry, changing mesh density and variable node counts.
Possible future approaches include canonical spatial sampling,
geometry-aware representations or other validated reductions.

No mesh-independent full-field prediction capability is certified here.

### 9.6 Independent ANSYS cross-check

Before commencing or approving the first Phase-4 ROM work, revisit the
planned independent ANSYS 2022 R2 comparison at the governed transition
point. Define the exact physical configuration, matched loads/constraints,
mesh considerations and comparison criteria.

Do not describe this cross-check as completed until its actual evidence
and disposition have been recorded.

---

## 10. Operating procedure for future ThreadROM work

### 10.1 Before changing code

1. Read this document and the current root README.
2. Inspect the relevant current source and authoritative campaign records.
3. Check the Git branch, current diff and untracked files.
4. Determine whether a certified implementation or evidence path already
   exists; prefer reuse over parallel replacement.
5. State the exact target, acceptance condition and remaining-step countdown.

### 10.2 During implementation

- Use one bounded, reviewable action at a time.
- Prefer exact Windows PowerShell blocks that make validated changes.
- Avoid asking for repetitive broad repository archaeology once the relevant
  contract has been established.
- Use assumption-checked patches; do not overwrite unrelated local changes.
- Verify the result of each action before proceeding.
- Do not launch a duplicate FEM or edit historical evidence.
- Do not silently turn an engineering-review state into a success state.

### 10.3 When reporting progress

Always distinguish:

1. Implemented software capability.
2. Passing software/integration tests.
3. Prepared geometry/mesh/deck evidence.
4. Actual executed solver evidence.
5. Case-level accepted physical evidence.
6. Dataset certification.
7. ROM training and independent model validation.

A milestone in one category does not automatically close another.

### 10.4 Source-of-truth hierarchy

For a factual case-specific claim, prefer the current governed case,
certification and trial-history records and their verified artifacts.

Use this document as a navigation and handover aid. If it conflicts with
newly verified source/evidence, investigate the difference and update
this document with a dated correction.

---

## 11. Current milestone summary

| Area | Status as of 2026-09-23 |
|---|---|
| Phase 1 / Phase 2 reusable engineering foundations | Existing project foundation |
| Phase 3 bounded factory qualification | **6/6 gates closed** |
| Latest full repository regression | **1,157 passed** |
| Frozen C01 geometry/preparation path | Qualified within documented scope |
| Two-group material transfer software path | Implemented and tested |
| Universal metric-fastener FEM qualification | Not established |
| Complete case-level DOE physics certification | Pending |
| Governed existing-evidence binding | Pending for A00–A03 |
| ROM-ready dataset freeze | Pending |
| First ROM | Not started; Phase 4 |
| Future diversified ROM family | Architectural direction, not implemented product claim |

**Immediate next milestone:** Preserve the verified factory source checkpoint,
then reconcile and certify existing DOE evidence before authorizing any
additional case-specific FEM work.

**Core principle:** Reuse each expensive, properly validated FEM result for
every legitimate downstream ROM purpose its physical evidence supports.
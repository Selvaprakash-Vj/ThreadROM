# ThreadROM — Engineering Evidence and ROM Dataset Guide

**Initial version:** 2026-09-23
**Current phase:** Phase 3 — governed DOE evidence completion
**Purpose:** Explain how existing engineering evidence is located, verified, reused and eventually admitted to a versioned ROM dataset.

> Start with [CURRENT_STATE.md](CURRENT_STATE.md) for the latest
> project checkpoint. This guide defines evidence-handling principles,
> review procedures and proposed dataset requirements.
>
> It does not create a physics certificate, certify a case, authorize
> a solver run or claim that the Phase-4 dataset interface already exists.

---

## 1. Essential references and source of truth

| Question | Starting reference |
|---|---|
| Where are we now? | [Current State](CURRENT_STATE.md) |
| How do we operate and recover the factory? | [Operating Runbook](OPERATING_RUNBOOK.md) |
| What scope and qualifications have been established? | [Phase-3 Engineering Reference](THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md) |
| Which file owns a function or references another module? | [Repository Atlas](THREADROM_REPOSITORY_ATLAS.md) |
| What does the frozen DOE configuration declare? | [C01 DOE configuration](../config/phase3_production_doe.toml) |
| How are existing trials represented and recovered? | [Trial-history implementation](../src/threadrom/factory/production_doe_trial_history.py) |
| How is case preparation represented? | [FEM case preparation](../src/threadrom/factory/fem_case_preparation.py) |
| How are resolved inputs transferred toward FEM? | [FEM definition bundle](../src/threadrom/factory/fem_case_definition_bundle.py) |
| Where is shared launch ownership enforced? | [Production DOE launch fence](../src/threadrom/factory/production_doe_launch_fence.py) |

For a specific case, its authoritative governed records and verified
artifacts take precedence over a historical progress summary.

This document must never replace an actual record schema, status enum,
hash verification or physics-verification implementation. Inspect those
in the current repository before performing a state-changing operation.

---

## 2. Evidence is not a single status

A design case can have several kinds of evidence at once. These
questions must be answered separately:

1. Is the canonical case defined and within the governed scope?
2. Was its resolved engineering configuration verified?
3. Are the CAD and mesh artifacts present and correctly identified?
4. Was a solver deck prepared and verified?
5. Was the intended solver trial actually executed?
6. Did the numerical solution meet its required solver criteria?
7. Did the calibration meet its own acceptance criteria?
8. Did the result pass the required physical engineering checks?
9. Is its target quantity suitable for a particular ROM?
10. Has it been admitted to a specific frozen dataset and partition?

Passing an earlier question does not imply passing a later one.

In particular:

**A generated deck is not an executed FEM trial. An executed trial is
not automatically converged. Solver convergence is not automatically
physics acceptance. Physics acceptance is not automatically ROM
dataset admission.**

---

## 3. Evidence-state vocabulary

The following terms are a documentation-level vocabulary. They are
not a claim that the current software implements an identically
named status enum or one linear state machine.

| Evidence state | What has been established | What has NOT been established solely by that state |
|---|---|---|
| DEFINED | A canonical engineering case exists. | CAD, FEM execution or physics acceptance. |
| RESOLVED | Its relevant parameters and configuration have been resolved. | Successful geometry, mesh or solver preparation. |
| GEOMETRY_PREPARED | Geometry artifacts exist with their recorded preparation provenance. | Valid mesh, converged FEM or accepted physics. |
| MESH_PREPARED | Mesh artifacts and applicable preparation checks exist. | Solver execution or accepted physical behaviour. |
| DECK_PREPARED | A governed FEM input deck and preparation evidence exist. | That the solver was launched. |
| EXECUTING | An identified trial has an active execution state. | Completion, convergence or physical acceptance. |
| EXECUTION_COMPLETE | The required execution-completion evidence has been verified. | Calibration acceptance or full physics certification. |
| CALIBRATION_ACCEPTED | The applicable calibration checks passed. | Independent acceptance of all required joint physics. |
| PHYSICS_ACCEPTED | The defined case-specific engineering validation requirements passed. | Suitability for every possible ROM target. |
| DATASET_ADMITTED | A particular sample satisfies a particular dataset's admission contract. | Validity outside that dataset or model domain. |
| ENGINEERING_REVIEW | Evidence or its interpretation needs a governed review. | An automatic failure, success or reason to rerun. |
| REJECTED_OR_FAILED | An applicable gate failed with a recorded reason. | That all artifacts are worthless or may be deleted. |

A case may possess multiple trials with different outcomes. Preserve
their individual provenance and dispositions. A later accepted trial
does not erase the history or measured information of an earlier one.

---

## 4. Evidence identity and provenance

Before comparing, binding, replacing or admitting engineering data,
establish the precise identities relevant to the operation.

### 4.1 Identity checklist

| Scope | Information to verify |
|---|---|
| Campaign | Campaign ID, governing configuration and frozen manifest identity. |
| Design | Design-case identity, parameter coordinates and membership. |
| Resolved case | Canonical engineering inputs, applicable standards, materials, geometry, loads and conditions. |
| Geometry | Artifact source, geometry identity, assembly registration and applicable geometry checks. |
| Mesh | Mesh identity, policy, classification, checks and artifact provenance. |
| FEM preparation | Definition bundle, generated deck, material/section assignments, contact and boundary-condition provenance. |
| Trial | Exact case-run and calibration-trial identity, trial order and previous attempts. |
| Execution | Solver and output identity, execution record, completion and numerical evidence. |
| Validation | Calibration result, physics checks, limits and authoritative disposition. |
| Dataset | Target definition, accepted sample identity, dataset version and partition. |

These are verification categories, not asserted JSON field names.
Use the actual implementation and authoritative record schema to
determine the relevant fields for each operation.

### 4.2 Hashes and equivalence

An artifact hash can demonstrate that inspected bytes match the bytes
recorded in an authoritative source. It does not independently prove
that the underlying physical model is appropriate.

Two cases may legitimately reuse identical geometry or mesh while
differing in loads, material properties, friction or requested outputs.

Therefore:

- Artifact equality does not imply complete physical-case equality.
- Matching nominal bolt designation does not establish equivalent FEM.
- Two accepted runs are not interchangeable merely because their
  output quantities look similar.
- Reuse requires evidence supporting the exact intended engineering
  question, quantities and applicability conditions.
- If identity or applicability cannot be established, stop for review.

---

## 5. Current frozen C01 evidence boundary

The six bounded factory-qualification gates are closed. Full DOE
case-level physics certification and dataset freeze remain pending.

The current frozen production DOE is `TRM-PDOE-C01`, with an M10x1.5
fastener designation and the documented bounded parameter envelope.

Its configuration and governing exclusions are recorded in
[the frozen DOE policy](../config/phase3_production_doe.toml).

The qualified C01 radial-geometry preparation path uses coupled
values for both clamped members:

| Radial-geometry endpoint | Member outer diameter | Clearance-hole diameter |
|---|---:|---:|
| Lower | 30 mm | 11 mm |
| Upper | 36 mm | 12 mm |

This preparation qualification is not proof that every resulting
physical FEM trial is accepted.

The two-group material software path supports one bolt/nut material
group and one upper/lower-member material group. The groups may differ
in elastic properties, but software deck-transfer verification alone
does not certify mixed-material FEM physics or enlarge the frozen
C01 material policy.

Do not use C01 evidence to claim arbitrary M8/M12, metric-fastener,
friction, material or load-domain ROM accuracy.

---

## 6. Dated C01 filesystem inventory

**Observation date:** 2026-09-23.

The final reported read-only inventory for the six-gate milestone
contained:

| Observed item | Count |
|---|---:|
| Frozen design cases | 24 |
| Sealed holdout cases | 6 |
| Cases with case-local preparation records | 19 |
| Cases with a run manifest at an inspected trial path | 11 |
| Run manifests at inspected trial paths | 16 |
| Trial directories without a local run manifest | 15 |
| Total inspected trial directories | 31 |
| A00–A03 cases awaiting existing-evidence binding | 4 |
| Frozen manifest design-case launch flags set to true | 0 |

This is a **filesystem inventory**, not a case-by-case physics
certificate, current live-job report or ROM training-sample count.

### 6.1 The preparation-only directory distinction

The 15 specifically examined directories without a conventional
local run manifest contained:

- A production DOE solver-preparation record.
- The record's SHA256 sidecar.
- A generated `.inp` solver input deck.

Those observations establish a local prepared state. They do not
by themselves establish solver execution, non-execution elsewhere,
completion, failure or a requirement for another solve.

The earlier count of 31 *run manifests* was corrected: the observed
31 items were trial directories, of which 16 had local run manifests
at the checked paths.

No historical record should be created or rewritten merely to
make an inventory count match an earlier incorrect report.

### 6.2 Frozen planning records versus later evidence

A frozen campaign manifest may preserve a planning-time execution
state. A planning label must not override a later authoritative
trial-history record or accepted engineering disposition.

Conversely, a historical statement that a case was completed must
not be promoted to a new certificate without locating the governing
supporting evidence.

Reconcile the actual records and their chronology before reporting
a final status.

---

## 7. Case-specific reuse and review instructions

### A00–A03: governed binding candidates

These four design cases were designated for binding to existing
evidence. The absence of new case-local solver directories is
not a gap that automatically requires four new FEM runs.

For each binding, verify:

1. The source evidence and its original case/trial identity.
2. The required physical configuration and applicability.
3. The target design case's resolved parameters.
4. Any permitted equivalence or reuse rule.
5. The source evidence's actual certification status.
6. The binding procedure and resulting governed provenance.

A valid binding must remain traceable to the original physical
evidence. Do not silently copy artifacts and present them as a
new execution.

### D-BND-001: preserved historical trials

Existing Trial-1 and Trial-2 evidence was previously recovered
without rerunning either trial.

The supervisor lifecycle dry run returned `ENGINEERING_REVIEW`
without launching FEM or fabricating a physics certificate.

Use the authoritative case-level records for its actual engineering
disposition rather than interpreting the dry-run response as
independent full-physics acceptance or failure.

### D-BND-004: verified geometry/mesh reuse

The inspected solver-preparation records for its two trials
referenced the existing D-BND-002 STEP and mesh artifacts with
matching recorded hashes.

This verified geometry/mesh reuse is not a reason to regenerate
geometry, remesh or rerun the solver.

Any full physical-case reuse must still be justified separately.

### Interior-case historical evidence

Previously recorded C01 milestones include completed and accepted
trial evidence for interior cases. Preserve the actual historical
records and reconcile their case-specific physics dispositions.

Do not let a narrow filesystem scan label previously completed
case evidence as missing or authorize duplicate simulation.

---

## 8. Read-only evidence reconciliation procedure

**Operation class: R0.**

Before undertaking new FEM work or assigning a case's final status:

1. Confirm the current campaign configuration and intended design case.
2. Establish the canonical resolved-case and case-run identities.
3. Review the governed trial-history records for the specific case.
4. Identify every relevant existing trial and preparation artifact.
5. Verify authoritative hashes and evidence references where applicable.
6. Distinguish prepared-only, executing, execution-complete,
   calibration-accepted and physics-accepted evidence.
7. Resolve historical planning snapshots against more recent records.
8. Identify uncertain, missing or conflicting evidence explicitly.
9. Record the required next action: reuse, binding review, physics
   verification, recovery review or justified new-solve request.

**Stop condition:** If case identity, evidence ownership or a required
physical disposition cannot be established, retain the uncertainty
and request engineering review. Do not auto-promote or auto-relaunch.

The exact record-reading or case-specific verification commands
must be taken from the current supported implementation, not
invented from filename patterns.

See the [Operating Runbook](OPERATING_RUNBOOK.md) for safe process and
trial-output inspection procedures.

---

## 9. What constitutes an engineering-accepted FEM sample?

The authoritative case-specific physics-verification rules determine
acceptance. The following table describes categories to check; it is
not an assertion that one generic threshold applies to every case.

| Verification category | Evidence or question to resolve |
|---|---|
| Canonical inputs | Are the resolved parameters and material groups correct? |
| Geometry | Does the intended assembly, registration and engagement match the case? |
| Mesh | Does the mesh satisfy the applicable quality and adequacy rules? |
| Connections and contacts | Are the physical interfaces and contact states valid? |
| Boundary conditions | Are supports and guidance constraints physically appropriate? |
| Loading and preload | Were loads and pretension applied with correct magnitude, distribution and convention? |
| Solver behaviour | Are completion, accepted increments, convergence and relevant warnings satisfactorily resolved? |
| Global equilibrium | Are required force/moment balances and reactions physically consistent? |
| Clamp force | Does the measured preload/calibration response meet its governed criterion? |
| Physical response | Are displacement, stiffness, stress and contact quantities credible under the defined acceptance rules? |
| Analytical comparison | Are deviations from the applicable analytical reference understood and acceptable? |
| Provenance | Can the accepted quantities be traced to the exact intended case, mesh, deck, run and verification record? |

The actual supported validation set may differ with the case and
target quantity. Determine the applicable checks and predefined
acceptance criteria from the current governed implementation.

Do not invent an acceptance tolerance, silently omit a failed gate
or retroactively widen a threshold to admit a desired sample.

An accepted calibration magnitude is not a substitute for the
remaining applicable physics checks.

---

## 10. When is an additional FEM solve genuinely necessary?

A new solve is a last resort after evidence reconciliation.

For each proposed case/trial, document:

| Decision question | Required outcome before proceeding |
|---|---|
| What exact engineering quantity is missing? | A specific, justified evidence requirement. |
| Is there already an accepted equivalent result? | Existing evidence and permitted bindings reviewed. |
| Is an earlier trial still executing or recoverable? | Current process, trial history and ownership reconciled. |
| Is an apparently missing file only a path/inventory issue? | Expected and authoritative locations checked. |
| Would a different extraction from an existing run suffice? | Available output fields and extraction requirements reviewed. |
| Is the case inside the currently governed physical envelope? | Exact policy and configuration checked. |
| Are preparation and calibration warm starts reusable? | Their provenance and applicability verified. |
| Is launch independently authorized? | Applicable exact-case/trial/deck authorization established. |
| Is capacity and output ownership safe? | Shared launch fence and reservation requirements satisfied. |

A requested training-sample count alone does not justify blindly
launching enough FEM runs to fill that count.

A failed or rejected prior run may inform the next governed
calibration or continuation decision, but must remain recorded.

No launch is authorized by this guide.

---

## 11. ROM dataset admission: a separate governed decision

**Status:** The following describes the required future Phase-3
dataset-freeze/Phase-4 interface. It is a design requirement, not
a claim that every item already exists in a production dataset schema.

An engineering-accepted run may provide one or more candidate
training labels. Each specific ROM must establish whether those
labels are suitable for its target and evaluation protocol.

### 11.1 Proposed canonical sample contract

Every admitted sample should provide or reference:

| Category | Proposed content |
|---|---|
| Dataset identity | Dataset name, immutable version and creation provenance. |
| Sample identity | Stable sample ID with source case and trial references. |
| Engineering inputs | Canonical geometry, materials, loads, interfaces and units. |
| Target definition | Physical quantity, sign convention, units and extraction rule. |
| Source artifacts | Exact accepted FEM evidence and relevant immutable hashes. |
| Validation | Governing physics acceptance record and target-specific quality checks. |
| Applicability | Supported parameter and physical-model domain. |
| Partition | Training, validation or independent evaluation assignment. |
| Exclusions | Missing quantities, failed checks and reasons a sample was not admitted. |
| Reproducibility | Versions of relevant extraction and preprocessing implementations. |

**Do not create these as arbitrary new JSON fields inside historical
certificates.** Implement the canonical contract through an explicitly
versioned, tested schema when the dataset workflow is designed.

### 11.2 Multiple ROMs from one FEM result

An accepted FEM result may support several downstream prediction
targets if its stored outputs and validation evidence are adequate.

For example, the same simulation might be a candidate source for:

- Clamp-force response.
- Joint stiffness or load sharing.
- Selected global displacements.
- Specified contact quantities.
- Selected stress responses.

Each target needs a precise extraction rule and its own acceptance
requirements.

A sample admitted for scalar clamp-force prediction is not
automatically admitted for a local contact-stress-field ROM.

### 11.3 Units and conventions

A dataset contract must explicitly define:

- Input and output units.
- Force and displacement sign conventions.
- Coordinate systems and component orientation.
- Stress/strain definitions and spatial sampling locations.
- Preload, external-load and response-time interpretation.
- Missing-data and invalid-output representation.

Do not train on visually similar values extracted using different
conventions without a verified transformation.

### 11.4 Field-output warning

A scalar output may be independent of mesh node numbering.

A full spatial stress, displacement or contact-field target requires
a defensible representation across changing geometries and meshes.

Canonical sampling, interpolation or other geometry-aware techniques
must be designed and validated for the specific field-ROM purpose.

The parametric CAD and mesh generator do not by themselves establish
a mesh-independent field-ROM target.

---

## 12. Dataset coverage, independence and sealed holdouts

Before dataset freeze, establish:

1. The exact intended ROM input domain and excluded configurations.
2. Which physically accepted design cases cover that domain.
3. How parameter-space boundaries, interactions and sparse regions
   are represented.
4. Whether accepted samples provide sufficient variation for the
   selected target and model family.
5. The independence of training, validation and evaluation examples.
6. The provenance of shared geometry, reused meshes, repeated
   calibrations and multiple outputs from the same underlying run.
7. The predefined evaluation metrics and acceptance limits.
8. The appropriate response to unsupported/out-of-domain inputs.

**Do not unseal the six frozen C01 holdout cases for exploratory
training, feature engineering, hyperparameter tuning or routine
debugging.**

Closely related trials of the same physical case must not be
distributed across training and independent evaluation in a way
that leaks the same underlying solution into both partitions.

If existing-evidence binding creates multiple case references to
one underlying FEM result, the dataset must preserve that shared
lineage. Duplicate references are not independent observations.

The appropriate independence rule depends on the model target
and intended generalization claim; document it before partitioning.

---

## 13. Proposed immutable dataset freeze record

**Status: to be designed and implemented before declaring Phase 3
ROM-ready.**

A dataset release should identify:

- The frozen engineering scope and allowed feature domain.
- The complete admitted-sample manifest.
- Each source evidence identity and verification status.
- Rejected/excluded candidate records and their reasons.
- Dataset schema, extraction and preprocessing versions.
- Stable content hashes for the release and referenced data.
- Explicit training/validation/evaluation partitions.
- Target-specific validity and missing-data handling.
- Predeclared performance/physical acceptance criteria.
- Known limitations and supported application claims.

After freezing a dataset release, correcting a sample or changing
its extraction must produce a new version or an explicitly governed
amendment. Do not silently mutate a dataset used for a published
model evaluation.

The existence of a frozen dataset does not guarantee that a trained
ROM will meet its accuracy targets. Model validation remains a
separate Phase-4 milestone.

---

## 14. Phase-3 evidence disposition worksheet

Use this checklist for each design case. It is a *review worksheet*,
not a new authoritative software record or permission to alter
historical evidence.

| Review field | Entry |
|---|---|
| Campaign and design-case identity | To be verified |
| Current resolved-case identity | To be verified |
| Existing case/trial records located | To be verified |
| Geometry/mesh evidence and provenance | To be verified |
| Existing solver executions | To be verified |
| Calibration dispositions | To be verified |
| Case-level physics dispositions | To be verified |
| Applicable accepted quantities | To be verified |
| Valid evidence-binding opportunities | To be verified |
| Remaining evidence gap, if any | To be justified |
| Need for another FEM solve | Not presumed |
| Exact next governed action | To be determined |

Do not fill this worksheet from filename patterns or a frozen
planning-state field alone.

For future efficiency, the factory should ultimately generate a
case-level disposition report from the authoritative records,
including uncertainties and evidence references, rather than
requiring manual reconstruction of all trial histories.

Such a generated report must be tested and must not silently
promote a trial to an accepted state.

---

## 15. Phase-3-to-Phase-4 acceptance boundary

The first ROM may begin only after the applicable Phase-3 dataset
requirements have been met and the selected bounded scope is
documented.

The transition should establish:

- A reviewed and reproducible engineering source checkpoint.
- Reconciled historical trial evidence and governed case dispositions.
- Completion of the genuinely necessary DOE work.
- Certified candidate samples for the intended prediction targets.
- A versioned dataset with explicit scope, lineage and exclusions.
- Protected independent evaluation data and predeclared criteria.
- A documented plan for the independent ANSYS 2022 R2 cross-check.

Do not claim that all metric-fastener configurations have been
physically validated when only the bounded DOE supports the model.

ROM development begins in **Phase 4**. Future model-family
diversification should reuse certified engineering evidence through
a stable, model-independent dataset interface, not depend directly
on temporary C01 solver-preparation folders.

---

## 16. Document maintenance and known open work

Update this guide when:

- An authoritative evidence schema or disposition contract changes.
- Existing DOE history is formally reconciled.
- A00–A03 receive verified evidence-binding dispositions.
- New cases obtain engineering acceptance or are rejected.
- A governed dataset-admission system is implemented.
- A dataset version is frozen or a Phase-4 ROM target is defined.

**Open implementation/documentation work:**

- Enumerate actual evidence-record schemas and their current owners
  directly from source and tests.
- Establish a verified case-by-case current disposition inventory.
- Define and test the canonical dataset-admission contract.
- Define the first ROM target, extraction, partitions and accuracy
  criteria before model training.
- Freeze and certify the dataset within its documented applicability.

Until those steps are completed, this guide provides an evidence
handling and design framework—not a declaration of dataset readiness.

**Operating principle:** Preserve what the engineering evidence
actually establishes, reuse it only where applicable, and spend new
FEM compute only when a specific unmet requirement justifies it.
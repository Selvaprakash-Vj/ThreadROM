# ThreadROM — Engineering Decisions and Design Rationale

**Initial record date:** 2026-09-23
**Purpose:** Preserve important ThreadROM decisions, their engineering
rationale, consequences and conditions for reconsideration.

> This is a decision-history and design-governance document, not
> a solver authorization, physics certificate or current runtime report.
>
> Historical decisions are recorded here as understood at this
> checkpoint. Their original decision dates are not asserted unless
> established by an authoritative dated source. Consult the current
> repository and governed evidence before taking operational action.

---

## 1. How to use this decision record

Start with [CURRENT_STATE.md](CURRENT_STATE.md) to determine the
latest verified checkpoint and immediate next work.

| Need | Reference |
|---|---|
| Latest project checkpoint | [Current State](CURRENT_STATE.md) |
| Scope, qualification and roadmap | [Phase-3 Engineering Reference](THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md) |
| File ownership and dependencies | [Repository Atlas](THREADROM_REPOSITORY_ATLAS.md) |
| Operational controls | [Operating Runbook](OPERATING_RUNBOOK.md) |
| Evidence and dataset admission | [Evidence and Dataset Guide](EVIDENCE_AND_DATASET_GUIDE.md) |
| Subsystem and interface design | [Architecture and Interfaces](ARCHITECTURE_AND_INTERFACES.md) |
| Frozen C01 configuration | [Phase-3 DOE policy](../config/phase3_production_doe.toml) |

The repository and its governing records remain authoritative for
actual implementation, accepted case evidence and active policy.
This document explains intent and rationale; it does not replace
source inspection or independent verification.

### Decision-status terminology

- **Established:** Adopted project direction or implemented design
  boundary documented at this checkpoint.
- **Bounded qualification:** Verified only for an explicitly stated
  software, configuration or physical scope.
- **Proposed:** Design direction that still requires implementation,
  verification or a later explicit engineering decision.
- **Revisit:** Conditions under which changing the decision may be
  justified. A revisit condition is not permission to bypass the
  current rule.

---

## 2. Established engineering and governance decisions

### DEC-001 — Complete a bounded DOE before the first ROM

**Status:** Established project direction.
**Recorded:** 2026-09-23; original decision date not asserted.

**Decision**

Complete Phase 3 within its explicitly documented fastener,
joint, material and load envelope before starting the first
ROM in Phase 4.

Universal metric-fastener qualification is a longer-term
expansion goal, not a prerequisite for every bounded ROM.

**Rationale**

An indefinitely expanding FEM scope would delay the first
testable ROM. A bounded, certified dataset permits an honest,
reproducible initial model and a controlled expansion path.

**Consequences**

- Phase 3 must finish case-level evidence disposition and
  the required dataset freeze before Phase 4 training.
- Every released model must state its supported applicability.
- Parametric CAD capability does not enlarge ROM validity.
- Future diversified DOE campaigns require their own criteria.

**Revisit when**

The intended first-ROM prediction target or documented
engineering envelope changes through a governed project
decision, with corresponding data and evaluation requirements.

**References:** [Engineering Reference](THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md),
[Evidence and Dataset Guide](EVIDENCE_AND_DATASET_GUIDE.md).

---

### DEC-002 — Keep the two clamped members in one material group

**Status:** Established bounded material rule.
**Recorded:** 2026-09-23; original decision date not asserted.

**Decision**

The upper and lower clamped members use one common material
identity and matching elastic properties for the current
ThreadROM material model.

The bolt and nut form a separate common material group.
The fastener group and member group may differ from each other.

**Rationale**

This preserves a manageable, internally consistent joint model
while allowing the meaningful distinction between fastener
material and clamped-member material.

**Consequences**

- Within-group material mismatches must not pass unnoticed.
- The two-group transfer must reach the actual FEM material
  assignments, not remain only in a case-definition object.
- Matching fastener material identity must not be confused
  with a separate fastener property-class/strength contract.
- Independent upper/lower-member material variation is outside
  the current adopted rule.

**Qualification boundary**

The two-group elastic-property software transfer was exercised
through a generated production deck. That does not, by itself,
certify mixed-material physical FEM results or authorize frozen
C01 material variation.

**Revisit when**

A future engineering use case requires dissimilar clamped-member
materials and a new explicitly governed case, physical model,
validation and DOE envelope is approved.

**References:** [Architecture and Interfaces](ARCHITECTURE_AND_INTERFACES.md),
[Engineering Reference](THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md).

---

### DEC-003 — Use governed configuration, not per-run hard-coding

**Status:** Established engineering rule.
**Recorded:** 2026-09-23; original decision date not asserted.

**Decision**

Derive case geometry, loads, material properties, mesh and FEM
transfer inputs from governed configuration and resolved
engineering metadata.

Do not use ad hoc per-case edits to preload, node/element IDs,
contact definitions, stress-seeding areas or solver deck cards.

**Rationale**

One-off overrides obscure physical identity, hinder automated
DOE execution and make accepted results difficult to reproduce.

**Consequences**

- New variation axes require explicit schema/policy handling.
- Derived assumptions must be validated against the intended case.
- Changes crossing analytical, CAD and FEM boundaries require
  focused and integration-level verification.
- The supported envelope must remain explicit.

**Revisit when**

A documented physical requirement demands a new configuration
capability. Implement that capability through the governed
contract and corresponding tests rather than a local bypass.

**References:** [Architecture and Interfaces](ARCHITECTURE_AND_INTERFACES.md),
[Repository Atlas](THREADROM_REPOSITORY_ATLAS.md).

---

### DEC-004 — Preserve and reuse historical FEM evidence

**Status:** Established operational and data-governance rule.
**Recorded:** 2026-09-23; original decision date not asserted.

**Decision**

Before launching FEM, locate and evaluate existing evidence.
Reuse it where the governing physical equivalence, acceptance
and provenance requirements permit.

Preserve completed, failed, rejected, incomplete and uncertain
realised trials with their actual dispositions.

**Rationale**

Historical simulations embody expensive compute and engineering
information. Repeating them because of a path mismatch or
incomplete inventory wastes resources and risks conflicting
evidence histories.

**Consequences**

- Missing a manifest at one conventional path does not prove
  that the case was never solved elsewhere.
- Existing accepted results must not be regenerated merely
  to populate a newer case-local directory.
- Duplicate references to one FEM result are not independent
  training observations.
- Rejected or failed trials remain recorded with reasons.

**Revisit when**

Authoritative evidence establishes that no existing accepted,
equivalent and recoverable result satisfies a particular new
engineering requirement.

A revisit permits consideration of a governed new-solve
request; it is not itself solver authorization.

**References:** [Evidence and Dataset Guide](EVIDENCE_AND_DATASET_GUIDE.md),
[Operating Runbook](OPERATING_RUNBOOK.md).

---

### DEC-005 — Keep solver execution behind independent admission

**Status:** Established, tested factory safety boundary.
**Recorded:** 2026-09-23; original decision date not asserted.

**Decision**

A new Trial-1 solver execution requires the applicable exact-case
independent authorization and shared durable launch fence.

Preparation, supervisor intent, a manifest entry and a passing
test suite must not independently grant launch permission.

**Rationale**

Nonlinear FEM can be expensive and produce conflicting outputs
when duplicate or unauthorized jobs are launched. Permission,
resource ownership and engineering readiness are separate checks.

**Consequences**

- An empty approval registry cannot authorize a launch.
- A proposed continuation must satisfy its applicable governed
  continuation/admission policy.
- Existing process, output ownership and capacity are checked
  before execution.
- Uncertain states must fail closed for review.

**Revisit when**

A new admission policy is deliberately designed, separately
verified and shown to preserve independent authorization,
durable ownership and non-duplication guarantees.

**References:** [Operating Runbook](OPERATING_RUNBOOK.md),
[Architecture and Interfaces](ARCHITECTURE_AND_INTERFACES.md).

---

### DEC-006 — Separate execution, calibration, physics acceptance
and dataset admission

**Status:** Established evidence-governance principle.
**Recorded:** 2026-09-23; original decision date not asserted.

**Decision**

Treat prepared geometry, prepared deck, actual execution,
numerical completion, calibration acceptance, engineering
physics acceptance and ROM dataset admission as distinct
evidence questions.

**Rationale**

A completed calculation can still be physically inappropriate.
A case accepted for one engineering quantity may be unsuitable
for another ROM prediction target.

**Consequences**

- Do not fabricate acceptance from adjacent records.
- Every admitted target must have appropriate extraction,
  engineering verification, units and provenance.
- The future dataset contract must preserve exclusions,
  uncertainty and rejected/failed evidence.
- An engineering-review state is not a synonym for failure.

**Revisit when**

A future evidence schema consolidates record storage while
preserving these distinct meanings and their independently
verifiable acceptance criteria.

**References:** [Evidence and Dataset Guide](EVIDENCE_AND_DATASET_GUIDE.md).

---

### DEC-007 — Keep uncertain recovery fail-closed

**Status:** Established factory operating principle.
**Recorded:** 2026-09-23; original decision date not asserted.

**Decision**

When historical execution state, artifact ownership, provenance
or physical acceptance is uncertain, stop for engineering review.

Do not automatically relaunch, clear claims, delete output
folders or promote results to an accepted state.

**Rationale**

Conservative recovery protects evidence integrity and avoids
silent duplicate compute or incorrect certification.

**Consequences**

- Recovery may intentionally end with `ENGINEERING_REVIEW`.
- Solver-process absence does not establish successful completion.
- Preparation-only directories are not counted as completed runs.
- Interruption handling must preserve partial evidence and
  the original trial identity.

**Revisit when**

A specific uncertain state gains a tested, provenance-preserving
and governed automatic resolution path. Other uncertain states
remain review-required.

**References:** [Operating Runbook](OPERATING_RUNBOOK.md),
[Evidence and Dataset Guide](EVIDENCE_AND_DATASET_GUIDE.md).

---

### DEC-008 — Treat frozen C01 scope as an explicit boundary

**Status:** Established bounded qualification.
**Recorded:** 2026-09-23; original decision date not asserted.

**Decision**

The six-gate factory milestone qualifies the documented frozen
C01 M10x1.5 software/preparation path within its stated scope.

Do not reinterpret that milestone as universal metric-fastener
FEM qualification or complete physical acceptance of every
DOE case.

**Rationale**

Software tests, geometry/mesh preparation evidence and
case-specific physical solver validation are different proofs.

**Consequences**

- M8/M12, arbitrary metric geometry and additional material,
  friction or loading regimes require separate qualification.
- The frozen C01 case and holdout identities remain governed.
- Future expansion must not silently mutate the frozen policy.
- Physical dataset suitability is decided at the case and
  prediction-target level.

**Revisit when**

A separately governed expansion campaign establishes the
required cross-size, material, geometry and physics evidence.

**References:** [Phase-3 DOE policy](../config/phase3_production_doe.toml),
[Engineering Reference](THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md).

---

### DEC-009 — Keep the six sealed holdouts independent

**Status:** Established evaluation-integrity rule.
**Recorded:** 2026-09-23; original decision date not asserted.

**Decision**

Do not inspect sealed holdout case contents for exploratory
training, tuning, routine debugging or convenience coverage
checks. Preserve their governed evaluation purpose.

**Rationale**

Using evaluation cases during model development undermines
independent assessment and can conceal generalization failures.

**Consequences**

- Inventory scripts must avoid accessing sealed holdout data.
- Reused source runs and related trials must be considered
  when assessing sample independence.
- Training/evaluation partition rules must be defined before
  model fitting and evaluated for leakage.

**Revisit when**

The governed evaluation protocol reaches its authorized
holdout-use point. That does not retroactively permit
training-time leakage.

**References:** [Evidence and Dataset Guide](EVIDENCE_AND_DATASET_GUIDE.md).

---

### DEC-010 — Prioritize efficient and energy-aware FEM

**Status:** Established engineering preference.
**Recorded:** 2026-09-23; original decision date not asserted.

**Decision**

Avoid unnecessary duplicate solves; use valid certified evidence
and governed analytical/FEM-informed warm starts before requesting
more compute.

Do not impose an arbitrary short timeout on a justified
long-running fine-mesh solve.

**Rationale**

Solver time, storage and energy are limited engineering resources.
A longer valid run can be preferable to repeated aborted runs.

**Consequences**

- Prove the engineering need for each proposed additional trial.
- Monitor accepted increments, convergence, resource usage
  and true solver health before intervening.
- Preserve valid states even if a particular trial is not
  admitted to the final dataset.
- Resource controls must coexist with physics and evidence
  integrity.

**Revisit when**

Measured capacity or solver constraints require an adjusted,
explicit and governed operating policy.

**References:** [Operating Runbook](OPERATING_RUNBOOK.md),
[Engineering Reference](THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md).

---

## 3. Current project checkpoint decisions

### DEC-011 — Close factory qualification; continue Phase 3 DOE work

**Status:** Established checkpoint on 2026-09-23.

**Decision**

Record the six bounded factory-qualification gates as closed.
Do not describe that closure as completion of Phase 3.

**Supporting checkpoint**

The reported full repository regression passed
`1157 tests in 555.92s`. The frozen inventory was reconciled
without launching FEM or changing existing evidence.

**Remaining work**

Review and preserve the source checkpoint; reconcile actual
trial history; establish case-level physical dispositions;
complete only justified additional DOE work; freeze the
bounded ROM-ready dataset.

**Revisit when**

A newly discovered defect or contradictory authoritative
evidence invalidates a specific gate claim. Reopen only the
affected qualification with an explicit reason and new test.

**References:** [Current State](CURRENT_STATE.md),
[Engineering Reference](THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md).

---

### DEC-012 — Preserve source changes through reviewed Git selection

**Status:** Established next-workflow rule; checkpoint pending.

**Decision**

Review the actual working-tree changes and select intended
factory source, tests and documentation deliberately before
committing and pushing.

**Rationale**

The passing regression was reported with modified and
untracked files present. A green test result does not
identify which untracked items belong in a release.

**Consequences**

- Do not stage everything indiscriminately.
- Preserve historical FEM artifacts and unrelated changes.
- Verify the final candidate source state.
- Update the current-state document after the actual
  committed and pushed checkpoint is established.

**Revisit when**

The repository has been reviewed, verified and checkpointed.
This decision then becomes normal ongoing change-control
practice rather than an open milestone.

**References:** [Current State](CURRENT_STATE.md),
[Operating Runbook](OPERATING_RUNBOOK.md).

---

## 4. Proposed Phase-4 architecture — not yet implemented

The following are design directions, not declarations of
completed code or decisions to start training immediately.

### PROP-001 — Certified dataset as the FEM-to-ROM boundary

**Status:** Proposed Phase-4 interface.

**Proposal**

Each ROM consumes versioned, accepted engineering samples
through a model-independent dataset contract.

The ROM should not directly depend on mutable C01 solver
staging paths, raw CalculiX file formats or trial-specific
directory naming.

**Rationale**

Several legitimate ROM targets can reuse one physically
accepted FEM result without duplicating simulation work.

**Before adoption**

Specify and test the canonical sample schema, source
provenance, target extraction, admission gates, immutable
dataset releases and compatibility behaviour.

**References:** [Architecture and Interfaces](ARCHITECTURE_AND_INTERFACES.md),
[Evidence and Dataset Guide](EVIDENCE_AND_DATASET_GUIDE.md).

---

### PROP-002 — Independent ROM families and applicability contracts

**Status:** Proposed Phase-4 architecture.

**Proposal**

Permit different ROMs to use the shared certified engineering
evidence while independently defining input features,
prediction targets, model families, units, applicability,
uncertainty, evaluation and versioned releases.

**Rationale**

Scalar clamp-force prediction, load-response curves and
spatial stress fields have different representation and
validation needs.

**Before adoption**

Define the first bounded ROM's target and criteria; test the
prediction interface and out-of-domain behaviour; establish
independent evaluation and release provenance.

Do not infer mesh-independent full-field capability from
parametric CAD or from successful scalar models.

**References:** [Architecture and Interfaces](ARCHITECTURE_AND_INTERFACES.md).

---

### PROP-003 — Independent ANSYS cross-check at the ROM transition

**Status:** Planned cross-check; not recorded as completed.

**Proposal**

Use the planned ANSYS 2022 R2 comparison as an independent
engineering cross-check at the governed Phase-3-to-Phase-4
transition.

**Before adoption**

Define the exact physical case, matched assumptions, loads,
constraints, mesh considerations, output quantities,
acceptance criteria and recorded evidence.

**Boundary**

Do not call the ANSYS cross-check certified or complete
until its actual execution and results have been verified.

**References:** [Engineering Reference](THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md).

---

## 5. How to record future decisions

Use the following structure for each new decision:

| Field | Required content |
|---|---|
| ID | Stable new `DEC-###` or `PROP-###` identifier. |
| Date | Actual decision/review date; distinguish an earlier event date if known. |
| Status | Proposed, established, superseded or withdrawn. |
| Context | Engineering problem and affected physical/software scope. |
| Decision | Exact chosen behaviour or architectural boundary. |
| Rationale | Evidence-backed reason for the choice. |
| Consequences | Affected cases, interfaces, tests, data and limitations. |
| Verification | Relevant source, configuration, tests and evidence records. |
| Revisit conditions | Specific circumstances requiring a new governed review. |

When a decision changes:

1. Preserve its original record and mark it superseded.
2. Create a new decision with its own ID and actual date.
3. Link the replacement to the earlier decision.
4. Identify affected source, policy, evidence and documentation.
5. Verify the new implementation and its compatibility with
   existing accepted engineering evidence.

A proposed decision becomes established only after the
appropriate explicit project decision. A claimed implemented
capability additionally requires relevant source and
verification evidence.

Do not rewrite historical rationale to make a new design
appear to have been the original plan.

---

## 6. Current handover

**Established:** A bounded, governed and meaningfully
adaptive Phase-3 FEM factory foundation with six closed
software/preparation qualification gates.

**Pending:** Reviewed source checkpoint, authoritative
case-level evidence dispositions, required DOE completion,
certified dataset freeze and first Phase-4 ROM.

**Future direction:** Reuse trustworthy engineering evidence
through a model-independent dataset interface to support
multiple separately validated ROM families.

**Guiding principle:** Preserve a decision's reasoning and
its actual qualification boundary so future changes are
deliberate, reviewable and reproducible.
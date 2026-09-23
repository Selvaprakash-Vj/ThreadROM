# ThreadROM — Architecture and Interface Boundaries

**Initial version:** 2026-09-23
**Project phase:** Phase 3 — governed DOE evidence completion
**Purpose:** Explain the engineering subsystems, their responsibilities,
the boundaries between them and the proposed interfaces for future ROMs.

> Begin with [CURRENT_STATE.md](CURRENT_STATE.md) for the latest
> verified checkpoint. This document is an architectural reference,
> not a substitute for the actual source contracts, tests, campaign
> policy or case-specific physics evidence.

---

## 1. How to navigate this document

| Need | Reference |
|---|---|
| Latest checkpoint and next action | [Current State](CURRENT_STATE.md) |
| Detailed engineering scope and six-gate history | [Phase-3 Engineering Reference](THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md) |
| Actual filenames, exported symbols and static imports | [Repository Atlas](THREADROM_REPOSITORY_ATLAS.md) |
| Safe operating and recovery procedures | [Operating Runbook](OPERATING_RUNBOOK.md) |
| Evidence interpretation and future dataset admission | [Evidence and Dataset Guide](EVIDENCE_AND_DATASET_GUIDE.md) |
| Frozen C01 configuration | [Phase-3 DOE policy](../config/phase3_production_doe.toml) |

**Interpretation key**

- **Implemented:** Functionality established by the existing project
  source and the previously completed qualification work.
- **Verified within C01:** A bounded software, geometry or preparation
  claim supported by the six-gate milestone.
- **Pending evidence:** A capability whose complete physical or
  case-level qualification has not yet been established.
- **Proposed:** A future architecture contract to design, implement
  and test; not an existing production interface.

The diagrams below are conceptual responsibility maps. They are
not generated call graphs or claims that every subsystem already
exposes a formal public API.

---

## 2. System context and responsibility flow

```text
                  GOVERNED ENGINEERING INPUTS
        geometry | fastener | materials | loads | policy
                                |
                                v
                  CASE RESOLUTION / PREFLIGHT
                                |
               +----------------+----------------+
               |                                 |
               v                                 v
       ANALYTICAL ENGINEERING             PARAMETRIC CAD
               |                                 |
               |                                 v
               |                        MESH / CLASSIFICATION
               |                                 |
               +----------------+----------------+
                                |
                                v
                   FEM DEFINITION / PREPARATION
                                |
                                v
              ADMISSION / RESERVATION / EXECUTION
                                |
                                v
             TRIAL HISTORY / RECOVERY / VERIFICATION
                                |
                                v
                  ACCEPTED ENGINEERING EVIDENCE
                                |
               +----------------+----------------+
               |                                 |
               v                                 v
      CASE-SPECIFIC REUSE              ROM DATASET ADMISSION
                                          [PROPOSED]
                                                |
                                                v
                                   INDEPENDENT ROM FAMILIES
                                          [PHASE 4]
```

The analytical, CAD and FEM branches must refer to the intended
canonical physical case. Agreement of filenames alone is not
enough to establish engineering equivalence.

The source of truth for an accepted result is its governing
engineering evidence. A diagram arrow does not imply successful
execution, acceptance or automatic promotion.

---

## 3. Existing engineering subsystem boundaries

### 3.1 Case definition and resolution

**Responsibility:** Represent the intended fastener-joint
configuration, resolve parameters and enforce applicable
configuration and engineering preflight constraints.

**Receives:** Canonical case inputs, material/standards data,
declared policy and the intended physical configuration.

**Provides:** Resolved inputs and identities for downstream
analytical, CAD, mesh and FEM operations.

**Boundary rule:** Downstream stages must not silently replace
governed case properties with local constants or contradictory
case-specific overrides.

The complete ownership map and exact current symbols are indexed
in the [Repository Atlas](THREADROM_REPOSITORY_ATLAS.md).

### 3.2 Analytical engineering

**Responsibility:** Calculate and check applicable bolt, member,
thread and joint quantities under defined analytical assumptions.

**Receives:** Resolved physical inputs and the relevant analytical
model assumptions.

**Provides:** Derived quantities, reference behaviour and
engineering checks usable in FEM preparation and validation.

**Boundary rule:** An analytical estimate is not a replacement
for required FEM evidence. Its limitations and assumptions must
remain visible during analytical-versus-FEM comparison.

### 3.3 Parametric geometry and mesh

**Responsibility:** Generate and identify the intended assembly
geometry, thread representation, mesh and classified interfaces.

**Receives:** Resolved case geometry and the governed mesh policy.

**Provides:** Geometry and mesh artifacts, classifications,
preparation checks and traceable artifact identities.

**Boundary rule:** Neither file existence nor a matching nominal
bolt size establishes mesh adequacy, thread registration or physical
configuration equivalence.

The September 2026 qualification verified the frozen C01
M10x1.5 radial-geometry preparation path. It did not certify all
metric-fastener sizes or arbitrary joint geometries.

### 3.4 FEM definition and deck preparation

**Responsibility:** Transfer the resolved engineering case,
materials, mesh, contacts, supports, loads and preload definition
into a governed solver preparation.

**Relevant current source:**

- [FEM case preparation](../src/threadrom/factory/fem_case_preparation.py)
- [FEM definition bundle](../src/threadrom/factory/fem_case_definition_bundle.py)
- [CalculiX joint transfer](../src/threadrom/solver/complete_joint_calculix_transfer.py)

**Receives:** Resolved case inputs, verified geometry/mesh,
applicable analytical quantities and solver configuration.

**Provides:** A case-specific FEM definition, generated solver
deck and governed preparation evidence.

**Boundary rule:** Solver preparation must not invent material
properties, change loads or quietly alter the intended physical
case to improve convergence.

A prepared and checked deck is not an executed or physically
accepted FEM trial.

### 3.5 Two-group material contract

**Implemented software rule:**

| Component | Material-group requirement |
|---|---|
| Bolt | Same material identity and elastic properties as nut |
| Nut | Same material identity and elastic properties as bolt |
| Upper member | Same material identity and elastic properties as lower member |
| Lower member | Same material identity and elastic properties as upper member |

The fastener group and member group may have different elastic
properties.

The actual production-deck transfer test exercised distinct
Young's modulus and Poisson's ratio values for these groups.
Historical equal-property behaviour remained supported.

**Boundary rule:** This is software-transfer qualification, not
a certificate that all mixed-material FEM combinations are
physically valid or admitted into frozen C01.

### 3.6 Admission, solver ownership and execution

**Responsibility:** Determine whether a proposed solver action
is permitted, independently authorized and safe to execute
without conflicting with existing work.

**Relevant current source:**

- [Launch fence](../src/threadrom/factory/production_doe_launch_fence.py)

**Receives:** Exact governed case/trial identity, applicable
authorization, known evidence and current execution ownership.

**Provides:** A permitted or blocked governed execution action,
together with its required provenance and reservation controls.

**Boundary rule:** A case listed in the DOE, an existing deck,
a passing unit test or a supervisor request is not itself
independent permission to launch FEM.

No new solve is authorized by this architectural document.

### 3.7 Adaptation and continuation

**Responsibility:** Use governed calibration, warm starts,
trial history and continuation policies to determine the
appropriate next action for an eligible case.

**Receives:** Prior realised-state evidence, solver/calibration
measurements, relevant policy and the applicable authorization
state.

**Provides:** A governed continuation, recovery or engineering
review decision.

**Boundary rule:** Adaptation is bounded by verified evidence
and policy. It must not silently overwrite prior trials, bypass
admission or declare uncertain physics acceptable.

The six-gate milestone included a full supervisor lifecycle
dry run, not a demonstration that every possible live nonlinear
FEM failure can be handled without engineering intervention.

### 3.8 Trial history and engineering evidence

**Responsibility:** Preserve and resolve actual preparation,
execution, calibration, recovery and verification history.

**Relevant current source:**

- [Production DOE trial history](../src/threadrom/factory/production_doe_trial_history.py)

**Receives:** Governed case/trial identity, existing records,
solver artifacts and validation evidence.

**Provides:** Traceable evidence and the applicable governed
disposition or escalation for review.

**Boundary rule:** Do not infer execution from preparation,
convergence from process exit, or physics acceptance from
calibration acceptance.

A missing file at one expected location is not proof that
the underlying historical evidence does not exist elsewhere.

The complete evidence-state distinctions are documented in
the [Evidence and Dataset Guide](EVIDENCE_AND_DATASET_GUIDE.md).

---

## 4. Cross-layer invariants

These rules protect the architecture when adding new cases,
solver policies, materials or ROM families.

| Invariant | Why it matters |
|---|---|
| One canonical physical case | Prevents analytical, geometry and FEM branches from modelling different configurations. |
| Governed, explicit units and conventions | Prevents silent sign, coordinate and measurement mismatches. |
| Traceable artifact identity | Connects actual input bytes, solver execution and accepted output. |
| Evidence-preserving recovery | Prevents unnecessary duplicate compute or loss of useful failed trials. |
| Separate execution and engineering acceptance | Prevents completed numerical jobs from becoming unverified training labels. |
| Independent launch authorization | Prevents unattended preparation or supervision from granting itself solve permission. |
| Fail-closed uncertain states | Preserves engineering review when records or physical behaviour are ambiguous. |
| Dataset scope independent of CAD capability | Prevents parametric inputs from being mistaken for validated predictive applicability. |
| Sealed independent evaluation | Protects future ROM assessment from data leakage. |
| Immutable published model/dataset identity | Makes a prediction and its validation evidence reproducible. |

Some invariants have implemented safeguards today; others,
especially the dataset and model-release rules, are requirements
for the Phase-3-to-Phase-4 transition.

Do not report this table as evidence that every future safeguard
has already been implemented.

---

## 5. Supported scope versus extensibility

### Currently qualified bounded foundation

The six factory-qualification gates establish the governed
software/preparation path within the documented frozen C01
M10x1.5 envelope.

The latest reported full repository regression was:

`1157 passed in 555.92s`

The result does not certify all completed FEM cases, establish a
ROM-ready dataset or prove absence of all software defects.

### Extensibility already supported in software

- Parametric engineering inputs, CAD and analytical foundations.
- Case-derived preparation and reusable nonlinear FEM machinery.
- Two-group isotropic elastic-property transfer to a real deck.
- Governed launch admission, lifecycle supervision and evidence
  recovery within the tested boundaries.

### Expansion requiring additional qualification

- Other metric-fastener sizes or pitches.
- Wider independent joint-geometry variation.
- New material combinations within a physical DOE.
- Additional friction, interface, loading or constraint regimes.
- Fully unattended operation across untested real-world failures.
- A prediction model claiming accuracy outside its certified
  training and independent-evaluation domain.

Extensibility means the architecture offers a place to make
a controlled change. It does not mean that the change is free,
physically valid or already tested.

---

## 6. Proposed certified engineering dataset interface

**Status: PROPOSED. Not yet a verified production interface.**

The first ROM should consume a governed dataset release rather
than read mutable solver staging folders directly.

```text
   Accepted governed FEM evidence
               |
               v
     Target-specific extraction
               |
               v
   Dataset eligibility and review
               |
               v
   Versioned engineering samples
               |
               v
      Frozen dataset release
               |
      +--------+---------+
      |                  |
      v                  v
  ROM family A       ROM family B
      |                  |
      v                  v
 Independent evaluation and model registration
```

### Proposed sample responsibilities

A canonical sample should reference:

- Stable case and originating trial identities.
- Canonical engineering parameters and units.
- The exact target and its extraction definition.
- Applicable geometry/mesh/solver and physics provenance.
- The governing acceptance record and source artifact hashes.
- Dataset-admission decision and exclusion reasons where relevant.
- Dataset partition, applicability information and schema version.

These are architectural requirements; they are **not** asserted
as existing fields in a current historical JSON record.

Never add guessed fields to an old certificate simply to satisfy
this proposed interface.

### Dataset ownership

The FEM factory owns physical preparation, execution, recovery
and engineering validation.

A separate dataset-admission workflow should own sample
selection, target extraction contracts, partition assignment,
dataset immutability and release identity.

A ROM training workflow should not alter the underlying
engineering case or promote its own unverified FEM labels.

---

## 7. Proposed diversified ROM architecture

**Status: PHASE 4 DESIGN DIRECTION.**

Future ROM families should share the certified engineering
data interface while independently declaring:

| Contract | ROM-specific responsibility |
|---|---|
| Input schema | Required features, units, preprocessing and allowed missing values |
| Output schema | Exact physical target, units and extraction definition |
| Applicability domain | Supported geometry, material, load and physical assumptions |
| Model family | Algorithm or representation appropriate for the target |
| Training provenance | Frozen dataset, partitions and training configuration |
| Evaluation | Predeclared metrics, independent data and physical consistency checks |
| Uncertainty | Defined uncertainty treatment and unsupported-input response |
| Release | Immutable model identity, evaluation evidence and limitations |

A clamp-force scalar ROM, response-curve ROM and spatial
stress-field ROM should not be forced into the same output
representation merely because they consume related joint cases.

### Diversification levels

**Level 1 — Same fastener-joint evidence, different outputs.**

An accepted simulation may provide multiple legitimate targets.
Each target requires its own extraction and quality criteria.

**Level 2 — Broader fastener-joint configurations.**

Expand the governed DOE and certify actual model performance
across the intended additional geometry, material and loading
domain. The first C01 ROM must not silently accept configurations
outside its validated envelope.

**Level 3 — Different physics domains.**

Modal, thermal, fatigue, fluid or multiphysics ROMs may reuse
selected governance, provenance, dataset and evaluation ideas.
They require new domain-specific physics implementations and
qualification rules.

### Full-field model caution

A scalar sample may be usable without knowledge of its source
mesh node numbering.

A spatial field ROM needs a separately validated method for
changing geometry, mesh density, coordinates and correspondence.
Parametric CAD alone does not solve this representation problem.

---

## 8. Interface-change review checklist

Before changing a cross-layer source contract:

1. Identify the owning module and current public symbols
   using the [Repository Atlas](THREADROM_REPOSITORY_ATLAS.md).
2. Inspect current callers, tests and serialized record consumers.
3. Identify which canonical physical inputs and units are affected.
4. Determine whether existing evidence identities or hashes change.
5. Check backward compatibility with historic accepted cases.
6. Confirm the change cannot bypass trial admission, launch
   ownership, recovery or physics-verification rules.
7. Add focused positive and negative tests for the actual contract.
8. Verify generated artifacts where the change crosses a
   physical transfer boundary.
9. Run the required broader regression.
10. Update the affected documentation and record the decision
    if the governing architecture changes.

Do not modify historical evidence in place merely because a
software interface has evolved. Introduce an explicit version,
migration or governed compatibility route where necessary.

---

## 9. Architecture risks and unresolved design work

| Area | Current caution |
|---|---|
| Universal fastener coverage | Parametric inputs exceed physically qualified C01 coverage. |
| Multi-material physics | Two-group deck transfer passed; diversified physical certification remains separate. |
| Real-world interruption handling | A passing mocked lifecycle does not establish every live recovery scenario. |
| DOE evidence readiness | File inventory does not establish all per-case physics dispositions. |
| Dataset contract | Canonical immutable sample and release interfaces remain to be designed and tested. |
| Spatial-field ROMs | Mesh-independent output representation remains a separate engineering problem. |
| Independent model evaluation | Target-specific acceptance criteria and protected evaluation must precede training. |

These are explicit engineering boundaries, not reasons to
rebuild the entire factory before starting the first bounded ROM.

---

## 10. Practical roadmap and maintenance

**Immediate Phase-3 sequence**

1. Preserve a reviewed and verified source/documentation checkpoint.
2. Reconcile existing DOE history and justified evidence bindings.
3. Certify the required case-level engineering evidence.
4. Authorize only genuinely necessary additional FEM.
5. Freeze the bounded ROM-ready dataset with documented limitations.

**Phase-4 sequence**

1. Define the first ROM target and its supported domain.
2. Implement and test the certified dataset interface.
3. Freeze training, validation and independent evaluation rules.
4. Train and evaluate the first model against predeclared criteria.
5. Record the independent ANSYS 2022 R2 cross-check at its
   governed transition point.
6. Register the model and preserve its dataset, evaluation
   evidence, limitations and prediction contract.

Update this document when an actual cross-layer interface,
supported scope or ROM architecture is changed. Verify the
current source before converting a proposed contract into
an implemented-capability claim.

**Architectural principle:** One trustworthy engineering evidence
foundation; explicit interfaces; independent, appropriately
qualified downstream ROM families.
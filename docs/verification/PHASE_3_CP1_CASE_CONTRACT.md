# Phase 3 CP1 — ThreadROM Case Contract and Parameter Capability Matrix

## 1. Purpose

Phase 3 converts the certified Phase-2 nonlinear threaded-joint model into a
governed, deterministic, fully parametric FEM factory.

The eventual ThreadROM product interface shall allow an engineer to describe
the physical joint using governed selections and bounded numerical inputs,
request a calculation, and receive engineering results without manually
editing CAD, mesh, contact, preload, solver, or post-processing data.

The governing architecture is:

USER / DOE INPUT
    ->
ThreadROMCase
    ->
CASE VALIDATION
    ->
CASE RESOLUTION
    ->
ANALYTICAL MODEL
    ->
GEOMETRY
    ->
MESH / TOPOLOGY
    ->
CONTACT
    ->
PRELOAD CALIBRATION
    ->
SOLVER
    ->
POST-PROCESSING
    ->
PHYSICS ACCEPTANCE
    ->
CERTIFIED RESULT / DATASET SAMPLE

The UI, DOE generator, CLI, FEM factory, and future ROM interface must consume
the same governed ThreadROMCase contract.

---

## 2. Single-source-of-truth rule

No Phase-3 subsystem configuration may act as an independent authoritative
source for a physical case quantity.

Legacy Phase-1 and Phase-2 TOML files remain frozen and usable for regression,
certification reproduction, and historical traceability.

New Phase-3 cases originate from ThreadROMCase.

Subsystem definitions may contain resolved values for traceability, but those
values must be generated from the authoritative case or from governed
standards/material/capability data.

Examples of prohibited duplicated ownership:

- thread designation plus independently authoritative diameter and pitch
- member thicknesses plus independently authoritative total grip length
- selected material plus independently authoritative E, nu, strength, or alpha
- target preload plus independently authoritative thermal actuator temperature
- standard bolt selection plus independently authoritative head dimensions

---

## 3. Parameter classifications

### 3.1 USER_INPUT

Physical choices the engineer may directly specify through the future UI,
CLI, or DOE definition.

### 3.2 GOVERNED_SELECTION

Discrete selections constrained by ThreadROM-supported standards, material
catalogues, analysis modes, fidelity levels, or certified capability domains.

### 3.3 DERIVED

Quantities calculated automatically from authoritative inputs or governed
reference data.

### 3.4 INTERNAL

Numerical implementation details that must never become normal engineering
inputs.

### 3.5 EXPERIMENTAL

Representable by part of the codebase but not yet certified through the full
geometry -> mesh -> solver -> physics-acceptance chain.

### 3.6 UNSUPPORTED

Known to be outside the currently validated model or numerical architecture.
Preflight must reject these cases before an expensive solve.

---

## 4. Product-level parameter capability matrix

| Domain | Parameter / concept | Classification | Phase-3 CP1 status | Geometry regeneration | Remesh | Preload recalibration | Notes |
|---|---|---|---|---:|---:|---:|---|
| Fastener | Bolt product standard | GOVERNED_SELECTION | ISO 4017:2022 baseline only | Yes | Yes | Yes | Future standards require governed resolvers |
| Fastener | Thread designation | GOVERNED_SELECTION | M10x1.5 baseline; other metric sizes experimental | Yes | Yes | Yes | Resolver derives nominal diameter and pitch |
| Fastener | Nominal diameter | DERIVED | Parametric kernel exists | Yes | Yes | Yes | Never independently authoritative in standard mode |
| Fastener | Pitch | DERIVED | Parametric kernel exists | Yes | Yes | Yes | Never independently authoritative in standard mode |
| Fastener | Handedness | GOVERNED_SELECTION | Right certified historically; left experimental | Yes | Yes | Yes | Reuses ThreadHandedness |
| Fastener | Thread starts | GOVERNED_SELECTION | Single-start only | Yes | Yes | Yes | Multi-start currently UNSUPPORTED |
| Fastener | Bolt length | USER_INPUT / GOVERNED_SELECTION | Parametric definition exists | Yes | Yes | Yes | Standard lengths may become dropdown values |
| Fastener | Bolt material ID | GOVERNED_SELECTION | Contract established | No | No | Yes | Material resolver required |
| Fastener | Bolt property class | GOVERNED_SELECTION | Contract established | No | No | Potentially | Strength/reference properties resolved downstream |
| Fastener | Bolt head AF / height | DERIVED | Baseline values currently configured | Yes | Yes | Yes | Must come from product-standard resolver |
| Nut | Nut product standard | GOVERNED_SELECTION | ISO 4032:2023 baseline only | Yes | Yes | Yes | Future standards require resolvers |
| Nut | Nut material ID | GOVERNED_SELECTION | Contract established | No | No | Yes | Material resolver required |
| Nut | Nut property class | GOVERNED_SELECTION | Contract established | No | No | Potentially | Compatibility policy required |
| Nut | Across flats / thickness | DERIVED | Parametric geometry exists; baseline config owns values today | Yes | Yes | Yes | Must come from nut-standard resolver |
| Nut | Thread engagement length | DERIVED / GOVERNED_POLICY | Existing analytical/FEM input | Yes | Yes | Yes | Derived from resolved nut/assembly geometry for current product family |
| Members | Member layer count | USER_INPUT | Contract supports arbitrary ordered layers | Yes | Yes | Yes | Certified FEM topology currently based on two-member baseline |
| Members | Layer order | USER_INPUT | Contract preserves order | Yes | Yes | Yes | Order is part of engineering identity |
| Members | Layer thickness | USER_INPUT | Fully represented | Yes | Yes | Yes | Total grip is derived |
| Members | Total grip length | DERIVED | Implemented property | Yes | Yes | Yes | Sum of member-layer thicknesses |
| Members | Member material ID | GOVERNED_SELECTION | Per-layer contract exists | No | No | Yes | Analytical layer already supports per-layer materials |
| Members | Outer diameter | USER_INPUT | Current coaxial cylindrical family | Yes | Yes | Yes | Future geometry families need separate schemas |
| Members | Clearance-hole diameter | USER_INPUT / GOVERNED_SELECTION | Explicit numeric input today | Yes | Yes | Yes | Later standard-clearance resolver may supply dropdowns |
| Interfaces | Thread friction coefficient | USER_INPUT / GOVERNED_SELECTION | Explicit independent value | No | No | Yes | Must remain bounded and validated |
| Interfaces | Head-bearing friction coefficient | USER_INPUT / GOVERNED_SELECTION | Explicit independent value | No | No | Yes | Baseline happened to use same coefficient |
| Interfaces | Nut-bearing friction coefficient | USER_INPUT / GOVERNED_SELECTION | Explicit independent value | No | No | Yes | Baseline happened to use same coefficient |
| Interfaces | Member-interface friction coefficient | USER_INPUT / GOVERNED_SELECTION | Explicit independent value | No | No | Yes | Baseline happened to use same coefficient |
| Loading | Target preload | USER_INPUT | Contract established | No | No | Yes | Thermal actuator Delta-T must never be user-entered |
| Loading | External axial load | USER_INPUT | Contract established; zero valid | No | No | No* | *Unless load architecture later couples preload calibration |
| Loading | Cyclic loading | EXPERIMENTAL / FUTURE | Analytical primitives exist | No | No | Case-dependent | Not yet in Phase-3 v1 contract |
| Materials | Young's modulus | DERIVED | Analytical primitives exist | No | No | Yes | Resolve from material definition |
| Materials | Poisson's ratio | DERIVED | Analytical primitives exist | No | No | Potentially | Resolve from material definition |
| Materials | Density | DERIVED | Baseline metadata exists | No | No | No | Needed where relevant |
| Materials | Proof / yield / ultimate strength | DERIVED | Analytical infrastructure exists | No | No | No | Used for governed utilisation checks |
| Materials | Thermal expansion coefficient | DERIVED | Current preload config owns baseline alpha | No | No | Yes | Must resolve from material/preload governance |
| Thread geometry | Fundamental triangle height | DERIVED | Parametric | Yes | Yes | Yes | Canonical metric-thread calculation |
| Thread geometry | Pitch diameter | DERIVED | Parametric | Yes | Yes | Yes | Canonical metric-thread calculation |
| Thread geometry | Internal minor diameter | DERIVED | Parametric | Yes | Yes | Yes | Canonical metric-thread calculation |
| Thread geometry | External minor diameter | DERIVED | Parametric | Yes | Yes | Yes | Canonical metric-thread calculation |
| Thread geometry | Thread phase / registration | DERIVED | Parametric infrastructure exists | Yes | Yes | Yes | Must remain topology validated |
| Thread geometry | Tolerance-realized 6g/6H CAD | EXPERIMENTAL / FUTURE | Metadata only today | Yes | Yes | Yes | UI must not claim tolerance-realized CAD yet |
| Thread geometry | Thread runout | UNSUPPORTED / FUTURE | Explicitly excluded baseline | Yes | Yes | Yes | Separate future capability |
| Geometry | Bolt/nut/member Z positions | DERIVED | Existing assembly logic | Yes | Yes | Yes | Never user-entered |
| Geometry | Protrusion | DERIVED | Existing assembly calculations | Yes | Yes | Yes | Must be resolved consistently with bolt/nut/member stack |
| Geometry | Arbitrary plate/flange profiles | UNSUPPORTED / FUTURE | Not in current FEM family | Yes | Yes | Yes | Current product family is coaxial cylindrical members |
| Mesh | Element type / mesh fidelity | GOVERNED_SELECTION | Existing mesh infrastructure | No geometry* | Yes | Possibly | *Geometry unchanged but regenerated mesh required |
| Mesh | Node IDs | INTERNAL | Must be automatically derived | No | Yes | No | Never accepted from UI/case config |
| Mesh | Element IDs | INTERNAL | Must be automatically derived | No | Yes | No | Never accepted from UI/case config |
| Mesh | Refinement regions | DERIVED / INTERNAL | Baseline-driven today | No | Yes | Possibly | Must derive from geometry/topology metadata |
| Contact | Contact facet identities | INTERNAL | Existing surface classification infrastructure | No | Yes | Yes | Must be derived and validated |
| Contact | Contact topology | DERIVED / GOVERNED | Four-interface baseline certified | Yes | Yes | Yes | Future topology changes require capability proof |
| Preload | Reference temperature | INTERNAL / GOVERNED | Baseline preload governance exists | No | No | Yes | Numerical actuator parameter |
| Preload | Thermal actuator Delta-T | DERIVED | Baseline calibrated value exists | No | No | Yes | Never reuse baseline Delta-T blindly |
| Preload | Applied bolt temperature | DERIVED | Existing thermal preload state | No | No | Yes | reference temperature + calibrated Delta-T |
| Preload | Calibration history | INTERNAL / PROVENANCE | Baseline metadata exists | No | No | Yes | New cases require governed automatic calibration |
| Solver | CalculiX node sets | INTERNAL | Symbolic set architecture exists | No | Yes | No | Derived from mesh metadata |
| Solver | Element sets | INTERNAL | Derived from mesh/component metadata | No | Yes | No | No manual IDs |
| Solver | Solver step architecture | GOVERNED / INTERNAL | Phase-2 baseline certified | No | No | Case-dependent | Do not expose arbitrary cards in normal UI |
| Solver | Numerical tolerances | GOVERNED / INTERNAL | Baseline certified | No | No | No | Future fidelity policy may select values |
| Results | Requested calculation backend | GOVERNED_SELECTION | AUTO / ANALYTICAL / FEM / ROM | No | Depends | Depends | Backend selection is separate from fidelity |
| Results | Analysis fidelity | GOVERNED_SELECTION | CERTIFICATION / PRODUCTION / SCREENING | Depends | Depends | Depends | Must map to validated factory policies |
| Results | Human case name / notes | USER_METADATA | Implemented | No | No | No | Excluded from engineering fingerprint |

---

## 5. Current capability truth at CP1

CP1 does not self-certify the new Phase-3 factory.

At CP1:

- Phase-2 certified physics and numerical machinery remain the trusted reference.
- ThreadROMCase can represent the baseline family.
- The new Phase-3 case path is EXPERIMENTAL until it reproduces the certified
  Phase-2 baseline automatically.
- CP4 is the earliest checkpoint allowed to promote the reproduced baseline
  factory path to SUPPORTED.
- Multi-start threads are currently UNSUPPORTED.
- Left-hand threads are representable but EXPERIMENTAL.
- Non-M10x1.5 metric threads are representable by much of the parametric
  geometry/analytical kernel but remain EXPERIMENTAL until end-to-end evidence
  exists.
- ISO 4017:2022 bolt and ISO 4032:2023 nut are the currently known baseline
  product standards. Other standards require governed standard resolvers.

Representable != certified.

---

## 6. Existing reusable Phase-1/2 primitives

The Phase-3 case layer shall reuse rather than duplicate existing primitives,
including:

- ThreadHandedness
- MetricThreadInput
- ElasticMaterial
- BoltAxialSegmentInput
- MemberLayerInput
- LoadingInput
- BoltInput
- NutInput
- AnalyticalMethodSelection
- AnalyticalJointInput
- canonical metric-thread geometry calculations
- bolt/nut/thread parametric CAD definitions
- assembly logic
- surface classification
- mesh-quality machinery
- CalculiX transfer/contact machinery
- thermal preload governance
- convergence/equilibrium/post-processing machinery

Phase 3 adds orchestration and authoritative parameter ownership around these
subsystems.

---

## 7. Phase-3 case identity

ThreadROMCase schema version starts at:

    CASE_SCHEMA_VERSION = 1

Canonical engineering serialization:

- excludes human metadata
- preserves ordered member layers
- normalizes numeric values
- serializes enums by stable value
- uses deterministic JSON representation

SHA-256 is used as the engineering request fingerprint.

A future refinement may separate:

- physical-case identity
- analysis/execution-request identity
- solver-deck identity

That separation is not required to close CP1.

---

## 8. UI contract principle

The eventual interface must be a thin consumer of the same governed case API.

The UI must not contain independent engineering formulas or hidden numerical
assumptions.

Conceptually:

    Engineer selections
        ->
    ThreadROMCase
        ->
    Resolver / capability / preflight
        ->
    Analytical / FEM / ROM execution
        ->
    ThreadROMResult

The engineer specifies the physical joint.

ThreadROM determines how to model it.

---

## 9. CP1 exit criteria

CP1 may close when all of the following are true:

- authoritative ThreadROMCase contract exists
- schema version exists
- deterministic case serialization exists
- SHA-256 engineering fingerprint exists
- support-status vocabulary exists
- conservative capability assessment exists
- parameter capability matrix is documented
- new contract/capability/serialization unit tests pass
- complete repository regression suite passes
- no certified Phase-2 production file has been unintentionally modified
- CP1 changes are reviewed and committed as one meaningful milestone

After CP1 closure, CP2 begins deterministic case resolution/factory work.

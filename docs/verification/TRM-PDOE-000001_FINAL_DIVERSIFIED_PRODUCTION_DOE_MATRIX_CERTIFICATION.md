# ThreadROM Final Diversified Production DOE Matrix Certification

**Record ID:** TRM-PDOE-000001
**Phase:** Phase 3 / CP11 pre-DOE hardening
**Status:** PASS
**Certification date:** 2026-09-18

## 1. Purpose

This record certifies the final diversified Phase-3 Production-DOE
matrix for the currently governed ThreadROM applicability envelope.

The certification is evidence-bounded. It certifies the frozen matrix,
its deterministic reproducibility, its public design-case identities,
its sealed blind-holdout count, its current FEM-preparation state, and
the output-contract readiness required for the remaining unsolved
Production-DOE cases.

This record does not authorize Production-DOE execution.

Gate 0 remains the separate final DOE-authorization gate.

No new FEM solution was executed for this Gate-1 certification.

## 2. Governed frozen campaign

The final diversified campaign is:

- campaign: `TRM-PDOE-C01`,
- deterministic seed: `310826`,
- deterministic maximin Latin-hypercube construction,
- boundary cases enabled,
- 16 interior diversified design points,
- 4 existing certified anchor states,
- 20 fresh Production-DOE design states,
- 24 public design rows in total,
- 6 blind holdouts,
- maximum fresh Production-DOE solve budget: 20.

The governed frozen artifacts are:

### Production-DOE policy

SHA256:

`43032557cb2abead0118362bcfc6a9b2e5246a7d363ca83eef5fcf35054befc1`

### Production-DOE campaign manifest

SHA256:

`84516519bbb188664268936e2d116e133431d90d037bed407ffb2d1fe92d2a67`

### Production-DOE preparation certification

SHA256:

`ad49cc35b61e95147ae669f0f915b8d7ae403145d098729e5540285f319befd5`

### Existing-anchor binding record

SHA256:

`ab861ff62af6bbc4589b3a469e8dc159c92dd61116fd8275c02e8f1adcf813b2`

All four hashes are preserved as governed campaign provenance.

## 3. Governed diversified parameter space

The current Production-DOE matrix spans the explicitly governed
three-dimensional design space:

- preload target: 15 kN to 20 kN,
- head-member thickness: 8 mm to 10 mm,
- radial-geometry fraction: 0 to 1.

The four existing anchor coordinates are:

- A00: `(1, 1, 0)`,
- A01: `(0, 1, 0)`,
- A02: `(1, 0, 0)`,
- A03: `(1, 1, 1)`.

The present campaign does not independently vary:

- external service load,
- friction coefficient,
- clearance or outer diameter as an independent DOE factor,
- material family,
- thread family,
- preload above 20 kN,
- the P02 25 kN condition,
- the reverse 12_8 grip condition.

Those exclusions remain outside this Gate-1 claim.

## 4. Final public design matrix

The frozen public design matrix contains exactly 24 rows in the
following governed order:

| Row | Case ID | Case hash prefix |
|---:|---|---|
| 01 | A00 | `ee7b1a1ae89d` |
| 02 | A01 | `a9b6196a25d4` |
| 03 | A02 | `30059c410f5c` |
| 04 | A03 | `ae87c6fcba11` |
| 05 | D-BND-001 | `a5e86e9150fb` |
| 06 | D-BND-002 | `4ec5fd412595` |
| 07 | D-BND-003 | `132f5f2b9795` |
| 08 | D-BND-004 | `9d11902c8c53` |
| 09 | D-INT-001 | `762a30bed266` |
| 10 | D-INT-002 | `cd79bd4336c0` |
| 11 | D-INT-003 | `226154f7ef4e` |
| 12 | D-INT-004 | `d0bfb12d44c2` |
| 13 | D-INT-005 | `4e77db0d0c12` |
| 14 | D-INT-006 | `6c0eb1807bb0` |
| 15 | D-INT-007 | `4766e95d0d13` |
| 16 | D-INT-008 | `1faafccbbc3b` |
| 17 | D-INT-009 | `37ea3dfbef25` |
| 18 | D-INT-010 | `dded29952881` |
| 19 | D-INT-011 | `06046fe91597` |
| 20 | D-INT-012 | `d667bb1aca27` |
| 21 | D-INT-013 | `039053767417` |
| 22 | D-INT-014 | `941ce23d715c` |
| 23 | D-INT-015 | `34fffb87e0f7` |
| 24 | D-INT-016 | `c74956ffff17` |

A read-only deterministic rebuild of the current campaign was compared
against the frozen campaign manifest.

Results:

- frozen policy SHA: PASS,
- frozen manifest SHA: PASS,
- current deterministic design rows: 24,
- frozen manifest design rows: 24,
- design-case identity: exact match,
- design-case ordering: exact match.

The frozen public matrix therefore remains identical to the
deterministic current Production-DOE construction.

## 5. Blind holdout governance

The campaign contains exactly 6 blind holdouts.

During Gate-1 reconciliation:

- blind-holdout coordinates were not printed,
- blind-holdout coordinates were not traversed by the matrix
  reconciliation,
- no blind holdout was promoted into accepted Production-DOE evidence,
- no blind holdout was used to alter the public design matrix.

The holdout population remains sealed for later governed validation.

## 6. Current Production-DOE execution state

The 20 fresh Production-DOE design cases currently reconcile as:

- accepted governed FEM states: 15,
- remaining unsolved design states: 5,
- blind holdouts accepted as training/design evidence: 0.

The remaining five public design cases are:

- D-INT-012,
- D-INT-013,
- D-INT-014,
- D-INT-015,
- D-INT-016.

No additional M10 FEM state was required to certify Gate 1.

Existing accepted evidence is reused rather than duplicated.

## 7. D-INT-008 prospective-state normalization

D-INT-008 was independently normalized as a governed accepted
Production-DOE FEM calibration state.

The normalized semantics are:

- warm-start knowledge eligibility: false,
- V2-anchor eligibility: false,
- Production-DOE dataset eligibility: true.

Its accepted physical calibration remains unchanged.

No additional D-INT-008 FEM execution is authorized or required by
this Gate-1 certification.

The historical support-only equilibrium result remains a diagnostic
failure at the unchanged `0.001 N` tolerance.

No support-only result was reclassified as a full-system equilibrium
PASS.

## 8. Equilibrium observability applicability

Historical accepted/prospective Production-DOE decks did not expose
the full constrained reaction system needed for a generalized
full-system equilibrium check.

Across the audited accepted/prospective population:

- support-only equilibrium PASS: 0 / 15,
- full-system equilibrium PASS inferred from support-only data: NO,
- equilibrium tolerance changed: NO,
- additional FEM authorized merely to repair historical observability:
  NO.

The governed classifier distinguishes:

- `FULL_SYSTEM_OBSERVABLE`,
- `DIAGNOSTIC_ONLY_INCOMPLETE_REACTION_SYSTEM`.

Incomplete historical reaction output therefore remains
diagnostic-only.

Observability is not itself an equilibrium PASS claim.

## 9. Reaction-observable Trial-1 revision contract

The five remaining unsolved Production-DOE cases require a fresh
output-contract sibling before execution so that the complete
constrained reaction system is observable.

The governed revision tag is:

`rfobs1`

Each revision preserves:

- the frozen Production-DOE case lineage,
- Trial-1 semantics,
- the governed source WSV21 delta temperature,
- the certified mesh,
- contact definitions,
- boundary-condition physics,
- material and thermal physics,
- calibration policy,
- the global FEM deck identity guard.

The revision changes only the required reaction-output observability
contract and execution-lineage compatibility needed by the frozen
campaign.

## 10. Frozen-lineage identity compatibility

The frozen Production-DOE campaign predates the later FEM execution
identity migration from case-hash-derived run IDs to
resolution-hash-derived run IDs.

The five remaining cases were audited individually.

For all five:

- frozen campaign identity remains case-hash derived,
- current preparation identity is resolution-hash derived,
- case identity is unchanged,
- resolved case provenance is unchanged,
- frozen evidence remains bound to the intended DOE case.

A narrowly scoped compatibility bridge therefore rebinds only the
execution identity required by the frozen DOE lineage.

The bridge preserves:

- `case_hash`,
- `resolution_hash`,
- physical preparation data,
- mesh definition,
- transfer definition,
- contact definition,
- boundary physics,
- guidance geometry,
- calibration seed,
- calibration policy.

The global FEM execution-identity semantics were not reverted.

The global calibration-deck lineage guard was not weakened.

Focused bridge and observability regression:

**11 passed**

## 11. Calibration-deck reaction-output hardening

The generic complete-joint physical-pretension renderer already
requested reaction-force output for the complete constrained system.

The dedicated FEM preload-calibration deck writer historically
requested explicit `*NODE PRINT` reaction output only for the
head-member support.

Gate-1 hardening added explicit RF output for the eight existing
guidance/reference carriers:

- `BOLT_HEAD_GUIDANCE_REFERENCE`,
- `BOLT_HEAD_ROTATION_X_REFERENCE`,
- `BOLT_HEAD_ROTATION_Y_REFERENCE`,
- `NUT_MEMBER_GUIDANCE_REFERENCE`,
- `NUT_ROTATION_GUIDANCE_REFERENCE`,
- `NUT_ROTATION_X_REFERENCE`,
- `NUT_ROTATION_Y_REFERENCE`,
- `NUT_TRANSLATION_GUIDANCE_REFERENCE`.

Together with `HEAD_MEMBER_SUPPORT_BAND`, every new `rfobs1` deck now
contains:

- constrained reaction carriers: 9,
- RF-observable constrained sets: 9,
- missing constrained carriers: 0.

No boundary condition, contact definition, material property,
calibration temperature, equilibrium tolerance, or nonlinear solver
criterion was changed by this output hardening.

Focused calibration-deck / reaction-observability regression:

**13 passed**

## 12. Published zero-solve rfobs1 preparations

The five remaining Trial-1 sibling preparations were first generated
in dry-run mode and then published immutably.

### D-INT-012

Run:

`trm_fem_d667bb1aca27_cal_01_wsv21_rfobs1`

Delta T:

`-265.94725419998827 C`

Deck SHA256:

`c270aa1a08186538b9f64829f07373de531949988466b7b2cff3c3fbad2c7e8d`

Preparation-record SHA256:

`b5a88ff926b49c774d1f209162e07740993eacd392ee8b72ede8c57a44f366be`

### D-INT-013

Run:

`trm_fem_039053767417_cal_01_wsv21_rfobs1`

Delta T:

`-230.58662904645178 C`

Deck SHA256:

`ea768a358a970bff7d760e1e7ad0c79afa0ac96226999de0fe5755bb9f59b5e4`

Preparation-record SHA256:

`f3d8b8b1f1efe21d77879276f959cb37edc3d089cdcd8d8f9738ef1d78257e37`

### D-INT-014

Run:

`trm_fem_941ce23d715c_cal_01_wsv21_rfobs1`

Delta T:

`-210.1757128216158 C`

Deck SHA256:

`863b41c5cc1c8b57d6805ff533a24014a392879be8f346d5d24025666906616a`

Preparation-record SHA256:

`8eb8e0a49fdcf6d73c9f2888a32bb4f18113b2c66f2006adb3b027b603f8a235`

### D-INT-015

Run:

`trm_fem_34fffb87e0f7_cal_01_wsv21_rfobs1`

Delta T:

`-253.5382976681505 C`

Deck SHA256:

`0e88df8e20631862d4d6aca374e65d5c7b0812d523548b0d420daeefec660ae5`

Preparation-record SHA256:

`f787276289df03f021db5ce596f864fac2fa438a819b55f5b27c3829d1168c72`

### D-INT-016

Run:

`trm_fem_c74956ffff17_cal_01_wsv21_rfobs1`

Delta T:

`-241.05204304189587 C`

Deck SHA256:

`e405d68998148b7feb9fb6fb2cd1d98c87522adb9623730d5c18b8e3dee19842`

Preparation-record SHA256:

`59d0c0dd734c023df87a95b8f48a4d9e4610d5f33b332e3e171d7e1af41a3209`

Independent post-publication audit:

- published cases verified: 5 / 5,
- deck SHA drift: NO,
- preparation-record SHA drift: NO,
- solver-result artifacts present: NO,
- CalculiX invoked: NO,
- FEM solutions executed: NO,
- meshes generated: NO,
- source WSV21 evidence mutated: NO,
- holdouts accessed: NO,
- equilibrium PASS claimed: NO,
- equilibrium tolerance changed: NO.

## 13. Software regression and repository hygiene

Focused frozen-lineage / equilibrium-applicability regression:

**11 passed**

Focused calibration-deck / reaction-observability regression:

**13 passed**

Final repository regression after Gate-1 hardening:

**PASS ? all tests passed with zero failures/errors**

The exact aggregate pytest count was not retained in the terminal
capture used for this record and is therefore not fabricated here.

Repository hygiene checks before certification:

- `git diff --check`: clean,
- `complete_nut.py`: no content diff,
- unrelated `scripts/run_cp8_overnight_warm_start.py`: excluded from
  this Gate-1 scope.

## 14. Certification boundaries

This certification does not:

- authorize Gate 0,
- authorize Production-DOE FEM execution,
- expose blind-holdout coordinates,
- alter the frozen 24-row public design matrix,
- alter the 6-case blind-holdout population,
- increase the maximum fresh-solve budget,
- weaken any preload-calibration acceptance criterion,
- weaken the `0.001 N` equilibrium tolerance,
- reinterpret historical support-only equilibrium failures as PASS,
- certify arbitrary geometries or bolt/joint families outside the
  documented diversified applicability envelope,
- claim universal industrial applicability.

ThreadROM remains a governed portfolio/research-grade engineering
project over its explicitly documented and validated applicability
domain.

## 15. Final disposition

The final diversified Phase-3 Production-DOE matrix is certified.

Gate 1 establishes:

- immutable frozen DOE policy and campaign identity,
- exact deterministic reproduction of all 24 public design rows,
- preserved ordering and case hashes,
- 4 certified existing anchors,
- 20 governed fresh design states,
- 6 sealed blind holdouts,
- reconciliation of 15 accepted and 5 remaining fresh FEM states,
- governed normalization of D-INT-008,
- explicit historical equilibrium-observability limitations,
- complete reaction observability for all five remaining Trial-1
  sibling decks,
- frozen-lineage compatibility without reverting current global
  execution identity semantics,
- immutable publication and independent verification of all five
  `rfobs1` preparations,
- no unnecessary duplicate FEM execution.

**PRE-DOE GATE 1 ? FINAL DIVERSIFIED PRODUCTION DOE MATRIX: PASS**

Remaining engineering gate before diversified Production DOE:

1. Gate 0 ? final DOE authorization

**DOE execution authorization: NOT YET GRANTED**

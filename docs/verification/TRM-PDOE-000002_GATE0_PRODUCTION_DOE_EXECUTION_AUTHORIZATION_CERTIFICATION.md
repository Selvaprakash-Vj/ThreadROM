# TRM-PDOE-000002 — Gate-0 Production DOE Execution Authorization Certification

**Record ID:** TRM-PDOE-000002
**Project:** ThreadROM
**Phase:** Phase 3 / CP11 pre-DOE hardening
**Gate:** Gate 0 — Final Production DOE Execution Authorization
**Status:** PASS
**Date:** 2026-09-18
**Campaign:** TRM-PDOE-C01

---

## 1. Purpose

This record certifies the final pre-execution Gate-0 authorization boundary for the
ThreadROM Phase-3 diversified Production DOE campaign.

Gate 0 does not certify FEM results.

Gate 0 certifies that the remaining governed Production DOE FEM executions may
begin only through an explicit, immutable, fail-closed execution-authorization
contract and only for the exact five certified reaction-observable Trial-1
siblings listed in this record.

No CalculiX solve was executed in order to produce this certification.

---

## 2. Upstream certified evidence

Gate 0 is bound to the following frozen upstream evidence.

### 2.1 Gate-1 final diversified Production DOE matrix certification

- Record: `TRM-PDOE-000001`
- Path:
  `docs/verification/TRM-PDOE-000001_FINAL_DIVERSIFIED_PRODUCTION_DOE_MATRIX_CERTIFICATION.md`
- Source commit:
  `ed3b357af87132ee1070c5abbc21cf5b991be152`
- SHA256:
  `743ea4bfa99994bcec5783e7d63aa5f03d5cef72256e795c533bef578c033ee3`
- Status: PASS
- DOE execution authorization in that record: NOT YET GRANTED

Gate 0 therefore does not reinterpret Gate 1. It supplies the separate execution
authorization explicitly required by the frozen campaign governance.

### 2.2 Frozen Production DOE policy

- Policy ID: `TRM-PDOE-000001`
- Path: `config/phase3_production_doe.toml`
- SHA256:
  `43032557cb2abead0118362bcfc6a9b2e5246a7d363ca83eef5fcf35054befc1`

The frozen policy explicitly does not authorize solver execution merely by being
frozen.

### 2.3 Frozen campaign manifest

- Record ID: `TRM-P3-CP8-PDOE-C01-MANIFEST-001`
- Status: FROZEN
- SHA256:
  `84516519bbb188664268936e2d116e133431d90d037bed407ffb2d1fe92d2a67`

The frozen campaign manifest remains unchanged and non-authorizing. Gate-0
authorization is issued through a separate immutable execution-certification
record.

---

## 3. Gate-0 immutable execution certification

The independent zero-solve Gate-0 certifier published:

`simulations/staging/phase3_cp8_production_doe/TRM-PDOE-C01/production_doe_gate0_execution_certification.json`

Certified SHA256:

`1de14304d291c8b5c4dfd763bafec41492128b2cba8eb9471b13c1390b6ecad6`

The published SHA matched the deterministic dry-run candidate SHA exactly.

Overall disposition:

`PRODUCTION_DOE_GATE0_EXECUTION_CERTIFIED_READY_FOR_FEM`

The certification authorizes exactly five remaining Production DOE design cases
and no others.

---

## 4. Authorized execution scope

| Case | Authorized run ID | Frozen ΔT [°C] | rfobs1 preparation SHA256 | Deck SHA256 |
| --- | --- | ---: | --- | --- |
| D-INT-012 | `trm_fem_d667bb1aca27_cal_01_wsv21_rfobs1` | -265.947254200 | `b5a88ff926b49c774d1f209162e07740993eacd392ee8b72ede8c57a44f366be` | `c270aa1a08186538b9f64829f07373de531949988466b7b2cff3c3fbad2c7e8d` |
| D-INT-013 | `trm_fem_039053767417_cal_01_wsv21_rfobs1` | -230.586629046 | `f3d8b8b1f1efe21d77879276f959cb37edc3d089cdcd8d8f9738ef1d78257e37` | `ea768a358a970bff7d760e1e7ad0c79afa0ac96226999de0fe5755bb9f59b5e4` |
| D-INT-014 | `trm_fem_941ce23d715c_cal_01_wsv21_rfobs1` | -210.175712822 | `8eb8e0a49fdcf6d73c9f2888a32bb4f18113b2c66f2006adb3b027b603f8a235` | `863b41c5cc1c8b57d6805ff533a24014a392879be8f346d5d24025666906616a` |
| D-INT-015 | `trm_fem_34fffb87e0f7_cal_01_wsv21_rfobs1` | -253.538297668 | `f787276289df03f021db5ce596f864fac2fa438a819b55f5b27c3829d1168c72` | `0e88df8e20631862d4d6aca374e65d5c7b0812d523548b0d420daeefec660ae5` |
| D-INT-016 | `trm_fem_c74956ffff17_cal_01_wsv21_rfobs1` | -241.052043042 | `59d0c0dd734c023df87a95b8f48a4d9e4610d5f33b332e3e171d7e1af41a3209` | `e405d68998148b7feb9fb6fb2cd1d98c87522adb9623730d5c18b8e3dee19842` |

Authorization is limited to these exact Trial-1 run identities and their exact
certified preparation/deck hashes.

---

## 5. Reaction-output contract

Each authorized `rfobs1` preparation was independently verified to contain all
nine governed constrained reaction carriers:

1. `BOLT_HEAD_GUIDANCE_REFERENCE`
2. `BOLT_HEAD_ROTATION_X_REFERENCE`
3. `BOLT_HEAD_ROTATION_Y_REFERENCE`
4. `HEAD_MEMBER_SUPPORT_BAND`
5. `NUT_MEMBER_GUIDANCE_REFERENCE`
6. `NUT_ROTATION_GUIDANCE_REFERENCE`
7. `NUT_ROTATION_X_REFERENCE`
8. `NUT_ROTATION_Y_REFERENCE`
9. `NUT_TRANSLATION_GUIDANCE_REFERENCE`

All five preparations certified:

- constrained reaction carriers: 9/9,
- observable reaction carriers: 9/9,
- missing reaction carriers: 0,
- full-system equilibrium PASS pre-claimed: NO,
- equilibrium tolerance changed: NO.

Reaction observability is therefore certified as an output contract only.
It is not a pre-claim of post-solve equilibrium acceptance.

---

## 6. Zero-solve certification evidence

The Gate-0 certifier independently verified:

- all five immutable `rfobs1` preparations,
- all five preparation SHA sidecars,
- all five exact `rfobs1` deck hashes,
- all source V2.1 preparation/deck bindings,
- certified mesh hashes,
- certified STEP hashes,
- FEM preflight PASS for every authorized case,
- Trial-1 semantics preserved,
- frozen V2.1 ΔT preserved,
- no mesh regeneration,
- no deck regeneration,
- no V2.1 refit,
- no solver result read,
- no existing FEM run manifest,
- no existing governed accepted evidence,
- no solver output in the authorized sibling directories,
- no blind-holdout access.

CalculiX invoked by Gate-0 certification: NO.

FEM solve performed by Gate-0 certification: NO.

---

## 7. Dedicated fail-closed execution path

Gate 0 introduces the dedicated runner:

`scripts/run_phase3_production_doe_rfobs1_case.py`

The runner is pinned to the exact immutable Gate-0 certification SHA256:

`1de14304d291c8b5c4dfd763bafec41492128b2cba8eb9471b13c1390b6ecad6`

Before the runner may reach the single CalculiX orchestration call, it verifies:

- Gate-0 certification SHA,
- FINAL / READY_FOR_FEM disposition,
- authorization semantics,
- exact authorized case membership,
- exact authorized run membership,
- frozen Production DOE case identity,
- exact `rfobs1` preparation SHA,
- exact `rfobs1` deck SHA,
- Trial-1 identity,
- frozen ΔT,
- 9/9 reaction-output observability,
- clean FEM preflight,
- no prior solver outputs,
- no existing FEM run manifest,
- no existing accepted FEM evidence,
- holdout exclusion.

A semantic static audit verified that the `--dry-run` return occurs before the
single `orchestrate_calculix_run(...)` call.

---

## 8. Positive execution-path dry-run

All five authorized cases were exercised through the dedicated runner with
`--dry-run`.

Result:

- D-INT-012: PASS
- D-INT-013: PASS
- D-INT-014: PASS
- D-INT-015: PASS
- D-INT-016: PASS

For every case:

- exact authorization: VERIFIED,
- exact `rfobs1` preparation: VERIFIED,
- exact `rfobs1` deck: VERIFIED,
- duplicate/partial outputs: NONE,
- CalculiX invoked: NO,
- FEM launched: NO.

---

## 9. Negative fail-closed execution proof

Two negative execution-path checks were performed.

### 9.1 Unauthorized design case

Requested:

`D-INT-011`

Result:

REFUSED because the case is outside the Gate-0-certified `rfobs1` scope.

### 9.2 Synthetic holdout-prefix case

Requested:

`H-GATE0-NEGATIVE-TEST`

Result:

REFUSED by the blind-holdout execution guard.

The synthetic identifier was used only to exercise the guard path. No blind
holdout coordinates were read or exposed.

Both negative checks exited non-zero with the expected rejection.

Unauthorized execution: REFUSED.

Holdout execution: REFUSED.

---

## 10. Execution governance

Gate-0 authorization is bounded as follows:

- authorized cases: exactly 5,
- authorized executions: exact `rfobs1` Trial-1 siblings only,
- maximum concurrent CalculiX runs: 4,
- fresh full solve required: YES,
- historical checkpoint resume authorized: NO,
- additional calibration trial authorized by Gate 0: NO,
- Trial 2 authorized by Gate 0: NO,
- Trial 2 requires separate governed post-reject preparation and authorization,
- V2.1 prediction must remain frozen,
- reaction-output contract must remain frozen,
- equilibrium tolerance change authorized: NO,
- blind-holdout execution authorized: NO,
- blind holdouts remain sealed: YES.

---

## 11. Repository regression

After Gate-0 implementation and execution-path verification, the full repository
regression completed successfully:

`928 passed in 539.99s (0:08:59)`

No regression failure or error remained.

---

## 12. Certification boundaries

This record does not claim:

- that the five remaining FEM solves have already been executed,
- that their realized clamp-force acceptance has already passed,
- that full-system equilibrium has already passed,
- that Trial 2 is authorized,
- that blind holdouts are authorized for execution,
- that the Production DOE campaign is complete,
- that Phase 3 is complete,
- that a Phase-4 ROM has begun,
- universal industrial applicability.

ThreadROM remains a portfolio/research-grade engineering project whose validated
applicability is bounded by the explicitly documented fastener, joint, material,
load, mesh and solver configuration envelope.

---

## 13. Gate-0 disposition

**PASS**

The final pre-execution authorization boundary is certified.

The five remaining governed Production DOE `rfobs1` Trial-1 FEM executions are
authorized under the immutable Gate-0 execution contract.

No other Production DOE execution is authorized by this record.

Blind holdouts remain sealed.

Equilibrium tolerance remains unchanged.

No FEM solve was consumed merely to establish this authorization.

**PRE-DOE GATE 0 — FINAL PRODUCTION DOE EXECUTION AUTHORIZATION: PASS**

**PRODUCTION DOE EXECUTION: AUTHORIZED FOR THE FIVE CERTIFIED RFOBS1 TRIAL-1 RUNS ONLY**

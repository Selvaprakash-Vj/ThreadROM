# ThreadROM — Current State and Resume Guide

**Engineering checkpoint date:** 2026-09-23
**Document purpose:** Quick project handover and exact resumption instructions.
**Current engineering phase:** Phase 3 — governed DOE evidence completion.
**Factory qualification:** Six of six bounded qualification gates closed.
**First ROM:** Not started; belongs to Phase 4.

> Read this document first when resuming ThreadROM after a break or
> starting a new conversation. It records the latest verified checkpoint
> available when written. It is not a live solver-status monitor or a
> substitute for the current Git tree and authoritative FEM evidence.

---

## 1. Start here

ThreadROM develops a governed, parametric bolted-joint engineering
workflow and, subsequently, reduced-order models (ROMs).

The immediate goal is to complete the explicitly bounded Phase-3 DOE,
certify the engineering dataset and begin the first ROM in Phase 4.

Do not extend the immediate project scope to universal metric-fastener
FEM certification before the first bounded ROM.

### Essential references

| Question | Read |
|---|---|
| What has been achieved and what remains? | [Phase-3 engineering reference](THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md) |
| Which source file owns a responsibility? | [Repository Atlas](THREADROM_REPOSITORY_ATLAS.md) |
| What is the frozen C01 parameter envelope? | `../config/phase3_production_doe.toml` |
| What is the frozen C01 design inventory? | `../simulations/staging/phase3_cp8_production_doe/TRM-PDOE-C01/production_doe_campaign_manifest.json` |
| What does the actual implementation currently do? | Read the current source, tests and governed evidence. |

The engineering reference documents the historical six-gate milestone.
The atlas is generated from the repository and includes source symbols,
static imports, tests and navigation paths.

Neither document grants a new FEM launch or independently certifies
an individual solver result.

---

## 2. Latest verified software milestone

**Factory software and bounded C01 preparation qualification: CLOSED.**

| Gate | Verified disposition |
|---|---|
| G1 — Initial Trial-1 admission and launch safety | Closed |
| G2 — New-case port and evidence-safe recovery | Closed |
| G3 — Supervisor lifecycle dry run | Closed |
| G4 — Two-group material software transfer | Closed |
| G5 — Frozen C01 geometry and mesh preparation | Closed |
| G6 — Full regression and reconciled inventory | Closed |

The full repository regression reported on 2026-09-23 was:

`1157 passed in 555.92s (0:09:15)`

This verifies the tested software state at that checkpoint. Re-run the
appropriate verification after subsequent source changes.

The six-gate milestone does **not** mean that every DOE case has passed
independent physics acceptance or that Phase 3 is complete.

---

## 3. Current physical qualification boundary

The qualified frozen C01 preparation path covers the documented
M10×1.5 campaign and its coupled radial-geometry path:

- Both clamped members follow the same radial-geometry configuration.
- Member outer diameter varies from 30 mm to 36 mm.
- Clearance-hole diameter varies from 11 mm to 12 mm.
- The governed mesh policies include `medium` and `medium_plus_v1`.

The software transfer path supports two material groups:

- Bolt and nut: same material identity and matching elastic properties.
- Upper and lower members: same material identity and matching elastic
  properties.
- Fastener and member groups may differ.

Distinct elastic-property transfer to a real generated CalculiX deck
was tested. Mixed-material *physical FEM qualification* has not been
established by that software test.

M8/M12 and arbitrary metric-fastener FEM qualification are not
established by the frozen C01 evidence. Consult the engineering
reference for the campaign exclusions.

---

## 4. Latest reconciled C01 filesystem inventory

The last reported read-only inspection of the frozen design inventory
established:

| Item | Observed count |
|---|---:|
| Frozen design cases | 24 |
| Sealed holdout cases | 6 |
| Case-local preparation records | 19 |
| Cases with a run manifest at an inspected trial path | 11 |
| Run manifests at inspected trial paths | 16 |
| Additional trial directories without a local run manifest | 15 |
| Total inspected trial directories | 31 |
| A00–A03 cases awaiting governed existing-evidence binding | 4 |
| Frozen manifest design-case launch flags set to true | 0 |

**These are filesystem observations, not complete physics dispositions.**

The 15 directories without a local run manifest contain preparation
records and solver input decks. Do not infer from this that the case
was never executed elsewhere, that its FEM failed or that a replacement
solve is needed.

The frozen manifest's historical `PLANNED_UNEXECUTED` field must not
override more recent authoritative trial-history evidence.

### Specific evidence-handling requirements

- `A00`–`A03`: Review governed binding to existing historical evidence.
  Do not treat the absence of case-local solver directories as
  authorization to generate replacement FEM runs.
- `D-BND-001`: Previously existing Trial-1 and Trial-2 evidence was
  recovered without rerunning either trial. Its conservative supervisor
  recovery stopped at engineering review without inferring a new
  full-physics certificate.
- `D-BND-004`: Its two solver-preparation records reference
  `D-BND-002`'s verified STEP/mesh evidence. Preserve this reuse path.
- Previously recorded accepted evidence for the C01 interior cases must
  be reconciled through its authoritative records, not overwritten by
  a narrower trial-directory inventory.

Do not inspect, train on or alter sealed holdout case contents as part
of routine DOE training-data preparation.

---

## 5. Repository checkpoint captured when this file was created

The following values were read directly from the local Git repository
before this document was written.

| Field | Value |
|---|---|
| Branch | `main` |
| HEAD commit | `19a74e94d15a6e4352d434d43256ad897a6a3659` |
| Working-tree state | 40 changed/untracked Git-status entries before creating this document. Review the actual diff before committing. |

The six-gate verification was previously reported against a working
tree containing modified and untracked factory source and tests.

**A clean, committed and pushed checkpoint of those changes was not
established by the reported full-regression output.**

Do not assume the current HEAD contains every qualified factory change
until the intended working-tree changes have been reviewed and committed.

This Git snapshot does not establish whether a solver is currently
running. Check runtime state independently before any solver-related
operation.

---

## 6. Immediate next workflow

### P3-R1 — Preserve the verified factory source checkpoint

**This is the next project milestone.**

1. Verify the actual branch, HEAD, working-tree diff and untracked files.
2. Distinguish intended factory source/tests/documentation from
   generated reports, temporary files and unrelated changes.
3. Verify that the six-gate implementation and its tests are included
   in the reviewed checkpoint scope.
4. Run the required verification on the final candidate source state.
5. Commit the deliberately selected files and push only after the
   resulting checkpoint has been verified.

Do not automatically stage the entire repository. Do not modify or
delete historical FEM evidence during checkpoint preparation.

### P3-R2 — Reconcile existing DOE evidence

Establish authoritative trial and case-level dispositions. Review
A00–A03 evidence binding and preserve valid historical accepted,
failed, rejected and incomplete states.

### P3-R3 — Certify engineering evidence

Check applicable calibration, solver convergence, equilibrium,
contact, mesh, geometry and physical acceptance criteria for each
candidate training sample.

Solver exit, deck generation and run-manifest presence are not
substitutes for full engineering acceptance.

### P3-R4 — Execute only genuinely necessary FEM

Identify remaining evidence gaps, prove that reuse cannot satisfy
them, obtain separate exact-case authorization and apply the
governed launch/capacity safeguards.

No new solve is authorized by this document.

### P3-R5 — Freeze the ROM-ready dataset

Confirm dataset quality, parameter coverage, provenance, case
independence, accepted targets, sealed evaluation partitions and
predeclared ROM accuracy criteria.

Only then begin the first ROM in Phase 4.

---

## 7. Hard operational boundaries

- No unapproved Trial-1 launch or automatic solver restart.
- No duplicate FEM run merely because an inventory script misses
  an expected record.
- No alteration of historical solver evidence or certification records.
- No inference of a full physics certificate from preparation,
  solver completion or accepted calibration alone.
- No automatic continuation from an uncertain engineering state.
- No unsealing of holdout cases for routine training or debugging.
- No universal FEM or ROM applicability claim without corresponding
  documented validation evidence.
- No silent change to the frozen C01 physical envelope.

---

## 8. How to resume in a future chat

Read this document and the companion engineering reference first.

Then inspect the **actual current Git and runtime state**. If those
differ from this snapshot, reconcile the difference before modifying
the repository or launching any FEM work.

Use the Repository Atlas to locate the exact source owner and
relevant tests. Prefer one bounded, assumption-checked PowerShell
action at a time and verify its output before proceeding.

For a running FEM job, inspect process health, solver progress,
increment/convergence history, output growth and governed
disposition before making any intervention.

For a proposed new FEM solve, first establish that no valid
existing evidence can satisfy the requirement.

---

## 9. Maintaining this checkpoint

Update this file after a meaningful project milestone, such as:

- A reviewed Git checkpoint is committed and pushed.
- Existing DOE evidence is formally bound or certified.
- An authorized FEM campaign advances.
- The ROM-ready dataset is frozen.
- Phase 4 begins or a new ROM version is independently validated.

Each update must distinguish:

**Observed facts → authoritative evidence → current limitations →
remaining work → next permitted action.**

Replace stale Git/run-status fields only after checking the actual
repository and governing records.

Do not silently rewrite earlier physical or software qualification
claims. Record corrections with their supporting evidence.

**Latest verified milestone at initial creation:** Six bounded
factory-qualification gates closed; Phase-3 dataset completion pending.
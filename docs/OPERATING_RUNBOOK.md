# ThreadROM — Operating Runbook

**Initial version:** 2026-09-23
**Purpose:** Safe operation, observation, recovery and verification of the governed ThreadROM engineering/FEM factory.
**Current workflow:** Phase 3 — governed DOE evidence completion.

> Read [CURRENT_STATE.md](CURRENT_STATE.md) before using this runbook.
> It identifies the latest verified project checkpoint and next permitted
> action. This runbook defines operating procedures; it does not grant
> permission to execute FEM or supersede the governing case records.

---

## 1. Essential references

| Information required | Authoritative starting point |
|---|---|
| Current milestone and next action | [CURRENT_STATE.md](CURRENT_STATE.md) |
| Engineering scope and six-gate history | [Phase-3 Engineering Reference](THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md) |
| File ownership, symbols, dependencies and tests | [Repository Atlas](THREADROM_REPOSITORY_ATLAS.md) |
| Frozen C01 configuration and exclusions | [Phase-3 DOE policy](../config/phase3_production_doe.toml) |
| Launch reservation and capacity controls | [Launch fence](../src/threadrom/factory/production_doe_launch_fence.py) |
| Historical trial verification and recovery | [Trial history](../src/threadrom/factory/production_doe_trial_history.py) |
| Initial Trial-1 owner authorization | [Initial launch authorization](../src/threadrom/factory/governed_fem_initial_launch_authorization.py) |
| Initial-case lifecycle and recovery | [Initial live port](../src/threadrom/factory/governed_fem_initial_live_port.py) |
| C01 adaptive continuation | [Adaptive C01 live port](../src/threadrom/factory/adaptive_fem_c01_live_port.py) |

**Scope warning:** The six factory-qualification gates are closed for the
bounded C01 software/preparation workflow. That is not universal metric
fastener FEM certification, blanket solver authorization, complete
case-level physics certification or a ROM-ready dataset declaration.

The current frozen C01 campaign is M10x1.5. Its material and geometry
qualification boundaries are documented in the engineering reference.

---

## 2. Operation classes and authorization

Every proposed operation must be classified before execution.

| Class | Examples | Required precaution |
|---|---|---|
| R0 — Read-only | Git inspection, evidence inventory, process monitoring, source inspection | Verify target identity; do not read sealed holdout contents. |
| R1 — Repository-changing | Source patch, test creation, documentation update, Git commit | Inspect existing changes; use assumption-checked writes and verify results. |
| R2 — Case-artifact-writing | New CAD, mesh, preparation record, deck or calibration preparation | Confirm exact governed case/trial, output ownership and existing evidence before writing. |
| R3 — Solver execution | Launch, relaunch, restart or continuation involving CalculiX | Require all applicable independent authorization, durable reservation, capacity, provenance and evidence gates. |
| R4 — Evidence promotion | Binding, acceptance certification or dataset admission | Require the actual governing verification contract and authoritative supporting evidence. |

**Critical:** An R0/R1 success never automatically authorizes R2, R3 or R4.

Neither a passing test suite, a frozen manifest entry, an existing deck nor
a supervisor's request to launch is independent owner authorization.

An existing trial must never be relaunched merely because a convenience
script does not find its expected manifest or certificate.

---

## 3. Start-of-session checklist

Before changing code or touching simulation artifacts:

1. Confirm the intended repository, branch and HEAD commit.
2. Inspect tracked modifications and untracked files.
3. Read the current project checkpoint and identify the exact next action.
4. Determine whether any solver or factory launcher is active.
5. Identify the exact campaign, case, trial and authoritative evidence
   relevant to the proposed operation.
6. Confirm that the action does not access sealed holdout contents.
7. Establish the operation class from Section 2.
8. Define its expected result and a clear fail-closed stop condition.

### 3.1 Read-only repository status

Run from PowerShell:

```powershell
Set-Location D:\ThreadROM
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
```

`git diff --check` verifies selected working-tree formatting conditions.
It does not certify source behaviour, FEM physics or repository cleanliness.

Do not use `git add -A`, `git reset --hard`, `git clean`, a forced checkout
or broad deletion as a routine way to prepare a checkpoint. Review the
specific affected paths first.

### 3.2 Read-only process inspection

```powershell
Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match '^(ccx|python|pythonw)(\.exe)?$'
    } |
    Select-Object ProcessId, ParentProcessId, Name, CommandLine
```

Use the reported command lines to distinguish an active ThreadROM job from
an unrelated Python or CalculiX process. Process presence alone does not
prove that the intended trial is healthy or making progress.

Process command lines may contain local paths or other sensitive values.
Avoid copying unrelated process details into public reports.

**Do not terminate an ambiguous process.** Determine its identity and
relationship to the governed trial before considering intervention.

---

## 4. Resolving a case before any preparation or solve

The source of truth is the governed case definition and its current
authoritative evidence, not an informal filename or an earlier chat.

Establish the following:

| Identity | Required evidence |
|---|---|
| Campaign | Exact campaign ID, policy and frozen manifest identity |
| Design case | Canonical case, case ID and case hash |
| Resolved case | Resolution identity and applicable engineering inputs |
| Geometry/mesh | Artifact identity, configuration, mesh policy and verified provenance |
| Trial | Exact trial ID, previously attempted states and existing outputs |
| Solver deck | Deck identity, hash and applicable preparation certification |
| Authorization | Exact-case/trial owner approval and valid launch reservation, if an R3 action is proposed |

Check whether the intended engineering question can be answered by a
previously certified result. Reuse is allowed only where the existing
evidence supports the same applicable physical configuration and quantity.

A previous run's existence is not sufficient to establish equivalence.

### 4.1 Specific C01 reuse rules

- **A00–A03:** Their frozen design entries request governed binding to
  existing evidence. Do not automatically prepare replacement cases or
  launch new solves because their derived case-local directories are empty.
- **D-BND-001:** Existing Trial-1 and Trial-2 evidence was recovered.
  Do not rerun it. Use its authoritative case-level engineering disposition.
- **D-BND-004:** Existing solver-preparation records reference D-BND-002's
  verified STEP and mesh. Preserve that intentional geometry/mesh reuse.
- **Prepared-only trial directories:** Presence of a preparation record and
  `.inp` file does not establish that a solver was executed or that a
  replacement solve is justified.

The dated evidence inventory is summarized in
[CURRENT_STATE.md](CURRENT_STATE.md). Reconcile it against the actual
authoritative trial history before acting.

---

## 5. Preparing a new case — governed workflow

**Operation class: R2.**

Preparation is permitted only when the exact case is in scope and existing
evidence cannot supply the required prepared state.

The required sequence is:

1. Resolve the governed case and validate its membership and supported scope.
2. Verify materials, standards, geometry, interfaces and loading.
3. Check existing case-specific geometry, mesh and preparation evidence.
4. Select the governed mesh policy derived from the case.
5. Produce artifacts only through the existing controlled preparation path.
6. Verify all required geometry, mesh, registration and solver-preparation
   gates and associated artifact hashes.
7. Record the resulting preparation disposition without claiming solver
   execution or physics acceptance.

Relevant implementation entry points include:

- `scripts/prepare_phase3_production_doe_case.py`
- `scripts/prepare_phase3_production_doe_solver_case.py`
- `src/threadrom/factory/governed_fem_physical_preparation.py`
- `src/threadrom/factory/fem_case_definition_bundle.py`

**Command safety:** Do not derive a production command merely from the
script filename. Inspect the current CLI parser, exact trial identity,
guards and output paths before documenting or executing a writing action.

The runbook intentionally contains no unverified case-preparation
command-line flags.

---

## 6. Launching or continuing FEM — governed workflow

**Operation class: R3. This section is a checklist, not launch permission.**

A valid candidate for a new solve must pass all applicable requirements:

- The exact case and trial are part of an authorized governed workflow.
- Existing acceptable evidence does not already answer the engineering
  question.
- The required preparation artifacts and identities are verified.
- The applicable initial-launch or continuation policy permits the action.
- The independent owner authorization is valid for the exact intended
  case/trial/deck/campaign where required.
- The shared durable launch fence confirms output ownership, concurrency
  limits and solver capacity.
- The correct warm-start and calibration provenance is available when
  applicable.
- There is no unresolved running, completed or uncertain trial that would
  be duplicated or overwritten.
- The intended physical acceptance criteria are known before execution.

The frozen campaign inventory recorded zero design-case manifest launch
flags set to true in the 2026-09-23 inspection. A frozen planning flag
is not a substitute for an independent approval pin.

Relevant code:

- `src/threadrom/factory/governed_fem_initial_launch_authorization.py`
- `src/threadrom/factory/production_doe_launch_fence.py`
- `scripts/run_phase3_production_doe_trial1_case.py`
- `scripts/run_phase3_production_doe_calibration_trial_case.py`
- `scripts/run_phase3_production_doe_adaptive_campaign.py`

Do not bypass the fence with a direct manual CalculiX invocation.

Do not edit a deck's preload, contacts, nodes, element IDs, boundary
conditions or material cards in an ad hoc attempt to make a case converge.

A new solver launch is never authorized solely by this documentation.

---

## 7. Monitoring a running FEM job

**Operation class: R0.**

For a running nonlinear FEM job, a complete monitor should cover:

| Area | Required observation |
|---|---|
| Identity | Campaign, case, trial, job name, deck hash and output directory |
| Process health | Launcher and CalculiX process identity, parent relationship and liveness |
| Compute | CPU progress, process memory, system memory and available storage |
| File activity | Solver output sizes, timestamps and sustained growth |
| Numerical progress | Step, increment, attempt, accepted increment and simulation time |
| Nonlinear convergence | Iteration counts, residual/convergence history and cutback/retry events |
| Warnings/errors | Relevant solver messages, termination indicators and I/O failures |
| Completion | Whether the solver actually finished and produced required outputs |
| Engineering status | Calibration measurement, clamp-force acceptance and subsequent physics disposition |

**Never report a solver as converged, accepted or certified merely because
its process is no longer running.**

### 7.1 Read-only process-health command

First determine the exact process ID from Section 3.2.

Then, using that verified PID:

```powershell
$solverPid = 12345  # REPLACE with the verified CalculiX process ID

Get-Process -Id $solverPid -ErrorAction Stop |
    Select-Object Id, ProcessName, CPU, WorkingSet64,
        PrivateMemorySize64, StartTime, Responding
```

The numeric PID above is illustrative, not a known active ThreadROM job.
The `CPU` value is cumulative CPU time. Obtain successive observations
before inferring progress or a stall.

### 7.2 Read-only solver-output activity

Set `$trialDirectory` only after identifying the exact existing trial.

```powershell
$trialDirectory = "D:\ThreadROM\simulations\staging\phase3_cp8_production_doe\TRM-PDOE-C01\solver_preparation\EXACT_CASE_RUN_ID\EXACT_TRIAL_RUN_ID"

if (-not (Test-Path -LiteralPath $trialDirectory -PathType Container)) {
    throw "Exact governed trial directory not found."
}

Get-ChildItem -LiteralPath $trialDirectory -File |
    Where-Object {
        $_.Extension -in @(
            ".rout", ".sta", ".dat", ".frd", ".cvg", ".log"
        )
    } |
    Sort-Object LastWriteTime -Descending |
    Select-Object Name, Length, LastWriteTime
```

This lists direct files without recursively scanning the entire campaign
or reading potentially enormous solver-result files into memory.

File growth alone is not accepted-increment progress. Use the appropriate
solver output and governed monitor/verification code to establish actual
increment, cutback, convergence and completion states.

### 7.3 Intervention policy

Before considering cancellation or restart:

1. Verify the exact job and its current owner.
2. Check recent accepted increments, retries, CPU activity and output growth.
3. Determine whether the solver is legitimately progressing slowly.
4. Check system resources and actual error indicators.
5. Review the governing recovery and launch-capacity rules.
6. Preserve the present evidence and record the reason for any intervention.

Do not impose an arbitrary 16-hour cap on a justified fine-mesh FEM run.

---

## 8. Interrupted, uncertain and partially completed trials

The objective is to preserve recoverable evidence and avoid duplicate
execution, not to force every state into a success/failure classification.

### 8.1 Process absent; outputs present

Do not infer solver completion from process absence.

Check the exact trial identity, output state, governing run manifest,
termination markers and accepted-increment history.

Use the trial-history verification machinery to distinguish a verified
completed trial from an incomplete or uncertain one.

### 8.2 Deck exists; no run manifest at the expected path

A prepared solver input may intentionally have no local run manifest.

Determine whether another authoritative trial-history or execution
record exists elsewhere before classifying the trial as unexecuted.

Do not create a synthetic completion manifest or automatically relaunch.

### 8.3 Partial outputs or uncertain ownership

Preserve files and inspect the durable claim, output ownership,
existing solver process and governed recovery state.

If the state cannot be resolved, stop for engineering review.

Do not clear locks, delete output folders or replace the deck as a
routine recovery step.

### 8.4 Completed solver; physical acceptance unknown

Keep execution completion separate from calibration acceptance,
engineering physics verification and ROM dataset admission.

An accepted calibration trial is not automatically a full physics
certificate.

### 8.5 Failed or rejected trial

Retain the failed realised state, available measurements, numerical
history, provenance and explicit failure reason.

A corrective continuation requires the applicable governed adaptation
policy and fresh authorization where required.

Do not silently exclude failures from the engineering evidence history.

---

## 9. Evidence verification and promotion

**Operation class: R4 when a disposition or dataset state is changed.**

The following states are distinct:

| State | Meaning |
|---|---|
| Case defined | Canonical engineering inputs exist. |
| Geometry/mesh prepared | Required preparation artifacts and checks exist. |
| Solver deck prepared | An input deck exists with governed preparation provenance. |
| Solver executing | An identified execution is active or being monitored. |
| Solver completed | Completion is established by the required execution evidence. |
| Calibration accepted | The applicable calibration target and acceptance checks passed. |
| Physics accepted | Required case-specific physical validation has been verified. |
| Dataset admitted | The sample meets the independent ROM dataset admission contract. |
| Engineering review | Evidence is incomplete, ambiguous or requires a governed decision. |
| Rejected/failed | An explicit recorded reason prevents the relevant promotion. |

Promotion must be supported by the appropriate authoritative record
and verification rules. It cannot be inferred from the existence of
an adjacent state.

For ROM use, the accepted sample must also have a consistent target
definition, units, provenance, applicability and dataset-partition status.

Future detailed schemas and admission procedures belong in
`EVIDENCE_AND_DATASET_GUIDE.md` once that companion document is created.

---

## 10. Safe verification of repository software

**Operation class: R0 for a source-inspecting test run, subject to the
individual tests' actual side effects.**

The following full-suite command was used successfully at the
2026-09-23 factory checkpoint:

```powershell
Set-Location D:\ThreadROM

.\.venv\Scripts\python.exe -m pytest -q
```

The reported checkpoint result was:

`1157 passed in 555.92s (0:09:15)`

A new test run verifies the code in its then-current state; the
historical result is not a guarantee after further source changes.

Some tests create temporary files. Before running an unfamiliar suite,
review its setup/fixtures and use a controlled temporary directory
where appropriate.

The generated repository atlas can be checked without rewriting it:

```powershell
Set-Location D:\ThreadROM

.\.venv\Scripts\python.exe `
    .\scripts\generate_threadrom_repository_atlas.py --check
```

The atlas check confirms reproducibility against the current selected
source inventory; it does not verify FEM physics or certify a case.

---

## 11. Source changes and Git checkpoint procedure

Before modifying source:

1. Establish the target function, calling contract and relevant tests
   using the Repository Atlas and current source.
2. Review the current working-tree diff and unrelated modifications.
3. Make one bounded, assumption-checked change.
4. Confirm the exact changed paths and review the resulting diff.
5. Run focused tests, then the required broader regression.
6. Confirm there are no unintended generated or historical-evidence
   changes.
7. Deliberately select files for the checkpoint.

Do not interpret a passing regression as evidence that every untracked
file belongs in the commit.

For the 2026-09-23 checkpoint, modified source, new factory tests and
new documentation coexisted with other untracked items. Review all
candidate files rather than staging everything indiscriminately.

A Git commit or push does not independently certify engineering physics.

---

## 12. Immediate Phase-3 operating sequence

The six bounded factory-qualification gates are closed.

The remaining practical sequence is:

1. Preserve the reviewed factory source and documentation checkpoint.
2. Reconcile existing trial evidence and bind eligible A00–A03 history.
3. Establish authoritative case-level physics dispositions.
4. Identify genuine evidence gaps and authorize only necessary FEM work.
5. Verify the resulting engineering samples and freeze the ROM-ready
   dataset.
6. Start the first bounded ROM in Phase 4.

Cross-size universalization, additional material combinations and
other ROM families require their own scope and qualification evidence.
They are not implied by the completed C01 factory gate record.

---

## 13. Future update requirements

Update this runbook whenever a governed operational interface changes,
especially:

- Solver admission, exact-case authorization or launch fence behaviour.
- Preparation and trial-history record schemas.
- Supported recovery and adaptation actions.
- Monitoring and physics-verification entry points.
- Case-specific acceptance and dataset-admission workflows.

When adding an executable command, verify its actual current CLI parser,
preconditions, side effects and expected outputs first.

Label all commands as read-only, repository-changing,
case-artifact-writing, solver-executing or evidence-promoting.

Never add a convenient bypass that undermines a previously verified
safety boundary.

**Operating principle:** Determine what already exists, establish what
is actually needed, and preserve all valid evidence before spending
compute or changing a governed state.
# ThreadROM

ThreadROM is a reproducible engineering research platform for verified
three-dimensional threaded bolt-nut finite-element simulations, governed
engineering datasets, surrogate models and reduced-order modelling.

## Core principle

Verified physics first, governed data second, trustworthy AI third,
integrated product last.

## Current status

- Phase 0 — Product Design Specification: Complete
- Phase 1 — Engineering Foundation and Baseline FEM: In progress
- Current work package: WP1 — Repository, environment and engineering controls

## V1 scope

- One bolt nominal size
- One thread pitch
- One standard nut configuration
- Full three-dimensional helical threads
- Static structural analysis
- Elastic material behaviour
- Controlled bolt preload
- External axial tensile loading
- Nonlinear threaded contact
- Friction where technically justified

## Repository structure

- `docs/` — PDS, decisions, engineering records and verification evidence
- `config/` — version-controlled engineering and simulation configuration
- `schemas/` — formal configuration and data contracts
- `src/` — ThreadROM Python source code
- `scripts/` — repeatable project and simulation utilities
- `tests/` — unit, integration and regression tests
- `simulations/` — staging, accepted and rejected simulation cases
- `data/` — raw, processed and released datasets
- `models/` — surrogate and reduced-order model artefacts
- `reports/` — generated engineering reports
- `logs/` — execution and audit logs
- `archive/` — withdrawn, superseded or historical artefacts

## Source-of-truth hierarchy

1. Approved Product Design Specification
2. Approved Engineering Decision Records
3. Version-controlled configurations and schemas
4. Released engineering artefacts
5. Implementation code and automated tests
6. Working notes
7. Chat discussions

## First principal deliverable

`TRM-KO-000001` — the first accepted and reproducible ThreadROM reference
simulation knowledge object.

## Status

Research and engineering implementation in progress. ThreadROM is not currently
intended for certified design, production approval or safety-critical use.

<!-- THREADROM_DOCUMENTATION_ENTRY_POINT_V1 -->

## Documentation and current project status

**Start here:** [Current State](docs/CURRENT_STATE.md) is the
short project handover. Read it first when returning to ThreadROM or
starting a new development conversation. It records the last verified
checkpoint, the outstanding work and the next governed action.

**Checkpoint recorded on 2026-09-23:** Six of six bounded Phase-3
factory-qualification gates were closed; the full repository regression
reported 1,157 passing tests. The governed DOE still requires
case-level evidence disposition, any genuinely necessary additional
FEM work and a certified dataset freeze. The first ROM belongs to
Phase 4.

That checkpoint is historical: verify the current Git state, active
jobs and authoritative case evidence before acting. Factory software
qualification does not imply universal metric-fastener FEM validation,
complete DOE physics certification or a ROM-ready dataset.

### Choose the right reference

| When you need to? | Read |
|---|---|
| Resume work and identify the exact next action | [Current State](docs/CURRENT_STATE.md) |
| Operate, monitor or recover the FEM factory safely | [Operating Runbook](docs/OPERATING_RUNBOOK.md) |
| Understand trial evidence, acceptance and ROM dataset admission | [Evidence and Dataset Guide](docs/EVIDENCE_AND_DATASET_GUIDE.md) |
| Understand subsystems, responsibilities and interface boundaries | [Architecture and Interfaces](docs/ARCHITECTURE_AND_INTERFACES.md) |
| Understand why important engineering choices were made | [Engineering Decisions](docs/DECISIONS.md) |
| Review detailed Phase-3 qualification, limitations and ROM roadmap | [Phase-3 Factory and ROM Roadmap](docs/THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md) |
| Find source files, public symbols, imports and relevant tests | [Repository Atlas](docs/THREADROM_REPOSITORY_ATLAS.md) |

The Repository Atlas is generated from the selected repository file
inventory. Regenerate it after adding or reorganizing source files,
tests or documentation; do not manually maintain its generated tables.

### Safe starting checks

From the repository root, inspect the actual working tree:

```powershell
Set-Location D:\ThreadROM
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
```

Verify whether an FEM job is already active before performing any
solver-related operation. No new solver launch is authorized by this
README or by the six-gate factory checkpoint.

To verify that the Repository Atlas matches the current selected
repository inventory:

```powershell
Set-Location D:\ThreadROM
.\.venv\Scripts\python.exe .\scripts\generate_threadrom_repository_atlas.py --check
```

**Working principle:** Locate and verify existing engineering evidence
before preparing or launching anything new. Keep execution, physics
acceptance, dataset admission and ROM validation separate.

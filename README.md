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

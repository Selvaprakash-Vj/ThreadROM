# TRM-ADR-000001 — Open-Source FEM Toolchain

## Record information

- Decision ID: TRM-ADR-000001
- Date: 2026-07-28
- Status: Proposed
- Owner: Selvaprakash-Vj
- Related phase: Phase 1, Work Package 1

## Context

ThreadROM is intended to be published as a reproducible engineering research
project. Users must be able to clone the repository and reproduce the approved
workflow without requiring a commercial finite-element licence.

## Problem

A commercial-solver-dependent implementation would prevent independent
reproduction and conflict with the public ThreadROM project objective.

## Decision

ThreadROM V1 will use an open-source and locally runnable engineering toolchain:

- CadQuery and OpenCascade for scripted parametric geometry
- Gmsh for geometry transfer, physical groups and finite-element meshing
- CalculiX CrunchiX for structural finite-element solution
- Python for configuration, automation, verification and result extraction

ANSYS is not a required ThreadROM dependency.

Commercial solvers may be used privately for optional comparison studies, but
their results must not be required to reproduce a released ThreadROM workflow.

## Engineering justification

The selected architecture supports:

- Scripted and version-controlled geometry
- Full three-dimensional solid meshing
- Reproducible command-line execution
- Public distribution without commercial solver licences
- Automated simulation campaigns
- Traceable input decks and result extraction
- Independent reproduction by other engineers

## Conditional acceptance

CalculiX remains subject to a Phase 1 feasibility gate.

Before the baseline threaded-joint model is authorised, ThreadROM must verify
that the selected CalculiX workflow can represent:

- Elastic three-dimensional solid mechanics
- Nonlinear contact
- Frictional thread-flank interaction
- Controlled preload or an approved equivalent load sequence
- External axial loading
- Reaction-force equilibrium
- Required stress, displacement and contact outputs
- Stable and repeatable nonlinear convergence

Failure of this feasibility gate requires an ADR review before another solver
is selected.

## Alternatives considered

### ANSYS Mechanical or MAPDL

Technically capable but rejected as the mandatory V1 solver because it requires
a commercial licence and prevents universal reproduction.

### Code_Aster

Open-source and technically capable, but not selected as the initial Windows
baseline because deployment and automation are more complex.

### FreeCAD FEM workflow

Useful as an optional visual interface, but not selected as the authoritative
pipeline because ThreadROM requires configuration-driven and script-controlled
execution.

## Impact on scope

No change to the approved V1 engineering scope.

## Impact on verification

Solver feasibility and benchmark verification must be completed before the
baseline threaded-joint simulation is accepted.

## Risks introduced

- CalculiX nonlinear-contact convergence may require careful controls.
- Windows installation may require a maintained binary distribution.
- Solver-specific limitations may require controlled workarounds.
- Geometry and mesh transfer must preserve named engineering regions.

## Implementation actions

- [ ] Install and verify CalculiX CrunchiX
- [ ] Install CadQuery inside the ThreadROM environment
- [ ] Install and verify Gmsh inside the ThreadROM environment
- [ ] Execute a minimal linear-elastic solver smoke test
- [ ] Execute a controlled contact benchmark
- [ ] Verify result extraction
- [ ] Approve or revise this ADR after the feasibility gate

## Approval

- Decision status: Proposed
- Approval condition: Successful Phase 1 solver feasibility gate
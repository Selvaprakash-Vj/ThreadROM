# ThreadROM

> **Working Title:** ThreadROM -- A Physics-Constrained Surrogate
> Framework for Parameterized Threaded Fastener Simulation

**Status:** Blueprint / Project Definition (Version 0.1)

------------------------------------------------------------------------

# Vision

ThreadROM aims to build a reusable computational engineering platform
capable of accelerating high-fidelity finite element simulations of
standardized threaded bolt--nut joints using surrogate modelling.

The long-term goal is **not** to create a surrogate for one bolt. The
goal is to build a continuously growing engineering knowledge base that
eventually supports complete families of standard ISO metric fasteners
(M6, M8, M10, M12, ...), multiple pitches, lengths, materials, preload
levels, friction conditions and axial loading cases.

Every new validated simulation becomes a permanent asset of the project.

------------------------------------------------------------------------

# Motivation

High-fidelity 3D threaded contact simulations are computationally
expensive.

Typical engineering workflows require repeated simulations while
changing:

-   Bolt diameter
-   Pitch
-   Length
-   Material
-   Preload
-   External axial load
-   Friction
-   Engagement length

Running a complete nonlinear contact simulation every time is expensive.

ThreadROM investigates whether a validated surrogate can reproduce the
engineering response much faster while maintaining engineering accuracy.

------------------------------------------------------------------------

# Core Philosophy

The project is built on five principles:

1.  Engineering before AI.
2.  Physics before machine learning.
3.  Validate everything before storing it.
4.  Build incrementally.
5.  Preserve every validated simulation permanently.

------------------------------------------------------------------------

# Research Inspiration

The project is inspired by published work on embedded surrogate finite
elements, especially research from Sandia National Laboratories.

However, ThreadROM extends the idea toward:

-   Explicit 3D helical ISO metric threads
-   Parameterized geometry
-   Standard bolt families
-   Growing engineering knowledge base
-   Long-term reusable surrogate framework

------------------------------------------------------------------------

# Long-Term Goal

Create a parameter-driven surrogate capable of predicting the mechanical
response of standardized threaded bolt--nut joints.

Ultimately support:

-   ISO metric bolts
-   Multiple diameters
-   Multiple pitches
-   Multiple lengths
-   Standard nuts
-   Elastic material combinations
-   Preload
-   Axial loading
-   Friction

------------------------------------------------------------------------

# V1 Scope

The first validated implementation will intentionally remain small.

Reference configuration:

-   One bolt size
-   One pitch
-   One bolt length
-   One standard nut
-   Elastic materials
-   Static loading
-   Controlled preload
-   Axial external load
-   Full 3D helical thread geometry

The software architecture will remain fully parameterized from the
beginning.

------------------------------------------------------------------------

# Validation Strategy

No physical experiments are planned for Version 1.

Validation consists of:

1.  Analytical calculations
2.  Engineering standards
3.  Published literature
4.  Mesh convergence
5.  High-fidelity FEM verification
6.  Surrogate comparison against validated FEM

Only validated simulations become part of the permanent dataset.

------------------------------------------------------------------------

# Computational Knowledge Base

Every validated simulation is stored permanently.

Each case contains:

-   Input parameters
-   Geometry version
-   Mesh information
-   Solver settings
-   Validation report
-   Extracted engineering quantities
-   Full-field results (where appropriate)

The surrogate trains only from validated cases.

------------------------------------------------------------------------

# Planned Workflow

1.  Define parameters
2.  Generate CAD
3.  Generate mesh
4.  Solve in FEM
5.  Verify & validate
6.  Store results
7.  Expand dataset
8.  Train surrogate
9.  Improve continuously

------------------------------------------------------------------------

# Software Architecture (High Level)

ThreadROM/ - docs/ - engine/ - cad/ - meshing/ - solver/ - validation/ -
datasets/ - models/ - results/ - scripts/ - tests/

------------------------------------------------------------------------

# Success Criteria

The project should demonstrate:

-   Reliable engineering predictions
-   Significant computational speed-up
-   Reproducible workflow
-   Fully traceable simulations
-   Expandable architecture
-   Clear applicability limits

------------------------------------------------------------------------

# Future Versions

## V1

Single validated bolt family.

## V2

Additional diameters, pitches and preload ranges.

## V3

Multiple materials and expanded parameter space.

## V4

Unified conditioned surrogate covering multiple standardized bolt
families.

## Future Research

Potential future topics include:

-   Plasticity
-   Fatigue
-   Thermal loading
-   Dynamic loading
-   Loosening
-   Washers
-   Different nut types
-   Manufacturing tolerances
-   Active learning for adaptive simulation generation

------------------------------------------------------------------------

# Immediate Next Milestone

Before building the surrogate:

Build the **ThreadROM Engine**.

The engine will automate:

Parameters → CAD → Mesh → FEM → Validation → Dataset

Only after this pipeline is reliable will surrogate development begin.

------------------------------------------------------------------------

# Guiding Principle

> Build slowly. Validate thoroughly. Preserve everything. Grow
> continuously.

This document is the project's living blueprint and should evolve as
ThreadROM matures.

# ThreadROM Parametric Analytical Engine Contract

## Purpose

The ThreadROM analytical engine provides governed, reusable and
fully parametric engineering calculations for threaded-fastener
assemblies.

The engine is not an M10-specific calculator. The M10 x 1.5 joint
is the first governed benchmark used to verify the general system.

The engine provides:

- independent analytical predictions;
- FEM validation targets;
- rapid parameter-space screening;
- physics-derived features for reduced-order models;
- engineering warnings, assumptions and validity flags;
- machine-readable and human-readable results.

## Design principles

1. Inputs, modelling assumptions and calculated results remain
   explicitly separated.
2. No engineering identity, property class, material strength or
   geometry value is hard-coded into reusable calculation logic.
3. All internal engineering calculations use one governed unit
   convention.
4. Every selectable analytical method is named in the result.
5. Every result records its assumptions and validity limitations.
6. Existing baseline analytical modules remain regression
   references until the replacement engine is fully verified.
7. Local FEM quantities are never compared against incompatible
   nominal analytical quantities.

## Supported canonical inputs

### Thread definition

- nominal diameter;
- pitch;
- thread form and included angle;
- external and internal thread classes;
- handedness and number of starts;
- optional custom pitch, minor and root diameters;
- optional manufacturing dimensions and tolerances.

### Bolt definition

- nominal length;
- threaded and unthreaded axial segments;
- shank diameters;
- head geometry;
- effective head participation model;
- material and strength reference;
- optional washer geometry.

### Nut definition

- nut thickness;
- thread engagement length;
- bearing geometry;
- effective nut participation model;
- material and strength reference;
- optional washer geometry.

### Clamped-member stack

- arbitrary number of member layers;
- thickness of every layer;
- elastic modulus and Poisson ratio of every layer;
- clearance-hole diameter;
- member outer or effective diameter;
- bearing diameters;
- optional washers;
- selected compression-spread model.

### Loading definition

- assembly preload;
- optional external axial service load;
- optional cyclic load range;
- load-introduction position or factor;
- preload scatter;
- thermal or settlement effects in later versions.

### Analytical-method selections

- tensile-area method;
- bolt-compliance method;
- head-participation method;
- nut-participation method;
- member-compression method;
- external-load-introduction method;
- thread-load-distribution method;
- strength and separation acceptance criteria.

## Required calculated outputs

### Thread geometry

- fundamental triangle height;
- basic pitch diameter;
- external minor diameter;
- internal minor diameter;
- tensile-stress area;
- root cross-sectional area;
- engaged pitch count;
- thread shear areas.

### Bolt mechanics

- preload stress and strain;
- segment compliances;
- total bolt compliance;
- bolt elongation;
- bolt stiffness;
- elastic strain energy;
- proof, yield and ultimate utilisation;
- strength margins.

### Member mechanics

- compression area or effective pressure cone;
- layer compliances;
- total member compression;
- member stiffness;
- mean bearing pressures;
- interface clamp force.

### Complete joint behaviour

- joint stiffness ratio;
- external-load fraction carried by the bolt;
- bolt-load increment;
- clamp-load loss;
- remaining clamp force;
- separation load;
- separation margin;
- maximum service bolt load;
- service-load stress range.

### Thread engagement

- load carried by each engaged thread;
- first-thread load fraction;
- cumulative load transfer;
- bolt-thread and nut-thread deformation contributions;
- stripping and shear utilisation;
- engagement-length sensitivity.

## FEM comparison contract

Analytical and FEM quantities must use compatible definitions.

| Analytical quantity | Compatible FEM extraction |
|---|---|
| Nominal bolt stress | Section-averaged axial stress |
| Bolt elongation | Relative displacement between governed gauge planes |
| Bolt stiffness | Pretension force divided by bolt elongation |
| Member compression | Relative displacement across the clamped stack |
| Member stiffness | Clamp force divided by member compression |
| Bearing pressure | Area-averaged contact pressure |
| Thread load share | Integrated axial contact force per thread turn |
| External equilibrium | Sum of all external forces and reactions |
| Thread-root stress | Mesh-converged local stress or calibrated notch model |

The nominal stress F divided by tensile-stress area must not be
compared directly with a singular or highly local thread-root peak.

## Comparison metrics

Where meaningful, comparison records contain:

- analytical value;
- FEM value;
- absolute difference;
- signed relative difference;
- absolute relative error;
- selected acceptance tolerance;
- pass, fail or not-comparable status;
- explanation of model-form differences.

## Method hierarchy

The analytical engine supports multiple fidelity levels:

1. Basic nominal formulas.
2. Segmented bolt and annular-member spring model.
3. Compression-cone and multilayer member model.
4. Discrete engaged-thread load-distribution model.
5. Calibrated analytical model using selected FEM anchor cases.

Results from different methods remain separate and identifiable.
A higher-fidelity method must not silently overwrite a simpler result.

## Existing implementation disposition

| Existing component | Decision |
|---|---|
| metric_thread.py | Retain and extend |
| baseline_reference.py | Preserve as baseline wrapper |
| baseline_assembly.py | Preserve, then replace with canonical inputs |
| baseline_capacity.py | Generalise equations into reusable mechanics |
| baseline_joint_stiffness.py | Preserve as legacy simplified benchmark |
| Baseline Markdown reports | Replace hard-coded metadata |
| Existing baseline unit tests | Preserve as regression tests |

## First governed benchmark

- Simulation: TRM-SIM-000009
- Mesh: TRM-MSH-000008
- Thread: M10 x 1.5
- Preload: 5000 N
- Grip length: 20 mm
- Nut engagement: 8 mm
- Bolt and member modulus: 210000 MPa
- Friction coefficient: 0.15

This benchmark verifies the general engine but does not define its
supported parameter range.

## Checkpoint acceptance

Checkpoint 1 is complete when this contract is present, the existing
analytical implementation has been classified, and the legacy
baseline calculations are explicitly retained as regression
references.

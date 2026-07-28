# ThreadROM Baseline Assembly Definition

## Status

Proposed reference assembly for Phase 1.

## Identity

- Assembly: TRM-ASM-000001
- Geometry: TRM-GEO-000001
- Simulation: TRM-SIM-000001

## Assembly stack

- M10 × 30 fully threaded hexagon-head screw
- Upper clamped member: 10 mm
- Lower clamped member: 10 mm
- Total grip length: 20 mm
- Nut thickness and thread engagement: 8 mm
- Thread protrusion beyond nut: 2 mm

The complete axial stack is therefore:

30 mm = 20 mm grip + 8 mm nut + 2 mm protrusion

## Clamped-member geometry

The initial members are coaxial cylindrical bodies:

- Outer diameter: 30 mm
- Clearance-hole diameter: 11 mm
- Two members of equal thickness

This controlled geometry reduces unrelated plate-edge effects while retaining
the bearing, member-interface and bolt-load-transfer behaviour required for the
baseline joint study.

## Proposed loading

- Target bolt preload: 20,000 N
- External axial tensile load: 8,000 N
- Sequence: preload first, external tension second

These values remain subject to analytical elastic-capacity and joint-stiffness
verification before FEM execution.

## Proposed contact model

- Thread-flank contact: frictional
- Bolt-head bearing contact: frictional
- Nut bearing contact: frictional
- Clamped-member interface: frictional
- Initial friction coefficient: 0.15

The friction value is a controlled baseline parameter, not a claim about every
real fastener surface condition.

## Exclusions

- Washers
- Manufacturing tolerance variation
- Surface roughness
- Coatings
- Plasticity
- Damage
- Fatigue
- Loosening

## Approval gate

TRM-ASM-000001 remains Proposed until:

1. Bolt elastic stress under preload is checked.
2. Preload is compared with the property-class reference limits.
3. External-load sharing is estimated analytically.
4. Member compression and bolt stiffness are calculated.
5. Load and boundary-condition application regions are documented.
6. The baseline geometry is generated and dimensionally verified.
# ThreadROM Baseline Fastener Definition

## Status

Proposed reference configuration for Phase 1.

## Persistent identities

- Geometry: TRM-GEO-000001
- Material: TRM-MAT-000001
- Mesh: TRM-MSH-000001
- Simulation: TRM-SIM-000001
- Knowledge Object: TRM-KO-000001

## Reference joint

- Thread designation: M10 × 1.5
- Thread form: ISO metric, right-hand, single-start
- External thread tolerance: 6g
- Internal thread tolerance: 6H
- Screw family: ISO 4017:2022
- Screw property class: 8.8
- Nut family: ISO 4032:2023, style 1
- Nut property class: 8
- Nominal screw length: 50 mm

## Material model

The initial FEM reference model uses homogeneous, isotropic, linear-elastic
steel:

- Young's modulus: 210 GPa
- Poisson's ratio: 0.30
- Density: 7850 kg/m³

Property classes define the physical fastener family and future allowable-load
reasoning. Plasticity is explicitly outside the V1 baseline simulation.

## Geometry scope

Included:

- Full three-dimensional helical external thread
- Full three-dimensional helical internal thread
- Bolt head
- Hexagonal style-1 nut body
- Controlled thread engagement

Initially excluded:

- Manufacturing tolerance variation
- Thread runout
- Surface roughness
- Coatings
- Plasticity
- Damage
- Wear
- Fatigue

## Engineering rationale

M10 × 1.5 provides a practical reference size with sufficient geometric scale
for controlled three-dimensional meshing while remaining computationally
manageable for repeated development and verification runs.

The reference family is intentionally fixed. Additional diameters, pitches,
standards or nut styles require a future approved Engineering Decision Record.

## Approval gate

This definition remains Proposed until:

1. Standard dimensions are entered and independently checked.
2. Analytical tensile-area and stiffness calculations are completed.
3. Thread-profile geometry is verified.
4. The selected engagement and grip arrangement are frozen.
5. TRM-ADR-000002 is approved.
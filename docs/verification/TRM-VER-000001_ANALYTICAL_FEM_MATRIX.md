# TRM-VER-000001 Analytical-to-FEM Verification Matrix

## Purpose

This artifact defines the governed Phase 1 verification relationship between
the `TRM-ANL-000001` analytical model and
`TRM-SIM-000010`.

A `pending` result is not a failed engineering check. It means that the
required accepted solver state, extractor or dedicated simulation is not yet
available.

An `inconclusive_solver` result means that a governed solver attempt was made,
but it produced no accepted equilibrium state suitable for analytical-to-FEM
comparison. It is neither a PASS nor a FAIL of the analytical prediction.

## Controlled model identity

| Field | Value |
|---|---|
| Verification ID | TRM-VER-000001 |
| Analytical joint | TRM-ANL-000001 |
| FEM simulation | TRM-SIM-000010 |
| Mesh level | coarse |
| Element type | C3D10 |
| Overall status | INCONCLUSIVE |
| Resolved targets | 0 |
| Unresolved targets | 8 |

## Status summary

| Evidence status | Target count |
|---|---:|
| pass | 0 |
| fail | 0 |
| inconclusive solver | 6 |
| pending solver | 0 |
| pending extractor | 0 |
| dedicated simulation required | 2 |

## Verification matrix

| Target | Quantity | Analytical value | Unit | Evidence status | Acceptance metric | Relative tolerance | Absolute tolerance |
|---|---|---:|---|---|---|---:|---:|
| pretension_ramp | Commanded pretension-force ramp | 5000 | N | inconclusive_solver | relative_or_absolute | 0.0001% | 1e-06 N |
| external_support_equilibrium | Preload-only external support reaction | 0 | N | inconclusive_solver | absolute | — | 0.001 N |
| final_preload_force | Final governed preload force | 5000 | N | inconclusive_solver | relative_or_absolute | 0.0001% | 1e-06 N |
| nominal_bolt_stress | Nominal bolt tensile stress at 5 kN | 86.2223617188 | MPa | inconclusive_solver | relative | 10% | — |
| bolt_stiffness | Bolt axial stiffness | 405927.178313 | N/mm | inconclusive_solver | relative | 10% | — |
| member_stiffness | Clamped-member axial stiffness | 6424164.27751 | N/mm | inconclusive_solver | relative | 15% | — |
| separation_load | Joint separation load | 5315.93773196 | N | dedicated_simulation_required | relative | 10% | — |
| first_thread_load_share | First engaged thread-turn load share | 21.4470973405 | % | dedicated_simulation_required | absolute | — | 5 % |

## Target evidence contracts

### `pretension_ramp`

- Quantity: Commanded pretension-force ramp
- Current status: `inconclusive_solver`
- FEM observable: BOLT_PRETENSION_REFERENCE RF1 at every accepted increment
- Extraction source: CalculiX DAT and STA accepted-increment history
- Evidence artifact: `docs/verification/TRM-SIM-000010_CLAMP_SMOKE_OUTCOME.json`
- Notes: The corrected deck commanded -250 N, -500 N and -750 N, but no equilibrium increment was accepted. The commanded deck contract is verified; the accepted physical force ramp is not.

### `external_support_equilibrium`

- Quantity: Preload-only external support reaction
- Current status: `inconclusive_solver`
- FEM observable: Maximum absolute component of HEAD_MEMBER_SUPPORT_BAND total reaction
- Extraction source: CalculiX DAT TOTALS=ONLY records
- Evidence artifact: `docs/verification/TRM-SIM-000010_CLAMP_SMOKE_OUTCOME.json`
- Notes: No accepted equilibrium state exists from which a governed external-support reaction can be extracted.

### `final_preload_force`

- Quantity: Final governed preload force
- Current status: `inconclusive_solver`
- FEM observable: BOLT_PRETENSION_REFERENCE RF1 at accepted step time 1.0
- Extraction source: CalculiX DAT and STA accepted final increment
- Evidence artifact: `docs/verification/TRM-SIM-000010_CLAMP_SMOKE_OUTCOME.json`
- Notes: The corrected 750 N smoke model diverged before its first accepted increment. The governed 5 kN final preload was therefore not reached.

### `nominal_bolt_stress`

- Quantity: Nominal bolt tensile stress at 5 kN
- Current status: `inconclusive_solver`
- FEM observable: Section-averaged axial stress over a governed threaded bolt section
- Extraction source: CalculiX FRD element stress field
- Evidence artifact: `docs/verification/TRM-SIM-000010_CLAMP_SMOKE_OUTCOME.json`
- Notes: No accepted physical pretension state exists. Stress values from unconverged Newton iterations are not admissible verification evidence.

### `bolt_stiffness`

- Quantity: Bolt axial stiffness
- Current status: `inconclusive_solver`
- FEM observable: Preload increment divided by governed bolt reference-plane elongation
- Extraction source: CalculiX FRD displacement field at accepted increments
- Evidence artifact: `docs/verification/TRM-SIM-000010_CLAMP_SMOKE_OUTCOME.json`
- Notes: The corrected nonlinear model produced no accepted preload-displacement state. Bolt stiffness cannot be calculated from unconverged iteration fields.

### `member_stiffness`

- Quantity: Clamped-member axial stiffness
- Current status: `inconclusive_solver`
- FEM observable: Preload increment divided by governed member-stack shortening
- Extraction source: CalculiX FRD displacement field at accepted increments
- Evidence artifact: `docs/verification/TRM-SIM-000010_CLAMP_SMOKE_OUTCOME.json`
- Notes: The corrected nonlinear model produced no accepted member-compression state. Member stiffness cannot be verified.

### `separation_load`

- Quantity: Joint separation load
- Current status: `dedicated_simulation_required`
- FEM observable: First governed loss of compressive member-interface contact under external separation loading
- Extraction source: Dedicated nonlinear separation-load simulation
- Evidence artifact: `not yet available`
- Notes: A preload-only smoke simulation cannot observe joint separation. A stabilised preload state and dedicated external-separation simulation are required.

### `first_thread_load_share`

- Quantity: First engaged thread-turn load share
- Current status: `dedicated_simulation_required`
- FEM observable: Integrated normal contact force on turn 1 divided by total engaged-thread flank force
- Extraction source: Dedicated contact-output simulation with per-turn flank groups
- Evidence artifact: `not yet available`
- Notes: The current deck does not request governed per-turn integrated contact forces. A stabilised contact solution and dedicated per-turn output groups are required.

## Current fidelity statement

The analytical model is internally validated, but full analytical-to-FEM
verification is not yet established.

An `inconclusive_solver` classification records an attempted governed
simulation that produced no accepted equilibrium state suitable for
comparison. It does not validate or invalidate the analytical prediction.

PASS or FAIL classifications require matching FEM observables extracted from
accepted solver states. Targets without such evidence remain pending or
require dedicated simulations.

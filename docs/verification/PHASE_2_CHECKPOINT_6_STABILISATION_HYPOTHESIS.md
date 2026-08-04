# Phase 2 Checkpoint 6 — Nonlinear Stabilisation Hypothesis

## Governed baseline

`TRM-SIM-000010` used the corrected pretension reference-force sign:

- `reference_force_sign = -1`
- Total target preload: 750 N
- Three preload checkpoints: 250 N, 500 N and 750 N
- Initial time increment: 1.0
- Step time: 1.0
- Maximum time increment: 1.0

The first 250 N checkpoint was therefore attempted in one complete nonlinear
increment.

## Observed failure signature

No equilibrium increment was accepted.

During the first increment and first attempt:

| Iteration | Contact spring elements | Residual force |
|---:|---:|---:|
| 1 | 511110 | 3.916e4 % |
| 2 | 274894 | 2.107e5 % |
| 3 | 171109 | 6.962e7 % |

The solver output also showed:

- Maximum displacement increment of approximately 0.552 mm before iteration 3.
- Maximum displacement increment and correction of approximately 5.53 mm at
  iteration 3.
- Rapid contact-element loss while residual force diverged.

## Stabilisation hypothesis

The corrected pretension direction is retained.

The first governed hypothesis is that the initial 250 N contact-seating transition
was too abrupt when applied in one nonlinear increment. The first stabilisation
experiment will therefore change only the load-ramp granularity.

No change will be made initially to:

- Geometry
- Mesh
- Pretension-section orientation
- Pretension reference-force sign
- Boundary conditions or guidance constraints
- Contact-pair definitions
- Contact pressure-overclosure stiffness
- Friction coefficient
- Friction stick-slope ratio
- Total preload
- Preload checkpoint forces

## First stabilisation experiment

The new governed simulation identity will be `TRM-SIM-000011`.

Proposed nonlinear controls:

| Control | TRM-SIM-000010 | TRM-SIM-000011 |
|---|---:|---:|
| Initial time increment | 1.0 | 0.02 |
| Minimum time increment | 1.0e-6 | 1.0e-6 |
| Maximum time increment | 1.0 | 0.02 |
| Step time | 1.0 | 1.0 |
| Maximum increments per step | 100 | 100 |

For the first 250 N checkpoint, a time increment of 0.02 corresponds to a
nominal 5 N load increment.

Using the same value for the initial and maximum increment deliberately prevents
the solver from immediately growing back toward a large load jump. This isolates
load-ramp granularity as the experimental variable.

## Acceptance gate

The first experiment is not required to complete the entire 750 N ramp before it
can provide useful evidence.

The immediate gate is:

1. At least one equilibrium increment is accepted.
2. The accepted increment uses the corrected negative reference-force sign.
3. Under-head and nut-bearing motion represents physical joint compression rather
   than joint opening.
4. Contact participation remains finite and does not collapse catastrophically.
5. Residual and displacement corrections trend toward convergence.
6. Only accepted-increment results may be used as physical evidence.

Failure to satisfy these conditions will trigger a new governed hypothesis rather
than uncontrolled simultaneous changes to contact, mesh and constraints.

No solver was launched while defining this hypothesis.

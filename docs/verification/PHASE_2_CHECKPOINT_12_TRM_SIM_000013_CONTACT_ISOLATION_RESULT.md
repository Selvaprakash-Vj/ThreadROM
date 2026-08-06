# Phase 2 Checkpoint 12 - TRM-SIM-000013 Contact-Isolation Result

## Purpose

TRM-SIM-000013 tested whether overlap between the bolt pretension cut and the
bolt-thread contact surface caused the previously observed bearing-interface
opening.

The validated positive-sign pretension experiment from TRM-SIM-000012 was
retained. Only the bolt-thread contact surface was changed so that all contact
faces touching pretension-section nodes were excluded.

## Governed experiment

- Simulation ID: `TRM-SIM-000013`
- Pretension model ID: `TRM-PTN-000008`
- Target preload: `750 N`
- First nominal increment: `5 N`
- Reference-force sign: `+1`
- Friction coefficient: `0.15`
- Element formulation: `C3D10`
- Deck SHA256:
  `8DA16BA3C26164DF3938DC1B3F26F0CDE2C30909403D99D82CA63CE83181DA43`
- Experiment-definition commit: `b1a1d99`
- Contact-isolation implementation commit: `4d0ebff`

## Pretension/contact topology correction

The original topology audit identified:

- Pretension-section faces: `763`
- Pretension-section nodes: `1590`
- Bolt-thread contact faces touching pretension nodes: `271`
- Pretension nodes overlapping the bolt-thread contact surface: `126`

TRM-SIM-000013 excluded every bolt-thread contact triangle touching a protected
pretension-section node.

The corrected deck contained:

- Original bolt-thread contact faces: `21676`
- Corrected bolt-thread contact faces: `21405`
- Removed contact faces: `271`
- Remaining pretension/contact overlap nodes: `0`
- Preserved pretension-section faces: `763`

The structural contact-isolation gate therefore passed before launch.

## Numerical result

Step 1, Increment 1 and Increment 2 were accepted.

### Increment 1

- Accepted time: `0.020000`
- Nominal accepted preload: `5 N`

### Increment 2

- Accepted time: `0.040000`
- Nominal accepted preload: `10 N`
- Iterations: `18`

At evidence capture, CalculiX was solving:

- Step: `1`
- Increment: `3`
- Attempt: `1`
- Iteration: `5`

The solver remained responsive and reported no stderr output.

## Geometry-aware physical clamp gate

Negative signed gap change denotes compression.

### Increment 1 - time 0.020000

#### Under-head bearing interface

- Signed gap change:
  `+6.116081335358e-4 mm`
- Result: **FAIL - interface opening**

#### Nut bearing interface

- Signed gap change:
  `+2.094950326924e-3 mm`
- Result: **FAIL - interface opening**

### Increment 2 - time 0.040000

#### Under-head bearing interface

- Signed gap change:
  `+8.610229054764e-4 mm`
- Result: **FAIL - interface opening**

#### Nut bearing interface

- Signed gap change:
  `+4.188891787444e-3 mm`
- Result: **FAIL - interface opening**

## Comparison with TRM-SIM-000012

The first accepted increment was numerically identical to the corresponding
TRM-SIM-000012 physical response:

| Interface | TRM-SIM-000012 | TRM-SIM-000013 |
|---|---:|---:|
| Under-head signed gap change | +6.116081335358e-4 mm | +6.116081335358e-4 mm |
| Nut-bearing signed gap change | +2.094950326924e-3 mm | +2.094950326924e-3 mm |

Removing all pretension/contact overlap therefore did not alter the first
accepted physical response.

## Engineering conclusion

The overlap between the pretension cut and the bolt-thread contact surface was
a real modelling defect and was correctly removed.

However, it was not the root cause of the bearing-interface opening.

The contact-overlap hypothesis is therefore falsified.

The remaining investigation must distinguish between:

- zero-load contact or constraint settling;
- kinematic effects introduced by the pretension-section node duplication and
  internal MPCs;
- pretension normal and reference-force semantics;
- interaction between pretension kinematics and the full-joint guidance
  constraints;
- initial geometric imbalance or contact positioning.

No further full-scale pretension simulation should be launched until these
mechanisms have been isolated using fast diagnostic models.

## Evidence preservation

Pre-shutdown and post-shutdown evidence is stored under:

`simulations/archive/TRM-SIM-000013/accepted_opening_state_20260806_100042`

The archive contains:

- governed input deck;
- accepted `.sta`, `.dat`, `.frd`, and `.cvg` results;
- solver stdout and stderr;
- launcher evidence;
- experiment configurations;
- live evidence manifest and SHA256 hashes;
- controlled-shutdown manifest and SHA256 hashes.

Evidence was preserved before CalculiX was stopped.

The controlled shutdown confirmed:

- Live files hashed: `15`
- Post-shutdown files hashed: `8`
- Matching processes remaining: `0`

## Checkpoint status

- Pretension/contact overlap removed: **PASS**
- Corrected deck topology gate: **PASS**
- Numerical stabilisation: **PASS**
- First two increments accepted: **PASS**
- Physical clamp behaviour: **FAIL**
- Contact-overlap hypothesis: **FALSIFIED**
- First accepted physically correct clamp state: **NOT YET ACHIEVED**

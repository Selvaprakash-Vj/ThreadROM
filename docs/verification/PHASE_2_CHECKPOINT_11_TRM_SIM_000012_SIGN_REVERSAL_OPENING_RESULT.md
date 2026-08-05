# Phase 2 Checkpoint 11 — TRM-SIM-000012 Sign-Reversal Opening Result

## Purpose

TRM-SIM-000012 tested whether reversing the pretension-reference force sign
would convert the previously observed bearing-interface opening into physical
clamping.

The validated stabilised increment controls from TRM-SIM-000011 were retained.
Only the pretension checkpoint-force direction was reversed.

## Governed experiment

- Simulation ID: `TRM-SIM-000012`
- Pretension model ID: `TRM-PTN-000007`
- Target preload: `750 N`
- First nominal increment: `5 N`
- Reference-force sign: `+1`
- Friction coefficient: `0.15`
- Element formulation: `C3D10`
- Deck SHA256:
  `CD4A4C799A37E52AE6FB8C19B37CB5FBA2BB051FA490C15625635C2156D24FEF`
- Experiment-definition commit: `6fb6483`

## Prelaunch equivalence result

After normalising simulation identifiers, the TRM-SIM-000011 and
TRM-SIM-000012 decks were identical except for three `*CLOAD` sign reversals:

| Checkpoint | TRM-SIM-000011 | TRM-SIM-000012 |
|---|---:|---:|
| Step 1 target | -250 N | +250 N |
| Step 2 target | -500 N | +500 N |
| Step 3 target | -750 N | +750 N |

The stabilised static controls remained:

`0.02, 1.0, 1.0e-6, 0.02`

## Numerical result

Step 1, Increment 1 was accepted:

- Accepted time: `0.020000`
- Nominal accepted preload: `5 N`
- Iterations: `15`
- Converged contact spring elements: `135677`

CalculiX confirmed that the positive reference force was applied:

- Reference force: `+5.000000 N`
- Reference displacement: `+3.100895e-7 mm`

For comparison, TRM-SIM-000011 produced:

- Reference force: `-5.000000 N`
- Reference displacement: `-2.941938e-7 mm`

Therefore, the configured force-sign reversal was genuinely applied by
CalculiX.

## Geometry-aware physical clamp gate

Negative signed gap change denotes compression.

### Under-head bearing interface

- Bolt under-head mean D3:
  `-6.116081335334e-4 mm`
- Head-member mean D3:
  `+2.377533918917e-15 mm`
- Bolt outward normal Z: `+1`
- Member outward normal Z: `-1`
- Signed gap change:
  `+6.116081335358e-4 mm`
- Result: **FAIL — interface opening**

### Nut bearing interface

- Nut lower-bearing mean D3:
  `+2.094950359367e-3 mm`
- Nut-member mean D3:
  `+3.244310333665e-11 mm`
- Nut outward normal Z: `-1`
- Member outward normal Z: `+1`
- Signed gap change:
  `+2.094950326924e-3 mm`
- Result: **FAIL — interface opening**

## Comparison with TRM-SIM-000011

Both force directions produced nearly identical bearing-interface opening:

| Interface | TRM-SIM-000011 | TRM-SIM-000012 |
|---|---:|---:|
| Under-head signed gap change | +6.120112798227e-4 mm | +6.116081335358e-4 mm |
| Nut-bearing signed gap change | +2.094950374778e-3 mm | +2.094950326924e-3 mm |

The reference-node displacement reversed direction, but the physical joint
motion did not.

## Engineering conclusion

The pretension reference-force sign is **not** the root cause of the
bearing-interface opening.

The sign-reversal hypothesis is therefore falsified.

The remaining investigation must focus on the pretension implementation
itself, including:

- section coupling and load transfer;
- pretension-section orientation and internal kinematics;
- reference-node degree-of-freedom interpretation;
- generated pretension-element connectivity;
- unintended rigid-body or release behaviour;
- whether the current formulation creates axial separation rather than bolt
  shortening and member compression.

## Evidence preservation

Pre-shutdown and post-shutdown evidence is stored under:

`simulations/archive/TRM-SIM-000012/accepted_opening_state_20260805_201241`

The archive contains:

- governed input deck;
- accepted `.sta`, `.dat`, `.frd`, and `.cvg` results;
- solver stdout and stderr;
- launcher evidence;
- experiment configurations;
- live evidence manifest and SHA256 hashes;
- controlled-shutdown manifest and SHA256 hashes.

The solver was stopped only after the accepted failed state had been
preserved.

## Checkpoint status

- Numerical stabilisation: **PASS**
- Configured sign reversal applied: **PASS**
- First increment accepted: **PASS**
- Physical clamp behaviour: **FAIL**
- First accepted physically correct clamp state: **NOT YET ACHIEVED**

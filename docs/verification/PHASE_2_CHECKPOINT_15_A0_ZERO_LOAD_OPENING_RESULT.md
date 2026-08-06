# Phase 2 Checkpoint 15 — A0 Zero-Load Opening Result

## Purpose

Determine whether the complete-joint bearing interfaces open before a
pretension section or reference force is introduced.

## Diagnostic identity

| Field | Value |
|---|---|
| Diagnostic | `TRM-DIAG-000002` |
| Simulation | `TRM-SIM-000014` |
| Mesh | `TRM-MSH-000009` |
| Element type | `C3D4` |
| Case | `A0` |
| Pretension section | Absent |
| Applied reference force | `0.0 N` |
| Contact pairs | `4` |
| Guidance samples | `240` |
| Isolated thread-contact faces | `271` |

## Solver outcome

CalculiX remained responsive and accepted five nonlinear increments before
the governed 1800-second timeout.

| Increment | Time | Iterations |
|---:|---:|---:|
| 1 | 0.050000 | 18 |
| 2 | 0.100000 | 18 |
| 3 | 0.150000 | 9 |
| 4 | 0.200000 | 20 |
| 5 | 0.250000 | 9 |

The partial solver evidence was archived at:

`simulations/archive/TRM-DIAG-000002/a0_partial_20260806_225552`

The archive contains the input deck, FRD results, convergence and status
files, solver logs, run manifest, and SHA-256 hashes.

## Geometry-aware bearing motion

Negative signed gap change denotes compression. Positive signed gap change
denotes opening.

| Increment | Time | Under-head gap change [mm] | Nut-bearing gap change [mm] |
|---:|---:|---:|---:|
| 1 | 0.050000 | +4.258420810056e-03 | +2.219786825553e-03 |
| 2 | 0.100000 | +7.322099357542e-03 | +4.779208823538e-03 |
| 3 | 0.150000 | +9.552136787710e-03 | +7.310563389189e-03 |
| 4 | 0.200000 | +9.950431759777e-03 | +1.113262222113e-02 |
| 5 | 0.250000 | +1.209971703911e-02 | +1.298677950614e-02 |

Both bearing interfaces opened monotonically throughout all five accepted
increments.

The member bearing surfaces remained effectively stationary, while:

- the bolt under-head surface moved in the negative axial direction;
- the nut lower-bearing surface moved in the positive axial direction.

The fastener components therefore moved away from their respective member
bearing surfaces.

## Engineering conclusion

The opening mechanism exists with:

- no pretension section;
- no reference-node force;
- no external axial load.

The CalculiX pretension implementation and its reference-force sign are
therefore excluded as the primary cause of the opening response.

The remaining cause lies in the base complete-joint model, within one or more
of the following mechanisms:

1. initial thread-contact incompatibility or overclosure;
2. contact-pair interaction during zero-load settling;
3. guidance constraints interacting with the initial contact state;
4. an incorrect initial axial relationship between the fastener and members.

Cases A1, A2, and A3 are no longer the highest-value next runs because A0 has
already demonstrated the defect before pretension is introduced.

The next diagnostic must isolate the individual contact families in the A0
zero-load configuration, beginning with removal of the bolt-to-nut thread
contact while retaining both bearing contacts and the existing guidance.

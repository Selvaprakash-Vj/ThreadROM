# Phase 2 Checkpoint 16 - Thread-Contact Isolation Result

## Purpose

Determine whether the bolt-to-nut thread contact drives the spontaneous
bearing-interface opening observed in the zero-load A0 settling case.

## Compared cases

| Field | A0 | A0T |
|---|---|---|
| Diagnostic | `TRM-DIAG-000002` | `TRM-DIAG-000002` |
| Simulation | `TRM-SIM-000014` | `TRM-SIM-000014` |
| Mesh | `TRM-MSH-000009` | `TRM-MSH-000009` |
| Pretension section | Absent | Absent |
| Applied force | `0.0 N` | `0.0 N` |
| Guidance samples | `240` | `240` |
| Thread contact | Included | Excluded |
| Contact-pair count | `4` | `3` |

A0T retained:

- under-head bearing contact;
- nut-bearing contact;
- member-interface contact;
- the complete diagnostic guidance system.

Only the bolt-to-nut thread-contact pair was removed.

## Solver progression

Both cases reached the governed 1800-second timeout while CalculiX remained
responsive.

| Case | Accepted increments | Final accepted time |
|---|---:|---:|
| A0 | 5 | 0.250000 |
| A0T | 9 | 0.450000 |

The A0T evidence was archived at:

`simulations/archive/TRM-DIAG-000002/a0t_partial_20260807_072604`

The archive contains the input deck, result files, convergence records, solver
logs, run manifest, and SHA-256 hashes.

## Common-increment comparison

Positive signed gap denotes opening. Negative signed gap denotes compression.

| Increment | Time | A0 under-head [mm] | A0T under-head [mm] | A0 nut-bearing [mm] | A0T nut-bearing [mm] |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.050000 | +4.258420810e-03 | -1.099004977e-18 | +2.219786826e-03 | -1.659119231e-16 |
| 2 | 0.100000 | +7.322099358e-03 | +1.280711128e-17 | +4.779208824e-03 | -4.911966196e-16 |
| 3 | 0.150000 | +9.552136788e-03 | +1.365374838e-16 | +7.310563389e-03 | +5.925209933e-16 |
| 4 | 0.200000 | +9.950431760e-03 | +4.097780316e-17 | +1.113262222e-02 | +2.147222776e-15 |
| 5 | 0.250000 | +1.209971704e-02 | +9.614879086e-17 | +1.298677951e-02 | +2.447964491e-15 |

Removing thread contact reduced both bearing-interface openings by effectively
100 percent.

Across all nine accepted A0T increments:

- under-head signed gap remained within approximately `1.4e-16 mm` of zero;
- nut-bearing signed gap remained within approximately `2.6e-15 mm` of zero.

These values are numerical round-off rather than physical separation.

## Engineering conclusion

The bolt-to-nut thread-contact pair is the driver of the zero-load axial
separation.

The following mechanisms are excluded as primary causes:

- CalculiX pretension-section behaviour;
- reference-force sign;
- applied preload;
- under-head bearing contact;
- nut-bearing contact;
- member-interface contact;
- the retained distributed guidance system.

The remaining defect is within the initial threaded engagement state. Candidate
mechanisms are:

1. geometric interference between the helical bolt and nut thread surfaces;
2. incorrect axial or angular thread-phase alignment;
3. excessive initial contact overclosure;
4. contact normals or master/slave behaviour converting interference relief
   into axial separation.

Checkpoint 4 is therefore complete.

The next checkpoint must quantify the initial bolt-to-nut thread interference
before any nonlinear solve and identify which thread regions generate the
opposing axial motion of the bolt and nut.

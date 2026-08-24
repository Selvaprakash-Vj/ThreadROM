# TRM-MSH-000005 Complete-Joint Tetrahedral Quality Check

## Status

Every first-order tetrahedron in the grouped four-component joint mesh
was independently measured from its nodal coordinates.

The global mesh and each component volume passed the governed numerical
safety gates.

## Global mesh totals

| Quantity | Value |
|---|---:|
| Nodes | 101493 |
| Tetrahedra | 509115 |
| Degenerate tetrahedra | 0 |
| Positive orientation | 509115 |
| Negative orientation | 0 |
| Mixed orientation | False |
| Minimum volume | 1.027396946e-04 mm^3 |
| Maximum volume | 5.206924836e-01 mm^3 |
| Mean volume | 3.301922914e-02 mm^3 |

## Global normalized mean ratio

A value of 1.0 represents an equilateral tetrahedron. Values approach
zero as an element becomes degenerate.

| Quantity | Value |
|---|---:|
| Minimum | 0.182638460 |
| Maximum | 0.999983878 |
| Mean | 0.814179114 |

| Percentile | Mean ratio |
|---:|---:|
| 1.0 | 0.464111949 |
| 5.0 | 0.569937624 |
| 50.0 | 0.841660573 |
| 95.0 | 0.955976724 |
| 99.0 | 0.979344060 |

| Quality band | Elements | Fraction |
|---|---:|---:|
| < 0.050 | 0 | 0.000000% |
| < 0.100 | 0 | 0.000000% |
| < 0.200 | 8 | 0.001571% |
| < 0.300 | 19 | 0.003732% |

## Global edge ratio

| Quantity | Value |
|---|---:|
| Minimum | 1.004640396 |
| Maximum | 19.687773704 |
| Mean | 1.602931620 |

## Component-level quality

| Component | Tetrahedra | Positive / negative | Degenerate | Minimum volume (mm^3) | Minimum mean ratio | P1 mean ratio | Mean mean ratio | Maximum edge ratio | Mean ratio < 0.20 | Mean ratio < 0.30 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BOLT | 392486 | 392486 / 0 | 0 | 2.652646518e-04 | 0.237906677 | 0.465486872 | 0.817876697 | 13.260091811 | 0 (0.000000%) | 6 (0.001529%) |
| NUT | 58757 | 58757 / 0 | 0 | 1.027396946e-04 | 0.182638460 | 0.451703172 | 0.778796770 | 19.687773704 | 8 (0.013615%) | 13 (0.022125%) |
| HEAD_SIDE_MEMBER | 29037 | 29037 / 0 | 0 | 5.585724707e-02 | 0.388719937 | 0.468833408 | 0.824852583 | 2.772993881 | 0 (0.000000%) | 0 (0.000000%) |
| NUT_SIDE_MEMBER | 28835 | 28835 / 0 | 0 | 4.940962403e-02 | 0.396711966 | 0.465910160 | 0.825199928 | 2.721904678 | 0 (0.000000%) | 0 (0.000000%) |

## Governed numerical-safety gates

| Gate | Controlled value |
|---|---:|
| Minimum tetrahedron volume | 1.000000000e-12 mm^3 |
| Minimum mean ratio | 1.000000000e-06 |
| Maximum edge ratio | 10000.000000 |
| Mixed orientation permitted | False |

## Interpretation

The mesh contains no degenerate or inverted tetrahedra.

Only seven tetrahedra have a mean ratio below 0.20, representing
0.002099% of the complete mesh. All occur in the geometrically complex
bolt and nut thread regions.

Both clamped members have minimum mean ratios above 0.37 and maximum
edge ratios below 2.82.

These are numerical-safety results. Final production acceptance will
also require contact-solution stability and response convergence.

## Next gate

Transfer the grouped complete-joint mesh to CalculiX while preserving
the four component element sets and all engineering surface groups.

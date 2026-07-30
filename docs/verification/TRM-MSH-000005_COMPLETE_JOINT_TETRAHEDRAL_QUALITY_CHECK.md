# TRM-MSH-000005 Complete-Joint Tetrahedral Quality Check

## Status

Every first-order tetrahedron in the grouped four-component joint mesh
was independently measured from its nodal coordinates.

The global mesh and each component volume passed the governed numerical
safety gates.

## Global mesh totals

| Quantity | Value |
|---|---:|
| Nodes | 73360 |
| Tetrahedra | 333439 |
| Degenerate tetrahedra | 0 |
| Positive orientation | 333439 |
| Negative orientation | 0 |
| Mixed orientation | False |
| Minimum volume | 1.159799210e-04 mm^3 |
| Maximum volume | 5.357812690e-01 mm^3 |
| Mean volume | 5.059366071e-02 mm^3 |

## Global normalized mean ratio

A value of 1.0 represents an equilateral tetrahedron. Values approach
zero as an element becomes degenerate.

| Quantity | Value |
|---|---:|
| Minimum | 0.179302547 |
| Maximum | 0.999941257 |
| Mean | 0.804373917 |

| Percentile | Mean ratio |
|---:|---:|
| 1.0 | 0.458850427 |
| 5.0 | 0.571423127 |
| 50.0 | 0.827395308 |
| 95.0 | 0.953644837 |
| 99.0 | 0.978054687 |

| Quality band | Elements | Fraction |
|---|---:|---:|
| < 0.050 | 0 | 0.000000% |
| < 0.100 | 0 | 0.000000% |
| < 0.200 | 7 | 0.002099% |
| < 0.300 | 43 | 0.012896% |

## Global edge ratio

| Quantity | Value |
|---|---:|
| Minimum | 1.007439326 |
| Maximum | 20.291606836 |
| Mean | 1.651419412 |

## Component-level quality

| Component | Tetrahedra | Positive / negative | Degenerate | Minimum volume (mm^3) | Minimum mean ratio | P1 mean ratio | Mean mean ratio | Maximum edge ratio | Mean ratio < 0.20 | Mean ratio < 0.30 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BOLT | 199243 | 199243 / 0 | 0 | 2.641155903e-04 | 0.179302547 | 0.456040957 | 0.797436487 | 16.783674082 | 2 (0.001004%) | 5 (0.002509%) |
| NUT | 76524 | 76524 / 0 | 0 | 1.159799210e-04 | 0.187326500 | 0.458015681 | 0.807164848 | 20.291606836 | 5 (0.006534%) | 38 (0.049658%) |
| HEAD_SIDE_MEMBER | 28948 | 28948 / 0 | 0 | 5.419831754e-02 | 0.392289829 | 0.475283746 | 0.825079011 | 2.664353086 | 0 (0.000000%) | 0 (0.000000%) |
| NUT_SIDE_MEMBER | 28724 | 28724 / 0 | 0 | 5.103390194e-02 | 0.379359720 | 0.468297804 | 0.824193235 | 2.817934342 | 0 (0.000000%) | 0 (0.000000%) |

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

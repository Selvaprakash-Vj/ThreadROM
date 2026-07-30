# TRM-MSH-000004 Tetrahedral Nut Quality Check

## Status

Every first-order tetrahedron in the grouped nut mesh was
independently measured from its nodal coordinates.

## Mesh totals

| Quantity | Value |
|---|---:|
| Nodes | 13075 |
| Tetrahedra | 55152 |
| Degenerate tetrahedra | 0 |
| Minimum volume | 1.101875903e-04 mm^3 |
| Maximum volume | 2.871572231e-01 mm^3 |
| Mean volume | 2.352037977e-02 mm^3 |

## Orientation

| Orientation | Count |
|---|---:|
| Positive | 55152 |
| Negative | 0 |
| Mixed orientation | False |

## Normalized mean ratio

A value of 1.0 represents an equilateral tetrahedron.
Values approach zero as an element becomes degenerate.

| Quantity | Value |
|---|---:|
| Minimum | 0.165042972 |
| Maximum | 0.999226804 |
| Mean | 0.800686682 |

| Percentile | Mean ratio |
|---:|---:|
| 1.0 | 0.446904654 |
| 5.0 | 0.571946345 |
| 50.0 | 0.819177447 |
| 95.0 | 0.952103720 |
| 99.0 | 0.978363554 |

| Quality band | Elements | Fraction |
|---|---:|---:|
| < 0.050 | 0 | 0.000000% |
| < 0.100 | 0 | 0.000000% |
| < 0.200 | 7 | 0.012692% |
| < 0.300 | 46 | 0.083406% |

## Edge ratio

| Quantity | Value |
|---|---:|
| Minimum | 1.029471574 |
| Maximum | 18.789369638 |
| Mean | 1.715225423 |

## Governed numerical-safety gates

| Gate | Controlled value |
|---|---:|
| Minimum tetrahedron volume | 1.000000000e-12 mm^3 |
| Minimum mean ratio | 1.000000000e-06 |
| Maximum edge ratio | 10000.000000 |
| Mixed orientation permitted | False |

## Interpretation

These are numerical-safety gates. Mesh acceptance for threaded-contact
analysis will additionally require refinement and response-convergence
evidence.

## Next gate

Establish the controlled coarse, medium and fine nut-mesh hierarchy,
including local refinement on the internal-thread surfaces.

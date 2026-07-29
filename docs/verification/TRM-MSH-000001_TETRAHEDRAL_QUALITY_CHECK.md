# TRM-MSH-000001 Tetrahedral Quality Check

## Status

Every first-order tetrahedron in the grouped bolt mesh was independently
measured using its nodal coordinates.

## Quality metrics

### Volume

| Quantity | Value |
|---|---:|
| Nodes | 5010 |
| Tetrahedra | 19503 |
| Minimum volume | 2.336082561e-03 mm? |
| Maximum volume | 5.304900097e-01 mm? |
| Mean volume | 1.704425255e-01 mm? |
| Degenerate tetrahedra | 0 |

### Orientation

| Orientation | Count |
|---|---:|
| Positive | 19503 |
| Negative | 0 |
| Mixed orientation | False |

### Normalized mean ratio

A value of 1.0 represents an equilateral tetrahedron. Values approach zero
as an element becomes degenerate.

| Quantity | Value |
|---|---:|
| Minimum | 0.119663375 |
| Maximum | 0.999493854 |
| Mean | 0.758389030 |

| Percentile | Mean ratio |
|---:|---:|
| 1.0 | 0.324520486 |
| 5.0 | 0.358704850 |
| 50.0 | 0.823847673 |
| 95.0 | 0.956198683 |
| 99.0 | 0.978708724 |

| Quality band | Element count | Fraction |
|---|---:|---:|
| < 0.050 | 0 | 0.000000% |
| < 0.100 | 0 | 0.000000% |
| < 0.200 | 5 | 0.025637% |
| < 0.300 | 94 | 0.481977% |

### Edge ratio

The edge ratio is the longest element edge divided by the shortest edge.
The ideal value is 1.0.

| Quantity | Value |
|---|---:|
| Minimum | 1.027766881 |
| Maximum | 42.760462330 |
| Mean | 2.275956509 |

## Preliminary safety gates

| Gate | Controlled value |
|---|---:|
| Minimum tetrahedron volume | 1.000000000e-12 mm? |
| Minimum mean ratio | 1.000000000e-06 |
| Maximum edge ratio | 10000.000000 |
| Mixed orientation permitted | False |

These are numerical-safety gates only. They reject zero-volume, degenerate
or catastrophically distorted elements.

Production-quality thresholds will be selected after inspecting this measured
distribution and later validating stress convergence.

## Next gate

Use the measured distribution to define coarse, medium and fine mesh levels,
then establish thread-region refinement and convergence criteria.

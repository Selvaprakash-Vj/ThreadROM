# ThreadROM Baseline Bolt Axial-Capacity Check

## Record information

- Simulation identity: TRM-SIM-000001
- Material identity: TRM-MAT-000001
- Bolt property class: 8.8
- Status: Preliminary analytical verification

## Inputs

| Quantity | Value |
|---|---:|
| Tensile stress area | 57.989597 mm² |
| Target preload | 20000.0 N |
| External axial load | 8000.0 N |
| Proof stress reference | 580.0 MPa |
| Yield-strength reference | 640.0 MPa |
| Ultimate-strength reference | 800.0 MPa |

## Calculated capacities

| Quantity | Value |
|---|---:|
| Proof load | 33634.0 N |
| Yield load | 37113.3 N |
| Ultimate tensile load | 46391.7 N |

## Load checks

| Check | Result |
|---|---:|
| Preload stress | 344.889 MPa |
| Preload proof utilisation | 0.5946 |
| Preload target check | PASS |
| Conservative combined stress | 482.845 MPa |
| Conservative proof utilisation | 0.8325 |
| Conservative yield utilisation | 0.7544 |
| Remaining proof-load margin | 5634.0 N |
| Conservative combined check | PASS |

## Interpretation

The preload-only check requires the proposed preload to remain at or below
70 percent of the configured proof load.

The conservative combined check assumes that the full external axial load is
added directly to the bolt preload. This deliberately ignores load sharing by
the clamped members and therefore provides an upper-bound axial bolt load.

This is not the final joint-load prediction. The next analytical stage must
calculate bolt stiffness, member stiffness and the resulting joint load factor.

## Limitations

The strength values are provisional controlled references and must be checked
against the approved fastener-standard source before TRM-MAT-000001 is released.

This check does not include:

- Thread-root stress concentration
- Bending
- Torsional tightening stress
- Local contact stress
- Plasticity
- Fatigue
- Assembly scatter

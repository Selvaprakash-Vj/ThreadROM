# ThreadROM Baseline Joint-Stiffness Check

## Record information

- Assembly identity: TRM-ASM-000001
- Simulation identity: TRM-SIM-000001
- Status: Preliminary analytical verification

## Analytical model

The bolt is represented using the tensile stress area and an effective elastic
length equal to the grip length plus 0.5 nominal diameters beneath the bolt head
and 0.5 nominal diameters within the nut.

The clamped members are represented as a uniform annular compression cylinder.
This is a deliberately simple preliminary model and is not the final compressed
cone or finite-element stiffness prediction.

## Calculated stiffness

| Quantity | Value |
|---|---:|
| Effective bolt length | 30.000 mm |
| Member compression area | 611.825 mm² |
| Bolt stiffness | 405.927 kN/mm |
| Member stiffness | 6424.164 kN/mm |
| Joint constant | 0.059432 |

## External-load sharing

| Quantity | Value |
|---|---:|
| External axial load | 8000.0 N |
| Bolt-load increment | 475.5 N |
| Member clamp-load loss | 7524.5 N |
| Maximum bolt load | 20475.5 N |
| Remaining clamp load | 12475.5 N |
| Estimated separation load | 21263.8 N |

## Strength check after external loading

| Quantity | Value |
|---|---:|
| Estimated maximum bolt stress | 353.088 MPa |
| Proof utilisation | 0.6088 |
| Proof check | PASS |
| Separation check | PASS |

## Interpretation

The preliminary joint constant determines the fraction of external axial load
that increases bolt force before joint separation.

The remaining fraction reduces the member clamp force.

This analytical result provides a reference trend for the future nonlinear FEM
model. It must not be treated as the final joint-stiffness prediction.

## Limitations

This model does not yet include:

- Compression-cone spreading
- Local bearing compliance
- Thread compliance
- Contact opening
- Frictional redistribution
- Member-interface slip
- Geometric nonlinearity
- Manufacturing variation

# TRM-ASM-000001 Bolt-Nut Assembly Check

## Status

The complete bolt and internally threaded nut were positioned using
the governed right-hand helical phase relation and exported as a
two-solid STEP assembly.

## Governed placement

| Quantity | Value |
|---|---:|
| Nut translation | 20.000000000 mm |
| Nut rotation | 120.000000000 deg |
| Lower nut bearing plane | 20.000000000 mm |
| Upper nut bearing plane | 28.000000000 mm |
| Thread protrusion | 2.000000000 mm |

## Native assembly

| Quantity | Value |
|---|---:|
| Bolt solids | 1 |
| Nut solids | 1 |
| Assembly solids | 2 |
| Bolt volume | 3337.480816997 mm^3 |
| Nut volume | 1296.914330392 mm^3 |
| Component-volume sum | 4634.395147388 mm^3 |
| Axial bounds | -6.400000000 to 30.000000605 mm |

## STEP round-trip

| Quantity | Value |
|---|---:|
| Native solids | 2 |
| Reimported solids | 2 |
| Relative volume error | 9.945942563929e-08 |
| Maximum bounds error | 5.049542082247e-07 mm |

## Acceptance gates

The STEP assembly must preserve:

- Exactly one bolt solid
- Exactly one nut solid
- Exactly two assembly volumes
- Governed right-hand nut phase
- STEP volume error within policy
- STEP bounds error within policy

## Next gate

Introduce the two clamped-member solids and verify the complete
four-component joint stack before contact meshing.

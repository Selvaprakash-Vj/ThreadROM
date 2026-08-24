# TRM-ASM-000001 Bolt-Nut Assembly Check

## Status

The complete bolt and internally threaded nut were positioned using
the governed parametric thread-pair registration law and exported as a
two-solid STEP assembly.

## Governed placement

| Quantity | Value |
|---|---:|
| Nut translation | 20.000000000 mm |
| Registration pitch | 1.500000000 mm |
| Registration handedness | right |
| Applied nut rotation | 120.000000000 deg |
| Registration basis | canonical rigid screw datum |
| Lower nut bearing plane | 20.000000000 mm |
| Upper nut bearing plane | 28.000000000 mm |
| Thread protrusion | 2.000000000 mm |

## Native assembly

| Quantity | Value |
|---|---:|
| Bolt solids | 1 |
| Nut solids | 1 |
| Assembly solids | 2 |
| Bolt volume | 3344.740848714 mm^3 |
| Nut volume | 1252.487467318 mm^3 |
| Component-volume sum | 4597.228316032 mm^3 |
| Axial bounds | -6.400000000 to 30.000000100 mm |

## STEP round-trip

| Quantity | Value |
|---|---:|
| Native solids | 2 |
| Reimported solids | 2 |
| Relative volume error | 1.669755672899e-09 |
| Maximum bounds error | 1.762145984685e-12 mm |

## Acceptance gates

The STEP assembly must preserve:

- Exactly one bolt solid
- Exactly one nut solid
- Exactly two assembly volumes
- Governed parametric thread-pair phase
- STEP volume error within policy
- STEP bounds error within policy

## Next gate

Introduce the two clamped-member solids and verify the complete
four-component joint stack before contact meshing.

# TRM-ASM-000001 Complete Joint Assembly Check

## Status

The complete bolt, internally threaded nut and two annular
clamped members were constructed as four independent solids.

All governed placement, topology, material-interference and STEP
round-trip gates passed.

## Component topology

| Component | Solid count |
|---|---:|
| bolt | 1 |
| nut | 1 |
| head_side_member | 1 |
| nut_side_member | 1 |

| Quantity | Value |
|---|---:|
| Complete assembly solids | 4 |
| Maximum pairwise interference | 0.000000000000e+00 mm^3 |

## Member placement

| Member | Minimum Z | Maximum Z |
|---|---:|---:|
| Head side | 0.000000000 mm | 10.000000000 mm |
| Nut side | 10.000000000 mm | 20.000000000 mm |

## Pairwise material-interference checks

| First component | Second component | Intersection volume (mm^3) |
|---|---|---:|
| bolt | nut | 0.000000000000e+00 |
| bolt | head_side_member | 0.000000000000e+00 |
| bolt | nut_side_member | 0.000000000000e+00 |
| nut | head_side_member | 0.000000000000e+00 |
| nut | nut_side_member | 0.000000000000e+00 |
| head_side_member | nut_side_member | 0.000000000000e+00 |

## STEP round-trip

| Quantity | Value |
|---|---:|
| Native solids | 4 |
| Reimported solids | 4 |
| Native component-volume sum | 16833.732044685 mm^3 |
| Reimported component-volume sum | 16833.732056234 mm^3 |
| Relative volume error | 6.860532442855e-10 |
| Maximum bounds error | 0.000000000000e+00 mm |

## Automated parametric gate

Every future generated design case must pass these same checks
before it is permitted to enter meshing, FEM execution or the
surrogate-model dataset.

## Next gate

Classify the complete-joint contact and boundary surfaces:

- Bolt-head bearing surface
- Nut bearing surface
- Upper/lower member interface
- Bolt and nut thread surfaces
- External member loading and support surfaces

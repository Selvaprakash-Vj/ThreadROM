# TRM-MSH-000001 Bolt Surface Classification

## Status

The complete TRM-GEO-000001 STEP bolt was imported into Gmsh and every
surface was assigned to a controlled engineering region.

## Classification basis

The classifier derives its axial reference planes from the parametric bolt
definition:

| Reference | Position |
|---|---:|
| Head top | -6.400000 mm |
| Under-head interface | 0.000000 mm |
| Bolt tip | 30.000000 mm |
| Classification tolerance | 0.005000 mm |

No CAD face tag is hard-coded. Surface tags may change after regeneration
without changing the engineering classification logic.

## Classified physical groups

| Region | Physical name | Surface count | Surface tags |
|---|---|---:|---|
| head_top | BOLT_HEAD_TOP | 1 | 5 |
| under_head_bearing | BOLT_UNDER_HEAD_BEARING | 1 | 4 |
| head_sides | BOLT_HEAD_SIDES | 6 | 1, 2, 3, 6, 7, 8 |
| thread_surfaces | BOLT_THREAD_SURFACES | 25 | 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33 |
| bolt_tip | BOLT_TIP | 1 | 34 |
| transition_surfaces | BOLT_TRANSITION_SURFACES | 0 | None |

## Surface measurements

| Tag | Region | Area (mm²) | Centre Z (mm) | Minimum Z (mm) | Maximum Z (mm) |
|---:|---|---:|---:|---:|---:|
| 1 | head_sides | 59.120668 | -3.200000 | -6.400000 | 0.000000 |
| 2 | head_sides | 59.120668 | -3.200000 | -6.400000 | 0.000000 |
| 3 | head_sides | 59.120668 | -3.200000 | -6.400000 | 0.000000 |
| 4 | under_head_bearing | 168.638331 | 0.000000 | -0.000000 | 0.000000 |
| 5 | head_top | 221.702503 | -6.400000 | -6.400000 | -6.400000 |
| 6 | head_sides | 59.120668 | -3.200000 | -6.400000 | 0.000000 |
| 7 | head_sides | 59.120668 | -3.200000 | -6.400000 | 0.000000 |
| 8 | head_sides | 59.120668 | -3.200000 | -6.400000 | 0.000000 |
| 9 | thread_surfaces | 20.233664 | 0.511423 | -0.000000 | 1.533562 |
| 10 | thread_surfaces | 560.009519 | 14.665485 | -0.000000 | 29.281250 |
| 11 | thread_surfaces | 8.188202 | 2.124995 | 1.216453 | 3.033543 |
| 12 | thread_surfaces | 0.609935 | 0.625000 | 0.033547 | 1.216453 |
| 13 | thread_surfaces | 8.188178 | 3.624997 | 2.716441 | 4.533568 |
| 14 | thread_surfaces | 8.188559 | 5.124995 | 4.216460 | 6.033539 |
| 15 | thread_surfaces | 8.188047 | 6.624991 | 5.716433 | 7.533556 |
| 16 | thread_surfaces | 8.188374 | 8.124981 | 7.216459 | 9.033544 |
| 17 | thread_surfaces | 8.188491 | 9.624987 | 8.716443 | 10.533565 |
| 18 | thread_surfaces | 8.188115 | 11.125006 | 10.216457 | 12.033544 |
| 19 | thread_surfaces | 8.188176 | 12.624999 | 11.716438 | 13.533567 |
| 20 | thread_surfaces | 8.188298 | 14.124992 | 13.216458 | 15.033537 |
| 21 | thread_surfaces | 8.188267 | 15.624995 | 14.716434 | 16.533553 |
| 22 | thread_surfaces | 8.188160 | 17.124996 | 16.216461 | 18.033534 |
| 23 | thread_surfaces | 8.188259 | 18.625004 | 17.716448 | 19.533568 |
| 24 | thread_surfaces | 8.188231 | 20.125004 | 19.216466 | 21.033545 |
| 25 | thread_surfaces | 8.188191 | 21.625006 | 20.716435 | 22.533565 |
| 26 | thread_surfaces | 8.187917 | 23.125009 | 22.216457 | 24.033535 |
| 27 | thread_surfaces | 8.187965 | 24.625005 | 23.716436 | 25.533549 |
| 28 | thread_surfaces | 8.188130 | 26.125004 | 25.216462 | 27.033525 |
| 29 | thread_surfaces | 8.188429 | 27.624988 | 26.716452 | 28.533570 |
| 30 | thread_surfaces | 21.597964 | 29.426120 | 28.216475 | 30.000000 |
| 31 | thread_surfaces | 0.609935 | 29.375000 | 28.783548 | 29.966454 |
| 32 | thread_surfaces | 112.900216 | 15.000000 | 0.531250 | 29.468750 |
| 33 | thread_surfaces | 560.013251 | 15.334524 | 0.718750 | 30.000001 |
| 34 | bolt_tip | 53.064172 | 30.000000 | 30.000000 | 30.000000 |

## Verification gates

The classification requires:

- Exactly one imported bolt volume
- Positive area for every surface
- Every surface assigned exactly once
- At least one head-top surface
- At least one under-head bearing surface
- At least six head-side surfaces
- At least one threaded-body surface
- At least one bolt-tip surface
- One Gmsh physical group for every non-empty region

## Interpretation

These regions are topology classifications only.

They do not yet define solver loads or contact behaviour. Later gates will
map them to CalculiX node sets, element-face sets, loads, constraints and
contact definitions.

## Next gate

Integrate these physical groups into the generated tetrahedral MSH file and
verify that Meshio preserves the named surface groups.

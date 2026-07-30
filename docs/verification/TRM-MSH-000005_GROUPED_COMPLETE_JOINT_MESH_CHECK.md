# TRM-MSH-000005 Grouped Complete-Joint Mesh Check

## Status

The complete four-component threaded joint was tetrahedrally meshed
with the bolt, nut and both clamped-member volumes preserved as named
physical groups.

All classified bolt, nut, bearing, clearance-hole and member-interface
surfaces were preserved in the written MSH file.

Meshio independently recovered the exported groups and element totals.

## Governed refinement

| Quantity | Value |
|---|---:|
| Selected level | medium |
| Global minimum size | 0.267926609 mm |
| Global maximum size | 1.005000000 mm |
| Bolt thread size | 0.303650157 mm |
| Nut thread size | 0.267926609 mm |

## Mesh totals

| Quantity | Gmsh | Meshio |
|---|---:|---:|
| Nodes | 73360 | 73360 |
| Tetrahedra | 333439 | 333439 |
| Boundary triangles | 76978 | 76978 |

## Preserved physical groups

| Physical name | Dimension | Cell type | Tag | Elements |
|---|---:|---|---:|---:|
| BOLT_HEAD_SIDES | 2 | triangle | 7 | 996 |
| BOLT_HEAD_TOP | 2 | triangle | 5 | 600 |
| BOLT_THREAD_SURFACES | 2 | triangle | 8 | 40770 |
| BOLT_TIP | 2 | triangle | 9 | 1406 |
| BOLT_UNDER_HEAD_BEARING | 2 | triangle | 6 | 1276 |
| HEAD_MEMBER_CLEARANCE_HOLE | 2 | triangle | 17 | 836 |
| HEAD_MEMBER_HEAD_BEARING | 2 | triangle | 14 | 1497 |
| HEAD_MEMBER_INTERFACE | 2 | triangle | 15 | 1497 |
| HEAD_MEMBER_OUTER | 2 | triangle | 16 | 2220 |
| NUT_MEMBER_CLEARANCE_HOLE | 2 | triangle | 21 | 838 |
| NUT_MEMBER_INTERFACE | 2 | triangle | 18 | 1497 |
| NUT_MEMBER_NUT_BEARING | 2 | triangle | 19 | 1497 |
| NUT_MEMBER_OUTER | 2 | triangle | 20 | 2226 |
| nut_internal_thread | 2 | triangle | 13 | 15717 |
| nut_lower_bearing | 2 | triangle | 10 | 1450 |
| nut_outer_hex | 2 | triangle | 12 | 1200 |
| nut_upper_bearing | 2 | triangle | 11 | 1455 |
| BOLT | 3 | tetra | 1 | 199243 |
| HEAD_SIDE_MEMBER | 3 | tetra | 3 | 28948 |
| NUT | 3 | tetra | 2 | 76524 |
| NUT_SIDE_MEMBER | 3 | tetra | 4 | 28724 |

## Verification gates

- Exactly four named component-volume groups
- Every component volume contains tetrahedral elements
- Named volumes contain all tetrahedra exactly once
- Every classified engineering surface contains triangles
- Matching Gmsh and Meshio node totals
- Matching Gmsh and Meshio tetrahedron totals
- Matching Gmsh and Meshio boundary-triangle totals
- Non-empty MSH output

## Engineering note

The member end faces are currently classified as complete candidate
bearing/interface faces. Load and support subregions will be partitioned
separately before boundary conditions are applied, avoiding overlap
between bearing contact and remote loading definitions.

## Next gate

Measure complete-joint tetrahedral quality and establish acceptance
criteria before CalculiX transfer and contact definition.

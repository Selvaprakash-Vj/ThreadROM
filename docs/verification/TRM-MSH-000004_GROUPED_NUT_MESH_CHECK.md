# TRM-MSH-000004 Grouped Nut Mesh Check

## Status

The complete internally threaded nut was tetrahedrally meshed with
its engineering surfaces preserved as named Gmsh physical groups.

Meshio independently recovered all volume and boundary groups from
the written MSH file.

## Mesh totals

| Quantity | Gmsh | Meshio |
|---|---:|---:|
| Nodes | 13075 | 13075 |
| Tetrahedra | 55152 | 55152 |
| Boundary triangles | 16284 | 16284 |

## Preserved physical groups

| Physical name | Dimension | Cell type | Tag | Elements |
|---|---:|---|---:|---:|
| nut_internal_thread | 2 | triangle | 5 | 12497 |
| nut_lower_bearing | 2 | triangle | 2 | 1288 |
| nut_outer_hex | 2 | triangle | 4 | 1200 |
| nut_upper_bearing | 2 | triangle | 3 | 1299 |
| NUT | 3 | tetra | 1 | 55152 |

## Surface topology

| Region | CAD surface count |
|---|---:|
| Lower bearing | 1 |
| Upper bearing | 1 |
| Outer hex | 6 |
| Internal thread | 12 |
| Transition surfaces | 0 |

## Verification gates

The grouped nut mesh requires:

- Matching Gmsh and Meshio node counts
- Matching tetrahedron counts
- Matching boundary-triangle counts
- One NUT volume group containing every tetrahedron
- Non-empty lower and upper bearing groups
- A non-empty outer-hex group
- A non-empty internal-thread group
- A non-empty MSH output file

## Next gate

Measure tetrahedral element quality and establish the controlled
coarse, medium and fine nut-mesh hierarchy.

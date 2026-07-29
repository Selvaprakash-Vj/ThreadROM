# TRM-MSH-000001 Grouped Mesh Check

## Status

The complete bolt was tetrahedrally meshed with its classified engineering
surfaces preserved as named Gmsh physical groups.

Meshio independently recovered the volume and boundary groups from the
written MSH file.

## Mesh totals

| Quantity | Gmsh | Meshio |
|---|---:|---:|
| Nodes | 5010 | 5010 |
| Tetrahedra | 19503 | 19503 |
| Boundary triangles | 6922 | 6922 |

## Preserved physical groups

| Physical name | Dimension | Cell type | Physical tag | Element count |
|---|---:|---|---:|---:|
| BOLT_HEAD_SIDES | 2 | triangle | 4 | 996 |
| BOLT_HEAD_TOP | 2 | triangle | 2 | 600 |
| BOLT_THREAD_SURFACES | 2 | triangle | 5 | 4728 |
| BOLT_TIP | 2 | triangle | 6 | 140 |
| BOLT_UNDER_HEAD_BEARING | 2 | triangle | 3 | 458 |
| BOLT | 3 | tetra | 1 | 19503 |

## Verification gates

The grouped mesh requires:

- Matching Gmsh and Meshio node counts
- Matching Gmsh and Meshio tetrahedron counts
- Matching Gmsh and Meshio boundary-triangle counts
- A named bolt-volume group containing every tetrahedron
- A non-empty named boundary group for every classified CAD region
- A non-empty MSH output file

## Interpretation

The mesh now contains stable engineering names rather than relying on
temporary CAD entity tags.

These physical names can be translated into CalculiX node sets and
element-face sets for loads, supports and contact definitions.

## Next gate

Measure tetrahedral element quality and establish controlled rejection
criteria before converting the grouped mesh to CalculiX input.

# TRM-MSH-000001 Gmsh Meshability Check

## Status

The complete TRM-GEO-000001 STEP geometry was successfully imported into
Gmsh and converted into a first-order tetrahedral volume mesh.

## Controlled mesh definition

| Quantity | Value |
|---|---:|
| Mesh identifier | TRM-MSH-000001 |
| Geometry identifier | TRM-GEO-000001 |
| Element order | 1 |
| 2D algorithm | 6 |
| 3D algorithm | 1 |
| Minimum mesh size | 0.300000 mm |
| Maximum mesh size | 1.000000 mm |
| MSH file version | 4.1 |
| Binary output | False |
| Save all elements | False |

## Imported CAD topology

| Entity type | Count |
|---|---:|
| Imported top-level entities | 1 |
| Points | 60 |
| Curves | 91 |
| Surfaces | 34 |
| Volumes | 1 |

## Imported CAD measurements

| Quantity | Value |
|---|---:|
| Gmsh OCC volume | 3337.480316 mm³ |
| Minimum X | -11.030739 mm |
| Maximum X | 10.688582 mm |
| Minimum Y | -10.953368 mm |
| Maximum Y | 11.030739 mm |
| Minimum Z | -6.400000 mm |
| Maximum Z | 30.000001 mm |

## Generated mesh

| Quantity | Value |
|---|---:|
| Gmsh node count | 5010 |
| Gmsh 3D element count | 19503 |
| Meshio node count | 5010 |
| Meshio tetrahedron count | 19503 |
| MSH file size | 997152 bytes |

## Three-dimensional element types

| Type | Name | Order | Nodes per element | Count |
|---:|---|---:|---:|---:|
| 4 | Tetrahedron 4 | 1 | 4 | 19503 |

## Acceptance gates

The meshability gate requires:

- Exactly one imported CAD volume
- Positive imported CAD volume
- At least 100 nodes
- At least 100 tetrahedral elements
- Matching Gmsh and Meshio node counts
- Matching Gmsh and Meshio tetrahedron counts
- A non-empty Gmsh MSH output file

## Interpretation

This is a meshability proof, not the final analysis mesh.

The present global size controls establish that the detailed helical bolt
geometry can pass through the complete STEP-to-Gmsh volume-meshing pipeline.

Local thread-contact refinement, element-quality limits, convergence studies
and production mesh release criteria remain separate later gates.

## Next gate

Classify the bolt surfaces into controlled engineering regions:

- Bolt-head loading surface
- Under-head bearing surface
- Thread-contact surfaces
- Thread tip/end surface

Those regions will later become solver boundary and contact sets.

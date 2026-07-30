# TRM-MSH-000004 Nut Mesh-Level Comparison

## Status

Coarse, medium and fine grouped nut meshes were generated from
dimensionless refinement factors tied to the internal-thread geometry.

Each mesh preserved the governed engineering physical groups and
passed independent tetrahedral numerical-safety analysis.

## Governing thread dimensions

| Quantity | Value |
|---|---:|
| Thread pitch | 1.500000000 mm |
| Radial thread depth | 0.811898816 mm |

## Mesh-level comparison

| Level | Minimum size (mm) | Maximum size (mm) | Thread size (mm) | Nodes | Tetrahedra | Minimum mean ratio | P1 mean ratio | Maximum edge ratio | Runtime (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| coarse | 0.405949 | 1.500000 | 0.405949 | 6495 | 25428 | 0.177030 | 0.418999 | 19.608082 | 0.732 |
| medium | 0.267927 | 1.005000 | 0.267927 | 17425 | 76967 | 0.190320 | 0.455997 | 18.544232 | 1.590 |
| fine | 0.178618 | 0.675000 | 0.178618 | 46971 | 223185 | 0.184464 | 0.458665 | 19.628035 | 4.492 |

## Parametric interpretation

The absolute mesh dimensions are derived from thread geometry:

- Global maximum size is derived from pitch.
- Global minimum size is derived from radial thread depth.
- Internal-thread surface size is derived from radial thread depth.
- Refinement progresses monotonically from coarse to fine.

## Acceptance status

These levels establish the controlled computational hierarchy.

The final joint mesh will later be selected using:

- Contact convergence
- Bolt and nut displacement convergence
- Thread-load distribution convergence
- Contact-pressure convergence
- Peak-stress sensitivity
- Runtime and memory cost

## Next gate

Select the provisional assembly mesh levels and combine the complete
bolt and nut geometries into the first threaded joint assembly.

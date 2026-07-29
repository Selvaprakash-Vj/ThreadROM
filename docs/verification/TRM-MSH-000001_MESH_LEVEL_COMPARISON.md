# TRM-MSH-000001 Mesh-Level Comparison

## Status

Coarse, medium and fine grouped bolt meshes were generated from
dimensionless factors tied to the thread geometry.

## Governing thread dimensions

| Quantity | Value |
|---|---:|
| Thread pitch | 1.500000000 mm |
| Radial thread depth | 0.920151992 mm |

## Mesh-level comparison

| Level | Minimum size (mm) | Maximum size (mm) | Thread size (mm) | Nodes | Tetrahedra | Minimum mean ratio | P1 mean ratio | Maximum edge ratio | Runtime (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| coarse | 0.460076 | 1.500000 | 0.460076 | 25958 | 125300 | 0.110288 | 0.451755 | 24.448620 | 2.767 |
| medium | 0.303650 | 1.005000 | 0.303650 | 43573 | 199032 | 0.246454 | 0.456216 | 15.400538 | 5.115 |
| fine | 0.202433 | 0.675000 | 0.202433 | 194527 | 1061483 | 0.274106 | 0.468069 | 9.513310 | 23.079 |

## Parametric interpretation

The absolute mesh dimensions are not stored as M10-specific constants.

For every bolt configuration:

- Global maximum size is derived from thread pitch.
- Global minimum size is derived from radial thread depth.
- Thread-region size is derived from radial thread depth.
- The hierarchy becomes progressively finer from coarse to fine.

This makes the mesh policy reusable when future verified fastener
definitions are introduced.

## Current interpretation

These levels establish a computational hierarchy only.

The final production level will be chosen later using:

- Solver stability
- Bolt-load convergence
- Contact-pressure convergence
- First-thread load-share convergence
- Peak-stress sensitivity
- Runtime and memory cost

## Next gate

Select the medium mesh as the provisional baseline and convert its named
volume and boundary groups into a CalculiX input deck.

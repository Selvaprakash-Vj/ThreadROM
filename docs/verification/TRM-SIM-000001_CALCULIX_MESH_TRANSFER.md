# TRM-SIM-000001 CalculiX Mesh-Transfer Check

## Status

The parameter-generated coarse grouped bolt mesh was
converted into a CalculiX C3D4 input deck and solved successfully.

## Purpose

This is a mesh-transfer and solver-read verification model.

It is not the final threaded-joint FEM simulation.

## Transfer summary

| Quantity | Value |
|---|---:|
| Source mesh level | coarse |
| Nodes | 25958 |
| C3D4 elements | 125300 |
| Named node sets | 5 |
| Fixed nodes | 343 |
| Loaded nodes | 169 |
| Load per node | -5.917159763 N |
| Total applied axial force | -1000.000000000 N |
| Reaction force X | 0.000000000 N |
| Reaction force Y | -0.000000000 N |
| Reaction force Z | 1000.000000000 N |
| Maximum equilibrium residual | 5.666245000e-12 N |
| Force-balance tolerance | 1.000000000e-01 N |
| Input file size | 5967107 bytes |

## Preserved boundary node sets

| CalculiX node set | Node count |
|---|---:|
| BOLT_HEAD_SIDES | 306 |
| BOLT_HEAD_TOP | 169 |
| BOLT_THREAD_SURFACES | 10519 |
| BOLT_TIP | 343 |
| BOLT_UNDER_HEAD_BEARING | 358 |

## Verification model

- Element type: C3D4
- Material: linear-elastic steel
- Young's modulus: 210000.000 MPa
- Poisson's ratio: 0.300000
- Fixed set: BOLT_TIP
- Loaded set: BOLT_HEAD_TOP
- Applied force: -1000.000 N in global Z
- Solver units: mm, N and MPa

## Solver outputs

| Output | Path |
|---|---|
| Input deck | `D:\ThreadROM\simulations\staging\TRM-SIM-000001\mesh_transfer\coarse\trm_msh_000001_coarse_transfer.inp` |
| Data file | `D:\ThreadROM\simulations\staging\TRM-SIM-000001\mesh_transfer\coarse\trm_msh_000001_coarse_transfer.dat` |
| Results file | `D:\ThreadROM\simulations\staging\TRM-SIM-000001\mesh_transfer\coarse\trm_msh_000001_coarse_transfer.frd` |
| Status file | `D:\ThreadROM\simulations\staging\TRM-SIM-000001\mesh_transfer\coarse\trm_msh_000001_coarse_transfer.sta` |
| Standard-output log | `D:\ThreadROM\simulations\staging\TRM-SIM-000001\mesh_transfer\coarse\trm_msh_000001_coarse_transfer.stdout.log` |
| Error-output log | `D:\ThreadROM\simulations\staging\TRM-SIM-000001\mesh_transfer\coarse\trm_msh_000001_coarse_transfer.stderr.log` |

## Acceptance gates

The transfer gate requires:

- All first-order tetrahedra converted to C3D4 elements
- Every required Gmsh boundary group preserved as a CalculiX node set
- Fixed and loaded node sets remain disjoint
- Distributed nodal forces sum to the controlled total force
- CalculiX returns exit code zero
- No CalculiX `*ERROR` diagnostics
- Non-empty DAT, FRD and STA outputs

## Interpretation

The complete parametric bolt mesh can now move from CadQuery through STEP,
Gmsh, Meshio and into a successfully solved CalculiX model.

The medium mesh remains the provisional engineering baseline. It will be
transferred after this coarse development gate is accepted.

## Next gate

Run the same verified deck-generation path using the medium mesh and extract
the resulting displacement and reaction-force balance.

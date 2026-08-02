# TRM-SIM-000009 Complete-Joint CalculiX Transfer Check

## Status

The grouped four-component threaded-joint mesh was transferred into
a CalculiX C3D10 input deck and processed successfully by CalculiX 2.23.

This is a transfer-only solver-read smoke test. It is not a physical
threaded-joint simulation.

## Transfer summary

| Quantity | Value |
|---|---:|
| Mesh level | coarse |
| Nodes | 259267 |
| C3D10 elements | 166445 |
| Component ELSETs | 4 |
| Engineering NSETs | 18 |
| Engineering element surfaces | 18 |
| Mapped C3D10 boundary faces | 39689 |
| Fully constrained smoke-test nodes | 259267 |
| Input file size | 32280478 bytes |

## Component element sets

| Component | C3D10 elements |
|---|---:|
| bolt | 122271 |
| nut | 25587 |
| head_side_member | 9350 |
| nut_side_member | 9237 |

## Solver result

| Quantity | Value |
|---|---:|
| CalculiX return code | 0 |
| Expected zero-DOF warning found | True |
| DAT size | 34249 bytes |
| FRD size | 35401946 bytes |
| STA size | 173 bytes |

## Smoke-test interpretation

Every mesh node was intentionally constrained in all three translational
degrees of freedom and no load was applied.

CalculiX therefore reported that the model contained no active degrees
of freedom. This warning is expected for this deliberately nonphysical
parser and solver-read test.

The gate verifies:

- All 259,267 nodes are readable
- All 166,445 C3D10 elements are readable
- Four component ELSETs are accepted
- 18 boundary NSETs are accepted
- 18 element-based surfaces are accepted
- All 39,689 mapped C3D10 faces are accepted
- Three independent material and section definitions are accepted
- CalculiX returns exit code zero
- No CalculiX `*ERROR` diagnostic is present
- DAT, FRD and STA outputs are created

## Solver outputs

| Output | Path |
|---|---|
| Input deck | `D:\ThreadROM\simulations\staging\TRM-SIM-000009\mesh_transfer\coarse\trm_msh_000008_coarse_pretension_transfer.inp` |
| DAT file | `D:\ThreadROM\simulations\staging\TRM-SIM-000009\mesh_transfer\coarse\trm_msh_000008_coarse_pretension_transfer.dat` |
| FRD file | `D:\ThreadROM\simulations\staging\TRM-SIM-000009\mesh_transfer\coarse\trm_msh_000008_coarse_pretension_transfer.frd` |
| STA file | `D:\ThreadROM\simulations\staging\TRM-SIM-000009\mesh_transfer\coarse\trm_msh_000008_coarse_pretension_transfer.sta` |
| Standard-output log | `D:\ThreadROM\simulations\staging\TRM-SIM-000009\mesh_transfer\coarse\trm_msh_000008_coarse_pretension_transfer.stdout.log` |
| Error-output log | `D:\ThreadROM\simulations\staging\TRM-SIM-000009\mesh_transfer\coarse\trm_msh_000008_coarse_pretension_transfer.stderr.log` |

## Next gate

Define and verify the four nonlinear contact interfaces:

1. Bolt external thread to nut internal thread
2. Bolt under-head bearing to head-side member
3. Nut bearing to nut-side member
4. Head-side member to nut-side member

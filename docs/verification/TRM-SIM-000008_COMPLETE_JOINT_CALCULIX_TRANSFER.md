# TRM-SIM-000008 Complete-Joint CalculiX Transfer Check

## Status

The grouped four-component threaded-joint mesh was transferred into
a CalculiX C3D10 input deck and processed successfully by CalculiX 2.23.

This is a transfer-only solver-read smoke test. It is not a physical
threaded-joint simulation.

## Transfer summary

| Quantity | Value |
|---|---:|
| Mesh level | medium |
| Nodes | 540210 |
| C3D10 elements | 349450 |
| Component ELSETs | 4 |
| Engineering NSETs | 18 |
| Engineering element surfaces | 18 |
| Mapped C3D10 boundary faces | 78963 |
| Fully constrained smoke-test nodes | 540210 |
| Input file size | 68389956 bytes |

## Component element sets

| Component | C3D10 elements |
|---|---:|
| bolt | 214945 |
| nut | 76550 |
| head_side_member | 29022 |
| nut_side_member | 28933 |

## Solver result

| Quantity | Value |
|---|---:|
| CalculiX return code | 0 |
| Expected zero-DOF warning found | True |
| DAT size | 68269 bytes |
| FRD size | 74117834 bytes |
| STA size | 173 bytes |

## Smoke-test interpretation

Every mesh node was intentionally constrained in all three translational
degrees of freedom and no load was applied.

CalculiX therefore reported that the model contained no active degrees
of freedom. This warning is expected for this deliberately nonphysical
parser and solver-read test.

The gate verifies:

- All 540,210 nodes are readable
- All 349,450 C3D10 elements are readable
- Four component ELSETs are accepted
- 18 boundary NSETs are accepted
- 18 element-based surfaces are accepted
- All 78,963 mapped C3D10 faces are accepted
- Three independent material and section definitions are accepted
- CalculiX returns exit code zero
- No CalculiX `*ERROR` diagnostic is present
- DAT, FRD and STA outputs are created

## Solver outputs

| Output | Path |
|---|---|
| Input deck | `D:\ThreadROM\simulations\staging\TRM-SIM-000008\mesh_transfer\medium\trm_msh_000007_medium_pretension_transfer.inp` |
| DAT file | `D:\ThreadROM\simulations\staging\TRM-SIM-000008\mesh_transfer\medium\trm_msh_000007_medium_pretension_transfer.dat` |
| FRD file | `D:\ThreadROM\simulations\staging\TRM-SIM-000008\mesh_transfer\medium\trm_msh_000007_medium_pretension_transfer.frd` |
| STA file | `D:\ThreadROM\simulations\staging\TRM-SIM-000008\mesh_transfer\medium\trm_msh_000007_medium_pretension_transfer.sta` |
| Standard-output log | `D:\ThreadROM\simulations\staging\TRM-SIM-000008\mesh_transfer\medium\trm_msh_000007_medium_pretension_transfer.stdout.log` |
| Error-output log | `D:\ThreadROM\simulations\staging\TRM-SIM-000008\mesh_transfer\medium\trm_msh_000007_medium_pretension_transfer.stderr.log` |

## Next gate

Define and verify the four nonlinear contact interfaces:

1. Bolt external thread to nut internal thread
2. Bolt under-head bearing to head-side member
3. Nut bearing to nut-side member
4. Head-side member to nut-side member

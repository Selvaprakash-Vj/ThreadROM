# TRM-SIM-000004 Complete-Joint CalculiX Transfer Check

## Status

The grouped four-component threaded-joint mesh was transferred into
a CalculiX C3D4 input deck and processed successfully by CalculiX 2.23.

This is a transfer-only solver-read smoke test. It is not a physical
threaded-joint simulation.

## Transfer summary

| Quantity | Value |
|---|---:|
| Mesh level | medium |
| Nodes | 101493 |
| C3D4 elements | 509115 |
| Component ELSETs | 4 |
| Engineering NSETs | 17 |
| Engineering element surfaces | 17 |
| Mapped C3D4 boundary faces | 78390 |
| Fully constrained smoke-test nodes | 101493 |
| Input file size | 25555504 bytes |

## Component element sets

| Component | C3D4 elements |
|---|---:|
| bolt | 392486 |
| nut | 58757 |
| head_side_member | 29037 |
| nut_side_member | 28835 |

## Solver result

| Quantity | Value |
|---|---:|
| CalculiX return code | 0 |
| Expected zero-DOF warning found | True |
| DAT size | 18049 bytes |
| FRD size | 42363227 bytes |
| STA size | 173 bytes |

## Smoke-test interpretation

Every mesh node was intentionally constrained in all three translational
degrees of freedom and no load was applied.

CalculiX therefore reported that the model contained no active degrees
of freedom. This warning is expected for this deliberately nonphysical
parser and solver-read test.

The gate verifies:

- All 101,493 nodes are readable
- All 509,115 C3D4 elements are readable
- Four component ELSETs are accepted
- 17 boundary NSETs are accepted
- 17 element-based surfaces are accepted
- All 78,390 mapped C3D4 faces are accepted
- Three independent material and section definitions are accepted
- CalculiX returns exit code zero
- No CalculiX `*ERROR` diagnostic is present
- DAT, FRD and STA outputs are created

## Solver outputs

| Output | Path |
|---|---|
| Input deck | `D:\ThreadROM\simulations\staging\TRM-SIM-000004\mesh_transfer\medium\trm_msh_000005_medium_transfer.inp` |
| DAT file | `D:\ThreadROM\simulations\staging\TRM-SIM-000004\mesh_transfer\medium\trm_msh_000005_medium_transfer.dat` |
| FRD file | `D:\ThreadROM\simulations\staging\TRM-SIM-000004\mesh_transfer\medium\trm_msh_000005_medium_transfer.frd` |
| STA file | `D:\ThreadROM\simulations\staging\TRM-SIM-000004\mesh_transfer\medium\trm_msh_000005_medium_transfer.sta` |
| Standard-output log | `D:\ThreadROM\simulations\staging\TRM-SIM-000004\mesh_transfer\medium\trm_msh_000005_medium_transfer.stdout.log` |
| Error-output log | `D:\ThreadROM\simulations\staging\TRM-SIM-000004\mesh_transfer\medium\trm_msh_000005_medium_transfer.stderr.log` |

## Next gate

Define and verify the four nonlinear contact interfaces:

1. Bolt external thread to nut internal thread
2. Bolt under-head bearing to head-side member
3. Nut bearing to nut-side member
4. Head-side member to nut-side member

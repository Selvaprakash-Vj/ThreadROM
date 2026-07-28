# ThreadROM Basic Thread Analytical Check

## Record information

- Geometry identity: TRM-GEO-000001
- Planned simulation identity: TRM-SIM-000001
- Thread designation: M10x1.5
- Status: Verified analytical reference
- Scope: Ideal ISO metric basic profile

## Input parameters

| Quantity | Value |
|---|---:|
| Nominal diameter | 10.000000 mm |
| Thread pitch | 1.500000 mm |

## Calculated basic dimensions

| Quantity | Value |
|---|---:|
| Fundamental triangle height | 1.299038106 mm |
| Basic pitch diameter | 9.025721421 mm |
| Basic internal minor diameter | 8.376202368 mm |
| Basic external minor diameter | 8.159696017 mm |
| Tensile stress area | 57.989596902 mm² |

## Interpretation

These values define the ideal analytical reference profile for the configured
M10 × 1.5 thread.

They do not yet include:

- External-thread tolerance class 6g
- Internal-thread tolerance class 6H
- Manufacturing variation
- Thread runout
- Root-radius implementation details
- CAD-kernel approximation
- Mesh discretisation effects

## Verification use

The future parametric CAD geometry must be checked against these values before
TRM-GEO-000001 can be approved.

The future finite-element model must not use manually copied thread dimensions
that conflict with this configuration-driven analytical reference.

# TRM-GEO-000001 Complete Bolt Check

## Status

Complete development bolt generated and verified through STEP round-trip.

## Parametric construction

1. Load controlled fastener, assembly and geometry definitions.
2. Build a regular hex head from the configured width across flats.
3. Build the verified additive helical threaded shank.
4. Add an internal parametric head-shank fusion bridge.
5. Fuse all components into one valid solid.
6. Export the complete bolt to STEP.
7. Re-import the STEP file and compare volume and bounds.

## Configuration

| Quantity | Value |
|---|---:|
| Geometry identifier | TRM-GEO-000001 |
| Nominal diameter | 10.000000 mm |
| Pitch | 1.500000 mm |
| Under-head length | 30.000000 mm |
| Head width across flats | 16.000000 mm |
| Expected width across corners | 18.475209 mm |
| Head height | 6.400000 mm |
| Handedness | right |
| Boolean tolerance | 0.000001000 mm |

## Native CAD measurements

| Quantity | Value |
|---|---:|
| Solid count | 1 |
| Valid solid | True |
| X bounding length | 16.000000 mm |
| Y bounding length | 18.475209 mm |
| Minimum Z | -6.400000 mm |
| Maximum Z | 30.000001 mm |
| Head volume | 1418.896022 mm³ |
| Threaded-shank volume | 1918.580601 mm³ |
| Fusion-bridge volume | 1.176577 mm³ |
| Complete-bolt volume | 3337.480817 mm³ |
| Union overlap volume | 1.172383 mm³ |
| Face count | 34 |
| Edge count | 91 |

## STEP round-trip measurements

| Quantity | Value |
|---|---:|
| STEP file size | 670435 bytes |
| Re-imported solid count | 1 |
| Re-imported valid shape | True |
| Re-imported volume | 3337.480316 mm³ |
| Relative volume error | 1.501744330e-07 |
| Maximum bounds error | 5.049542082e-07 mm |

## Verification gates

The complete bolt must:

- Consist of exactly one valid solid
- Preserve the configured under-head length
- Preserve the configured head height
- Preserve the regular-hex across-flats and across-corners dimensions
- Contain positive head-shank fusion overlap
- Survive STEP export and re-import
- Preserve volume and bounds within the controlled quality policy

## Current limitations

The geometry remains an idealized Phase 1 engineering reference.

Not yet included:

- Tip chamfer
- Under-head fillet
- Thread lead-in and runout
- External tolerance-class allowance
- Rounded thread root
- Manufacturing variation

## Next gate

Import the complete STEP geometry into Gmsh and establish the first
meshability and topology-classification check.

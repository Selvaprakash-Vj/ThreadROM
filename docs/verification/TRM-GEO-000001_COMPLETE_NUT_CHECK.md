# TRM-GEO-000001 Complete Nut Check

## Status

Complete internally threaded nut generated and verified through a STEP
export and re-import round trip.

## Parametric construction

1. Load the governed fastener, assembly and nut definitions.
2. Build the regular hexagonal nut blank.
3. Create the basic internal minor-diameter bore.
4. Sweep the full three-dimensional helical internal-thread cutter.
5. Subtract the cutter from the nut blank.
6. Verify that the result is one valid solid.
7. Export the complete nut to STEP.
8. Re-import the STEP file and compare its volume and bounds.

## Configuration

| Quantity | Value |
|---|---:|
| Geometry identifier | TRM-GEO-000001 |
| Assembly identifier | TRM-ASM-000001 |
| Component | baseline_hex_nut |
| Nominal diameter | 10.000000 mm |
| Pitch | 1.500000 mm |
| Nut width across flats | 16.000000 mm |
| Nut width across corners | 18.475209 mm |
| Nut thickness | 8.000000 mm |
| Basic internal minor diameter | 8.376202 mm |
| Internal-thread radial depth | 0.811899 mm |
| Thread handedness | right |
| Helical sweep turns | 5.333333 |

## Native CAD measurements

| Quantity | Value |
|---|---:|
| Solid count | 1 |
| Valid solid | True |
| X bounding length | 18.475209 mm |
| Y bounding length | 16.000000 mm |
| Minimum Z | -0.000000 mm |
| Maximum Z | 8.000000 mm |
| Plain-bore blank volume | 1332.786932 mm^3 |
| Helical cutter volume | 87.189263 mm^3 |
| Removed thread volume | 85.066487 mm^3 |
| Complete nut volume | 1247.720445 mm^3 |
| Face count | 20 |
| Edge count | 53 |

## STEP round-trip measurements

| Quantity | Value |
|---|---:|
| STEP file size | 239751 bytes |
| Re-imported solid count | 1 |
| Re-imported valid shape | True |
| Re-imported volume | 1247.720497 mm^3 |
| Relative volume error | 4.193592492e-08 |
| Maximum bounds error | 1.746158773e-12 mm |

## Verification gates

The complete nut must:

- Consist of exactly one valid solid
- Preserve the governed nut thickness
- Preserve the external across-flats and across-corners envelope
- Contain a full three-dimensional helical internal thread
- Remove positive material beyond the initial cylindrical bore
- Survive STEP export and re-import
- Preserve volume and bounds through the STEP round trip

## Current limitations

The Phase 1 nut remains an idealized engineering reference.

Not yet included:

- Nut-face chamfers
- Thread lead-in and runout
- Rounded internal-thread root
- Explicit ISO 6H tolerance allowance
- Manufacturing variation
- Surface roughness

## Next gate

Import the complete nut STEP geometry into Gmsh and establish the
nut meshability and topology-classification baseline.

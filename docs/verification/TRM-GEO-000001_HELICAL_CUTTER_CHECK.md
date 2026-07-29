# TRM-GEO-000001 Helical Thread Cutter Check

## Status

Development cutter generated and geometrically checked.

## Configuration

| Quantity | Value |
|---|---:|
| Nominal diameter | 10.000000 mm |
| Major radius | 5.000000000 mm |
| Minor radius | 4.079848008 mm |
| Pitch | 1.500000 mm |
| Threaded length | 30.000000 mm |
| Sweep height | 33.000000 mm |
| Helical turns | 22.000000 |
| Start Z | -1.500000 mm |
| Handedness | right |
| Radial clearance | 0.050000 mm |

## CAD measurements

| Quantity | Value |
|---|---:|
| Solid count | 1 |
| Valid solid | True |
| Cutter volume | 507.074619 mm³ |
| X bounding length | 10.100013 mm |
| Y bounding length | 10.100013 mm |
| Minimum Z | -2.156250 mm |
| Maximum Z | 32.156250 mm |

## Interpretation

The cutter extends one pitch below and above the final 30 mm threaded region.

This deliberate overshoot allows the future threaded shank to be trimmed
cleanly at Z = 0 mm and Z = 30 mm.

The cutter is not itself a released engineering geometry. It is a controlled
construction artefact used to produce TRM-GEO-000001.

## Next gate

The cutter must be subtracted from an isolated cylindrical shank.

The resulting threaded shank must then pass:

- Single-solid validation
- Major-diameter verification
- Minor-diameter verification
- Axial-length verification
- STEP export and re-import verification

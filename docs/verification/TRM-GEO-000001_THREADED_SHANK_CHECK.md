# TRM-GEO-000001 Threaded Shank Check

## Status

Development threaded shank generated using additive construction.

## Construction method

The previous subtractive helical-groove approach was rejected after the
OpenCascade Boolean intersection returned an invalid result approximately
equal to the complete cylindrical blank.

The controlled replacement construction is:

1. Build a continuous minor-diameter core.
2. Sweep a trapezoidal external-thread ridge along a right-hand helix.
3. Introduce controlled radial overlap.
4. Fuse the core and ridge using a fuzzy Boolean tolerance.

## Configuration

| Quantity | Value |
|---|---:|
| Nominal major diameter | 10.000000 mm |
| Basic minor diameter | 8.159696017 mm |
| Threaded length | 30.000000 mm |
| Pitch | 1.500000 mm |
| Handedness | right |

## CAD measurements

| Quantity | Value |
|---|---:|
| Solid count | 1 |
| Valid solid | True |
| X bounding length | 10.000113 mm |
| Y bounding length | 10.000138 mm |
| Minimum Z | -0.000000 mm |
| Maximum Z | 30.000001 mm |
| Core volume | 1591.925170 mm³ |
| Ridge volume | 362.513175 mm³ |
| Threaded volume | 1918.580601 mm³ |
| Fusion overlap volume | 35.857744 mm³ |
| Major-cylinder upper-bound volume | 2356.194490 mm³ |
| Face count | 27 |
| Edge count | 73 |

## Verification interpretation

The threaded volume must:

- Exceed the minor-core volume
- Remain below the unthreaded major-cylinder volume
- Contain a positive fusion-overlap volume
- Form exactly one valid solid
- Remain within the nominal major diameter
- Span the complete configured axial length

## Current limitations

The threaded shank does not yet include:

- Hexagonal bolt head
- Underhead fillet
- Thread runout
- Tip chamfer
- External tolerance class 6g
- Rounded thread root
- Manufacturing variation

## Next gate

The threaded shank must be fused with the verified hexagonal bolt head and
subsequently pass STEP export and re-import verification.

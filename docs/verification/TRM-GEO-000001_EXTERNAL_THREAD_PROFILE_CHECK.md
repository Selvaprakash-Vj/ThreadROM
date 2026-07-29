# TRM-GEO-000001 External Thread Profile Check

## Status

Verified analytical profile for geometry development.

## Profile definition

| Quantity | Value |
|---|---:|
| Nominal diameter | 10.000000 mm |
| Pitch | 1.500000 mm |
| Major radius | 5.000000000 mm |
| Pitch radius | 4.512860710 mm |
| Minor radius | 4.079848008 mm |
| Radial thread depth | 0.920151992 mm |
| Fundamental triangle height | 1.299038106 mm |
| Crest-flat width | 0.187500000 mm |
| Root-flat width | 0.250000000 mm |
| Included flank angle | 60.000 degrees |
| Left flank angle to axis | 60.000000 degrees |
| Right flank angle to axis | 60.000000 degrees |

## One-pitch profile points

| Point | Axial coordinate | Radius |
|---:|---:|---:|
| 1 | -0.750000000 | 4.079848008 |
| 2 | -0.625000000 | 4.079848008 |
| 3 | -0.093750000 | 5.000000000 |
| 4 | 0.093750000 | 5.000000000 |
| 5 | 0.625000000 | 4.079848008 |
| 6 | 0.750000000 | 4.079848008 |

## Coordinate interpretation

- Axial coordinates are parallel to the global Z-axis.
- Radius is measured normally from the global Z-axis.
- The profile is centred on one external-thread crest.
- Adjacent pitch cells repeat every 1.5 mm.

## Current limitations

This is the ideal external basic profile.

It does not yet include:

- External tolerance class 6g
- Rounded root implementation
- Thread runout
- Start chamfer
- Manufacturing variation
- CAD-kernel approximation

The verified profile will next be swept along a right-handed helix.

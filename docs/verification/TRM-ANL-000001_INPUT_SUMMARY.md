# ThreadROM Analytical Joint Input Summary

## Identity

- Analytical joint: TRM-ANL-000001
- Status: Governed analytical input

## Thread definition

| Quantity | Value |
|---|---:|
| Nominal diameter | 10.000000 mm |
| Pitch | 1.500000 mm |
| Handedness | right |
| Starts | 1 |
| Included angle | 60.000000 deg |
| External tolerance class | 6g |
| Internal tolerance class | 6H |

## Bolt definition

- Bolt identity: TRM-BLT-000001
- Material identity: steel_8_8
- Nominal length: 30.000000 mm
- Explicit segment length: 20.000000 mm
- Head bearing ring: 11.000000 to 16.000000 mm

### Bolt axial segments

| Segment | Kind | Length | Diameter | Area | Material override |
|---|---|---:|---:|---:|---|
| grip_thread | threaded | 20.000000 mm | derived | derived | bolt material |

## Nut definition

- Nut identity: TRM-NUT-000001
- Material identity: steel_8
- Thickness: 8.000000 mm
- Thread engagement: 8.000000 mm
- Nominal engaged pitches: 5.333333
- Bearing ring: 11.000000 to 16.000000 mm

## Clamped-member stack

- Total grip length: 20.000000 mm
- Number of layers: 2

| Layer | Thickness | Material | Hole diameter | Outer diameter |
|---|---:|---|---:|---:|
| head_side_member | 10.000000 mm | member_steel | 11.000000 mm | 30.000000 mm |
| nut_side_member | 10.000000 mm | member_steel | 11.000000 mm | 30.000000 mm |

## Materials

| Material | E | Poisson ratio | Proof | Yield | Ultimate |
|---|---:|---:|---:|---:|---:|
| steel_8_8 | 210000.000000 MPa | 0.300000 | 580.000000 MPa | 640.000000 MPa | 800.000000 MPa |
| steel_8 | 210000.000000 MPa | 0.300000 | not specified | not specified | not specified |
| member_steel | 210000.000000 MPa | 0.300000 | not specified | not specified | not specified |

## Loading

- Preload: 5000.000000 N
- External separating load: 0.000000 N
- Preload scatter fraction: 0.000000

## Selected analytical methods

- Bolt compliance: segmented
- Member compression: uniform_annular_cylinder
- External-load treatment: basic_spring_ratio
- Thread-load distribution: discrete_spring
- Head participation factor: 0.500000
- Nut participation factor: 0.500000
- Load-introduction factor: 1.000000

## Scope

This record contains canonical inputs and selected assumptions.
It does not yet contain calculated analytical mechanics results.

# ThreadROM Analytical Member-Mechanics Report

## Record information

- Analytical joint: TRM-ANL-000001
- Compression method: uniform_annular_cylinder
- Material behaviour: Linear elastic
- Physics validation: PASS

## Loading and stack geometry

| Quantity | Value |
|---|---:|
| Preload | 5000.000000000 N |
| Total member thickness | 20.000000000 mm |
| Minimum compression area | 611.825169287 mm2 |

## Member layers

| Layer | Material | Thickness | Hole diameter | Outer diameter | Area | Stress | Strain | Shortening | Compliance | Energy |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| head_side_member | member_steel | 10.000000000 mm | 11.000000000 mm | 30.000000000 mm | 611.825169287 mm2 | 8.172269222 MPa | 3.891556772221e-05 | 3.891556772221e-04 mm | 7.783113544441e-08 mm/N | 9.728891930552e-01 N mm |
| nut_side_member | member_steel | 10.000000000 mm | 11.000000000 mm | 30.000000000 mm | 611.825169287 mm2 | 8.172269222 MPa | 3.891556772221e-05 | 3.891556772221e-04 mm | 7.783113544441e-08 mm/N | 9.728891930552e-01 N mm |

## Combined member response

| Quantity | Value |
|---|---:|
| Total compliance | 1.556622708888e-07 mm/N |
| Axial stiffness | 6424164.277509429 N/mm |
| Total shortening | 7.783113544441e-04 mm |
| Elastic strain energy | 1.945778386110e+00 N mm |
| Maximum layer compressive stress | 8.172269222 MPa |

## Bearing references

| Quantity | Value |
|---|---:|
| Head-side bearing area | 106.028752059 mm2 |
| Nut-side bearing area | 106.028752059 mm2 |
| Head-side mean bearing pressure | 47.157020175 MPa |
| Nut-side mean bearing pressure | 47.157020175 MPa |

## Physics-consistency validation

- Method: linear_member_compression_invariants_v1
- Overall status: PASS

| Check | Status | Description |
|---|---|---|
| nonempty_layers | PASS | At least one effective member layer must be present. |
| positive_layer_properties | PASS | Every member layer must have positive thickness, compression area, modulus and compliance. |
| compliance_sum | PASS | Total member compliance must equal the sum of the series-layer compliances. |
| stiffness_reciprocal | PASS | Member stiffness must equal the reciprocal of total compliance. |
| force_displacement_identity | PASS | Total shortening must equal preload multiplied by total member compliance. |
| layer_shortening_sum | PASS | Total shortening must equal the sum of all layer shortenings. |
| strain_energy_identity | PASS | Linear-elastic member strain energy must equal one-half force multiplied by shortening. |
| thickness_sum | PASS | Total member thickness must equal the sum of all layer thicknesses. |
| minimum_compression_area | PASS | Reported minimum compression area must equal the smallest resolved layer area. |
| maximum_compressive_stress | PASS | Reported maximum compressive stress must equal the maximum resolved layer stress. |
| positive_bearing_areas | PASS | Head-side and nut-side bearing areas must be positive. |
| head_bearing_pressure | PASS | Head-side mean bearing pressure must equal preload divided by head bearing area. |
| nut_bearing_pressure | PASS | Nut-side mean bearing pressure must equal preload divided by nut bearing area. |

## FEM comparison targets

- Total member shortening must be compared using governed head-side and nut-side reference planes.
- Member stiffness must use the same compressive force and relative displacement definitions.
- Layer stress is an analytical area-average value, not a local FEM contact or notch stress.
- Mean bearing pressure must be compared with a contact-area-weighted FEM pressure.

## Current limitations

- The uniform annular-cylinder method assumes constant compression area within each layer.
- Compression spreading and cone interaction are excluded.
- Local bearing deformation is excluded.
- Member-interface contact compliance is excluded.
- Interface opening, slip and friction are excluded.
- Plasticity and manufacturing variation are excluded.

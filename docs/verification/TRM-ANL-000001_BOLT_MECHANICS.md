# ThreadROM Analytical Bolt-Mechanics Report

## Record information

- Analytical joint: TRM-ANL-000001
- Bolt: TRM-BLT-000001
- Compliance method: segmented
- Material behaviour: Linear elastic
- Physics validation: PASS

## Loading and effective geometry

| Quantity | Value |
|---|---:|
| Preload | 5000.000000000 N |
| Tensile-stress area | 57.989596902 mm2 |
| External-root area | 52.292311658 mm2 |
| Head participation length | 5.000000000 mm |
| Nut participation length | 5.000000000 mm |
| Total effective bolt length | 30.000000000 mm |

## Effective axial segments

| Segment | Kind | Material | Length | Area | Stress | Strain | Elongation | Compliance | Energy |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| grip_thread | threaded | steel_8_8 | 20.000000000 mm | 57.989596902 mm2 | 86.222361719 MPa | 4.105826748516e-04 | 8.211653497031e-03 mm | 1.642330699406e-06 mm/N | 2.052913374258e+01 N mm |
| effective_head_participation | effective_head_participation | steel_8_8 | 5.000000000 mm | 57.989596902 mm2 | 86.222361719 MPa | 4.105826748516e-04 | 2.052913374258e-03 mm | 4.105826748516e-07 mm/N | 5.132283435645e+00 N mm |
| effective_nut_participation | effective_nut_participation | steel_8_8 | 5.000000000 mm | 57.989596902 mm2 | 86.222361719 MPa | 4.105826748516e-04 | 2.052913374258e-03 mm | 4.105826748516e-07 mm/N | 5.132283435645e+00 N mm |

## Combined axial response

| Quantity | Value |
|---|---:|
| Total compliance | 2.463496049109e-06 mm/N |
| Axial stiffness | 405927.178312916 N/mm |
| Total elongation | 1.231748024555e-02 mm |
| Elastic strain energy | 3.079370061387e+01 N mm |

## Stress and strength references

| Quantity | Value |
|---|---:|
| Nominal tensile-area stress | 86.222361719 MPa |
| Root-section reference stress | 95.616350500 MPa |
| Maximum effective-segment stress | 86.222361719 MPa |
| Proof utilisation | 0.148659244 |
| Yield utilisation | 0.134722440 |
| Ultimate utilisation | 0.107777952 |

## Physics-consistency validation

- Method: linear_axial_mechanics_invariants_v1
- Overall status: PASS

| Check | Status | Description |
|---|---|---|
| nonempty_segments | PASS | At least one effective axial bolt segment must be present. |
| positive_segment_properties | PASS | Every effective segment must have positive length, area, modulus and compliance. |
| compliance_sum | PASS | Total bolt compliance must equal the sum of the series-segment compliances. |
| stiffness_reciprocal | PASS | Axial stiffness must equal the reciprocal of total compliance. |
| force_displacement_identity | PASS | Total elongation must equal preload multiplied by total compliance. |
| segment_elongation_sum | PASS | Total elongation must equal the sum of all segment elongations. |
| strain_energy_identity | PASS | Linear-elastic strain energy must equal one-half force multiplied by elongation. |
| effective_length_sum | PASS | Effective bolt length must equal the sum of all effective segment lengths. |
| maximum_segment_stress | PASS | Reported maximum segment stress must equal the maximum resolved segment stress. |
| reference_stress_order | PASS | For positive preload, root-section reference stress must exceed nominal tensile-area stress. |

## FEM comparison targets

- Bolt elongation must be compared with relative axial
  displacement between governed bolt gauge planes.
- Bolt stiffness must use the same force and displacement
  definitions as the analytical result.
- Nominal tensile-area stress must be compared with a
  section-averaged axial FEM stress.
- The root-section reference stress is not a prediction
  of the local thread-root von Mises stress.

## Current limitations

- Head and nut participation are effective assumptions.
- Thread bending and local contact compliance are excluded.
- Tightening torsion is excluded.
- Thread-root stress concentration is excluded.
- Plasticity, fatigue and preload scatter are excluded.

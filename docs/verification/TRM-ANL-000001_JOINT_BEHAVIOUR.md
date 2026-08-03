# ThreadROM Analytical Joint-Behaviour Report

## Record information

- Analytical joint: TRM-ANL-000001
- External-load method: basic_spring_ratio
- Joint model: Piecewise linear two-spring model
- Material behaviour: Linear elastic
- Physics validation: PASS

## Stiffness and load sharing

| Quantity | Value |
|---|---:|
| Bolt stiffness | 405927.178312916 N/mm |
| Member stiffness | 6424164.277509429 N/mm |
| Basic bolt-load fraction | 0.059432173191 |
| Load-introduction factor | 1.000000000000 |
| Effective bolt-load fraction | 0.059432173191 |
| Nominal separation load | 5315.937731958 N |

## Preload envelope

| Quantity | Value |
|---|---:|
| Preload scatter fraction | 0.000000000000 |
| Minimum preload | 5000.000000000 N |
| Nominal preload | 5000.000000000 N |
| Maximum preload | 5000.000000000 N |

## Evaluated joint states

| Point | Preload case | External-load case | Preload | External load | Regime | Bolt force | Member compression | Separation margin | Opening |
|---|---|---|---:|---:|---|---:|---:|---:|---:|
| minimum_preload:static | minimum_preload | static | 5000.000000000 N | 0.000000000 N | clamped | 5000.000000000 N | 5000.000000000 N | 5315.937731958 N | 0.000000000000e+00 mm |
| nominal_preload:static | nominal_preload | static | 5000.000000000 N | 0.000000000 N | clamped | 5000.000000000 N | 5000.000000000 N | 5315.937731958 N | 0.000000000000e+00 mm |
| maximum_preload:static | maximum_preload | static | 5000.000000000 N | 0.000000000 N | clamped | 5000.000000000 N | 5000.000000000 N | 5315.937731958 N | 0.000000000000e+00 mm |

## Envelope extrema

| Quantity | Value |
|---|---:|
| Highest bolt force | 5000.000000000 N |
| Lowest member compression | 5000.000000000 N |
| Minimum separation margin | 5315.937731958 N |
| Maximum joint opening | 0.000000000000e+00 mm |
| Separation in configured envelope | NO |

## Cyclic response

No cyclic external-load range is configured.

## Governing bolt-strength references

| Quantity | Value |
|---|---:|
| Governing envelope point | minimum_preload:static |
| Highest bolt force | 5000.000000000 N |
| Tensile-stress area | 57.989596902 mm2 |
| External-root area | 52.292311658 mm2 |
| Highest nominal tensile stress | 86.222361719 MPa |
| Highest root-section reference stress | 95.616350500 MPa |
| Proof utilisation | 0.148659244343 |
| Yield utilisation | 0.134722440186 |
| Ultimate utilisation | 0.107777952149 |
| Maximum nominal cyclic-stress amplitude | not available |
| Maximum root-reference stress amplitude | not available |

## Physics-consistency validation

- Method: piecewise_two_spring_joint_invariants_v1
- Overall status: PASS

| Check | Status | Description |
|---|---|---|
| nonempty_envelope | PASS | At least one preload and external-load combination must be evaluated. |
| unique_point_ids | PASS | Every joint-envelope point must have a unique identity. |
| positive_stiffnesses | PASS | Bolt and member stiffnesses must remain positive for every evaluated point. |
| valid_load_fractions | PASS | Basic and effective bolt-load fractions must lie in [0, 1). |
| external_load_equilibrium | PASS | Bolt tension minus member compression must equal the external separating load. |
| clamped_state_consistency | PASS | Clamped states must follow the two-spring load-sharing equations without joint opening. |
| separated_state_consistency | PASS | Separated states must carry the full external load in the bolt with zero member compression. |
| envelope_extrema | PASS | Reported envelope extrema must equal the extrema of all evaluated points. |
| separation_flag | PASS | The envelope separation flag must match the evaluated contact regimes. |
| cyclic_response_identities | PASS | Cyclic force means, amplitudes, ranges and member-force ordering must be consistent. |
| strength_envelope_identity | PASS | The strength result must use the same joint identity and governing bolt force. |
| governing_point | PASS | The reported governing point must exist and carry the envelope maximum bolt force. |
| section_stress_identities | PASS | Nominal and root-section reference stresses must equal force divided by their areas. |
| reference_stress_order | PASS | For positive bolt force, root-section reference stress must exceed nominal tensile-area stress. |

## FEM comparison targets

- Bolt and member stiffnesses must be compared using matching force and displacement definitions.
- The pre-separation bolt-force slope must be compared with the FEM bolt-force response.
- The analytical separation load must be compared with the first governed loss of interface compression.
- Post-separation opening must use governed member reference planes rather than a single nodal displacement.
- Section stresses must be compared with section-averaged axial FEM stresses.

## Current limitations

- The model is axial, linear elastic and quasi-static.
- Before separation, external load is shared through the selected two-spring load fraction.
- After separation, the bolt is assumed to carry the full separating load and member compression is zero.
- Bending, shear, prying, transverse slip and frictional load transfer are excluded.
- The root-section value is a reference stress, not a local thread-root notch stress.
- Cyclic stress amplitudes are reference quantities; fatigue life is not evaluated.
- Preload scatter is represented as symmetric bounds around the nominal preload.

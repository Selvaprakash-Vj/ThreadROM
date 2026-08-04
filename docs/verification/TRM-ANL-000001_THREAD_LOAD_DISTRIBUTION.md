# ThreadROM Analytical Thread-Load Distribution Report

## Record information

- Analytical joint: TRM-ANL-000001
- Distribution method: two_axial_bars_centroid_springs_v1
- Thread-stiffness method: iso_triangle_elastic_transfer_stiffness_v1
- Engagement discretization: axial_pitch_cells_v1
- Boundary condition: nut_fixed_at_bearing_face__bolt_force_at_bearing_face__both_bars_free_at_engagement_end
- Physics validation: PASS

## Engagement convention

- Axial origin: nut_bearing_face
- Numbering direction: bearing_face_to_nut_free_end
- Turn 1 is the engaged turn nearest the nut bearing face.

| Quantity | Value |
|---|---:|
| Pitch | 1.500000000 mm |
| Engagement length | 8.000000000 mm |
| Nominal engaged pitches | 5.333333333333 |
| Active discrete turns | 6 |
| Complete turns | 5 |
| Final partial-turn fraction | 0.333333333333 |

## Elastic transfer properties

| Quantity | Value |
|---|---:|
| Bolt axial area | 52.292311658 mm2 |
| Nut axial area | 145.957792986 mm2 |
| Combined distributed thread stiffness | 78054.631677944 N/mm2 |
| Transfer parameter | 0.098257076973 1/mm |
| Characteristic transfer length | 10.177383969 mm |
| Helix angle | 3.028150570 deg |
| Projection convention | distributed_axial_stiffness_equals_helix_stiffness_times_sin_beta |

## Per-turn load distribution

| Turn | Axial centroid | Engagement fraction | Spring stiffness | Turn load | Load share | Cumulative share | Remaining bolt force |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 0.750000000 mm | 1.000000000000 | 117081.947516917 N/mm | 1072.354867025 N | 21.447097% | 21.447097% | 3927.645132975 N |
| 2 | 2.250000000 mm | 1.000000000000 | 117081.947516917 N/mm | 987.036518469 N | 19.740730% | 41.187828% | 2940.608614506 N |
| 3 | 3.750000000 mm | 1.000000000000 | 117081.947516917 N/mm | 923.159090074 N | 18.463182% | 59.651010% | 2017.449524432 N |
| 4 | 5.250000000 mm | 1.000000000000 | 117081.947516917 N/mm | 879.335003148 N | 17.586700% | 77.237710% | 1138.114521285 N |
| 5 | 6.750000000 mm | 1.000000000000 | 117081.947516917 N/mm | 854.612288102 N | 17.092246% | 94.329955% | 283.502233183 N |
| 6 | 7.750000000 mm | 0.333333333333 | 39027.315838972 N/mm | 283.502233183 N | 5.670045% | 100.000000% | 0.000000000 N |

## Governing distribution quantities

| Quantity | Value |
|---|---:|
| Total transferred load | 5000.000000000 N |
| First-turn load | 1072.354867025 N |
| First-turn load share | 21.447097% |
| Maximum-loaded turn | 1 |
| Maximum turn load | 1072.354867025 N |
| Maximum turn load share | 21.447097% |
| Final remaining bolt force | 2.819433575496e-11 N |
| Load-conservation error | -2.910383045673e-11 N |
| Nut-bearing reaction | -5000.000000000 N |
| Global-equilibrium error | 2.364686224610e-11 N |

## Physics-consistency validation

- Validation method: discrete_thread_spring_invariants_v1
- Overall status: PASS

| Check | Status | Description |
|---|---|---|
| nonempty_turn_distribution | PASS | At least one engaged thread turn must carry the transferred load. |
| turn_count_consistency | PASS | Reported active-turn counts must match the distribution and engagement records. |
| turn_numbering_consistency | PASS | Thread turns must be numbered consecutively from the nut bearing face. |
| positive_thread_stiffness | PASS | All thread springs and governing transfer stiffnesses must be finite and positive. |
| nonnegative_turn_loads | PASS | Every active thread turn must carry a finite nonnegative axial load. |
| turn_load_share_identity | PASS | Each reported load share must equal its turn load divided by total transferred load. |
| cumulative_force_identities | PASS | Cumulative load, cumulative share and remaining bolt force must be internally consistent. |
| monotonic_cumulative_transfer | PASS | Cumulative transferred load must not decrease and remaining bolt force must not increase. |
| load_conservation | PASS | Thread-turn loads and load shares must conserve the full transferred axial load. |
| bearing_reaction_equilibrium | PASS | The nut-bearing reaction must balance the applied bolt load. |
| first_turn_identity | PASS | Reported first-turn force and share must match the first turn in the distribution. |
| maximum_turn_identity | PASS | Reported maximum-loaded turn quantities must match the governing turn record. |
| engagement_fraction_consistency | PASS | Turn engagement fractions must be valid and sum to the nominal engaged-pitch count. |
| transfer_length_identity | PASS | The characteristic transfer length must be the reciprocal of the transfer parameter. |

## FEM comparison targets

- Compare the analytical load share of each turn against integrated normal contact force on matching bolt-nut flank pairs.
- Compare the analytical first-turn share only after the FEM thread numbering and bearing-face origin have been confirmed.
- Verify convergence of the first-turn share across coarse, medium and fine contact meshes.
- Check whether the partial final turn exists in the FEM geometry before including it in the comparison.
- Evaluate the selected helix projection convention against FEM and literature evidence during Checkpoint 8.

## Current limitations

- The model uses linear-elastic one-dimensional bolt and nut bars coupled by discrete axial springs.
- Thread springs are concentrated at pitch-cell centroids rather than distributed continuously.
- Local flank contact pressure, root bending stress, plasticity and contact opening are not resolved.
- Manufacturing tolerances, pitch error, flank error and incomplete first-thread geometry are excluded.
- Friction, tightening torsion and helical circumferential load variation are excluded.
- The final partial turn is scaled by engaged axial length using the same local stiffness law.
- The reported first-turn share is a provisional analytical prediction pending Checkpoint 8 verification.

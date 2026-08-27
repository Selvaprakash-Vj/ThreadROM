# ThreadROM Analytical Thread-Mechanics Report

## Record information

- Analytical joint: TRM-ANL-000002
- Bolt: TRM-BLT-000001
- Nut: TRM-NUT-000001
- Method: iso_metric_basic_profile_60_deg
- Status: Governed analytical result
- Physics validation: PASS

## Thread definition

| Quantity | Value |
|---|---:|
| Nominal diameter | 10.000000000 mm |
| Pitch | 1.500000000 mm |
| Starts | 1 |
| Lead | 1.500000000 mm |
| Included angle | 60.000000000 deg |
| Flank half-angle | 30.000000000 deg |
| External tolerance class | 6g |
| Internal tolerance class | 6H |

## Basic ISO metric dimensions

| Quantity | Value |
|---|---:|
| Fundamental triangle height | 1.299038106 mm |
| Basic pitch diameter | 9.025721421 mm |
| Basic internal minor diameter | 8.376202368 mm |
| Basic external minor diameter | 8.159696017 mm |
| External radial thread depth | 0.920151992 mm |
| Internal radial thread depth | 0.811898816 mm |

## Cross-sectional properties

| Quantity | Value |
|---|---:|
| Nominal shank area | 78.539816340 mm2 |
| Pitch-diameter area | 63.981398867 mm2 |
| Tensile-stress area | 57.989596902 mm2 |
| External-root area | 52.292311658 mm2 |
| Tensile-to-nominal area ratio | 0.738346480 |
| Root-to-nominal area ratio | 0.665806391 |

## Engagement and helix

| Quantity | Value |
|---|---:|
| Engagement length | 8.000000000 mm |
| Engaged pitch count | 5.333333333 |
| Engaged lead-turn count | 5.333333333 |
| Helix angle at pitch diameter | 3.028150570 deg |

## Physics-consistency validation

- Method: deterministic_geometry_invariants_v1
- Overall status: PASS

| Check | Status | Description |
|---|---|---|
| diameter_order | PASS | External minor, internal minor, pitch and nominal diameters must be positive and strictly ordered. |
| area_order | PASS | Root, tensile, pitch-diameter and nominal areas must be positive and strictly ordered. |
| positive_thread_depths | PASS | External and internal radial thread depths must be positive. |
| lead_consistency | PASS | Thread lead must equal pitch multiplied by the number of starts. |
| engaged_pitch_count_consistency | PASS | Engaged pitch count must equal engagement length divided by pitch. |
| engaged_turn_count_consistency | PASS | Engaged lead-turn count must equal engagement length divided by lead. |
| area_ratio_bounds | PASS | Root and tensile area ratios must remain between zero and one and physically ordered. |
| helix_angle_bounds | PASS | Pitch-diameter helix angle must be finite and lie strictly between zero and 90 degrees. |

## Interpretation

The reported dimensions use the ideal 60-degree ISO metric
basic profile. Tolerance classes are retained as governed
metadata but are not yet applied as dimensional deviations.

The tensile-stress area is intended for nominal axial stress
and threaded-segment compliance calculations.

The external-root area is a geometric root-section reference.
It is not a substitute for a thread-root stress-concentration
or local notch-stress calculation.

The engaged pitch count can be non-integer because the input
engagement length is treated as a continuous geometric value.

## Current limitations

- Tolerance deviations are not yet resolved.
- Manufacturing truncation variation is not included.
- Root radius and thread runout are not included.
- Thread shear and stripping areas are not yet calculated.
- Per-thread load distribution is handled in Checkpoint 7.

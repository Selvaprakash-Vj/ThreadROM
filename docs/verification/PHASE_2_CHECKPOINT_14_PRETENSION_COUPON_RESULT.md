# Phase 2 Checkpoint 14 - Contact-Free Pretension Coupon Result

## Purpose

This checkpoint independently validated the CalculiX pretension-section
semantics used by the complete threaded-joint model.

The diagnostic removed all contact, joint members, DCOUP3D elements, MEANROT
constraints, and full-joint guidance conditions.

The coupon tested whether:

- the pretension-section syntax is valid;
- reference-node degree of freedom 1 is correct;
- positive and negative reference forces produce opposite physical responses;
- the specified pretension vector and owner surface generate the expected
  axial stress sign.

## Governed diagnostic

- Diagnostic ID: `TRM-DIAG-000001`
- Definition commit: `ed034c6`
- Element type: `C3D8`
- Elements: `4`
- Physical nodes: `20`
- Pretension reference nodes: `1`
- Coupon dimensions: `10 x 10 x 40 mm`
- Cross-sectional area: `100 mm^2`
- Material Young's modulus: `210000 MPa`
- Poisson ratio: `0.30`
- Pretension cut position: `z = 20 mm`
- Pretension owner surface: element `2`, face `S2`
- Pretension vector: `(0, 0, +1)`
- Reference-node load degree of freedom: `1`
- Applied force magnitude: `1000 N`
- Expected axial-stress magnitude: `10 MPa`

The positive and negative decks were identical except for the heading and
reference-force sign.

## Positive-force result

The positive case applied:

`+1000 N`

The accepted increment converged in two iterations.

Measured results:

- Reference-node U1:
  `+1.859705e-3 mm`
- Reference-node force:
  `+1000 N`
- Bottom reaction in Z:
  `-1000 N`
- Top reaction in Z:
  `+1000 N`
- Mean axial stress S33:
  `+10.000256625 MPa`
- Expected axial stress:
  `+10.000000000 MPa`
- Relative stress error:
  `+0.00256625 %`

The positive reference force therefore produced structural tension.

## Negative-force result

The negative case applied:

`-1000 N`

The accepted increment converged in two iterations.

Measured results:

- Reference-node U1:
  `-1.859966e-3 mm`
- Reference-node force:
  `-1000 N`
- Bottom reaction in Z:
  `+1000 N`
- Top reaction in Z:
  `-1000 N`
- Mean axial stress S33:
  `-9.999743000 MPa`
- Expected axial stress:
  `-10.000000000 MPa`
- Relative stress-magnitude error:
  `-0.00257000 %`

The negative reference force therefore produced structural compression.

## Sign-reversal symmetry

The two cases demonstrated the expected sign reversal:

| Quantity | Positive case | Negative case |
|---|---:|---:|
| Reference force | +1000 N | -1000 N |
| Reference U1 | +1.859705e-3 mm | -1.859966e-3 mm |
| Mean S33 | +10.000256625 MPa | -9.999743000 MPa |
| Bottom reaction Z | -1000 N | +1000 N |
| Top reaction Z | +1000 N | -1000 N |

The stress magnitudes agree with the analytical value of `10 MPa` to within
approximately `0.003 %`.

## Engineering conclusion

The CalculiX pretension implementation is functioning correctly in isolation.

The diagnostic proves that:

- `*PRE-TENSION SECTION` syntax is valid;
- reference-node degree of freedom 1 is correct;
- the element-based pretension surface is valid;
- the specified vector and owner-face combination is valid;
- positive reference force produces axial tension;
- negative reference force produces axial compression;
- the solver responds correctly and symmetrically to force-sign reversal.

Therefore, the physically invalid opening observed in the complete joint is
not caused by a fundamental CalculiX pretension-sign or reference-DOF error.

The remaining root cause must involve the complete-joint environment,
including one or more of:

- zero-load contact or constraint settling;
- pretension-section insertion interacting with the assembled joint;
- guidance constraints;
- initial geometry or contact imbalance;
- interaction between contact, pretension kinematics, and joint supports.

## Evidence preservation

The complete diagnostic evidence is stored under:

`simulations/archive/TRM-DIAG-000001/pretension_coupon_20260806_163923`

The archive contains:

- positive and negative governed input decks;
- DAT, FRD, STA, and CVG results;
- solver stdout and stderr logs;
- run manifest;
- result manifest;
- SHA256 hash manifest.

Archive verification confirmed:

- Source files copied: `18`
- Evidence files hashed: `19`
- Solver failures: `0`
- Nonempty stderr logs: `0`

## Checkpoint status

- Contact-free coupon definition: **PASS**
- Positive-force solve: **PASS**
- Negative-force solve: **PASS**
- Analytical stress agreement: **PASS**
- Force-sign reversal: **PASS**
- Reference-node DOF semantics: **PASS**
- CalculiX pretension implementation: **VALIDATED**
- Full-joint physical clamp state: **NOT YET ACHIEVED**

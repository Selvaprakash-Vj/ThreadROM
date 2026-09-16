# TRM-ANA-000001 ? Thermal Preload Compatibility Certification

**Status:** VERIFIED
**Project:** ThreadROM
**Phase:** Phase 3 ? Pre-DOE hardening
**Gate:** Gate 5 ? Geometry + Analytical Mechanics
**Applicability:** Current governed elastic bolted-joint topology; M10 FEM evidence anchor with diversified architecture prepared for M8/M10/M12 transfer
**DOE authorization:** NO ? this certificate closes Gate 5 only

---

## 1. Purpose

This record certifies the analytical mechanics used to generate the
physics-derived thermal-preload seed for the governed ThreadROM FEM
workflow.

The audit was performed before diversified FEM DOE execution so that
the analytical preload model would not silently mix:

- mechanical bolt effective length,
- thermal eigenstrain actuation length,
- engaged-thread load transfer,
- member compression,
- contact/seating behaviour, or
- execution-generation-specific FEM residuals.

The governing principle is that analytical physics must explain the
load path independently of FEM calibration. FEM evidence may validate
or correct a trial temperature, but it must not be converted into an
unidentified fitted analytical coefficient.

---

## 2. Historical V1 finding

The historical analytical seed used

    alpha * |deltaT| * L_eff
        = F_target * (C_bolt + C_member)

where `L_eff` came from the general analytical bolt-mechanics model.

For the certified M10 baseline:

- total grip length = 20.0 mm
- head participation = 5.0 mm
- nut participation = 5.0 mm
- historical mechanical effective bolt length = 30.0 mm

The FEM semantic deformation definition independently establishes the
physical thermal free span as the distance from the bolt under-head
bearing plane to the thread-engagement entry plane.

For all four certified legacy M10 anchors:

- free-span start Z = 0.0 mm
- free-span end Z = 20.0 mm
- physical thermal actuation length = 20.0 mm

Therefore the historical 30 mm mechanical effective length is not a
valid thermal eigenstrain actuation length.

The historical V1 implementation and its frozen evidence remain
preserved for provenance and replay. They are not silently rewritten.

---

## 3. V2 load-path separation

The V2 thermal-preload compatibility model separates three concepts:

1. physical thermal actuation span,
2. free-span bolt mechanical compliance,
3. engaged-thread bolt load-transfer compliance.

The thermal actuation length is

    L_thermal = L_grip

for the current governed assembly topology.

The bolt mechanical compliance is

    C_bolt,V2
        = C_free_span
        + C_thread_transfer

The engaged-thread equivalent transfer length is derived from the
existing governed discrete thread-load distribution:

    L_thread_transfer
        = sum(s_i * z_i)

where:

- `s_i` is the resolved load share of engaged turn `i`,
- `z_i` is its axial centroid measured from the nut bearing face.

This is the discrete equivalent of integrating the remaining bolt-force
fraction through the engagement.

No FEM-fitted participation factor or calibration coefficient is used.

---

## 4. Certified M10 V2 analytical values

For the certified M10 baseline:

- thermal actuation length:
  - 20.000000000 mm
- free-span bolt length:
  - 20.000000000 mm
- thread-transfer equivalent length:
  - 3.813845784596 mm
- governed thread-transfer bolt axial area:
  - 52.292311658456 mm?
- free-span bolt compliance:
  - 1.642330699406e-06 mm/N
- thread-transfer bolt compliance:
  - 3.473009669463e-07 mm/N
- total V2 bolt compliance:
  - 1.989631666353e-06 mm/N

The V2 analytical preload seed retains the existing governed member
compliance model and uses the physical thermal actuation length rather
than the general mechanical effective bolt length.

For the M10 baseline, the V2 analytical first-trial temperature is:

- V1 historical prediction:
  - -145.508795555458 ?C
- V2 prediction:
  - -178.774494770112 ?C
- certified legacy FEM accepted temperature:
  - -243.274497100000 ?C

The remaining difference is intentionally left for governed FEM
calibration/warm-start logic rather than embedded into analytical
physics.

---

## 5. Independent FEM bolt-compliance comparison

The V2 bolt-compliance model was compared against four already-certified
legacy FEM anchors. No new CalculiX solve was executed for this audit.

| Anchor | Case | FEM bolt compliance [mm/N] | V2 analytical [mm/N] | Relative error |
|---|---|---:|---:|---:|
| A00 | P00_BASELINE_CONTROL | 1.910004757759e-06 | 1.989631666353e-06 | +4.17% |
| A01 | P01_PRELOAD_LOW | 1.879148390523e-06 | 1.989631666353e-06 | +5.88% |
| A02 | P03_ASYMMETRIC_GRIP | 1.931610448050e-06 | 1.989631666353e-06 | +3.00% |
| A03 | P04_RADIAL_GEOMETRY | 2.006304035936e-06 | 1.989631666353e-06 | -0.83% |

Maximum absolute relative error:

- < 6%

Mean absolute relative error:

- approximately 3.47%

This agreement is achieved without fitting the V2 compliance to the FEM
anchor values.

---

## 6. Member-compliance finding

The FEM semantic deformation replay produced:

| Anchor | FEM member compliance [mm/N] |
|---|---:|
| A00 | 1.601263498092e-07 |
| A01 | 1.599877562754e-07 |
| A02 | 1.646144428274e-07 |
| A03 | 1.014944294168e-07 |

For A00-A02 the existing uniform-annular analytical member model remains
close to the FEM evidence.

The audited 30-degree cone model was substantially more compliant and is
therefore not adopted merely to reduce preload-seed error.

A03 intentionally changes radial geometry and demonstrates that member
compliance remains geometry dependent.

---

## 7. Legacy seating / transfer residual

The FEM deformation decomposition also exposed displacement between the
member bearing planes and the bolt semantic load-transfer locations.

For identical A00/A01 geometry and mesh, the nut/thread-side displacement
changed only weakly despite a 25% preload reduction.

A robustness check replaced the single engagement-entry node with
multi-node axial-band regressions over:

- ?0.25 pitch,
- ?0.50 pitch,
- ?1.00 pitch.

The same behaviour remained.

Therefore this residual is not treated as a simple linear analytical
spring.

It may include nonlinear thread/contact seating and
execution-generation-specific initialization effects.

Such residual behaviour remains the responsibility of governed FEM
calibration and must not be converted into an unidentified universal
analytical compliance.

---

## 8. Historical evidence protection

The V2 implementation is additive.

The historical function:

    derive_analytical_thermal_preload_seed(...)

retains the certified V1 behaviour used by historical CP8 evidence.

The new V2 mechanics and seed are separate APIs.

Historical warm-start records, geometry identity, execution-generation
identity, and accepted FEM artifacts therefore remain reproducible
without silent reinterpretation.

Production adoption of the V2 seed belongs to the following preload /
contact / boundary-condition certification gate.

---

## 9. Geometry interaction

Gate-5 geometry certification established that:

- the external threaded-shank physical core now terminates at the true
  governed minor radius rather than absorbing Boolean overlap;
- fusion-bridge construction height is physically invariant across the
  audited range;
- thread Boolean overlap preserves the finished envelope but can produce
  a very small finite non-engaged thread-termination volume effect;
- the certified overlap sensitivity remains below 1.5e-4 relative
  complete-bolt volume across the governed audit range;
- geometry implementation revision is explicitly part of geometry
  identity;
- legacy FEM evidence cannot silently certify the corrected geometry
  generation.

The detailed geometry evidence is recorded separately in
`TRM-GEO-000001_DIVERSIFIED_GEOMETRY_CERTIFICATION.md`.

---

## 10. Verification evidence

Focused V2 preload compatibility regression:

- 7 passed

Corrected CAD construction-aid contract regression:

- 6 passed

Final complete unit regression:

- 865 passed
- 0 failed

Final unit-suite runtime:

- 598.08 s

No new CalculiX solve was executed for this analytical certification.

No sealed holdout evidence was accessed.

---

## 11. Gate-5 disposition

**PASS**

Gate 5 ? Geometry + Analytical Mechanics is technically certified.

The following are explicitly *not* certified by this record:

- production adoption of the V2 preload seed,
- current-generation contact / boundary-condition behaviour,
- current-generation nonlinear solver path,
- cross-size FEM transfer,
- diversified FEM DOE,
- ROM applicability.

Those remain governed by subsequent pre-DOE gates.

The diversified production DOE remains **NOT AUTHORIZED** by this
certificate alone.

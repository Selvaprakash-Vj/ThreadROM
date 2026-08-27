# ThreadROM Phase 2 Final 20 kN Certification

**Status:** PASS  
**Certification date:** 2026-08-27  
**Certified run:** `trm_sim_000004_run_a2_thermal_20kn`  
**Purpose:** Governed nonlinear physical preload baseline for Phase 3.

---

## 1. Certified baseline

- Joint: M10 ? 1.5 threaded bolted joint
- Target preload: **20.000 kN**
- Preload actuator: governed bolt-only thermal eigenstrain
- Reference temperature: **20.0 ?C**
- Governed equivalent ?T: **-243.2744971 ?C**
- Applied bolt temperature: **-223.2744971 ?C**
- Native CalculiX pretension section: **not used**
- Direct mechanical CLOAD preload: **not used**

The thermal field is a numerical preload actuator only and is not
interpreted as a physical service temperature.

---

## 2. Physical preload result

Final Increment 20:

| Quantity | Result |
|---|---:|
| Under-head CFN | 20.060270 kN |
| Nut-bearing CFN | 20.066050 kN |
| Member-interface CFN | 20.064180 kN |
| Mean planar clamp force | **20.063500 kN** |
| Target error | **+0.31750 %** |
| Interface spread | **5.780 N / 0.02881 %** |
| Thread scalar normal force | 15.318240 kN |

Acceptance:

- preload tolerance ?1 %: **PASS**
- planar interface spread ?0.5 %: **PASS**

---

## 3. Thread-flank load state

A final-state solid-STRESS diagnostic was evaluated on the real
bolt-thread surface inside the nut engagement span.

| Quantity | Intended / dominant flank | Opposite flank |
|---|---:|---:|
| Outward-normal family | -Z | +Z |
| Area-weighted compression | 317.140 MPa | 38.443 MPa |
| Median compression | 46.030 MPa | 0.000 MPa |
| Compressive-area proxy | 59.844 % | 19.163 % |

Mean compression dominance ratio:

**8.2496 ?**

**Result: PASS ? decisive intended-flank dominance.**

This is a solid-stress directionality diagnostic rather than native
`CPRESS/COPEN`; it is therefore used to certify flank-loading
direction, not absolute contact pressure.

---

## 4. Axial mechanics

| Quantity | Result |
|---|---:|
| Bolt free-span mean SZZ | +315.656 MPa |
| Bolt free-span median SZZ | +335.369 MPa |
| Head-side member mean SZZ | -33.081 MPa |
| Nut-side member mean SZZ | -32.952 MPa |

Interpretation:

- bolt axial state: **tension ? PASS**
- head-side member: **compression ? PASS**
- nut-side member: **compression ? PASS**

The FE free-span mean stress and the analytical ISO tensile-area
stress are not identical measures. The FE value averages stress over
the actual three-dimensional threaded-band geometry, whereas the
analytical value uses the idealized tensile stress area.

---

## 5. Deformation consistency

| Quantity | Result |
|---|---:|
| FEM member shortening | **0.003212695 mm** |
| Analytical member shortening | **0.003113245 mm** |
| FEM / analytical | **1.031944** |
| Inferred bolt mechanical extension | **+0.038321380 mm** |

The member-shortening difference relative to the analytical
benchmark is approximately **3.19 %**.

**Result: PASS.**

---

## 6. Local displacement maximum

Raw global maximum displacement:

**0.524556893 mm**

Location:

- nut internal-thread/contact region
- node 7902
- `(0.098269, 4.186948, 28.000000) mm`

Nut population statistics:

| Quantity | Entire nut | Internal-thread surface |
|---|---:|---:|
| Median magnitude | 0.038693 mm | 0.042062 mm |
| P95 magnitude | 0.068809 mm | 0.070647 mm |
| Mean radial displacement | +0.011258 mm | +0.011087 mm |
| Mean tangential displacement | -0.000784 mm | -0.000731 mm |

Neighboring nodes around node 7902 also exhibit elevated but
continuously varying displacement.

Therefore the 0.525 mm result is classified as a **localized
thread/contact deformation maximum**, not representative global
joint elongation and not an isolated single-node numerical spike.

Engineering axial deformation is represented by the bolt mechanical
extension and member-stack shortening reported above.

---

## 7. Stress-hotspot interpretation

Raw extrapolated nodal maxima included:

- global / nut von Mises: ~217.5 GPa
- bolt von Mises: ~20.8 GPa
- head-side member: ~367.6 MPa
- nut-side member: ~418.2 MPa

The extreme bolt/nut thread/contact-edge values are classified as
mesh-dependent local singularity/hotspot quantities and **must not**
be interpreted as physical bulk steel stresses or used directly for
strength utilization.

The representative preload stress state is instead supported by:

- analytical nominal tensile stress: ~344.9 MPa
- analytical thread-root reference: ~382.5 MPa
- FE free-span mean SZZ: ~315.7 MPa
- FE free-span median SZZ: ~335.4 MPa

### Plate-strength limitation

Phase 2 does **not** certify plate strength from the raw
367.6 / 418.2 MPa hole/bearing-edge maxima.

Those local values require a separately governed material allowable
and mesh-sensitivity / bearing assessment before being used as a
plate-strength criterion.

This limitation does not invalidate the Phase-2 preload/load-transfer
baseline.

---

## 8. Numerical quality

- Accepted increments: **20 / 20**
- Final increment attempts: **ATT1**
- Unsuccessful attempts / cutbacks: **0**
- Final increment nonlinear iterations: **21**
- CalculiX termination: **Job finished**

**Result: PASS.**

---

## 9. Regression

Final repository regression suite:

**337 passed in 1418.04 s (23:38)**

No failing tests remained after updating stale expectations to the
certified governed thermal calibration.

**Result: PASS.**

---

## 10. Rejected preload routes retained as engineering evidence

### Native CalculiX pretension section

Rejected because the tetrahedral pretension-cut topology violated the
required section topology and produced approximately 20 kN reference
force without equivalent physical clamp-force transfer.

### Nut-turn / MEANROT route

Produced coherent and balanced contact-force transfer but saturated at
approximately 3.2?3.4 kN instead of reaching 20 kN.

Rejected as the Phase-2 preload actuator.

The unresolved ideal-pitch-versus-effective-MEANROT relationship is
retained as a future investigation topic and does not block the
certified thermal preload baseline.

---

## 11. Certification conclusion

The governed A2 baseline demonstrates:

- target physical preload within tolerance,
- consistent clamp force across all three planar load-transfer paths,
- correct thread-flank load direction,
- bolt net tension,
- member net compression,
- deformation consistent with the analytical joint model,
- clean nonlinear convergence,
- and a fully green repository regression suite.

**PHASE 2 PHYSICAL BASELINE: CERTIFIED PASS**

The model is suitable to be frozen as the reference nonlinear
preloaded joint state for the governed Phase-3 FEM factory.

---

## 12. Evidence hashes

- **governed preload config:** `2e5af364e52552ee3b683414842d8ee2a50d5bdb111a9e7dea2cc00037115da9`
- **analytical benchmark config:** `7bca8ebfd27df82dda9d9e5a98aca1e65446e436049e7fb91610b3b27dd8d28a`
- **A2 solver deck:** `dcf571506a46679f2eab2f7c5e2e3a85af861544ddf56d84d60466c8dd90c634`
- **A2 contact results:** `21c91f504eeda90cd96fa6ace083e7fa981dd4fa238ae25d311f9ef5e8f0f86c`
- **A2 solver status:** `e2d5ba88509242ca03329d1e9dee6c5d87ccb22426bdc0cd47bcce8e5b8512e4`
- **A2 solver log:** `25ef8d50c72ca0f757eedac48af7edbdc2ba103652944fa03d72ebadff638415`

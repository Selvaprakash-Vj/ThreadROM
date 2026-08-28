# Phase 3 CP4 – Certified FEM Reproduction

## Status

**PASS – CERTIFIED**

Phase 3 Checkpoint 4 demonstrates that the governed ThreadROM FEM
factory can regenerate and reproduce the certified Phase 2 nonlinear
M10×1.5 threaded-joint baseline without manual solver/model tweaking.

The authoritative live reproduction passed:

- 13 / 13 hard acceptance gates
- 31 / 31 Phase 2 reproduction-parity gates
- 0 diagnostics
- 0 failed checks

The successful governed live CalculiX execution returned process code 0,
completed all 20 nonlinear increments on ATT1, emitted the CalculiX
`Job finished` marker, and reproduced the certified final nonlinear
signature:

- STEP 1
- INC 20
- ATT 1
- 21 iterations

---

## Governing certified case

Run ID:

`trm_sim_000004_run_a2_thermal_20kn`

Certified mesh:

`TRM-MSH-000005`

Element formulation:

`C3D4`

Mesh size:

- 101,493 nodes
- 509,115 tetrahedral elements

Certified preload target:

`20,000 N`

Governed bolt-only thermal eigenstrain:

- reference temperature: 20 °C
- thermal expansion coefficient: 1.2e-5 /°C
- equivalent delta temperature: -243.2744971 °C

The equivalent temperature is a calibrated preload eigenstrain and is
not interpreted as a physical service temperature.

---

## Phase 3 deterministic deck reproduction

The Phase 3 factory regenerated the certified CalculiX input deck
deterministically.

Fresh deck:

`D:\ThreadROM\.tmp\cp4_step6_live_reproduction\trm_sim_000004_run_a2_thermal_20kn.inp`

Size:

`26,774,872 bytes`

SHA-256:

`dcf571506a46679f2eab2f7c5e2e3a85af861544ddf56d84d60466c8dd90c634`

This exactly matches the certified Phase 2 deck hash.

---

## Live solver execution

The authoritative CP4 live run used CalculiX 2.23 with the governed
certified FEM profile.

Observed completion evidence:

- process return code: 0
- accepted increments: 20 / 20
- attempts: ATT1 throughout
- final increment: STEP 1 / INC 20
- final attempt: ATT 1
- final iterations: 21
- CalculiX `Job finished`: true

No cutback/retry was observed.

---

## Fresh clamp-transfer reproduction

Final native CalculiX contact-statistics values:

| Quantity | Fresh result |
|---|---:|
| Under-head clamp force | 20,060.270 N |
| Nut-bearing clamp force | 20,066.050 N |
| Member-interface clamp force | 20,064.180 N |
| Three-path mean | 20,063.500 N |
| Three-path spread | 5.780 N |
| Thread normal-force magnitude | 15,318.240 N |

The governed preload-calibration controller disposition was:

`accept`

The three independent planar load-transfer paths therefore reproduce
the certified Phase 2 clamp state and satisfy the governed consistency
criterion.

---

## Fresh axial mechanics reproduction

Production semantic post-processing reported:

| Quantity | Fresh result |
|---|---:|
| Selected bolt free-span tetrahedra | 128,619 |
| Bolt mean SZZ | +315.656054 MPa |
| Bolt median SZZ | +335.368500 MPa |
| Head-side member mean SZZ | -33.081018 MPa |
| Nut-side member mean SZZ | -32.951690 MPa |

The bolt free span is in net tension and both clamped members are in
net compression, matching the certified Phase 2 mechanical state.

Raw local stress hotspots are not used as strength-certification gates
because they remain mesh/singularity sensitive.

---

## Fresh deformation reproduction

Production semantic deformation extraction reported:

| Quantity | Fresh result |
|---|---:|
| FEM member shortening | 0.003212695019 mm |
| Analytical member shortening | 0.003113245418 mm |
| FEM / analytical ratio | 1.031944029 |
| Bolt mechanical extension | +0.038321380457 mm |
| Engagement-entry node count | 1 |

The member stack shortens physically and the bolt exhibits positive
mechanical extension after removal of the imposed thermal eigenstrain.

---

## Fresh thread-flank reproduction

The production engaged-thread-flank diagnostic reported:

| Quantity | Fresh result |
|---|---:|
| Engaged bolt-thread triangles | 11,943 |
| +Z flank triangles | 3,949 |
| -Z flank triangles | 3,948 |
| +Z mean compression | 38.442914 MPa |
| -Z mean compression | 317.140284 MPa |
| +Z compressed area | 19.162511 % |
| -Z compressed area | 59.843728 % |
| Dominant flank | -Z-normal flank |
| Dominance ratio | 8.249642 × |

The intended -Z-normal bearing flank is therefore the dominant
load-carrying flank, matching the certified Phase 2 state.

The dominance ratio is reproduction evidence for this certified case;
it is not encoded as a universal physics threshold for future cases.

---

## Acceptance-engine result

Authoritative aggregate evaluation:

- hard gates: 13
- reproduction-parity gates: 31
- diagnostics: 0
- failed checks: 0

Final disposition:

**PASS**

The aggregate evaluation consumed:

- governed preload configuration
- immutable certified-result oracle
- native CalculiX DAT contact statistics
- production targeted FRD STRESS reader
- production targeted FRD DISP reader
- production semantic axial-mechanics extractor
- production semantic deformation extractor
- production engaged-thread-flank diagnostic
- real analytical member-mechanics model
- production nonlinear STA parser
- fresh solver stdout
- observed live process return code 0

No certified mechanical result was injected into the measured side of
the evaluation.

---

## Successful-run provenance

Authoritative workspace:

`D:\ThreadROM\.tmp\cp4_step6_live_reproduction`

| File | Bytes | SHA-256 |
|---|---:|---|
| trm_sim_000004_run_a2_thermal_20kn.inp | 26,774,872 | dcf571506a46679f2eab2f7c5e2e3a85af861544ddf56d84d60466c8dd90c634 |
| trm_sim_000004_run_a2_thermal_20kn.dat | 54,825 | 21c91f504eeda90cd96fa6ace083e7fa981dd4fa238ae25d311f9ef5e8f0f86c |
| trm_sim_000004_run_a2_thermal_20kn.frd | 668,609,082 | 3329beaedb997870e5ea50b027419c56edb54bb4104e0122e35305f31d3f3ba1 |
| trm_sim_000004_run_a2_thermal_20kn.sta | 1,560 | e2d5ba88509242ca03329d1e9dee6c5d87ccb22426bdc0cd47bcce8e5b8512e4 |
| trm_sim_000004_run_a2_thermal_20kn.cvg | 10,487 | ef45d48cba5c2a9581375bf3863cad7a59bf20d0bc35678e6477be891d5f9f9c |
| trm_sim_000004_run_a2_thermal_20kn.stdout.log | 104,208 | fa0bb67e3365ab437863153cf9ea92db56fb42f5461632becfc8bd7996d9b27a |
| trm_sim_000004_run_a2_thermal_20kn.stderr.log | 0 | e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 |

---

## Attempt #1 timeout and corrective action

The first CP4 live attempt was terminated by orchestration after the
legacy 1,800-second transfer timeout.

Evidence from the partial run showed:

- Increment 1 accepted on ATT1
- Increment 2 had begun
- no nonlinear convergence failure was observed

The termination was therefore classified as an orchestration timeout,
not a FEM-physics failure.

The timeout behavior was corrected by governing the certified FEM
profile with a solver timeout of 57,600 seconds while preserving
fallback behavior for non-certified profiles.

The deterministic deck remained byte-identical after this change.

Timeout-governance fix commit:

`4d14ff4 fix: govern certified FEM solver timeout`

The failed attempt remains preserved as failure/provenance evidence and
must not be confused with the authoritative successful reproduction.

---

## Engineering conclusion

CP4 establishes that Phase 2 successfully certified reusable nonlinear
FEM machinery rather than a one-off manually tuned result.

For the canonical certified case, Phase 3 now demonstrates an automated
governed path from case definition through deterministic FEM generation,
preload calibration, solver execution, semantic post-processing,
physics acceptance and strict certified-result parity.

This closes the central Phase 3 requirement that supported FEM cases
must flow through reusable governed machinery rather than Phase 2-style
manual troubleshooting.

Checkpoint 4 may be closed after:

1. this certification record is committed,
2. the complete regression suite passes,
3. repository state is reviewed,
4. the CP4 milestone is committed and pushed.

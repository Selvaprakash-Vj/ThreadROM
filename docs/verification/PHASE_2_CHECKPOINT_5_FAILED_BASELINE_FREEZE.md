# Phase 2 Checkpoint 5 — Failed Nonlinear Baseline Freeze

## Purpose

This record freezes the governed failed nonlinear clamp baseline
before any stabilisation changes are introduced.

## Repository state

- Branch: `main`
- Commit: `505c123b27344ba51888243f07e2a776a8ff3230`
- Genuine CalculiX processes detected during freeze: `0`

## Governed engineering conclusion

- `TRM-SIM-000009` is rejected because the pretension direction
  opened the joint rather than producing physical clamping.
- `TRM-SIM-000010` uses the corrected negative reference-force
  sign but diverged before accepting an equilibrium increment.
- The analytical-to-FEM comparison remains `INCONCLUSIVE`.
- Unconverged Newton-iteration results are not admissible
  verification evidence.

## Pretension-direction control

- Configuration: `config/complete_joint_pretension_c3d10_coarse_750n_clamp_smoke.toml`
- Frozen `reference_force_sign`: `-1`

## Authoritative outcome

- `docs/verification/TRM-SIM-000010_CLAMP_SMOKE_OUTCOME.json`

## Frozen evidence hashes

| Artifact | SHA-256 |
|---|---|
| `config/complete_joint_pretension_boundary_regions_c3d10_coarse_clamp_smoke.toml` | `4DC20FB0D475DD5DDA6ECEDB1439262DE739835B9D532271A0EE7BB89722EADF` |
| `config/complete_joint_pretension_c3d10_coarse_750n_clamp_smoke.toml` | `AC283E054D9003333CF3022050E4B01498D40600C0EB6C322E6D01B165F82CB9` |
| `config/complete_joint_pretension_calculix_transfer_c3d10_coarse_clamp_smoke.toml` | `E1A1B20E5616575C8D6252AF85761C6877041E3481EDE988E8A6563FE3CB4CB9` |
| `config/complete_joint_pretension_contact_c3d10_coarse_clamp_smoke.toml` | `7BF7164F536C51918B7C988FDC1DADB7D1568284E843F7CCC5DAC736ECD68EF9` |
| `docs/verification/TRM-SIM-000010_CLAMP_SMOKE_OUTCOME.json` | `CC203B2BAAFECE245E03CC3B67D71C60C06AB93A3A771A40F6B3C1C2E0B3C752` |
| `simulations/archive/TRM-SIM-000010_clamp_smoke_divergence_20260804_163943/manifest.json` | `D0A4D8B002206E96A6A48ABD903026E4C8274953A183EB3A0972A60641B710B5` |
| `simulations/archive/TRM-SIM-000010_clamp_smoke_divergence_20260804_163943/post_termination/trm_sim_000010_c3d10_750n_pretension.inp` | `4D1D16EE88D34B08C8485D682922677CA7770FC48752892ED1D0968C9C10FE58` |

## Stabilisation boundary

The failed baseline must not be rewritten or reclassified as a
passing solution. Subsequent work must use a new governed simulation
identity and demonstrate at least one accepted, physically
compressive clamp-state increment before downstream FEM verification
resumes.

No solver was launched or terminated while producing this record.

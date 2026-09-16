# ThreadROM Diversified Mesh and Solver Certification

**Record ID:** TRM-MSH-000001
**Phase:** Phase 3 / CP11 pre-DOE hardening
**Status:** PASS
**Certification date:** 2026-09-16

## 1. Purpose

This record certifies the governed mesh and nonlinear-solver path used
for the current Phase-3 diversified Production DOE.

The certification is evidence-bounded. It does not claim that one mesh
policy is universally sufficient for every future bolt size, geometry,
material system, contact state, or loading condition.

No new CalculiX solve was required for this certification. Existing
governed FEM evidence was reused.

## 2. Mesh-quality policy

The complete-joint production mesh-quality policy is:

- zero degenerate tetrahedra,
- mixed tetrahedral orientation forbidden,
- minimum tetrahedron mean ratio >= 0.05,
- maximum tetrahedron edge ratio <= 50.0.

The existing absolute minimum tetrahedron volume of 1.0e-12 mm^3 is
retained only as a numerical degeneracy guard.

Absolute element volume is scale-dependent and is therefore not used as
an M10-derived diversified production-quality criterion.

## 3. Accepted quality evidence

### Certified baseline medium mesh

TRM-MSH-000005:

- nodes: 101,493
- tetrahedra: 509,115
- degenerate tetrahedra: 0
- mixed orientation: false
- minimum mean ratio: 0.182638460
- maximum edge ratio: 19.687773704

Result: PASS against the hardened production-quality floor.

### P04 Medium+ mesh

TRM-LRP-000001 / medium_plus_v1:

- nodes: 188,960
- tetrahedra: 985,634
- degenerate tetrahedra: 0
- mixed orientation: false
- minimum mean ratio: 0.053519098
- maximum edge ratio: 40.435962904

Result: PASS against the hardened production-quality floor.

The P04 Medium+ realization is the limiting accepted mesh used when
setting the present dimensionless quality bounds.

## 4. Mesh-sufficiency evidence

Ordinary medium is not considered sufficient for the governed P04
radial-geometry condition.

The permanently preserved VV06-S1 result is:

`S1_REJECTS_MEDIUM_FOR_P04`

The governed Medium+ sentinel was compared against the existing global
fine reference and closed with:

`MEDIUM_PLUS_SUPPORTED_FOR_P04`

The certification contained:

- 9 / 9 supporting matched-preload metric checks,
- 2 / 2 supporting direct thread-flank checks,
- strict clamp monotonicity PASS,
- 20 accepted increments for both compared realizations.

Across the governing preload points, nominal Medium+ versus fine
differences were approximately:

- member shortening: 1.20 % to 1.34 %,
- bolt free-span mean SZZ: 0.683 %,
- thread normal force: 0.11 % to 0.43 %.

No additional P04 solve is authorized or required.

This evidence supports Medium+ only for the governed P04 applicability
condition represented by the sentinel. It does not establish global
Medium+ sufficiency for arbitrary future parameter space.

## 5. Production mesh-selection governance

The current Phase-3 Production DOE policy uses:

- ordinary medium for the certified baseline radial endpoint,
- governed `medium_plus_v1` for any nonzero radial excursion,
- no automatic global-fine production requirement.

This deliberately conservative switch avoids inferring an unvalidated
transition threshold from one sentinel.

Future cross-size or newly introduced geometry regimes remain subject to
their own governed evidence and may require additional sentinels.

## 6. Fail-closed production quality enforcement

The Production DOE preparation path now performs explicit governed
mesh-quality validation after grouped-mesh generation and before
preparation evidence is accepted.

The path is:

generated grouped mesh
? `complete_joint_mesh_quality.toml`
? tetrahedral quality analysis
? fail-closed rejection on violation
? measured quality and policy SHA recorded
? production preparation evidence.

The immutable preparation record stores:

- policy path,
- policy SHA256,
- controlled thresholds,
- measured node and tetrahedron counts,
- degenerate count,
- minimum volume,
- minimum mean ratio,
- maximum edge ratio,
- mixed-orientation status,
- explicit `mesh_quality_validation = PASS`.

A deliberate negative-path test confirmed that a mesh is rejected when
the controlled minimum mean-ratio requirement is violated.

The reusable quality validator therefore propagates a hard failure
rather than silently accepting a nonconforming production mesh.

## 7. Nonlinear solver and resilience evidence

The certified nonlinear preload path already possesses governed solver
evidence.

The Phase-2 physical 20 kN baseline completed:

- 20 / 20 accepted increments,
- final increment on ATT1,
- zero unsuccessful attempts / cutbacks,
- CalculiX `Job finished`,
- coherent physical clamp transfer.

Phase-3 CP4 independently reproduced the certified nonlinear M10 state
through the governed FEM factory with:

- 13 / 13 hard acceptance gates,
- 31 / 31 reproduction-parity gates,
- zero diagnostics,
- zero failed checks.

The execution and adjudication machinery separately governs:

- accepted versus retried/cutback increments,
- solver completion evidence,
- return code,
- `Job finished`,
- nonlinear-progress history,
- failed/interrupted run preservation,
- solver-error classification,
- orchestration failures versus FEM-physics failures.

A completion marker alone is not treated as sufficient physics
acceptance.

Rigid-body modes remain unexpected for the governed constrained model
and are to be treated as a boundary-condition-definition failure, not
as removable nuisance modes.

## 8. Solver-duration policy

Long nonlinear FEM runs are not subject to an artificial short
engineering timeout.

Historical CP4 evidence demonstrated that orchestration timeout must be
distinguished from nonlinear FEM failure.

The current governed execution architecture preserves failed or
interrupted attempts as provenance evidence rather than confusing them
with authoritative accepted results.

## 9. Production limitations

This certification does not authorize:

- raw local thread/contact stress maxima as converged strength metrics,
- global use of Medium+ outside its certified applicability,
- arbitrary cross-size extrapolation without governed evidence,
- relaxation of mesh-quality limits after results are observed,
- duplicate FEM execution merely to reproduce existing certified
  evidence.

Raw contact-edge and thread-root extrapolated stress maxima remain
mesh/singularity sensitive unless separately governed by an appropriate
local-stress convergence study.

## 10. Software regression

Final repository regression after Gate-3 hardening:

**879 passed in 1288.85 s (0:21:28)**

Additional focused Gate-3 enforcement regression:

**6 passed**

`git diff --check` returned clean.

## 11. Final disposition

The current diversified Production DOE mesh/solver path is certified for
its documented applicability.

The certification establishes:

- governed production mesh-quality limits,
- preservation of scale-aware diversified behavior,
- evidence-backed Medium / Medium+ selection,
- bounded mesh-sufficiency claims,
- fail-closed Production DOE mesh-quality validation,
- established nonlinear solver resilience and adjudication,
- no unnecessary duplicate FEM solve.

**PRE-DOE GATE 3 ? MESH / SOLVER: PASS**

Remaining engineering gates before diversified Production DOE:

1. Gate 2 ? persistent governed FEM factory and cross-size sentinels
2. Gate 1 ? final diversified Production DOE matrix
3. Gate 0 ? DOE authorization

# Phase 2 Checkpoint 1 — Untracked Artifact Triage

## Purpose

This record classifies the untracked artifacts remaining after Phase 1.

No artifact was deleted, moved, or staged during the investigation. Classification
was based on file inventory, content review, SHA-256 comparison, repository policy,
and targeted quality checks.

## Govern

The following implementation artifacts are reusable engineering functionality and
must enter normal source governance:

- `src/threadrom/postprocessing/calculix_frd_displacement.py`
- `tests/unit/test_calculix_frd_displacement.py`

Verification completed:

- Targeted unit tests: 5 passed
- Ruff: clean
- MyPy: clean

## Preserve / Archive

The following artifacts contain solver-history or verification evidence and must
be preserved before any cleanup:

- `simulations/archive/TRM-SIM-000009/`
- `simulations/archive/TRM-SIM-000009_wrong_pretension_direction_20260804_153131/`
- `simulations/archive/TRM-SIM-000010_clamp_smoke_divergence_20260804_163943/`
- `docs/verification/TRM-SIM-000009_NONLINEAR_PRETENSION_PROGRESS.md`
- `docs/verification/figures/TRM-SIM-000009_NONLINEAR_CONVERGENCE.png`
- `docs/verification/figures/TRM-SIM-000009_NONLINEAR_CONVERGENCE.svg`

The top-level PNG and SVG are byte-identical to copies in the interrupted-run
archive. They remain associated with the newer top-level Markdown evidence until
that evidence is safely consolidated into an archive.

The top-level Markdown report is not identical to its archived predecessor. It
contains later nonlinear iteration records and additional external-equilibrium
status, so it must not be discarded as a duplicate.

The simulation archives are not currently ignored by Git. Large input decks must
therefore not be staged accidentally.

## Discard

The following temporary PowerShell utilities are run-specific, hard-coded,
duplicated, obsolete, or damaged and are not suitable for repository governance:

- `scripts/check_c3d10_coarse_progress.ps1`
- `scripts/check_increment_3_retry.ps1`
- `scripts/diagnose_c3d10_5kn_run.ps1`
- `scripts/diagnose_c3d10_termination.ps1`
- `scripts/diagnose_current_c3d10_solver.ps1`
- `scripts/launch_c3d10_5kn_overnight.ps1`
- `scripts/monitor_c3d10_5kn.ps1`
- `scripts/monitor_c3d10_coarse_5kn.ps1`
- `scripts/monitor_c3d10_iterations.ps1`
- `scripts/monitor_current_c3d10_run.ps1`
- `scripts/verify_c3d10_parallel_run.ps1`
- `scripts/verify_c3d10_parallel_stage.ps1`
- `scripts/watch_increment_3_triage.ps1`

They may be removed only after the preservation actions above are complete and
the proposed deletion list has been verified explicitly.

## Safety Decision

- Do not use `git add .`.
- Do not stage `simulations/archive/`.
- Do not delete the temporary scripts until archive consolidation is verified.
- Do not launch or terminate CalculiX as part of this checkpoint.

# CalculiX External-Equilibrium Validation

## Purpose

This verification capability evaluates external support-force
equilibrium during preload-only CalculiX analyses.

Bolt pretension is an internal, self-equilibrated action. The
pretension-reference force must therefore not be compared directly
against the external support reaction.

## Implemented capabilities

- Live-safe parsing of CalculiX `TOTALS=ONLY` force histories.
- Filtering by named support node set.
- Alignment with accepted nonlinear increments using DAT time.
- Pass, fail, and pending classifications.
- Governed JSON output.
- Nonlinear-progress report integration.
- Explicit reporting of scope and limitations.

## Validation rule

During preload-only loading, the printed external support-force
vector is expected to remain near zero.

The validator compares the maximum absolute component of the support
force vector against a governed absolute tolerance of `1.0e-3 N`.

Each accepted increment is classified as follows:

- `pass`: every support-force component is within tolerance.
- `fail`: at least one component exceeds tolerance.
- `pending`: no complete matching DAT force record is available.

Incomplete trailing DAT blocks are ignored. This allows the parser
to read a DAT file safely while CalculiX continues writing to it.

## Current commissioning evidence

- Simulation: `TRM-SIM-000009`
- Mesh: `TRM-MSH-000008`
- Support set: `HEAD_MEMBER_SUPPORT_BAND`
- Accepted increments: 2
- Complete support-force records: 1
- Passed increments: 1
- Failed increments: 0
- Pending increments: 1
- Overall validation status: `pending`

The first complete support-force vector was
`(6.355773e-08, 3.999832e-08, -3.253635e-11) N`.

Its maximum absolute component was approximately
`6.355773e-08 N`, which is substantially below the governed
tolerance of `1.0e-3 N`.

The second accepted increment remains pending because its complete
support-force DAT block has not yet been written.

## Interpretation

The near-zero support reaction is physically consistent with a
self-equilibrated internal pretension load.

The extracted pretension-reference force is a control quantity used
to apply bolt preload. It is not an external force that should be
balanced directly against the support reaction.

Pretension-ramp validation and external-equilibrium validation serve
different purposes:

1. Pretension-ramp validation confirms that the commanded internal
   preload is applied correctly.
2. External-equilibrium validation confirms that preload-only
   loading does not create an unintended net external force at the
   printed support set.

## Governed runtime artifacts

- `simulations/staging/TRM-SIM-000009/results/total_force.json`
- `simulations/staging/TRM-SIM-000009/results/external_equilibrium.json`
- `docs/verification/TRM-SIM-000009_NONLINEAR_PRETENSION_PROGRESS.md`

## Current limitations

The present validation covers only the explicitly printed
`HEAD_MEMBER_SUPPORT_BAND` force total.

It does not yet establish:

- Combined equilibrium across every constrained guidance reference.
- Internal contact-interface force transfer.
- Bolt-to-nut thread-load distribution.
- Head-bearing and nut-bearing interface equilibrium.
- Per-thread-turn force balance.
- Final completed-solution structural validity.

Future governed decks must request the additional force outputs
required for complete three-axis global-equilibrium and internal
load-path verification.

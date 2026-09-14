# TRM-ADR-000002 — Governed Fastener Dimensional Data and Provenance

## Record information

- Decision ID: TRM-ADR-000002
- Date: 2026-09-13
- Status: Proposed
- Owner: Selvaprakash-Vj
- Related phase: Phase 3, CP11 — Universal Applicability Hardening
- Related artefacts:
  - `docs/engineering/BASELINE_FASTENER_DEFINITION.md`
  - `src/threadrom/case/standards.py`
  - `src/threadrom/case/standard_catalog.py`
  - `src/threadrom/case/iso_inventory_2026.py`
  - `docs/verification/PHASE_3_CP4_CERTIFIED_FEM_REPRODUCTION.md`

## Context

ThreadROM began with M10x1.5 as the fixed Phase-1 reference family.

The original baseline definition explicitly required standard dimensions to be
entered and independently checked before approval, and identified
TRM-ADR-000002 as the governing decision record for that approval.

The implemented M10 geometry was subsequently exercised through the full
ThreadROM analytical, geometry, mesh, nonlinear FEM, reproduction, and
Phase-3 governed-production workflow. The implemented M10 reference therefore
has substantial empirical and certification evidence.

However, the runtime standard resolver currently stores dimensional values
directly in `src/threadrom/case/standards.py` without an explicit,
machine-readable provenance link to the engineering evidence from which each
value was admitted.

CP10 and CP11 expand ThreadROM from an M10 reference model toward a universal
ISO-metric threaded-joint framework. M8x1.25 and M12x1.75 are the first planned
cross-size candidate families around the certified M10 anchor.

## Problem

Adding new standard sizes merely as numerical dictionary entries would create
untraceable engineering constants and would blur the distinction between:

1. knowledge that an ISO standard exists,
2. possession and verification of dimensional engineering data,
3. CAD representability,
4. FEM support, and
5. certified ThreadROM applicability.

ThreadROM must therefore establish a governed dimensional-data provenance
contract before additional sizes are admitted to the runtime resolver.

## Decision

ThreadROM shall maintain a separate and explicit provenance chain for every
standard-derived engineering dimension used by the runtime case resolver.

A dimensional record may enter the governed runtime standards catalogue only
when:

1. its product/thread standard identity is explicit;
2. the engineering datum and units are explicit;
3. its source or evidence reference is traceable;
4. the datum has been independently checked;
5. the verification state is recorded;
6. the dimensional record is distinguishable from ISO catalogue metadata; and
7. its presence in the resolver does not imply CAD, FEM, ROM, or certification
   support beyond the separately governed capability level.

ISO catalogue metadata and engineering dimensional data shall remain separate
concepts.

The existing `StandardCapability` maturity hierarchy remains authoritative:

- `METADATA_ONLY`
- `DIMENSIONAL_DATA`
- `CAD_SUPPORTED`
- `FEM_SUPPORTED`
- `CERTIFIED`

The capability assigned to a product or size shall reflect demonstrated
ThreadROM evidence and shall never be inferred merely because dimensions are
available.

## M10 reference treatment

M10x1.5 remains the certified ThreadROM anchor family.

The currently implemented M10 dimensions shall not be silently rewritten during
this provenance hardening.

Instead, CP11 shall attach explicit provenance and verification metadata to the
existing implemented dimensions while preserving exact certified Phase-2 and
Phase-3 reproduction behaviour.

Existing certified FEM evidence remains valid unless a subsequent dimensional
audit finds a material discrepancy requiring governed review.

## M8 and M12 candidate treatment

M8x1.25 and M12x1.75 are the first intended cross-size candidate families for
Universal ThreadROM.

They shall not be inserted into the governed runtime dimensional catalogue
until their required thread, bolt, and nut dimensions have been sourced and
independently verified.

Admission of dimensional data does not by itself certify either family.

Their maturity shall progress separately through dimensional resolution,
parametric CAD verification, governed FEM evidence, and eventual certified
applicability.

## Engineering justification

This separation prevents three failure modes:

- unexplained engineering constants entering the product;
- catalogue knowledge being mistaken for solver capability;
- parametric representability being mistaken for physical certification.

It also allows ThreadROM to scale to additional diameters, pitches, product
standards, materials, and future thread families without weakening the
governance established by the M10 reference programme.

The approach is compatible with the existing parametric geometry and analytical
architecture, which already consumes resolved nominal diameter, pitch, product
dimensions, materials, and assembly parameters rather than relying on a fixed
M10 geometry.

## Alternatives considered

### Store additional sizes directly in `standards.py`

Rejected.

This is simple technically but provides insufficient engineering provenance and
would allow unexplained constants to enter a commercially relevant simulation
pipeline.

### Treat ISO catalogue metadata as dimensional evidence

Rejected.

The existing ISO inventory intentionally stores public catalogue metadata and
does not reproduce or imply possession of detailed copyrighted dimensional
tables.

### Keep ThreadROM permanently limited to M10

Rejected.

M10 is the certified anchor, not the intended product boundary. The Universal
ThreadROM roadmap explicitly requires controlled cross-size applicability.

## Impact on scope

This decision does not broaden the certified applicability envelope by itself.

It establishes the governance mechanism required to expand that envelope
safely.

The initial target remains:

- ISO metric coarse thread
- M8x1.25
- M10x1.5 certified anchor
- M12x1.75
- ISO 4017:2022 fully threaded hexagon-head fastener family
- ISO 4032:2023 style-1 hex nut family
- right-hand
- single-start

Actual support remains evidence-gated.

## Impact on verification

Each new dimensional family requires, at minimum:

1. independent dimensional-data verification;
2. deterministic resolver tests;
3. thread-basic-dimension checks;
4. CAD construction checks;
5. geometry and assembly sanity checks;
6. mesh/classification verification;
7. FEM physics acceptance before FEM support is claimed; and
8. cross-solver or other governed V&V before certified applicability where
   required by the Phase-3 roadmap.

M10 must retain exact certified reproduction parity after provenance hardening.

## Impact on dataset compatibility

Existing M10 FEM and analytical evidence remains valid because this decision
does not alter the realised certified M10 geometry.

New dimensional provenance metadata may be added to future knowledge records so
that datasets remain auditable across standards and sizes.

No historical FEM result shall be relabelled as supporting a newly introduced
size.

## Impact on model compatibility

No existing ROM exists yet, so no released reduced-order model requires
migration.

Future ROM releases shall bind their applicability envelope to governed
standards/dimensional-data identities and knowledge-base snapshots.

## Risks introduced

- Incorrect source transcription could contaminate multiple downstream cases.
  Mitigation: independent verification before admission.

- A dimensionally resolvable case could be mistaken for a certified case.
  Mitigation: retain separate capability maturity and applicability gates.

- Future source revisions could change a standard datum.
  Mitigation: immutable/versioned evidence records and explicit standard
  references.

- Historical M10 configuration files contain legacy status labels such as
  `proposed` or `development`.
  Mitigation: treat certification evidence and current governed records as the
  authoritative maturity source rather than silently rewriting historical
  artefacts.

## Implementation actions

- [ ] Define a machine-readable dimensional-data provenance record.
- [ ] Attach governed provenance to the existing M10 runtime dimensional data.
- [ ] Independently verify the required M10 dimensional values.
- [ ] Independently verify required M8x1.25 dimensions.
- [ ] Independently verify required M12x1.75 dimensions.
- [ ] Add M8/M12 runtime records only after dimensional verification.
- [ ] Update capability assessment to reflect current post-CP4 M10 maturity.
- [ ] Preserve M10 certified reproduction parity.
- [ ] Add deterministic resolver and provenance tests.
- [ ] Complete cross-size CAD/FEM verification before FEM support is promoted.
- [ ] Update verification documentation.

## Approval

- Decision status: Proposed
- Approval condition: Required dimensional sources and provenance mechanism are
  independently verified and regression-tested.
- Approved by:
- Approval date:
- Supersedes:
- Superseded by:

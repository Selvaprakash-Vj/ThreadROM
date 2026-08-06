# Phase 2 Checkpoint 13 - TRM-SIM-000013 Generated-Deck Audit

## Purpose

This checkpoint audited the governed TRM-SIM-000013 CalculiX input deck before
any further solver experiment.

The audit tested whether the accepted but physically invalid opening response
could be explained directly by:

- contact ADJUST behavior;
- node-to-surface tensile-tail behavior;
- an explicit constraint on the pretension reference node;
- an obvious mismatch between the pretension load and reference node.

No solver was launched.

## Governed source

- Simulation ID: `TRM-SIM-000013`
- Deck SHA256:
  `8DA16BA3C26164DF3938DC1B3F26F0CDE2C30909403D99D82CA63CE83181DA43`
- Evidence archive:
  `simulations/archive/TRM-SIM-000013/accepted_opening_state_20260806_100042`
- Result-record commit: `30a7653`

## Contact definition

The deck contains four contact pairs:

1. Nut internal thread to bolt thread
2. Head-member bearing to bolt under-head bearing
3. Nut-member bearing to nut lower bearing
4. Head-member interface to nut-member interface

All four pairs use:

`TYPE=SURFACE TO SURFACE`

The audit found:

- Contact pairs: `4`
- Surface-to-surface pairs: `4`
- Node-to-surface pairs: `0`
- Pairs containing `ADJUST`: `0`
- Pairs containing `SMALL SLIDING`: `0`

## Contact interaction

The common interaction is:

- Pressure-overclosure formulation: `LINEAR`
- Explicit slope: `2.100000000000e+06`
- Steel Young's modulus: `2.100000000000e+05`
- Slope-to-modulus ratio: `10`
- Friction coefficient: `0.15`
- Friction regularization value: `2.100000000000e+04`

Because all pairs are surface-to-surface, the node-to-surface
large-clearance tensile-tail hypothesis does not apply to this deck.

Because `ADJUST` is absent, no explicitly requested strain-free ADJUST
operation is present.

## Pretension definition

The pretension section is:

- Surface: `SURF_BOLT_PRETENSION_SECTION`
- Reference node: `259268`
- Specified vector: `(0, 0, +1)`

The reference node is defined at:

`(0, 0, 5 mm)`

The load is applied to reference-node degree of freedom `1`:

- Step 1 target: `+250 N`
- Step 2 target: `+500 N`
- Step 3 target: `+750 N`

The topology audit previously established that the specified `+Z` vector
points toward the elements owning the pretension surface.

The physical meaning of force sign, surface ownership, and reference degree of
freedom must therefore be established independently using a pretension coupon.

## Reference-node constraint audit

Pretension reference node `259268` is not explicitly used by:

- `*BOUNDARY`
- user-defined `*MPC`
- `DCOUP3D`
- `*DISTRIBUTING COUPLING`

Its exact explicit uses are limited to:

- node definition;
- `*PRE-TENSION SECTION`;
- the three pretension force targets.

Therefore, direct explicit overconstraint of the pretension reference node is
not supported by the generated deck.

## Full-joint guidance system

The deck contains three DCOUP3D elements:

- Bolt-head guidance reference: `259269`
- Nut-translation guidance reference: `259270`
- Nut-member guidance reference: `259271`

It also contains five MEANROT reference nodes:

- `259272`
- `259273`
- `259274`
- `259275`
- `259276`

The explicit boundary block constrains:

- the head-member support band in DOFs 1 through 3;
- three translation-guidance references in DOFs 1 and 2;
- five rotation-guidance references in DOF 1.

These constraints do not directly include pretension reference node `259268`.

However, indirect interaction between pretension kinematics, contact, and the
full-joint guidance system remains possible and has not yet been falsified.

## Eliminated hypotheses

The generated-deck audit eliminates the following direct explanations:

- Explicit contact `ADJUST`: **ABSENT**
- Node-to-surface tensile-tail mechanism: **NOT APPLICABLE**
- Direct explicit boundary on pretension reference node: **ABSENT**
- Direct user-defined MPC on pretension reference node: **ABSENT**
- Direct DCOUP3D use of pretension reference node: **ABSENT**

## Remaining hypotheses

The remaining investigation must focus on:

- CalculiX pretension-section semantics and internal MPC behavior;
- pretension vector, surface ownership, and force-sign convention;
- zero-load behavior introduced by the pretension section itself;
- zero-load contact or constraint settling;
- indirect interaction between pretension kinematics and guidance constraints;
- initial geometric or contact imbalance.

## Engineering decision

No additional full-scale C3D10 joint simulation will be launched yet.

The next governed experiment will be a tiny contact-free pretension coupon
that validates the pretension convention independently of the full joint.

## Checkpoint status

- Governed deck located and verified: **PASS**
- Contact mode audited: **PASS**
- ADJUST hypothesis: **ELIMINATED**
- Node-to-surface tensile-tail hypothesis: **ELIMINATED**
- Direct pretension-reference constraint hypothesis: **ELIMINATED**
- Pretension semantics independently validated: **NOT YET**
- CalculiX launched during audit: **NO**

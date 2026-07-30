# Complete-Joint Contact Smoke Verification

## Identity

- Contact model: `TRM-CNT-000001`
- Simulation: `TRM-SIM-000005`
- Mesh: `TRM-MSH-000005`
- Mesh level: `medium`
- Solver job: `trm_cnt_000001_contact_smoke`
- Generated UTC: `2026-07-30T22:41:41.543453+00:00`

## Model content

- Nodes: 73360
- C3D4 elements: 333439
- Element surfaces: 17
- Mapped element faces: 76978
- Surface interactions: 1
- Contact pairs: 4

## Governed interaction

- Contact formulation: `SURFACE TO SURFACE`
- Pressure-overclosure law: `LINEAR`
- Normal stiffness: 2100000.000000 N/mm?
- Friction coefficient: 0.150000
- Friction stick slope: 21000.000000 N/mm?

## Contact pairs

- `thread`: `SURF_NUT_INTERNAL_THREAD` ? `SURF_BOLT_THREAD_SURFACES`
- `under_head`: `SURF_HEAD_MEMBER_HEAD_BEARING` ? `SURF_BOLT_UNDER_HEAD_BEARING`
- `nut_bearing`: `SURF_NUT_MEMBER_NUT_BEARING` ? `SURF_NUT_LOWER_BEARING`
- `member_interface`: `SURF_HEAD_MEMBER_INTERFACE` ? `SURF_NUT_MEMBER_INTERFACE`

## Solver verification

- CalculiX return code: 0
- `.dat` size: 18049 bytes
- `.frd` size: 28103615 bytes
- `.sta` size: 173 bytes
- Expected zero-DOF warning found: True
- CalculiX `*ERROR` detected: false

## Scope

This is a solver-read and contact-keyword smoke test.
All mesh nodes are constrained and no physical load is applied.
It verifies that CalculiX accepts the transferred surfaces,
interaction law, and four contact-pair definitions. It does not
constitute a converged physical contact solution.

## Verdict

**VERIFIED**

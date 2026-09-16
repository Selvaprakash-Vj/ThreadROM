# TRM-STD-000001 — M10x1.5 Dimensional Provenance Verification

**Record ID:** TRM-STD-000001
**Status:** VERIFIED
**Verification date:** 2026-09-14
**Scope:** ThreadROM certified M10x1.5 anchor dimensional provenance
**Geometry-change authorization:** NONE

## 1. Purpose

This record independently verifies the dimensional basis of the certified
ThreadROM M10x1.5 anchor before any runtime datum is promoted from
CERTIFIED_REALIZED_BASELINE to STANDARD_DERIVED.

This verification does not authorize alteration of the already certified
Phase-2 M10 geometry.

## 2. Governing standards chain

The verified metric-thread standards chain is:

- ISO 261:1998 — ISO general purpose metric screw threads — General plan
  - Current; reviewed and confirmed in 2024.
- ISO 262:2023 — ISO general purpose metric screw threads — Selected sizes
  for bolts, screws, studs and nuts.
- ISO 68-1:2023 — ISO general purpose screw threads — Basic and design
  profiles — Part 1: Metric screw threads.
- ISO 724:2023 — ISO general purpose metric screw threads — Basic dimensions.
- ISO 4017:2022 — Fasteners — Hexagon head screws — Product grades A and B.
- ISO 4032:2023 — Fasteners — Hexagon regular nuts (style 1).
- ISO 965-1:2026 — ISO general purpose metric screw threads — Tolerances —
  Part 1: Principles and basic data.
- ISO 965-2:2024 — ISO general purpose metric screw threads — Tolerances —
  Part 2: Limits of sizes for tolerance classes including 6H and 6g.

ISO 724 basic dimensions refer to the metric design profiles governed through
ISO 68-1 and the general-plan diameter/pitch system of ISO 261.

## 3. Independent M10x1.5 thread calculation

Runtime inputs:

- nominal diameter d = 10.0 mm
- pitch P = 1.5 mm

Fundamental triangle:

H = sqrt(3) / 2 * P

H = 1.299038105676658 mm

ThreadROM basic-profile equations independently evaluated:

d2 = d - 3H/4
   = 9.025721420742506 mm

D1 = d - 5H/4
   = 8.376202367904177 mm

d3 = d - 17H/12
   = 8.159696016958067 mm

Tensile stress area:

As = pi/4 * (d - 0.938194 P)^2
   = 57.9895969018452 mm^2

These values independently reproduce the existing ThreadROM analytical
results exactly.

## 4. Product-standard dimensional verification

### 4.1 ISO 4017:2022 M10 hexagon-head screw

ThreadROM realised values:

- head across flats = 16.0 mm
- head height = 6.4 mm

Independent product-standard cross-check:

- nominal M10 width across flats s = 16.0 mm
- nominal M10 head height k = 6.4 mm
- published product data additionally provides manufacturing limits around
  these nominal values.

Disposition:

- 16.0 mm across flats: STANDARD_DERIVED — PASS
- 6.4 mm head height: STANDARD_DERIVED — PASS

ThreadROM models the nominal/design geometry and does not claim that the CAD
represents a particular manufactured part at one location within its permitted
dimensional tolerance range.

### 4.2 ISO 4032:2023 M10 style-1 hex nut

ThreadROM realised values:

- nut across flats = 16.0 mm
- nut thickness = 8.0 mm

Independent product-standard cross-check:

- coarse pitch P = 1.50 mm
- nominal/max width across flats s = 16.0 mm
- current ISO 4032 style-1 M10 nut height m is published as
  8.04 mm minimum to 8.40 mm maximum.

Disposition:

- 16.0 mm across flats: STANDARD_DERIVED — PASS
- 8.0 mm nut thickness: CERTIFIED_REALIZED_BASELINE ONLY

The existing 8.0 mm value shall not be represented as an exact
ISO 4032:2023 dimensional value.

No existing M10 FEM evidence is invalidated by this finding because the
certified simulations remain evidence for the exact realised 8.0 mm
ThreadROM anchor geometry.

## 5. Thread tolerance-class interpretation

The source fastener contract states intended external/internal tolerance
classes 6g / 6H.

The existing geometry configuration also explicitly states:

include_manufacturing_tolerances = false

Therefore the current ThreadROM CAD shall be interpreted as an idealised
basic/design-profile engineering geometry associated with the M10x1.5
fastener family.

It shall NOT be described as literal manufactured ISO 965 6g/6H limit
geometry.

The 6g/6H designations remain useful as intended fastener-thread contract
metadata, but tolerance-zone geometry is not presently instantiated in CAD.

## 6. Governed runtime dispositions

| Quantity | Runtime value | Evidence disposition |
| --- | ---: | --- |
| nominal_diameter_mm | 10.0 mm | STANDARD_DERIVED — PASS |
| pitch_mm | 1.5 mm | STANDARD_DERIVED — PASS |
| head_across_flats_mm | 16.0 mm | STANDARD_DERIVED — PASS |
| head_height_mm | 6.4 mm | STANDARD_DERIVED — PASS |
| nut_across_flats_mm | 16.0 mm | STANDARD_DERIVED — PASS |
| nut_thickness_mm | 8.0 mm | CERTIFIED_REALIZED_BASELINE ONLY |

## 7. Independent reference evidence

Authoritative standard-status metadata was checked against the ISO catalogue.

Dimensional cross-checks were additionally made against:

- Fastenal Product Standard M.HCS.4017.10.9.Z, revision 05,
  dated 2025-10-09, for ISO 4017 dimensional data.
- Böllhoff, The Manual of Fastening, 8100/23-V1-EN,
  for ISO 4032 style-1 nut-height comparison data.
- Böllhoff product data sheet, ISO 4032 similar to DIN 934,
  steel property class 8, for M10 pitch, width across flats and nut height.

Only the individual values required for ThreadROM verification are recorded
here; external standards tables are not reproduced.

## 8. Certification result

PASS WITH ONE PRESERVED BASELINE EXCEPTION.

Five governed runtime dimensions are independently eligible for promotion to
STANDARD_DERIVED:

1. nominal diameter 10.0 mm
2. pitch 1.5 mm
3. bolt head across flats 16.0 mm
4. bolt head height 6.4 mm
5. nut across flats 16.0 mm

The M10 nut thickness 8.0 mm remains
CERTIFIED_REALIZED_BASELINE and must retain exact Phase-2 reproduction
semantics unless a separately governed geometry migration is authorised.

No numerical runtime value is changed by this verification.

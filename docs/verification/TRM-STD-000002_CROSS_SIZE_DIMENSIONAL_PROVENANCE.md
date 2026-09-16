# TRM-STD-000002 — M8/M12 Cross-Size Dimensional Provenance Verification

**Record ID:** TRM-STD-000002
**Status:** VERIFIED
**Verification date:** 2026-09-15
**Scope:** M8x1.25 and M12x1.75 candidate families for diversified Phase-3 expansion
**Geometry-change authorization:** governed admission of new cross-size candidates only
**Existing M10 geometry change:** NONE

## 1. Purpose

This record verifies the dimensional inputs required to admit M8x1.25 and
M12x1.75 into the governed ThreadROM standards resolver.

The purpose is not to certify FEM behavior for either size.

Dimensional admission, CAD support, FEM support, FEM certification and ROM
support remain separate maturity levels.

## 2. Governing standards

The dimensional chain used for this verification is:

- ISO 262:2023 — selected metric sizes for bolts, screws, studs and nuts
- ISO 68-1:2023 — metric screw-thread basic/design profile
- ISO 724:2023 — metric screw-thread basic dimensions
- ISO 4017:2022 — hexagon head screws, product grades A and B
- ISO 4032:2023 — hexagon regular nuts, style 1

Thread tolerance-zone geometry is not instantiated by this admission.
Current ThreadROM CAD remains an idealised basic/design-profile geometry.

## 3. M8x1.25 verification

### 3.1 Thread

Governed candidate inputs:

- nominal diameter d = 8.0 mm
- coarse pitch P = 1.25 mm

Independent basic-profile evaluation:

H = sqrt(3)/2 * P
  = 1.082531754730548 mm

d2 = d - 3H/4
   = 7.188101183952089 mm

D1 = d - 5H/4
   = 6.646835306586815 mm

d3 = d - 17H/12
   = 6.466413347465057 mm

Tensile stress area:

As = pi/4 * (d - 0.938194 P)^2
   = 36.6085432741553 mm^2

Disposition:

- nominal diameter 8.0 mm: STANDARD_DERIVED
- pitch 1.25 mm: STANDARD_DERIVED

### 3.2 ISO 4017 bolt

Verified representative product dimensions:

- head across flats s = 13.0 mm
- head height k = 5.3 mm

Disposition:

- head across flats: STANDARD_DERIVED
- head height: STANDARD_DERIVED

### 3.3 ISO 4032 style-1 nut

Verified dimensional range:

- across flats s = 13.0 mm nominal/max
- nut height m = 6.44 mm minimum to 6.80 mm maximum

ThreadROM representative nut thickness:

m_rep = (6.44 + 6.80) / 2
      = 6.620 mm

Disposition:

- across flats 13.0 mm: STANDARD_DERIVED
- nut thickness 6.620 mm: STANDARD_RANGE_SELECTED
- governed range: [6.44, 6.80] mm
- selection rule: midpoint_of_verified_standard_range

The representative value is a ThreadROM modelling selection inside the
verified permitted range. It is not represented as an exact ISO nominal
dimension or as a manufacturing mean.

## 4. M12x1.75 verification

### 4.1 Thread

Governed candidate inputs:

- nominal diameter d = 12.0 mm
- coarse pitch P = 1.75 mm

Independent basic-profile evaluation:

H = sqrt(3)/2 * P
  = 1.515544456622768 mm

d2 = d - 3H/4
   = 10.863341657532924 mm

D1 = d - 5H/4
   = 10.105569429221540 mm

d3 = d - 17H/12
   = 9.852978686451079 mm

Tensile stress area:

As = pi/4 * (d - 0.938194 P)^2
   = 84.2665383650636 mm^2

Disposition:

- nominal diameter 12.0 mm: STANDARD_DERIVED
- pitch 1.75 mm: STANDARD_DERIVED

### 4.2 ISO 4017 bolt

Verified representative product dimensions:

- head across flats s = 18.0 mm
- head height k = 7.5 mm

Disposition:

- head across flats: STANDARD_DERIVED
- head height: STANDARD_DERIVED

### 4.3 ISO 4032 style-1 nut

Verified dimensional range:

- across flats s = 18.0 mm nominal/max
- nut height m = 10.37 mm minimum to 10.80 mm maximum

ThreadROM representative nut thickness:

m_rep = (10.37 + 10.80) / 2
      = 10.585 mm

Disposition:

- across flats 18.0 mm: STANDARD_DERIVED
- nut thickness 10.585 mm: STANDARD_RANGE_SELECTED
- governed range: [10.37, 10.80] mm
- selection rule: midpoint_of_verified_standard_range

The representative value is a ThreadROM modelling selection inside the
verified permitted range. It is not represented as an exact ISO nominal
dimension or as a manufacturing mean.

## 5. Cross-size governed matrix

| Quantity | M8x1.25 | M12x1.75 | Evidence basis |
| --- | ---: | ---: | --- |
| nominal diameter | 8.0 mm | 12.0 mm | STANDARD_DERIVED |
| coarse pitch | 1.25 mm | 1.75 mm | STANDARD_DERIVED |
| bolt across flats | 13.0 mm | 18.0 mm | STANDARD_DERIVED |
| bolt head height | 5.3 mm | 7.5 mm | STANDARD_DERIVED |
| nut across flats | 13.0 mm | 18.0 mm | STANDARD_DERIVED |
| nut thickness | 6.620 mm | 10.585 mm | STANDARD_RANGE_SELECTED |

## 6. Maturity boundary

This verification authorizes DIMENSIONAL_DATA admission only.

It does not claim:

- CAD certification
- FEM support
- FEM certification
- ROM support
- literal ISO 965 tolerance-zone CAD
- manufactured-part dimensional probability distributions
- material/property-class certification beyond separately governed evidence

M8 and M12 shall advance through the same governed capability ladder as any
future metric size.

## 7. External verification evidence

Current standard status was checked against the ISO catalogue.

Dimensional cross-check evidence included current ISO 4017 product-standard
data and independent industrial product data for M8 and M12, together with
ISO 4032 style-1 nut dimensional data.

Only the individual dimensional values needed for ThreadROM verification are
recorded here. External standards tables are not reproduced.

## 8. Certification result

PASS FOR DIMENSIONAL ADMISSION.

M8x1.25 and M12x1.75 have sufficient independently verified dimensional
provenance to enter the ThreadROM standards resolver at DIMENSIONAL_DATA
maturity.

No CAD, FEM or ROM certification is implied.

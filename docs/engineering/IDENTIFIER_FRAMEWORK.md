# ThreadROM Identifier Framework

## Purpose

Every controlled ThreadROM artefact receives a permanent and unique identifier.

Identifiers must never be reused, including after an artefact is rejected,
withdrawn, deprecated or archived.

## Identifier families

| Prefix | Artefact type |
|---|---|
| TRM-ADR | Engineering Decision Record |
| TRM-GEO | Geometry definition |
| TRM-MAT | Material definition |
| TRM-MSH | Mesh definition |
| TRM-SIM | Simulation case |
| TRM-KO | Knowledge Object |
| TRM-DS | Dataset release |
| TRM-MDL | Model release |
| TRM-SCH | Schema release |
| TRM-REL | System release |

## Identifier format

TRM-TYPE-NNNNNN

Example:

TRM-SIM-000001

## Numbering rules

1. Each identifier family uses an independent sequence.
2. Numbers contain six digits with leading zeros.
3. Numbering begins at 000001.
4. Issued identifiers must never be reused.
5. Rejected and withdrawn artefacts retain their identifiers.
6. Filenames may contain identifiers but are not the authoritative identity.
7. Relationships between artefacts must be recorded explicitly in metadata.
8. Human-readable names may change; persistent identifiers must not.

## Reserved Phase 1 identities

- TRM-ADR-000001 — First engineering decision record
- TRM-GEO-000001 — Baseline threaded-joint geometry
- TRM-MAT-000001 — Baseline material definition
- TRM-MSH-000001 — Baseline mesh definition
- TRM-SIM-000001 — Baseline FEM simulation
- TRM-KO-000001 — First accepted ThreadROM Knowledge Object

Reservation does not imply approval. Each artefact must pass its applicable
engineering, verification and release gates.

## Current status

- Status: Draft
- Applies from: Phase 1
- Review required before: First baseline artefact release
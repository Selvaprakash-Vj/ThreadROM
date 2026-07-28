# ThreadROM Coordinate-System Convention

## Global coordinate system

ThreadROM uses a right-handed Cartesian coordinate system.

- Global X-axis: transverse direction
- Global Y-axis: transverse direction
- Global Z-axis: bolt axis and primary tensile-loading direction
- Positive Z: from the bolt head toward the nut
- Rotation follows the right-hand rule

## Geometry alignment

1. The bolt axis must coincide with the global Z-axis.
2. The bolt-head reference surface must remain perpendicular to the Z-axis.
3. The nut reference surface must remain perpendicular to the Z-axis.
4. The joint centreline must pass through X = 0 and Y = 0.
5. Thread geometry must be generated consistently with the defined handedness.
6. Any geometry transformation must be recorded in the simulation metadata.

## Loading convention

- Bolt preload acts along the bolt axis.
- External tensile load is positive in the axial direction.
- Compressive axial load is negative.
- Reaction forces must be reported using the same sign convention.

## Result convention

- Axial displacement: Z-direction displacement
- Radial displacement: displacement normal to the bolt axis
- Circumferential direction: rotation around the Z-axis
- Thread positions are referenced from the first engaged thread
- Thread numbering increases away from the loaded bearing interface

## Mandatory rules

1. Solver adapters must map their native coordinates to this convention.
2. All exported field data must declare its coordinate system.
3. Local coordinate systems must have persistent names and documented origins.
4. Mirroring, rotation or axis reversal must not occur without metadata.
5. Plots and reports must display orientation markers where interpretation depends on direction.

## Current status

**Status:** Draft  
**Applies from:** Phase 1  
**Review required before:** Baseline geometry release

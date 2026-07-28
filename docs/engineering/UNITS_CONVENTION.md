# ThreadROM Engineering Units Convention

## Canonical project units

ThreadROM stores and exchanges engineering quantities using explicit SI units.

| Quantity | Canonical unit |
|---|---|
| Length | metre (`m`) |
| Force | newton (`N`) |
| Mass | kilogram (`kg`) |
| Time | second (`s`) |
| Stress and pressure | pascal (`Pa`) |
| Temperature | kelvin (`K`) |
| Angle | radian (`rad`) |
| Density | kilogram per cubic metre (`kg/m^3`) |

## Engineering display units

Human-readable reports may use:

- Length: millimetres (`mm`)
- Stress and pressure: megapascals (`MPa`)
- Force: newtons (`N`)
- Preload: newtons (`N`)
- Displacement: millimetres (`mm`)

## Mandatory rules

1. Every numerical configuration value must declare its unit.
2. Unit conversions must occur through controlled code, not manual interpretation.
3. Solver adapters must declare the consistent unit system they use.
4. Raw solver values must not be mixed with canonical project values without conversion.
5. Reports must display units beside every engineering quantity.
6. Unitless values must be explicitly identified as dimensionless.
7. No implicit or undocumented unit assumptions are permitted.

## Current status

**Status:** Draft  
**Applies from:** Phase 1  
**Review required before:** First baseline FEM execution

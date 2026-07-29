# TRM-MSH-000001 Axial Response Comparison

## Purpose

This verification compares the global axial response of the bolt-only
CalculiX transfer model across controlled mesh levels.

The model uses a total axial force of
-1000.000 N applied equally to the nodes in
`BOLT_HEAD_TOP`.

Because every loaded node receives the same nodal force, the arithmetic mean
of the loaded-node axial displacements is also the load-weighted,
work-conjugate displacement for this verification model.

## Results

| Mesh level | Simulation | Loaded nodes | Mean VZ (mm) | Minimum VZ (mm) | Maximum VZ (mm) | VZ standard deviation (mm) | Coefficient of variation | Apparent stiffness (kN/mm) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| coarse | TRM-SIM-000001 | 169 | -2.841180307692e-03 | -3.041512000000e-03 | -2.643210000000e-03 | 9.972404362934e-05 | 3.509951 | 351.966398 |
| medium | TRM-SIM-000002 | 331 | -2.857074770393e-03 | -3.055441000000e-03 | -2.666429000000e-03 | 9.483184471526e-05 | 3.319194 | 350.008341 |

## Mesh-to-mesh change

Changes are calculated relative to the finer result.

| Transition | Mean-displacement change | Stiffness change | Maximum global-response difference |
|---|---:|---:|---:|
| coarse to medium | 0.556319% | -0.559432% | 0.559432% |

## Interpretation

The coarse and medium meshes agree to approximately 0.56 percent for the
global axial displacement and apparent stiffness of this bolt-only model.

The medium mesh is therefore retained as the provisional engineering
baseline for global response.

This comparison does not establish convergence for:

- Thread-root stress
- Local stress concentration
- Thread-flank contact pressure
- First-thread load share
- Preload loss
- Nonlinear frictional contact
- Full joint stiffness

Those quantities require the complete threaded-joint assembly and dedicated
local mesh-convergence studies.

## Next verification gate

Run the same controlled model with the fine mesh and extend this report with
a medium-to-fine reference comparison.

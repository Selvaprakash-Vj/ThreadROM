# Phase 2 Checkpoint 10 — TRM-SIM-000011 Accepted Opening State

## Classification

`TRM-SIM-000011` achieved nonlinear equilibrium but failed the physical
clamp-direction gate.

**Status: ACCEPTED BUT PHYSICALLY INVALID**

## Controlled experiment

The experiment retained the TRM-SIM-000010 physical model and changed only the
nonlinear load-ramp granularity:

- Total target preload: 750 N
- Pretension reference-force sign: -1
- Initial time increment: 0.02
- Maximum time increment: 0.02
- Nominal first load increment: 5 N

## Numerically accepted state

CalculiX accepted:

- Step: 1
- Increment: 1
- Time: 0.02
- Nominal preload: 5 N
- Equilibrium iterations: 15
- Contact spring elements at convergence: 135680

This validates the hypothesis that reducing the initial load jump from 250 N to
5 N can stabilise the nonlinear contact solve.

## Geometry-aware physical-direction result

| Surface | Mean D3 |
|---|---:|
| Bolt under-head bearing | -6.120112798200e-04 mm |
| Head-member bearing | +2.791175527714e-15 mm |
| Nut lower bearing | +2.094950414050e-03 mm |
| Nut-member bearing | +3.927225029768e-11 mm |

Geometry-aware interface changes:

| Interface | Gap change | Result |
|---|---:|---|
| Under-head | +6.120112798227e-04 mm | Opening |
| Nut bearing | +2.094950374778e-03 mm | Opening |

Positive geometry-aware gap change represents separation. Both bearing
interfaces therefore opened.

## Engineering conclusion

The reduced increment size solved the immediate numerical-divergence problem,
but the retained negative pretension reference-force sign does not create a
physical clamp state.

The next governed hypothesis must retain the validated 5 N ramp while reversing
only the pretension load direction. No contact, friction, mesh, stiffness or
constraint changes are justified by this result.

The active solver was not modified or disturbed while this evidence was frozen.
## Controlled shutdown

After the accepted-opening evidence was preserved, the invalid experiment was
terminated deliberately.

Final process verification:

- Matching CalculiX processes: 0
- Matching ThreadROM runner processes: 0
- No unrelated process was terminated.
- The final `.sta`, `.cvg`, `.dat`, `.frd`, solver stdout and solver stderr files
  were copied into the ignored simulation archive.
- The governed input configurations and repository files were not altered during
  shutdown.

`TRM-SIM-000011` is closed with the final classification:

**NUMERICALLY STABILISED, PHYSICALLY INVALID — BOTH BEARING INTERFACES OPENED**

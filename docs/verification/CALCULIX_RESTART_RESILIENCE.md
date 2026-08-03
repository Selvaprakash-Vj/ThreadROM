# CalculiX Restart-Resilience Verification

## Status

**Verified**

ThreadROM now supports recoverable CalculiX checkpoints at completed preload-step boundaries for newly generated governed pretension decks.

The currently running `TRM-SIM-000009` job was created from the earlier one-step deck and cannot use this new restart architecture.

## Governed design

The pretension configuration now controls:

- checkpoint count;
- nonlinear increment limits;
- initial, minimum, and maximum time increments;
- restart-write enablement and frequency;
- latest-checkpoint overlay behavior.

The baseline uses 20 sequential preload steps. Each step advances the cumulative target by 5%. For the 5 kN model, the targets are 250 N, 500 N, 750 N, and so on through 5000 N.

The first step activates:

```text
*RESTART,WRITE,FREQUENCY=1,OVERLAY
```

Each fully completed step becomes a recoverable checkpoint. Recovery is not available from an incomplete Newton iteration or unfinished increment.

## Continuation workflow

The non-destructive continuation tool:

1. parses the `.sta` history;
2. identifies the latest fully completed checkpoint;
3. verifies the `.rout` source;
4. copies it to the continuation job's `.rin`;
5. verifies the copy with SHA-256;
6. writes `*RESTART,READ` first in the continuation deck;
7. removes completed preload steps;
8. preserves only the remaining governed steps;
9. re-enables restart writing;
10. writes a provenance manifest;
11. refuses to overwrite an existing bundle.

The original solver files are not modified.

## Real CalculiX proof

A lightweight C3D8 model was solved with CalculiX 2.23 using:

1. checkpoint 1 and a real `.rout`;
2. a verified `.rin` continuation;
3. resumed completion of checkpoint 2;
4. an independent uninterrupted two-step solution.

| Result | Value |
|---|---:|
| Completed checkpoint | 1 of 2 |
| Resumed checkpoint | 2 of 2 |
| Restart size | 9,821 bytes |
| Restart SHA-256 | `1ad5a1a14a4037975f2ba8c39c7cc99ee6339921a914636251615669001c7e93` |
| Restarted final UZ | `-8.784507000000e-03 mm` |
| Direct final UZ | `-8.784507000000e-03 mm` |
| Absolute difference | `0.000000000000e+00 mm` |

Runtime evidence:

```text
simulations/staging/calculix_restart_smoke/20260803T075143Z
```

The runtime directory is verification evidence and is not intended for source control.

## Implemented components

- `src/threadrom/solver/complete_joint_pretension.py`
- `src/threadrom/solver/complete_joint_physical_pretension.py`
- `src/threadrom/solver/complete_joint_pretension_restart.py`
- `scripts/prepare_complete_joint_pretension_restart.py`
- `scripts/run_calculix_restart_smoke.py`
- focused unit tests for configuration, deck generation, STA parsing, bundle creation, and overwrite protection

## Conclusion

The restart-resilience architecture is verified for the next governed full-joint pretension run. Once at least one governed preload step completes and produces a valid restart file, an external interruption no longer requires restarting the entire preload history from zero.

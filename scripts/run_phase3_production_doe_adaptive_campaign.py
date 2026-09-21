from __future__ import annotations

import argparse
import time
from pathlib import Path

from threadrom.factory.adaptive_fem_c01_live_port import (
    C01LiveFactoryPort,
    C01PredecessorPending,
)
from threadrom.factory.adaptive_fem_lifecycle import (
    LifecycleAction,
    decide_fem_lifecycle,
)
from threadrom.factory.adaptive_fem_supervisor import (
    SupervisorStop,
    drive_fem_supervisor,
)
from threadrom.factory.production_doe_gate0_evidence import (
    GATE0_CASE_IDS,
)


ROOT = Path(__file__).resolve().parents[1]

TERMINAL_STOPS = {
    SupervisorStop.COMPLETE,
    SupervisorStop.ENGINEERING_REVIEW,
    SupervisorStop.TRIAL_LIMIT,
}


def run_cycle(*, execute: bool, max_actions: int) -> tuple[bool, bool]:
    """Recover every C01 case from disk; return (all_done, blocked)."""

    all_done = True
    blocked = False

    for case_id in GATE0_CASE_IDS:
        port = C01LiveFactoryPort(
            repo_root=ROOT,
            case_id=case_id,
        )

        try:
            snapshot = port.snapshot()
        except C01PredecessorPending:
            print(
                f"{case_id}: WAIT_FOR_VERIFIED_TRIAL_1",
                flush=True,
            )
            all_done = False
            continue

        # Without --execute, inspect only. Do not ask the supervisor
        # to perform preparation, solver launch or physics assessment.
        if not execute:
            decision = decide_fem_lifecycle(snapshot)
            print(
                f"{case_id}: trial={snapshot.trial_index} "
                f"run={snapshot.run_id} "
                f"action={decision.action.value}",
                flush=True,
            )
            if decision.action is not LifecycleAction.CERTIFIED_COMPLETE:
                all_done = False
            continue

        # The port delegates every real launch to the existing
        # campaign-authorized coordinator and shared capacity fence.
        result = drive_fem_supervisor(
            port,
            max_actions=max_actions,
        )

        print(
            f"{case_id}: stop={result.stop.value} "
            f"actions={result.actions_performed} "
            f"run={result.last_run_id}",
            flush=True,
        )

        if result.stop is not SupervisorStop.COMPLETE:
            all_done = False

        if result.stop in {
            SupervisorStop.ENGINEERING_REVIEW,
            SupervisorStop.TRIAL_LIMIT,
        }:
            blocked = True

    return all_done, blocked


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Restartable C01 adapter for the universal FEM supervisor."
        )
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Repeat evidence recovery until stopped or complete.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Allow the supervisor to request governed actions. "
            "Does not create solver authorization."
        ),
    )
    parser.add_argument(
        "--poll-seconds",
        type=float,
        default=60.0,
    )
    parser.add_argument(
        "--max-actions-per-case",
        type=int,
        default=24,
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=0,
        help="0 means unlimited cycles in --watch mode.",
    )

    args = parser.parse_args()

    if args.execute and not args.watch:
        parser.error(
            "--execute requires --watch; one-shot mode is read-only."
        )

    if not 1.0 <= args.poll_seconds <= 3600.0:
        parser.error("--poll-seconds must be between 1 and 3600.")

    if args.max_actions_per_case < 1:
        parser.error("--max-actions-per-case must be positive.")

    if args.max_cycles < 0:
        parser.error("--max-cycles cannot be negative.")

    print(
        "Mode:",
        (
            "GOVERNED EXECUTION"
            if args.execute
            else "READ-ONLY EVIDENCE RECOVERY"
        ),
        flush=True,
    )

    cycle = 0

    try:
        while True:
            cycle += 1
            print(
                f"=== C01 CAMPAIGN CYCLE {cycle} ===",
                flush=True,
            )

            # Each cycle constructs new evidence-backed ports.
            # Restarting this process does not reset trial history.
            all_done, blocked = run_cycle(
                execute=args.execute,
                max_actions=args.max_actions_per_case,
            )

            if blocked:
                print(
                    "STOP: governed engineering review required.",
                    flush=True,
                )
                return 2

            if all_done:
                print(
                    "All governed cases report certified completion.",
                    flush=True,
                )
                return 0

            if not args.watch:
                print(
                    "Read-only cycle complete. No actions executed.",
                    flush=True,
                )
                return 0

            if args.max_cycles and cycle >= args.max_cycles:
                print(
                    "Configured cycle limit reached; "
                    "durable evidence preserved.",
                    flush=True,
                )
                return 0

            time.sleep(args.poll_seconds)

    except KeyboardInterrupt:
        print(
            "Campaign driver interrupted. "
            "Recover verified evidence before any further launch.",
            flush=True,
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

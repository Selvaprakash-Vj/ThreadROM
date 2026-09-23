"""Governed initial-case FEM port.

Existing or uncertain solver evidence is never replaced. Full-physics
assessment and independent certification are NOT inferred here.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from threadrom.factory.adaptive_fem_lifecycle import (
    FEMLifecycleSnapshot,
    PhysicsDisposition,
    RunPhase,
)
from threadrom.factory.production_doe_trial_history import (
    verify_completed_trial,
)
from threadrom.factory.production_doe_launch_fence import (
    CLAIM_FILENAME,
)
from threadrom.factory.production_doe_case_registry import resolve_governed_c01_case
from threadrom.factory.preload_calibration_campaign import PreloadCalibrationCampaignPolicy


class GovernedInitialFEMLivePort:
    """Initial DOE lifecycle; no corrective-trial or physics shortcuts."""

    def __init__(self, *, repo_root: Path, case_id: str):
        self.root = Path(repo_root).resolve(strict=True)
        self.case_id = case_id
        self.case = resolve_governed_c01_case(
            repo_root=self.root,
            requested_case_id=case_id,
        )
        if (
            self.case.case_id != case_id
            or self.case.case_run_id
            != "trm_fem_" + self.case.case_hash[:12]
        ):
            raise RuntimeError("Governed case identity mismatch.")

        self.maximum_trials = (
            PreloadCalibrationCampaignPolicy().maximum_trials
        )
        self.campaign_root = (
            self.root
            / "simulations/staging/phase3_cp8_production_doe"
            / "TRM-PDOE-C01"
        )
        self.case_root = (
            self.campaign_root
            / "solver_preparation"
            / self.case.case_run_id
        )

    def _trial_id(self, index: int) -> str:
        return f"{self.case.case_run_id}_cal_{index:02d}"

    def _uncertain(self, index: int) -> FEMLifecycleSnapshot:
        return FEMLifecycleSnapshot(
            run_id=self._trial_id(index),
            trial_index=index,
            maximum_trials=self.maximum_trials,
            phase=RunPhase.UNCERTAIN,
        )

    def _prepared_deck_hash(
        self, index: int, run_dir: Path,
    ) -> str | None:
        """Read and check local preparation identity, not solver approval."""
        name = (
            "production_doe_solver_preparation_record.json"
            if index == 1
            else "production_doe_calibration_solver_preparation_record.json"
        )
        record_path = run_dir / name
        if not record_path.is_file():
            return None

        try:
            record = json.loads(
                record_path.read_text(encoding="utf-8-sig")
            )
            expected_trial = (
                "trial_1" if index == 1 else "next_trial"
            )
            assert isinstance(record, dict)
            assert record["case"]["case_hash"] == self.case.case_hash
            assert (
                record[expected_trial]["run_id"]
                == self._trial_id(index)
            )
            deck_hash = record["deck"]["sha256"]
            assert (
                isinstance(deck_hash, str)
                and len(deck_hash) == 64
                and all(c in "0123456789abcdef" for c in deck_hash)
            )
            deck_path = run_dir / (self._trial_id(index) + ".inp")
            assert deck_path.is_file()
            assert (
                hashlib.sha256(deck_path.read_bytes()).hexdigest()
                == deck_hash
            )
            return deck_hash
        except (
            AssertionError,
            KeyError,
            TypeError,
            ValueError,
            OSError,
        ):
            return None

    def _recover(self):
        """Return verified consecutive completed trials and next run state.

        A nonempty, incomplete, conflicting or unverified run is always
        UNCERTAIN. The method never authorizes or starts another solve.
        """
        completed = []
        next_index = 1

        if self.case_root.exists() and not self.case_root.is_dir():
            return completed, self._uncertain(1)

        if self.case_root.is_dir():
            for item in self.case_root.iterdir():
                if (
                    item.name.startswith(
                        self.case.case_run_id + "_cal_"
                    )
                    and item.name not in {
                        self._trial_id(i)
                        for i in range(1, self.maximum_trials + 1)
                    }
                ):
                    return completed, self._uncertain(1)

        for index in range(1, self.maximum_trials + 1):
            run_id = self._trial_id(index)
            run_dir = self.case_root / run_id

            if not run_dir.exists():
                next_index = index
                # An earlier completed run is not permission to prepare
                # or launch the next calibration trial.
                if completed:
                    return completed, self._uncertain(index - 1)
                if index == 1:
                    if self.case_root.is_dir():
                        unexpected = [
                            p for p in self.case_root.iterdir()
                            if p.is_file() and p.name.startswith(
                                "production_doe_accepted_fem_evidence"
                            )
                        ]
                        if unexpected:
                            return completed, self._uncertain(1)
                    return completed, FEMLifecycleSnapshot(
                        run_id=run_id,
                        trial_index=1,
                        maximum_trials=self.maximum_trials,
                        phase=RunPhase.NOT_PREPARED,
                    )
                return completed, self._uncertain(index)

            if not run_dir.is_dir():
                return completed, self._uncertain(index)

            deck_hash = self._prepared_deck_hash(index, run_dir)
            manifest = run_dir / "fem_run_manifest.json"

            if manifest.is_file():
                if deck_hash is None:
                    return completed, self._uncertain(index)
                try:
                    verify_completed_trial(
                        repo_root=self.root,
                        manifest_path=manifest,
                        expected_run_id=run_id,
                        expected_case_hash=self.case.case_hash,
                        expected_deck_sha256=deck_hash,
                    )
                except Exception:
                    return completed, self._uncertain(index)
                completed.append(run_id)
                continue

            # A pending or interrupted solve must not become PREPARED.
            if index != 1 or completed:
                return completed, self._uncertain(index)

            if not deck_hash:
                if any(run_dir.iterdir()):
                    return completed, self._uncertain(index)
                return completed, FEMLifecycleSnapshot(
                    run_id=run_id,
                    trial_index=1,
                    maximum_trials=self.maximum_trials,
                    phase=RunPhase.NOT_PREPARED,
                )

            unsafe_names = (
                CLAIM_FILENAME,
                "fem_run_manifest.json",
            )
            unsafe_extensions = (
                ".sta", ".dat", ".frd", ".rout", ".cvg",
                ".12d", ".stdout.log", ".stderr.log",
            )
            if (
                any((run_dir / name).exists() for name in unsafe_names)
                or any(
                    p.is_file()
                    and p.name.startswith(run_id)
                    and p.name.endswith(unsafe_extensions)
                    for p in run_dir.iterdir()
                )
            ):
                return completed, self._uncertain(index)

            return completed, FEMLifecycleSnapshot(
                run_id=run_id,
                trial_index=1,
                maximum_trials=self.maximum_trials,
                phase=RunPhase.PREPARED,
            )

        return completed, self._uncertain(self.maximum_trials)

    def recover_verified_trials(self) -> tuple[str, ...]:
        """Read-only verified completion inventory; not a physics verdict."""
        completed, _ = self._recover()
        return tuple(completed)

    def snapshot(self) -> FEMLifecycleSnapshot:
        _, state = self._recover()
        return state

    def prepare(self, snapshot: FEMLifecycleSnapshot) -> None:
        if (
            snapshot.phase is not RunPhase.NOT_PREPARED
            or self.snapshot() != snapshot
            or self.recover_verified_trials()
        ):
            raise RuntimeError(
                "Initial preparation state changed or evidence exists."
            )

        prepared_record = (
            self.campaign_root
            / "prepared_cases"
            / self.case.case_run_id
            / "production_doe_preparation_record.json"
        )

        if not prepared_record.is_file():
            self._run_preparation(
                "prepare_phase3_production_doe_case.py"
            )

        # The solver-preparation script performs its own independent
        # policy, manifest, physical and immutable-input checks.
        self._run_preparation(
            "prepare_phase3_production_doe_solver_case.py"
        )

        if self.snapshot().phase is not RunPhase.PREPARED:
            raise RuntimeError(
                "Initial preparation did not yield a verified "
                "unexecuted Trial-1 deck. No solve requested."
            )

    def _run_preparation(self, script_name: str) -> None:
        script = self.root / "scripts" / script_name
        subprocess.run(
            [
                sys.executable,
                str(script),
                "--case-id",
                self.case_id,
            ],
            cwd=self.root,
            check=True,
        )

    def launch_authorized(
        self, snapshot: FEMLifecycleSnapshot,
    ) -> bool:
        if (
            snapshot.phase is not RunPhase.PREPARED
            or self.snapshot() != snapshot
            or self.recover_verified_trials()
        ):
            raise RuntimeError(
                "Initial launch state changed or prior FEM exists."
            )

        # Only the existing, independently authorized and
        # reservation-guarded Trial-1 entry point may execute FEM.
        script = (
            self.root
            / "scripts/run_phase3_production_doe_trial1_case.py"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--case-id",
                self.case_id,
            ],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

        output = result.stdout + result.stderr

        if (
            result.returncode != 0
            and "BLOCKED_UNAUTHORIZED_INITIAL_TRIAL" in output
        ):
            return False

        if result.returncode != 0:
            raise RuntimeError(
                "Initial-trial launcher stopped. Inspect existing "
                "evidence and output before any retry.\n"
                + output[-5000:]
            )

        if self._trial_id(1) not in self.recover_verified_trials():
            raise RuntimeError(
                "Launcher returned success without independently "
                "verified completed Trial-1 evidence."
            )
        return True

    def prepare_adaptation(self, snapshot, decision) -> None:
        raise RuntimeError(
            "Correction requires separately governed trial history "
            "and the existing authorized continuation coordinator."
        )

    def assess_verified_physics(
        self, snapshot: FEMLifecycleSnapshot,
    ) -> None:
        raise RuntimeError(
            "Full-physics assessment is not established by "
            "initial-case evidence recovery."
        )

    def verify_full_physics_certificate(
        self, snapshot: FEMLifecycleSnapshot,
    ) -> bool:
        return False

from __future__ import annotations

import hashlib
import json

from pathlib import Path
from types import SimpleNamespace

import pytest

import threadrom.factory.diversified_doe_adaptive_live_port as live_port_module

from threadrom.factory.adaptive_fem_lifecycle import (
    PhysicsDisposition,
    RunPhase,
)
from threadrom.factory.diversified_doe_adaptive_live_port import (
    DiversifiedDOEAdaptiveLivePort,
    DiversifiedGovernedCase,
)
from threadrom.factory.diversified_doe_prepared_trial import (
    make_diversified_prepared_trial_verifier,
)
from threadrom.factory.governed_calibration_history import (
    GovernedCalibrationReplay,
)
from threadrom.factory.governed_trial_history import (
    VerifiedPreparedTrialEvidence,
    recover_governed_trial_history,
)
from threadrom.factory.preload_calibration_campaign import (
    PreloadCalibrationTrial,
    PreloadCalibrationTrialSource,
)
from threadrom.factory.production_doe_adaptive_controller import (
    AdaptiveCalibrationAction,
)
from threadrom.factory.windows_process_adjudication import (
    FemProcessAdjudication,
    FemProcessStatus,
)


CASE_ID = "TRM-DDOE-D-TEST-01"
CASE_HASH = "a" * 64

# Intentionally NOT derived from CASE_HASH.
CASE_RUN_ID = "trm_fem_bbbbbbbbbbbb"

CAL01_ID = CASE_RUN_ID + "_cal_01"
CAL02_ID = CASE_RUN_ID + "_cal_02"
CAL03_ID = CASE_RUN_ID + "_cal_03"

CORRECTIVE_RULE = "governed_preload_calibration"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _verified_initial():
    return SimpleNamespace(
        completion_status=(
            "COMPLETED_INPUT_EVIDENCE_VERIFIED"
        ),
        run_id=CAL01_ID,
    )


def _trial(
    *,
    index: int,
    run_id: str,
    delta_temperature_c: float,
    source: str,
):
    return PreloadCalibrationTrial(
        trial_index=index,
        run_id=run_id,
        delta_temperature_c=delta_temperature_c,
        source=PreloadCalibrationTrialSource(
            source
        ),
    )


def test_history_accepts_independent_case_run_identity(
    tmp_path,
):
    root = tmp_path
    solver_root = root / "solver"
    run_dir = (
        solver_root
        / CASE_RUN_ID
        / CAL02_ID
    )

    run_dir.mkdir(
        parents=True
    )

    deck = (
        run_dir
        / f"{CAL02_ID}.inp"
    )

    deck.write_text(
        "*HEADING\n",
        encoding="utf-8",
    )

    deck_sha = _sha256(
        deck
    )

    def verifier(
        *,
        repo_root,
        case_id,
        case_hash,
        case_run_id,
        trial_index,
        run_dir,
    ):
        assert case_id == CASE_ID
        assert case_hash == CASE_HASH
        assert case_run_id == CASE_RUN_ID
        assert trial_index == 2

        return VerifiedPreparedTrialEvidence(
            run_id=CAL02_ID,
            trial_index=2,
            deck_path=deck,
            deck_sha256=deck_sha,
        )

    history = recover_governed_trial_history(
        repo_root=root,
        case_id=CASE_ID,
        case_hash=CASE_HASH,
        case_run_id=CASE_RUN_ID,
        solver_preparation_root=(
            solver_root
        ),
        verified_initial_trial=(
            _verified_initial()
        ),
        maximum_trials=6,
        verify_prepared_trial=verifier,
    )

    assert history.case_id == CASE_ID
    assert history.completed_run_ids == (
        CAL01_ID,
    )
    assert history.next_trial_index == 2
    assert (
        history.state
        == "PREPARED_TRIAL_NOT_COMPLETED"
    )


def test_history_rejects_trial_gap(
    tmp_path,
):
    root = tmp_path
    solver_root = root / "solver"

    (
        solver_root
        / CASE_RUN_ID
        / CAL03_ID
    ).mkdir(
        parents=True
    )

    def verifier(**kwargs):
        raise AssertionError(
            "Verifier must not run across a history gap."
        )

    with pytest.raises(
        RuntimeError,
        match="trial-history gap",
    ):
        recover_governed_trial_history(
            repo_root=root,
            case_id=CASE_ID,
            case_hash=CASE_HASH,
            case_run_id=CASE_RUN_ID,
            solver_preparation_root=(
                solver_root
            ),
            verified_initial_trial=(
                _verified_initial()
            ),
            maximum_trials=6,
            verify_prepared_trial=verifier,
        )


def test_diversified_preparation_requires_pinned_bytes(
    tmp_path,
):
    root = tmp_path

    run_dir = (
        root
        / "simulations"
        / CASE_RUN_ID
        / CAL02_ID
    )

    run_dir.mkdir(
        parents=True
    )

    deck = (
        run_dir
        / f"{CAL02_ID}.inp"
    )

    deck.write_text(
        "*HEADING\n",
        encoding="utf-8",
    )

    record_path = (
        run_dir
        / "pilot_adaptive_factory_preflight.json"
    )

    record = {
        "case_hash": CASE_HASH,
        "case_run_id": CASE_RUN_ID,
        "scope": "test_scope",
        "sealed_holdouts_accessed": False,
        "dataset_admission_authorized": False,
        "doe_wide_solver_launch_authorized": False,
        "production_doe_authorization_claimed": False,
        "next_trial": {
            "run_id": CAL02_ID,
            "trial_index": 2,
            "delta_temperature_c": -10.0,
            "source": "proportional",
        },
        "deck": {
            "relative_path": (
                deck.relative_to(
                    root
                ).as_posix()
            ),
            "sha256": _sha256(
                deck
            ),
        },
    }

    record_path.write_text(
        json.dumps(
            record,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    good_sha = _sha256(
        record_path
    )

    verifier = (
        make_diversified_prepared_trial_verifier(
            preparation_records={
                CAL02_ID: (
                    record_path,
                    good_sha,
                ),
            },
            required_scope="test_scope",
        )
    )

    evidence = verifier(
        repo_root=root,
        case_id=CASE_ID,
        case_hash=CASE_HASH,
        case_run_id=CASE_RUN_ID,
        trial_index=2,
        run_dir=run_dir,
    )

    assert evidence.run_id == CAL02_ID
    assert evidence.trial_index == 2
    assert evidence.deck_sha256 == _sha256(
        deck
    )

    bad_verifier = (
        make_diversified_prepared_trial_verifier(
            preparation_records={
                CAL02_ID: (
                    record_path,
                    "0" * 64,
                ),
            },
            required_scope="test_scope",
        )
    )

    with pytest.raises(
        RuntimeError,
        match="SHA-256 drift",
    ):
        bad_verifier(
            repo_root=root,
            case_id=CASE_ID,
            case_hash=CASE_HASH,
            case_run_id=CASE_RUN_ID,
            trial_index=2,
            run_dir=run_dir,
        )


class _SnapshotHarness(
    DiversifiedDOEAdaptiveLivePort
):
    def __init__(
        self,
        *,
        history,
        replay,
    ):
        self.case_id = CASE_ID

        self.case = DiversifiedGovernedCase(
            case_id=CASE_ID,
            case_hash=CASE_HASH,
            case_run_id=CASE_RUN_ID,
            thread_designation="M10x1.5",
            member_material_id="test_material",
        )

        self.maximum_trials = 6
        self.corrective_rule_id = (
            CORRECTIVE_RULE
        )
        self.calibration_replay = (
            lambda completed: replay
        )
        self._test_history = history

    def _history(self):
        return self._test_history


def test_live_snapshot_running_requires_matching_replay(
    monkeypatch,
):
    history = SimpleNamespace(
        state=(
            "PREPARED_TRIAL_NOT_COMPLETED"
        ),
        completed_run_ids=(
            CAL01_ID,
        ),
        next_trial_index=2,
    )

    replay = GovernedCalibrationReplay(
        case_id=CASE_ID,
        completed_trial_count=1,
        last_completed_run_id=(
            CAL01_ID
        ),
        action=(
            AdaptiveCalibrationAction
            .NEXT_TRIAL_REQUIRES_AUTHORIZATION
        ),
        next_trial=_trial(
            index=2,
            run_id=CAL02_ID,
            delta_temperature_c=-20.0,
            source="proportional",
        ),
    )

    monkeypatch.setattr(
        live_port_module,
        "adjudicate_live_fem_processes",
        lambda **kwargs: (
            FemProcessAdjudication(
                status=(
                    FemProcessStatus
                    .LIVE_MATCH
                ),
                matching_process_ids=(
                    1234,
                ),
                reason="test",
            )
        ),
    )

    port = _SnapshotHarness(
        history=history,
        replay=replay,
    )

    snapshot = port.snapshot()

    assert snapshot.run_id == CAL02_ID
    assert snapshot.trial_index == 2
    assert snapshot.phase is RunPhase.RUNNING
    assert (
        snapshot.completed_evidence_verified
        is False
    )


def test_live_snapshot_rejects_prepared_trial_not_demanded_by_replay(
    monkeypatch,
):
    history = SimpleNamespace(
        state=(
            "PREPARED_TRIAL_NOT_COMPLETED"
        ),
        completed_run_ids=(
            CAL01_ID,
        ),
        next_trial_index=2,
    )

    replay = GovernedCalibrationReplay(
        case_id=CASE_ID,
        completed_trial_count=1,
        last_completed_run_id=(
            CAL01_ID
        ),
        action=(
            AdaptiveCalibrationAction
            .NEXT_TRIAL_REQUIRES_AUTHORIZATION
        ),
        next_trial=_trial(
            index=3,
            run_id=CAL03_ID,
            delta_temperature_c=-30.0,
            source="proportional",
        ),
    )

    monkeypatch.setattr(
        live_port_module,
        "adjudicate_live_fem_processes",
        lambda **kwargs: pytest.fail(
            "Process adjudication must not happen "
            "after calibration-lineage mismatch."
        ),
    )

    port = _SnapshotHarness(
        history=history,
        replay=replay,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "prepared trial differs from "
            "governed calibration replay"
        ),
    ):
        port.snapshot()


def test_completed_calibration_accept_transitions_to_physics_pending():
    history = SimpleNamespace(
        state=(
            "NEXT_TRIAL_NOT_PREPARED"
        ),
        completed_run_ids=(
            CAL01_ID,
            CAL02_ID,
        ),
        next_trial_index=3,
    )

    replay = GovernedCalibrationReplay(
        case_id=CASE_ID,
        completed_trial_count=2,
        last_completed_run_id=(
            CAL02_ID
        ),
        action=(
            AdaptiveCalibrationAction
            .CALIBRATION_ACCEPTED_PENDING_FULL_PHYSICS
        ),
        next_trial=None,
    )

    port = _SnapshotHarness(
        history=history,
        replay=replay,
    )

    snapshot = port.snapshot()

    assert snapshot.run_id == CAL02_ID
    assert snapshot.trial_index == 2
    assert (
        snapshot.phase
        is RunPhase.COMPLETED
    )
    assert (
        snapshot.completed_evidence_verified
        is True
    )
    assert (
        snapshot.physics
        is PhysicsDisposition.NOT_ASSESSED
    )
    assert (
        snapshot.corrective_rule_id
        is None
    )


def test_completed_calibration_continue_transitions_to_adapt():
    history = SimpleNamespace(
        state=(
            "NEXT_TRIAL_NOT_PREPARED"
        ),
        completed_run_ids=(
            CAL01_ID,
            CAL02_ID,
        ),
        next_trial_index=3,
    )

    replay = GovernedCalibrationReplay(
        case_id=CASE_ID,
        completed_trial_count=2,
        last_completed_run_id=(
            CAL02_ID
        ),
        action=(
            AdaptiveCalibrationAction
            .NEXT_TRIAL_REQUIRES_AUTHORIZATION
        ),
        next_trial=_trial(
            index=3,
            run_id=CAL03_ID,
            delta_temperature_c=-30.0,
            source="proportional",
        ),
    )

    port = _SnapshotHarness(
        history=history,
        replay=replay,
    )

    snapshot = port.snapshot()

    assert snapshot.run_id == CAL02_ID
    assert snapshot.trial_index == 2
    assert (
        snapshot.phase
        is RunPhase.COMPLETED
    )
    assert (
        snapshot.completed_evidence_verified
        is True
    )
    assert (
        snapshot.physics
        is PhysicsDisposition.ADAPT
    )
    assert (
        snapshot.corrective_rule_id
        == CORRECTIVE_RULE
    )


def test_recovery_port_mutating_methods_are_hard_blocked():
    port = object.__new__(
        DiversifiedDOEAdaptiveLivePort
    )

    expected = (
        "DIVERSIFIED_MUTATION_NOT_WIRED"
    )

    with pytest.raises(
        RuntimeError,
        match=expected,
    ):
        port.prepare(None)

    with pytest.raises(
        RuntimeError,
        match=expected,
    ):
        port.prepare_adaptation(
            None,
            None,
        )

    with pytest.raises(
        RuntimeError,
        match=expected,
    ):
        port.launch_authorized(
            None
        )

    with pytest.raises(
        RuntimeError,
        match=expected,
    ):
        port.assess_verified_physics(
            None
        )

    with pytest.raises(
        RuntimeError,
        match=expected,
    ):
        port.verify_full_physics_certificate(
            None
        )

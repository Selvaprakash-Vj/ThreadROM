"""Initial-trial admission through the existing Windows launch fence."""

from pathlib import Path

import pytest

import threadrom.factory.production_doe_launch_fence as fence


CASE_RUN_ID = "trm_fem_" + "a" * 12
TRIAL_RUN_ID = CASE_RUN_ID + "_cal_01"


def _trial(tmp_path, monkeypatch):
    campaign = tmp_path / "campaign"
    run_dir = (
        campaign
        / "solver_preparation"
        / CASE_RUN_ID
        / TRIAL_RUN_ID
    )
    run_dir.mkdir(parents=True)
    monkeypatch.setattr(fence, "count_running_ccx", lambda: 0)
    return campaign, run_dir


def _reserve(campaign, **changes):
    args = {
        "campaign_root": campaign,
        "case_run_id": CASE_RUN_ID,
        "trial_run_id": TRIAL_RUN_ID,
        "maximum_authorized_ccx": 1,
        "allow_initial_trial": True,
    }
    args.update(changes)
    return fence.reserve_adaptive_trial_launch(**args)


def test_initial_trial_claim_persists_after_success(
    tmp_path, monkeypatch,
):
    campaign, run_dir = _trial(tmp_path, monkeypatch)

    with _reserve(campaign) as claim:
        assert claim.is_file()
        assert claim.parent == run_dir

    assert claim.is_file()

    with pytest.raises(RuntimeError, match="durable launch claim"):
        with _reserve(campaign):
            pass


def test_existing_manifest_refuses_duplicate(
    tmp_path, monkeypatch,
):
    campaign, run_dir = _trial(tmp_path, monkeypatch)
    (run_dir / "fem_run_manifest.json").write_text("{}")

    with pytest.raises(RuntimeError, match="manifest"):
        with _reserve(campaign):
            pass

    assert not (run_dir / fence.CLAIM_FILENAME).exists()


def test_orphan_solver_output_requires_review(
    tmp_path, monkeypatch,
):
    campaign, run_dir = _trial(tmp_path, monkeypatch)
    (run_dir / f"{TRIAL_RUN_ID}.dat").write_text("existing")

    with pytest.raises(RuntimeError, match="Pre-existing solver output"):
        with _reserve(campaign):
            pass

    assert not (run_dir / fence.CLAIM_FILENAME).exists()


def test_initial_trial_requires_explicit_opt_in(
    tmp_path, monkeypatch,
):
    campaign, run_dir = _trial(tmp_path, monkeypatch)

    with pytest.raises(RuntimeError, match="continuation-trial"):
        with _reserve(campaign, allow_initial_trial=False):
            pass

    assert not (run_dir / fence.CLAIM_FILENAME).exists()


def test_initial_flag_rejects_trial_two(
    tmp_path, monkeypatch,
):
    campaign, run_dir = _trial(tmp_path, monkeypatch)

    with pytest.raises(RuntimeError, match="initial-trial identity"):
        with _reserve(
            campaign,
            trial_run_id=CASE_RUN_ID + "_cal_02",
        ):
            pass


def test_initial_trial_requires_explicit_capacity(
    tmp_path, monkeypatch,
):
    campaign, run_dir = _trial(tmp_path, monkeypatch)

    with pytest.raises(RuntimeError, match="explicit"):
        with _reserve(campaign, maximum_authorized_ccx=None):
            pass

    assert not (run_dir / fence.CLAIM_FILENAME).exists()


def test_capacity_denial_creates_no_claim(
    tmp_path, monkeypatch,
):
    campaign, run_dir = _trial(tmp_path, monkeypatch)
    monkeypatch.setattr(fence, "count_running_ccx", lambda: 1)

    with pytest.raises(RuntimeError, match="BLOCKED_SOLVER_CAPACITY"):
        with _reserve(campaign):
            pass

    assert not (run_dir / fence.CLAIM_FILENAME).exists()


def test_interrupted_operation_keeps_durable_claim(
    tmp_path, monkeypatch,
):
    campaign, run_dir = _trial(tmp_path, monkeypatch)

    with pytest.raises(RuntimeError, match="synthetic interruption"):
        with _reserve(campaign):
            raise RuntimeError("synthetic interruption")

    assert (run_dir / fence.CLAIM_FILENAME).is_file()

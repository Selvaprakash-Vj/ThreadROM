import json

import pytest

import threadrom.factory.production_doe_launch_fence as fence


CASE = "trm_fem_d667bb1aca27"
TRIAL = f"{CASE}_cal_02"


def campaign(tmp_path):
    run_dir = tmp_path / "solver_preparation" / CASE / TRIAL
    run_dir.mkdir(parents=True)
    return tmp_path, run_dir


def reserve(root):
    return fence.reserve_adaptive_trial_launch(
        campaign_root=root,
        case_run_id=CASE,
        trial_run_id=TRIAL,
    )


def test_claim_is_durable_and_blocks_duplicate(tmp_path, monkeypatch):
    root, run_dir = campaign(tmp_path)
    monkeypatch.setattr(fence, "count_running_ccx", lambda: 3)

    with reserve(root) as claim:
        assert claim.is_file()
        record = json.loads(claim.read_text(encoding="utf-8"))
        assert record["trial_run_id"] == TRIAL
        assert record["automatic_retry_authorized"] is False

    assert claim.is_file()

    with pytest.raises(RuntimeError, match="durable launch claim"):
        with reserve(root):
            pass


def test_four_existing_solvers_block_launch(tmp_path, monkeypatch):
    root, run_dir = campaign(tmp_path)
    monkeypatch.setattr(fence, "count_running_ccx", lambda: 4)

    with pytest.raises(RuntimeError, match="capacity exhausted"):
        with reserve(root):
            pass

    assert not (run_dir / fence.CLAIM_FILENAME).exists()


def test_existing_manifest_blocks_launch(tmp_path, monkeypatch):
    root, run_dir = campaign(tmp_path)
    (run_dir / "fem_run_manifest.json").write_text(
        "{}",
        encoding="utf-8",
    )
    monkeypatch.setattr(fence, "count_running_ccx", lambda: 0)

    with pytest.raises(RuntimeError, match="duplicate solve"):
        with reserve(root):
            pass


def test_orphan_solver_output_blocks_launch(tmp_path, monkeypatch):
    root, run_dir = campaign(tmp_path)
    (run_dir / f"{TRIAL}.dat").write_bytes(b"existing evidence")
    monkeypatch.setattr(fence, "count_running_ccx", lambda: 0)

    with pytest.raises(RuntimeError, match="Pre-existing"):
        with reserve(root):
            pass


def test_competing_launch_cannot_take_same_lock(tmp_path, monkeypatch):
    root, _ = campaign(tmp_path)
    monkeypatch.setattr(fence, "count_running_ccx", lambda: 0)

    with reserve(root):
        with pytest.raises(RuntimeError, match="campaign lock"):
            with reserve(root):
                pass


def test_failed_operation_preserves_claim(tmp_path, monkeypatch):
    root, run_dir = campaign(tmp_path)
    monkeypatch.setattr(fence, "count_running_ccx", lambda: 0)

    with pytest.raises(ValueError, match="synthetic failure"):
        with reserve(root):
            raise ValueError("synthetic failure")

    assert (run_dir / fence.CLAIM_FILENAME).is_file()


def test_invalid_trial_identity_rejected(tmp_path, monkeypatch):
    root, _ = campaign(tmp_path)
    monkeypatch.setattr(fence, "count_running_ccx", lambda: 0)

    with pytest.raises(RuntimeError, match="bounded"):
        with fence.reserve_adaptive_trial_launch(
            campaign_root=root,
            case_run_id=CASE,
            trial_run_id=f"{CASE}_cal_07",
        ):
            pass

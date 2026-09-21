import copy
import hashlib
import json

import pytest

from threadrom.factory.production_doe_completed_trial import (
    verify_completed_trial,
)


RUN_ID = "trm_fem_d667bb1aca27_cal_01_wsv21_rfobs1"
CASE_HASH = "d667bb1aca2720b10e8a80dbcfba700b042b45a20289927feb5e97a33f3b244c"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def fixture_run(tmp_path):
    root = tmp_path
    run_dir = root / "simulations" / RUN_ID
    run_dir.mkdir(parents=True)

    artifacts = []
    for role, extension, data in (
        ("dat", "dat", b"MEASURED CLAMP FORCE"),
        ("input_deck", "inp", b"CERTIFIED INPUT DECK"),
    ):
        path = run_dir / f"{RUN_ID}.{extension}"
        path.write_bytes(data)
        artifacts.append({
            "role": role,
            "relative_path": path.relative_to(root).as_posix(),
            "sha256": digest(data),
            "size_bytes": len(data),
        })

    manifest = {
        "run_id": RUN_ID,
        "job_name": RUN_ID,
        "case_hash": CASE_HASH,
        "disposition": "succeeded",
        "job_finished": True,
        "return_code": 0,
        "failure_category": None,
        "failure_message": None,
        "accepted_increment_count": 20,
        "final_step": 20,
        "artifacts": artifacts,
    }
    manifest_path = run_dir / "fem_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return root, run_dir, manifest_path, manifest


def verify(root, manifest_path, **overrides):
    arguments = {
        "repo_root": root,
        "manifest_path": manifest_path,
        "expected_run_id": RUN_ID,
        "expected_case_hash": CASE_HASH,
        "expected_deck_sha256": digest(b"CERTIFIED INPUT DECK"),
    }
    arguments.update(overrides)
    return verify_completed_trial(**arguments)


def test_verified_completed_trial(tmp_path):
    root, _, manifest_path, _ = fixture_run(tmp_path)
    result = verify(root, manifest_path)
    assert result.run_id == RUN_ID
    assert result.dat_sha256 == digest(b"MEASURED CLAMP FORCE")


@pytest.mark.parametrize(
    "change",
    [
        lambda m: m.update(job_finished=False),
        lambda m: m.update(disposition="failed"),
        lambda m: m.update(return_code=1),
        lambda m: m.update(case_hash="0" * 64),
        lambda m: m.update(accepted_increment_count=0),
        lambda m: m["artifacts"].append(
            copy.deepcopy(m["artifacts"][0])
        ),
        lambda m: m["artifacts"][0].update(
            relative_path="../wrong.dat"
        ),
    ],
)
def test_bad_manifest_fails_closed(tmp_path, change):
    root, _, manifest_path, manifest = fixture_run(tmp_path)
    change(manifest)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(RuntimeError):
        verify(root, manifest_path)


def test_modified_dat_fails_closed(tmp_path):
    root, run_dir, manifest_path, _ = fixture_run(tmp_path)
    (run_dir / f"{RUN_ID}.dat").write_bytes(b"ALTERED CLAMP FORCE")

    with pytest.raises(RuntimeError, match="DAT|dat"):
        verify(root, manifest_path)


def test_wrong_preparation_deck_hash_fails_closed(tmp_path):
    root, _, manifest_path, _ = fixture_run(tmp_path)

    with pytest.raises(RuntimeError, match="certified trial preparation"):
        verify(
            root,
            manifest_path,
            expected_deck_sha256="0" * 64,
        )

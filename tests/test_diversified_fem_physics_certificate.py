from __future__ import annotations

from pathlib import Path

import pytest

from threadrom.factory.diversified_fem_physics_certificate import (
    CERTIFICATE_FILENAME,
    persist_governed_physics_certificate,
    recover_governed_physics_certificate,
)


CASE_ID = "D-PILOT-AL"
CASE_HASH = "a" * 64
CASE_RUN = "trm_fem_123456789abc"
RUN_ID = CASE_RUN + "_cal_02"


def _make_repo(
    tmp_path: Path,
) -> tuple[
    Path,
    Path,
    tuple[str, ...],
]:
    root = tmp_path / "repo"
    run_dir = root / "run"

    run_dir.mkdir(
        parents=True
    )

    artifacts = (
        "fem_run_manifest.json",
        f"{RUN_ID}.inp",
        f"{RUN_ID}.dat",
        f"{RUN_ID}.frd",
        f"{RUN_ID}.sta",
        f"{RUN_ID}.cvg",
        f"{RUN_ID}.stdout.log",
    )

    for index, name in enumerate(
        artifacts
    ):
        (
            run_dir / name
        ).write_bytes(
            f"artifact-{index}".encode()
        )

    source = root / "source.py"
    source.write_text(
        "VALUE = 1\n",
        encoding="utf-8",
    )

    return (
        root,
        run_dir,
        ("source.py",),
    )


def _assessment():
    return {
        "calibration_disposition": "accept",
        "next_trial_run_id": None,
        "calibration_target_force_n": 15000.0,
        "calibration_mean_force_n": 14891.163,
        "calibration_target_error_percent": -0.7256,
        "calibration_spread_percent": 0.0353,
        "result_policy_id": (
            "complete_joint_semantic_results_v1"
        ),
        "physics_policy_id": (
            "complete_joint_general_v2_"
            "external_support_equilibrium"
        ),
        "equilibrium_status": "pass",
        "maximum_translational_resultant_n": (
            0.000022998
        ),
        "translational_force_tolerance_n": (
            0.001
        ),
        "accepted_increment_count": 20,
        "thread_normal_force_n": 11858.48,
        "physics_checks": [
            {
                "name": "gate-a",
                "kind": "hard_gate",
                "passed": True,
            },
            {
                "name": "diagnostic-a",
                "kind": "diagnostic",
                "passed": True,
            },
        ],
        "failed_governed_checks": [],
        "full_physics_passed": True,
        "rotational_moment_equilibrium_status": (
            "not_assessed"
        ),
    }


def test_persist_and_recover_certificate(
    tmp_path: Path,
) -> None:
    root, run_dir, sources = (
        _make_repo(tmp_path)
    )

    path = persist_governed_physics_certificate(
        repo_root=root,
        run_dir=run_dir,
        case_id=CASE_ID,
        case_hash=CASE_HASH,
        case_run_id=CASE_RUN,
        run_id=RUN_ID,
        trial_index=2,
        assessment=_assessment(),
        source_paths=sources,
    )

    assert path.name == (
        CERTIFICATE_FILENAME
    )

    record = (
        recover_governed_physics_certificate(
            repo_root=root,
            run_dir=run_dir,
            case_id=CASE_ID,
            case_hash=CASE_HASH,
            case_run_id=CASE_RUN,
            run_id=RUN_ID,
            trial_index=2,
            source_paths=sources,
        )
    )

    assert record is not None
    assert (
        record["assessment"]
        ["full_physics_passed"]
        is True
    )


def test_persist_is_idempotent(
    tmp_path: Path,
) -> None:
    root, run_dir, sources = (
        _make_repo(tmp_path)
    )

    kwargs = dict(
        repo_root=root,
        run_dir=run_dir,
        case_id=CASE_ID,
        case_hash=CASE_HASH,
        case_run_id=CASE_RUN,
        run_id=RUN_ID,
        trial_index=2,
        assessment=_assessment(),
        source_paths=sources,
    )

    first = (
        persist_governed_physics_certificate(
            **kwargs
        )
    )

    second = (
        persist_governed_physics_certificate(
            **kwargs
        )
    )

    assert first == second


def test_recovery_fails_if_artifact_changes(
    tmp_path: Path,
) -> None:
    root, run_dir, sources = (
        _make_repo(tmp_path)
    )

    persist_governed_physics_certificate(
        repo_root=root,
        run_dir=run_dir,
        case_id=CASE_ID,
        case_hash=CASE_HASH,
        case_run_id=CASE_RUN,
        run_id=RUN_ID,
        trial_index=2,
        assessment=_assessment(),
        source_paths=sources,
    )

    (
        run_dir / f"{RUN_ID}.dat"
    ).write_text(
        "changed\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="artifact changed",
    ):
        recover_governed_physics_certificate(
            repo_root=root,
            run_dir=run_dir,
            case_id=CASE_ID,
            case_hash=CASE_HASH,
            case_run_id=CASE_RUN,
            run_id=RUN_ID,
            trial_index=2,
            source_paths=sources,
        )


def test_recovery_fails_if_source_changes(
    tmp_path: Path,
) -> None:
    root, run_dir, sources = (
        _make_repo(tmp_path)
    )

    persist_governed_physics_certificate(
        repo_root=root,
        run_dir=run_dir,
        case_id=CASE_ID,
        case_hash=CASE_HASH,
        case_run_id=CASE_RUN,
        run_id=RUN_ID,
        trial_index=2,
        assessment=_assessment(),
        source_paths=sources,
    )

    (
        root / "source.py"
    ).write_text(
        "VALUE = 2\n",
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="source changed",
    ):
        recover_governed_physics_certificate(
            repo_root=root,
            run_dir=run_dir,
            case_id=CASE_ID,
            case_hash=CASE_HASH,
            case_run_id=CASE_RUN,
            run_id=RUN_ID,
            trial_index=2,
            source_paths=sources,
        )


def test_certificate_refuses_failed_physics(
    tmp_path: Path,
) -> None:
    root, run_dir, sources = (
        _make_repo(tmp_path)
    )

    assessment = _assessment()
    assessment[
        "full_physics_passed"
    ] = False

    with pytest.raises(
        RuntimeError,
        match="did not PASS",
    ):
        persist_governed_physics_certificate(
            repo_root=root,
            run_dir=run_dir,
            case_id=CASE_ID,
            case_hash=CASE_HASH,
            case_run_id=CASE_RUN,
            run_id=RUN_ID,
            trial_index=2,
            assessment=assessment,
            source_paths=sources,
        )

from types import SimpleNamespace

import pytest

import threadrom.factory.adaptive_fem_physics_assessment as bridge
from threadrom.factory.adaptive_fem_physics_assessment import (
    AssessmentDisposition as D,
    assess_extracted_fem_physics,
)


def inputs(*, support_required=True, equilibrium="pass",
           return_code=0, increments=("accepted",)):
    return dict(
        policy=SimpleNamespace(
            require_external_support_equilibrium=support_required,
        ),
        preload_decision=object(),
        evidence=SimpleNamespace(
            thread_normal_force_n=1200.0,
            axial_state=object(),
            deformation_state=object(),
            thread_flank_state=object(),
            accepted_increments=increments,
            return_code=return_code,
            stdout="synthetic completed solver",
        ),
        external_equilibrium_payload=(
            None
            if equilibrium is None
            else {"overall_status": equilibrium}
        ),
    )


def test_existing_evaluator_receives_all_physics_evidence(
    monkeypatch,
):
    calls = []

    def evaluator(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            passed=True,
            policy_id="synthetic-governed-policy",
            failed_checks=(),
        )

    monkeypatch.setattr(
        bridge,
        "evaluate_fem_physics_acceptance",
        evaluator,
    )

    assessment = assess_extracted_fem_physics(**inputs())

    assert len(calls) == 1
    assert calls[0]["thread_normal_force_n"] == 1200.0
    assert calls[0]["require_process_return_code"] is True
    assert calls[0]["external_equilibrium_payload"] == {
        "overall_status": "pass"
    }
    assert assessment.disposition is (
        D.CHECKS_PASSED_PENDING_CERTIFICATION
    )
    assert assessment.full_physics_certified is False


@pytest.mark.parametrize("equilibrium", [None, "fail", "unknown"])
def test_missing_or_failed_equilibrium_is_review_not_pass(
    monkeypatch, equilibrium
):
    captured = []

    def evaluator(**kwargs):
        captured.append(kwargs["external_equilibrium_payload"])
        # Even a future evaluator bug that returns PASS cannot bypass
        # the independent complete-equilibrium guard in the bridge.
        return SimpleNamespace(
            passed=True,
            policy_id="synthetic-governed-policy",
            failed_checks=(),
        )

    monkeypatch.setattr(
        bridge, "evaluate_fem_physics_acceptance", evaluator,
    )
    assessment = assess_extracted_fem_physics(
        **inputs(equilibrium=equilibrium)
    )
    assert len(captured) == 1
    assert assessment.disposition is D.ENGINEERING_REVIEW_REQUIRED
    assert "external support equilibrium" in assessment.failed_governed_checks
    assert not assessment.full_physics_certified


def test_weakened_equilibrium_policy_is_rejected():
    with pytest.raises(
        RuntimeError, match="BLOCKED_PHYSICS_POLICY"
    ):
        assess_extracted_fem_physics(
            **inputs(support_required=False)
        )


@pytest.mark.parametrize(
    "return_code,increments",
    [(1, ("accepted",)), (0, ())],
)
def test_incomplete_solver_evidence_is_rejected(
    return_code, increments
):
    with pytest.raises(
        RuntimeError, match="BLOCKED_SOLVER_EVIDENCE"
    ):
        assess_extracted_fem_physics(
            **inputs(
                return_code=return_code,
                increments=increments,
            )
        )


def test_failed_physics_gate_requires_review(monkeypatch):
    monkeypatch.setattr(
        bridge,
        "evaluate_fem_physics_acceptance",
        lambda **kwargs: SimpleNamespace(
            passed=False,
            policy_id="synthetic-governed-policy",
            failed_checks=(
                SimpleNamespace(name="thread_contact_gate"),
            ),
        ),
    )

    assessment = assess_extracted_fem_physics(**inputs())

    assert assessment.disposition is D.ENGINEERING_REVIEW_REQUIRED
    assert assessment.failed_governed_checks == (
        "thread_contact_gate",
    )
    assert assessment.full_physics_certified is False


def test_verified_run_assessment_uses_existing_extractor(
    tmp_path, monkeypatch
):
    import hashlib
    import json
    from types import SimpleNamespace

    root = tmp_path
    run_id = "synthetic_cal_02"
    run_dir = root / "run"
    run_dir.mkdir()

    paths = {
        role: run_dir / f"{run_id}.{role}"
        for role in ("dat", "frd", "sta", "stdout")
    }

    for role, path in paths.items():
        path.write_text(
            f"synthetic {role}", encoding="ascii"
        )

    manifest = run_dir / "fem_run_manifest.json"
    manifest.write_text(
        json.dumps({
            "artifacts": [
                {
                    "role": role,
                    "relative_path": (
                        path.relative_to(root).as_posix()
                    ),
                    "sha256": hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest(),
                }
                for role, path in paths.items()
            ]
        }),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        bridge,
        "verify_completed_trial",
        lambda **kwargs: SimpleNamespace(
            dat_path=paths["dat"]
        ),
    )

    extracted = SimpleNamespace(
        thread_normal_force_n=1200.0,
        axial_state=object(),
        deformation_state=object(),
        thread_flank_state=object(),
        accepted_increments=("accepted",),
        return_code=0,
        stdout="synthetic",
    )

    calls = []
    monkeypatch.setattr(
        bridge,
        "extract_fem_physics_result_evidence",
        lambda **kwargs: (
            calls.append(kwargs) or extracted
        ),
    )
    monkeypatch.setattr(
        bridge,
        "evaluate_fem_physics_acceptance",
        lambda **kwargs: SimpleNamespace(
            passed=True,
            policy_id="synthetic-policy",
            failed_checks=(),
        ),
    )

    kwargs = dict(
        repo_root=root,
        manifest_path=manifest,
        expected_run_id=run_id,
        expected_case_hash="a" * 64,
        expected_deck_sha256="b" * 64,
        frd_path=paths["frd"],
        sta_path=paths["sta"],
        stdout_path=paths["stdout"],
        mesh_data=object(),
        extraction_policy=object(),
        contact_pairs=(),
        thermal_expansion_coefficient_per_c=1.0e-5,
        equivalent_delta_temperature_c=-273.0,
        physics_policy=SimpleNamespace(
            require_external_support_equilibrium=True
        ),
        preload_decision=object(),
        external_equilibrium_payload={
            "overall_status": "pass"
        },
    )

    assessment = bridge.assess_verified_completed_fem(**kwargs)

    assert len(calls) == 1
    assert calls[0]["dat_path"] == paths["dat"]
    assert assessment.disposition is (
        D.CHECKS_PASSED_PENDING_CERTIFICATION
    )
    assert not assessment.full_physics_certified

    # A changed result artifact must be rejected BEFORE extraction.
    paths["frd"].write_text(
        "altered synthetic frd", encoding="ascii"
    )
    calls.clear()

    with pytest.raises(RuntimeError, match="frd hash drift"):
        bridge.assess_verified_completed_fem(**kwargs)

    assert not calls

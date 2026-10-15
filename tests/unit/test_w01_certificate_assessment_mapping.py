from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

RUNNER = (
    ROOT
    / "scripts"
    / "run_phase3_diversified_w01_adaptive_factory.py"
)


def _assessment_keys() -> set[str]:
    source = RUNNER.read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(
        source,
        filename=str(RUNNER),
    )

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if not any(
            isinstance(
                target,
                ast.Name,
            )
            and target.id == "assessment"
            for target in node.targets
        ):
            continue

        if not isinstance(
            node.value,
            ast.Dict,
        ):
            continue

        return {
            key.value
            for key in node.value.keys
            if (
                isinstance(
                    key,
                    ast.Constant,
                )
                and isinstance(
                    key.value,
                    str,
                )
            )
        }

    raise AssertionError(
        "W01 assessment mapping not found."
    )


def test_w01_assessment_satisfies_certificate_contract():
    keys = _assessment_keys()

    required = {
        "calibration_disposition",
        "next_trial_run_id",
        "calibration_target_force_n",
        "calibration_mean_force_n",
        "calibration_target_error_percent",
        "calibration_spread_percent",
        "result_policy_id",
        "physics_policy_id",
        "equilibrium_status",
        "maximum_translational_resultant_n",
        "translational_force_tolerance_n",
        "accepted_increment_count",
        "thread_normal_force_n",
        "physics_checks",
        "failed_governed_checks",
        "full_physics_passed",
        "rotational_moment_equilibrium_status",
    }

    assert required <= keys


def test_w01_uses_versioned_v2_assessment_record():
    source = RUNNER.read_text(
        encoding="utf-8-sig"
    )

    assert (
        "w01_governed_full_physics_assessment_v2.json"
        in source
    )

    assert (
        '"w01_full_physics_assessment.v2"'
        in source
    )

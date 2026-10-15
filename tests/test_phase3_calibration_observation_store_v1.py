"""Persistent Phase-3 calibration observation store V1 checks."""

from __future__ import annotations

import hashlib
from pathlib import Path

from threadrom.factory.fem_calibration_observation_store import (
    calibration_observations,
    load_calibration_observation_store,
)


ROOT = Path(__file__).resolve().parents[1]

STORE = (
    ROOT
    / "docs"
    / "phase3_calibration_knowledge"
    / "observations_v1.json"
)


def _sha(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def test_governed_backfill_preserves_w01_w02_baseline_and_w03_growth() -> None:
    store = (
        load_calibration_observation_store(
            STORE
        )
    )

    observations = (
        calibration_observations(
            store
        )
    )

    baseline_case_ids = {
        "TRM-DDOE-D-M12x1_75__member_aluminium_en_aw_6082_t6-01",
        "TRM-DDOE-D-M12x1_75__steel_member-12",
        "TRM-DDOE-D-M8x1_25__member_aluminium_en_aw_6082_t6-01",
        "TRM-DDOE-D-M8x1_25__steel_member-12",
        "TRM-DDOE-D-M10x1_5__member_aluminium_en_aw_6082_t6-02",
        "TRM-DDOE-D-M12x1_75__member_aluminium_en_aw_6082_t6-02",
        "TRM-DDOE-D-M12x1_75__steel_member-02",
        "TRM-DDOE-D-M8x1_25__member_aluminium_en_aw_6082_t6-02",
    }

    w03_expected = {
        (
            "TRM-DDOE-D-M10x1_5__member_aluminium_en_aw_6082_t6-03",
            1,
            "accept",
        ),
        (
            "TRM-DDOE-D-M12x1_75__member_aluminium_en_aw_6082_t6-03",
            1,
            "accept",
        ),
        (
            "TRM-DDOE-D-M12x1_75__steel_member-03",
            1,
            "continue",
        ),
        (
            "TRM-DDOE-D-M12x1_75__steel_member-03",
            2,
            "accept",
        ),
        (
            "TRM-DDOE-D-M8x1_25__member_aluminium_en_aw_6082_t6-03",
            1,
            "continue",
        ),
        (
            "TRM-DDOE-D-M8x1_25__member_aluminium_en_aw_6082_t6-03",
            2,
            "accept",
        ),
    }

    baseline = tuple(
        item
        for item in observations
        if item.case_id
        in baseline_case_ids
    )

    assert len(baseline) == 16

    assert {
        item.case_id
        for item in baseline
    } == baseline_case_ids

    assert (
        sum(
            item.decision_disposition
            == "continue"
            for item in baseline
        )
        == 8
    )

    assert (
        sum(
            item.decision_disposition
            == "accept"
            for item in baseline
        )
        == 8
    )

    w03_actual = {
        (
            item.case_id,
            item.trial_index,
            item.decision_disposition,
        )
        for item in observations
        if item.case_id.endswith(
            "-03"
        )
    }

    assert w03_actual == w03_expected

    assert (
        store[
            "source_evidence"
        ][
            "TRM-DDOE-001-W03"
        ][
            "wave_closure_sha256"
        ]
        == (
            "1e5fb74cae994a32f3eead9ae33ebae"
            "56517e29f0e6e3e2379990e54240caa36"
        )
    )

    assert (
        store[
            "source_evidence"
        ][
            "TRM-DDOE-001-W03"
        ][
            "geometry_mesh_atlas_sha256"
        ]
        == (
            "6d026016affecc9151989b7a6b142dc0"
            "dccafa00f79580d9057c15f32787fb4f"
        )
    )

    # Append-only contract:
    # future governed waves may add observations, but they may not remove
    # or rewrite the certified W01/W02 baseline or W03 realized history.
    assert len(observations) >= 22

    assert (
        sum(
            item.decision_disposition
            == "accept"
            for item in observations
        )
        >= 12
    )

    assert (
        sum(
            item.decision_disposition
            == "continue"
            for item in observations
        )
        >= 10
    )


def test_interrupted_w02_attempts_are_not_admitted() -> None:
    store = (
        load_calibration_observation_store(
            STORE
        )
    )

    for observation in calibration_observations(
        store
    ):
        assert (
            "_interrupted_attempt_"
            not in observation.dat_relative_path
        )

        dat_path = (
            ROOT
            / observation.dat_relative_path
        )

        assert dat_path.stat().st_size > 0

        assert (
            hashlib.sha256(
                dat_path.read_bytes()
            ).hexdigest()
            == observation.dat_sha256
        )


def test_store_is_separate_from_rom_dataset_authority() -> None:
    store = (
        load_calibration_observation_store(
            STORE
        )
    )

    assert (
        store[
            "governance"
        ][
            "rom_dataset_admission"
        ]
        is False
    )

    assert (
        store[
            "governance"
        ][
            "holdout_access"
        ]
        is False
    )
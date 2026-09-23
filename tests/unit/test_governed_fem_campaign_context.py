"""Frozen campaign-row checks for governed FEM preparation."""

from types import SimpleNamespace

import pytest

from threadrom.factory.governed_fem_campaign_context import (
    _verify_frozen_design_row,
)


CASE_HASH = "a" * 64


def _case(**changes):
    values = {
        "case_id": "SYNTHETIC-M12",
        "case_hash": CASE_HASH,
        "mesh_policy_name": "medium",
        "source_case_id": None,
    }
    values.update(changes)
    return SimpleNamespace(**values)


def _manifest(**changes):
    row = {
        "case_id": "SYNTHETIC-M12",
        "case_hash": CASE_HASH,
        "mesh_policy_name": "medium",
        "existing_evidence_reuse_planned": False,
    }
    row.update(changes)
    return {"design_cases": [row]}


def test_matching_new_evidence_case_is_accepted():
    row = _verify_frozen_design_row(
        manifest=_manifest(),
        production_case=_case(),
    )
    assert row["case_hash"] == CASE_HASH


def test_case_absent_from_frozen_design_inventory_fails():
    with pytest.raises(RuntimeError, match="exactly one"):
        _verify_frozen_design_row(
            manifest={"design_cases": []},
            production_case=_case(),
        )


def test_duplicate_frozen_case_identity_fails():
    row = _manifest()["design_cases"][0]
    with pytest.raises(RuntimeError, match="exactly one"):
        _verify_frozen_design_row(
            manifest={"design_cases": [row, dict(row)]},
            production_case=_case(),
        )


def test_frozen_case_hash_drift_fails():
    with pytest.raises(RuntimeError, match="case-hash"):
        _verify_frozen_design_row(
            manifest=_manifest(case_hash="b" * 64),
            production_case=_case(),
        )


def test_frozen_mesh_policy_drift_fails():
    with pytest.raises(RuntimeError, match="mesh-policy"):
        _verify_frozen_design_row(
            manifest=_manifest(mesh_policy_name="other"),
            production_case=_case(),
        )


def test_manifest_anchor_reuse_fails():
    with pytest.raises(RuntimeError, match="anchor"):
        _verify_frozen_design_row(
            manifest=_manifest(
                existing_evidence_reuse_planned=True
            ),
            production_case=_case(),
        )


def test_case_source_anchor_reuse_fails():
    with pytest.raises(RuntimeError, match="anchors"):
        _verify_frozen_design_row(
            manifest=_manifest(),
            production_case=_case(
                source_case_id="CERTIFIED-ANCHOR"
            ),
        )

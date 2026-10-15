"""Closure checks for Phase-3 Geometry/Mesh Atlas V1."""

from __future__ import annotations

import hashlib
import json

from pathlib import Path

from threadrom.factory.geometry_mesh_atlas import (
    load_geometry_mesh_atlas,
)


ROOT = Path(__file__).resolve().parents[1]

ATLAS = (
    ROOT
    / "docs"
    / "phase3_geometry_mesh_atlas"
    / "atlas.json"
)

CLOSURE = (
    ROOT
    / "docs"
    / "phase3_geometry_mesh_atlas"
    / "slice1_closure.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256(
        path.read_bytes()
    )

    return digest.hexdigest()


def test_slice1_closure_remains_historical_while_live_atlas_grows() -> None:
    atlas = load_geometry_mesh_atlas(
        ATLAS
    )

    closure = json.loads(
        CLOSURE.read_text(
            encoding="utf-8-sig"
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

    w03_case_ids = {
        "TRM-DDOE-D-M10x1_5__member_aluminium_en_aw_6082_t6-03",
        "TRM-DDOE-D-M12x1_75__member_aluminium_en_aw_6082_t6-03",
        "TRM-DDOE-D-M12x1_75__steel_member-03",
        "TRM-DDOE-D-M8x1_25__member_aluminium_en_aw_6082_t6-03",
    }

    bindings = atlas[
        "case_bindings"
    ]

    assert baseline_case_ids <= set(
        bindings
    )

    assert w03_case_ids <= set(
        bindings
    )

    # Slice-1 is an immutable historical closure of the original
    # eight-binding Atlas.  The live Atlas is intentionally append-only.
    assert (
        closure[
            "overall_disposition"
        ]
        == (
            "SLICE_1_GEOMETRY_MESH_ATLAS_V1_CLOSED"
        )
    )

    assert (
        closure[
            "atlas"
        ][
            "case_binding_count"
        ]
        == 8
    )

    assert (
        closure[
            "atlas"
        ][
            "sha256"
        ]
        == (
            "29b39b7da47bf96410fd4d6af3b6780e"
            "cb25f06047d333aef9076f54c2c84ff4"
        )
    )

    assert (
        _sha256(
            ATLAS
        )
        != closure[
            "atlas"
        ][
            "sha256"
        ]
    )

    # W03 governed append-only evidence must be present and pinned.
    w03_evidence = atlas[
        "source_evidence"
    ][
        "TRM-DDOE-001-W03"
    ]

    assert (
        w03_evidence[
            "preparation_index_sha256"
        ]
        == (
            "813b602392dd66cf0b30e2089b3695c"
            "8e8ae0859946da775bfc1736efd404393"
        )
    )

    assert (
        w03_evidence[
            "wave_closure_sha256"
        ]
        == (
            "1e5fb74cae994a32f3eead9ae33ebae"
            "56517e29f0e6e3e2379990e54240caa36"
        )
    )

    assert (
        len(
            bindings
        )
        >= 12
    )

    assert (
        len(
            atlas[
                "geometries"
            ]
        )
        >= 12
    )

    assert (
        len(
            atlas[
                "meshes"
            ]
        )
        >= 12
    )

    assert (
        closure[
            "governance"
        ][
            "new_geometry_generated"
        ]
        is False
    )

    assert (
        closure[
            "governance"
        ][
            "new_mesh_generated"
        ]
        is False
    )

    assert (
        closure[
            "governance"
        ][
            "fem_executed"
        ]
        is False
    )

    assert (
        closure[
            "governance"
        ][
            "holdouts_accessed"
        ]
        is False
    )


def test_every_case_binding_resolves_to_registered_assets() -> None:
    atlas = load_geometry_mesh_atlas(
        ATLAS
    )

    for case_id, binding in atlas[
        "case_bindings"
    ].items():

        geometry = atlas[
            "geometries"
        ][
            binding[
                "geometry_id"
            ]
        ]

        mesh = atlas[
            "meshes"
        ][
            binding[
                "mesh_id"
            ]
        ]

        assert (
            geometry[
                "identity_sha256"
            ]
            == binding[
                "geometry_identity_sha256"
            ]
        )

        assert (
            mesh[
                "identity_sha256"
            ]
            == binding[
                "mesh_identity_sha256"
            ]
        )

        assert (
            mesh[
                "geometry_id"
            ]
            == binding[
                "geometry_id"
            ]
        )

        assert case_id in geometry[
            "source_case_ids"
        ]

        assert case_id in mesh[
            "source_case_ids"
        ]
from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(r"D:\ThreadROM")

V2 = (
    ROOT
    / "scripts"
    / "prepare_phase3_da08_fine_reference_decks_v2.py"
)

V3 = (
    ROOT
    / "scripts"
    / "prepare_phase3_da08_fine_reference_decks_v3.py"
)

EXPECTED_V2_SHA256 = (
    "06746c7efc40fbb6e29dd2f5788b3054f3f3713380b330b203baa57eda778c6f"
)


def sha256(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


if sha256(V2) != EXPECTED_V2_SHA256:

    raise RuntimeError(
        "Pinned V2 source SHA drift."
    )


if V3.exists():

    raise RuntimeError(
        "V3 already exists; refusing overwrite."
    )


text = V2.read_text(
    encoding="utf-8"
)


# ================================================================================================
# REMOVE THE INCORRECT GUIDANCE-BUILDER CALL.
#
# FemGuidanceGeometry already belongs to FemCaseDefinitionBundle.
# fem_guidance.resolve_fem_distributed_guidance_policy() consumes that
# geometry later inside the production writer; it does NOT create it.
# ================================================================================================

old_call = '''        (
            guidance_builder_name,
            guidance_geometry,
        ) = (
            resolve_guidance_geometry(
                mesh_data=(
                    mesh_data
                ),
                transfer=(
                    fine_transfer
                ),
                resolved=(
                    resolved
                ),
                bundle=(
                    bundle
                ),
                backend=(
                    fine_backend
                ),
            )
        )


'''


new_call = '''        # -----------------------------------------------------------------------------------------
        # GOVERNED GUIDANCE GEOMETRY
        #
        # FemGuidanceGeometry is already a case-specific component of
        # FemCaseDefinitionBundle. The production renderer itself later
        # resolves mesh-relative DistributedGuidancePolicy from:
        #
        #   mesh_data
        #   backend.guidance_policy
        #   guidance_geometry.nominal_thread_diameter_mm
        #
        # Therefore no secondary geometry builder is allowed here.
        # -----------------------------------------------------------------------------------------

        guidance_geometry = (
            bundle
            .guidance_geometry
        )


        if (
            guidance_geometry is None
            or guidance_geometry
            .__class__
            .__name__
            != "FemGuidanceGeometry"
        ):

            raise RuntimeError(
                f"{case_id}: generic FEM bundle "
                "does not expose governed "
                "FemGuidanceGeometry."
            )


        nominal_guidance_diameter = float(
            guidance_geometry
            .nominal_thread_diameter_mm
        )


        if (
            not math.isfinite(
                nominal_guidance_diameter
            )
            or nominal_guidance_diameter
            <= 0.0
        ):

            raise RuntimeError(
                f"{case_id}: governed guidance "
                "nominal thread diameter is invalid."
            )


'''


count = text.count(
    old_call
)


if count != 1:

    raise RuntimeError(
        "Expected exactly one V2 guidance-builder "
        f"call seam; found {count}."
    )


text = text.replace(
    old_call,
    new_call,
    1,
)


# ================================================================================================
# REPLACE THE PER-CASE CERTIFICATE DESCRIPTION.
# ================================================================================================

old_record = '''                "guidance_builder":
                    (
                        f"{fem_guidance_mod.__name__}."
                        f"{guidance_builder_name}"
                    ),

                "semantic_mode":
'''


new_record = '''                "guidance_source":
                    (
                        "FemCaseDefinitionBundle."
                        "guidance_geometry"
                    ),

                "semantic_mode":
'''


count = text.count(
    old_record
)


if count != 1:

    raise RuntimeError(
        "Expected exactly one guidance-builder "
        f"certificate seam; found {count}."
    )


text = text.replace(
    old_record,
    new_record,
    1,
)


# ================================================================================================
# WRITE V3 ONLY.
# ================================================================================================

V3.write_text(
    text,
    encoding="utf-8",
    newline="\n",
)


print(
    "PASS: V2 SHA pinned."
)

print(
    "PASS: V2 left untouched."
)

print(
    "PASS: incorrect guidance-builder "
    "dependency removed."
)

print(
    "PASS: bundle.guidance_geometry "
    "bound directly."
)

print(
    "V3    :",
    V3,
)

print(
    "SHA256:",
    sha256(
        V3
    ),
)

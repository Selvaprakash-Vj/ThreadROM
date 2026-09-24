"""Phase-3 candidate material catalog; NOT a FEM certification.

This module leaves the certified Phase-2 baseline catalog unchanged.
A candidate material requires independent case-level FEM qualification
and physical acceptance before DOE execution or dataset admission.
"""

from threadrom.materials.baseline_catalog import (
    BASELINE_MATERIAL_CATALOG,
)
from threadrom.materials.catalog import MaterialCatalog
from threadrom.materials.models import MaterialFamily


MEMBER_ALUMINIUM_EN_AW_6082_T6 = MaterialFamily(
    material_id="member_aluminium_en_aw_6082_t6",
    display_name="EN AW-6082-T6 aluminium clamped member",
    youngs_modulus_mpa=70000.0,
    poissons_ratio=0.33,
    elastic_source_reference=(
        "https://www.euralliage.com/6082_english.htm"
        " | 6082, T6, elastic/physical properties table: "
        "E=70000 MPa; Poisson ratio=0.33; "
        "source reviewed 2026-09-24."
    ),
    # This first candidate is limited to static linear-elastic
    # material definition. Do not infer strength, density or thermal
    # properties from its material name.
)


DIVERSIFIED_CANDIDATE_MATERIAL_CATALOG = MaterialCatalog(
    catalog_id="threadrom_phase3_diversified_candidate_v1",
    material_families=(
        *BASELINE_MATERIAL_CATALOG.material_families,
        MEMBER_ALUMINIUM_EN_AW_6082_T6,
    ),
    fastener_property_classes=(
        BASELINE_MATERIAL_CATALOG.fastener_property_classes
    ),
)

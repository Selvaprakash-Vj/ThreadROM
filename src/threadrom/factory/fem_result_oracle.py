"""Structured result oracle for certified FEM reproduction."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class CertifiedClampForceOracle:
    """Certified Phase-2 clamp-force resultants."""

    target_force_n: float
    under_head_force_n: float
    nut_bearing_force_n: float
    member_interface_force_n: float
    thread_normal_force_n: float

    @property
    def mean_force_n(self) -> float:
        return (
            self.under_head_force_n
            + self.nut_bearing_force_n
            + self.member_interface_force_n
        ) / 3.0

    @property
    def spread_n(self) -> float:
        values = (
            self.under_head_force_n,
            self.nut_bearing_force_n,
            self.member_interface_force_n,
        )
        return max(values) - min(values)

    @property
    def target_relative_error(self) -> float:
        return (
            self.mean_force_n
            - self.target_force_n
        ) / self.target_force_n

    @property
    def spread_relative(self) -> float:
        return (
            self.spread_n
            / self.mean_force_n
        )


@dataclass(frozen=True, slots=True)
class CertifiedAxialStressOracle:
    """Certified representative axial-stress state."""

    bolt_mean_szz_mpa: float
    bolt_median_szz_mpa: float
    head_member_mean_szz_mpa: float
    nut_member_mean_szz_mpa: float
    bolt_selected_tetrahedra: int
    head_member_tetrahedra: int
    nut_member_tetrahedra: int


@dataclass(frozen=True, slots=True)
class CertifiedDeformationOracle:
    """Certified representative deformation state."""

    member_shortening_mm: float
    analytical_member_shortening_mm: float
    bolt_mechanical_extension_mm: float

    @property
    def member_shortening_ratio(self) -> float:
        return (
            self.member_shortening_mm
            / self.analytical_member_shortening_mm
        )


@dataclass(frozen=True, slots=True)
class CertifiedThreadFlankOracle:
    """Certified solid-STRESS thread-flank directionality state."""

    intended_flank_name: str
    engagement_min_z_mm: float
    engagement_max_z_mm: float
    engaged_triangle_count: int

    positive_triangle_count: int
    positive_mean_compression_mpa: float
    positive_median_compression_mpa: float
    positive_compressed_area_percent: float

    negative_triangle_count: int
    negative_mean_compression_mpa: float
    negative_median_compression_mpa: float
    negative_compressed_area_percent: float

    dominance_ratio: float


@dataclass(frozen=True, slots=True)
class CertifiedNumericalOracle:
    """Certified nonlinear numerical signature."""

    accepted_increment_count: int
    final_step: int
    final_increment: int
    final_attempt: int
    final_iterations: int
    final_time: float


@dataclass(frozen=True, slots=True)
class FemCertifiedResultOracle:
    """Immutable numerical/physical outputs of the Phase-2 reference."""

    clamp_force: CertifiedClampForceOracle
    axial_stress: CertifiedAxialStressOracle
    deformation: CertifiedDeformationOracle
    thread_flank: CertifiedThreadFlankOracle
    numerical: CertifiedNumericalOracle


def _finite(
    name: str,
    value: object,
) -> float:
    number = float(
        value
    )

    if not math.isfinite(
        number
    ):
        raise ValueError(
            f"{name} must be finite."
        )

    return number


def _positive(
    name: str,
    value: object,
) -> float:
    number = _finite(
        name,
        value,
    )

    if number <= 0.0:
        raise ValueError(
            f"{name} must be positive."
        )

    return number


def _positive_int(
    name: str,
    value: object,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value <= 0
    ):
        raise ValueError(
            f"{name} must be a positive integer."
        )

    return value


def load_fem_certified_result_oracle(
    path: Path,
) -> FemCertifiedResultOracle:
    """Load and validate the structured certified result oracle."""

    with path.open(
        "rb"
    ) as stream:
        raw = tomllib.load(
            stream
        )

    clamp_raw = raw[
        "clamp_force"
    ]

    axial_raw = raw[
        "axial_stress"
    ]

    deformation_raw = raw[
        "deformation"
    ]

    flank_raw = raw[
        "thread_flank"
    ]

    numerical_raw = raw[
        "numerical"
    ]

    clamp = CertifiedClampForceOracle(
        target_force_n=_positive(
            "clamp_force.target_force_n",
            clamp_raw["target_force_n"],
        ),
        under_head_force_n=_positive(
            "clamp_force.under_head_force_n",
            clamp_raw["under_head_force_n"],
        ),
        nut_bearing_force_n=_positive(
            "clamp_force.nut_bearing_force_n",
            clamp_raw["nut_bearing_force_n"],
        ),
        member_interface_force_n=_positive(
            "clamp_force.member_interface_force_n",
            clamp_raw["member_interface_force_n"],
        ),
        thread_normal_force_n=_positive(
            "clamp_force.thread_normal_force_n",
            clamp_raw["thread_normal_force_n"],
        ),
    )

    axial = CertifiedAxialStressOracle(
        bolt_mean_szz_mpa=_positive(
            "axial_stress.bolt_mean_szz_mpa",
            axial_raw["bolt_mean_szz_mpa"],
        ),
        bolt_median_szz_mpa=_positive(
            "axial_stress.bolt_median_szz_mpa",
            axial_raw["bolt_median_szz_mpa"],
        ),
        head_member_mean_szz_mpa=_finite(
            "axial_stress.head_member_mean_szz_mpa",
            axial_raw["head_member_mean_szz_mpa"],
        ),
        nut_member_mean_szz_mpa=_finite(
            "axial_stress.nut_member_mean_szz_mpa",
            axial_raw["nut_member_mean_szz_mpa"],
        ),
        bolt_selected_tetrahedra=_positive_int(
            "axial_stress.bolt_selected_tetrahedra",
            axial_raw["bolt_selected_tetrahedra"],
        ),
        head_member_tetrahedra=_positive_int(
            "axial_stress.head_member_tetrahedra",
            axial_raw["head_member_tetrahedra"],
        ),
        nut_member_tetrahedra=_positive_int(
            "axial_stress.nut_member_tetrahedra",
            axial_raw["nut_member_tetrahedra"],
        ),
    )

    if axial.head_member_mean_szz_mpa >= 0.0:
        raise ValueError(
            "Certified head-member SZZ must be compressive."
        )

    if axial.nut_member_mean_szz_mpa >= 0.0:
        raise ValueError(
            "Certified nut-member SZZ must be compressive."
        )

    deformation = CertifiedDeformationOracle(
        member_shortening_mm=_positive(
            "deformation.member_shortening_mm",
            deformation_raw["member_shortening_mm"],
        ),
        analytical_member_shortening_mm=_positive(
            "deformation.analytical_member_shortening_mm",
            deformation_raw[
                "analytical_member_shortening_mm"
            ],
        ),
        bolt_mechanical_extension_mm=_positive(
            "deformation.bolt_mechanical_extension_mm",
            deformation_raw[
                "bolt_mechanical_extension_mm"
            ],
        ),
    )

    intended_flank_name = str(
        flank_raw[
            "intended_flank_name"
        ]
    )

    if intended_flank_name not in (
        "+Z-normal flank",
        "-Z-normal flank",
    ):
        raise ValueError(
            "thread_flank.intended_flank_name must identify "
            "one axial-normal flank family."
        )

    engagement_min_z = _finite(
        "thread_flank.engagement_min_z_mm",
        flank_raw[
            "engagement_min_z_mm"
        ],
    )

    engagement_max_z = _finite(
        "thread_flank.engagement_max_z_mm",
        flank_raw[
            "engagement_max_z_mm"
        ],
    )

    if engagement_max_z <= engagement_min_z:
        raise ValueError(
            "Certified thread engagement span must be positive."
        )

    flank = CertifiedThreadFlankOracle(
        intended_flank_name=intended_flank_name,
        engagement_min_z_mm=engagement_min_z,
        engagement_max_z_mm=engagement_max_z,
        engaged_triangle_count=_positive_int(
            "thread_flank.engaged_triangle_count",
            flank_raw[
                "engaged_triangle_count"
            ],
        ),
        positive_triangle_count=_positive_int(
            "thread_flank.positive_triangle_count",
            flank_raw[
                "positive_triangle_count"
            ],
        ),
        positive_mean_compression_mpa=_finite(
            "thread_flank.positive_mean_compression_mpa",
            flank_raw[
                "positive_mean_compression_mpa"
            ],
        ),
        positive_median_compression_mpa=_finite(
            "thread_flank.positive_median_compression_mpa",
            flank_raw[
                "positive_median_compression_mpa"
            ],
        ),
        positive_compressed_area_percent=_finite(
            "thread_flank.positive_compressed_area_percent",
            flank_raw[
                "positive_compressed_area_percent"
            ],
        ),
        negative_triangle_count=_positive_int(
            "thread_flank.negative_triangle_count",
            flank_raw[
                "negative_triangle_count"
            ],
        ),
        negative_mean_compression_mpa=_finite(
            "thread_flank.negative_mean_compression_mpa",
            flank_raw[
                "negative_mean_compression_mpa"
            ],
        ),
        negative_median_compression_mpa=_finite(
            "thread_flank.negative_median_compression_mpa",
            flank_raw[
                "negative_median_compression_mpa"
            ],
        ),
        negative_compressed_area_percent=_finite(
            "thread_flank.negative_compressed_area_percent",
            flank_raw[
                "negative_compressed_area_percent"
            ],
        ),
        dominance_ratio=_positive(
            "thread_flank.dominance_ratio",
            flank_raw[
                "dominance_ratio"
            ],
        ),
    )

    for name, value in (
        (
            "positive_compressed_area_percent",
            flank.positive_compressed_area_percent,
        ),
        (
            "negative_compressed_area_percent",
            flank.negative_compressed_area_percent,
        ),
    ):
        if not 0.0 <= value <= 100.0:
            raise ValueError(
                f"thread_flank.{name} must be in [0, 100]."
            )

    numerical = CertifiedNumericalOracle(
        accepted_increment_count=_positive_int(
            "numerical.accepted_increment_count",
            numerical_raw[
                "accepted_increment_count"
            ],
        ),
        final_step=_positive_int(
            "numerical.final_step",
            numerical_raw[
                "final_step"
            ],
        ),
        final_increment=_positive_int(
            "numerical.final_increment",
            numerical_raw[
                "final_increment"
            ],
        ),
        final_attempt=_positive_int(
            "numerical.final_attempt",
            numerical_raw[
                "final_attempt"
            ],
        ),
        final_iterations=_positive_int(
            "numerical.final_iterations",
            numerical_raw[
                "final_iterations"
            ],
        ),
        final_time=_positive(
            "numerical.final_time",
            numerical_raw[
                "final_time"
            ],
        ),
    )

    return FemCertifiedResultOracle(
        clamp_force=clamp,
        axial_stress=axial,
        deformation=deformation,
        thread_flank=flank,
        numerical=numerical,
    )

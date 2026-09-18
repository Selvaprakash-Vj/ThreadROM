from __future__ import annotations

from dataclasses import dataclass, replace

from threadrom.factory.production_doe_equilibrium_applicability import (
    ProductionDoeEquilibriumApplicability,
    classify_production_doe_equilibrium_applicability,
)


REACTION_OBSERVABLE_REVISION_TAG = "rfobs1"


@dataclass(frozen=True)
class ReactionObservableRevisionIdentity:
    """Identity for an output-contract-only Trial-1 sibling."""

    case_run_id: str
    source_trial_run_id: str
    revision_trial_run_id: str
    trial_index: int
    revision_tag: str


@dataclass(frozen=True)
class NamedReactionObservability:
    """Certified named reaction-output coverage for one deck."""

    constrained_reaction_sets: tuple[str, ...]
    observable_reaction_sets: tuple[str, ...]
    missing_reaction_sets: tuple[str, ...]
    fully_observable: bool


def _normalize_names(
    values: tuple[str, ...],
) -> tuple[str, ...]:
    normalized = tuple(
        sorted(
            {
                value.strip().upper()
                for value in values
                if value.strip()
            }
        )
    )

    return normalized


def bridge_bundle_to_frozen_production_doe_identity(
    *,
    bundle,
    case_hash: str,
    resolution_hash: str,
    frozen_case_run_id: str,
):
    """Rebind only execution identity to the frozen DOE lineage.

    This compatibility bridge is intentionally scoped to the frozen
    Production-DOE campaign created before FEM execution identity moved
    from case-hash-derived IDs to resolution-hash-derived IDs.

    Physical inputs, resolution provenance, mesh/contact/boundary
    definitions and calibration policy remain unchanged.
    """

    expected_frozen = (
        "trm_fem_"
        + case_hash[:12]
    )

    expected_current = (
        "trm_fem_"
        + resolution_hash[:12]
    )

    if (
        frozen_case_run_id
        != expected_frozen
    ):
        raise ValueError(
            "Frozen Production-DOE case run ID does not "
            "match the governed case hash."
        )

    identity = (
        bundle
        .preparation
        .identity
    )

    if (
        identity.case_hash
        != case_hash
    ):
        raise ValueError(
            "Bundle case hash does not match the frozen "
            "Production-DOE case."
        )

    if (
        identity.resolution_hash
        != resolution_hash
    ):
        raise ValueError(
            "Bundle resolution hash does not match the "
            "current resolved execution identity."
        )

    if (
        identity.run_id
        != expected_current
        or identity.job_name
        != expected_current
    ):
        raise ValueError(
            "Bundle does not carry the expected current "
            "resolution-hash execution identity."
        )

    if (
        expected_current
        == expected_frozen
    ):
        raise ValueError(
            "Frozen-lineage compatibility bridge is not "
            "required when identities already match."
        )

    if (
        bundle.transfer.simulation_id
        != expected_current
        or bundle.transfer.job_name
        != expected_current
    ):
        raise ValueError(
            "Transfer identity is not synchronized with "
            "the current FEM preparation identity."
        )

    if (
        bundle.contact.simulation_id
        != expected_current
        or bundle.contact.solver_job_name
        != expected_current
    ):
        raise ValueError(
            "Contact identity is not synchronized with "
            "the current FEM preparation identity."
        )

    if (
        bundle.boundary.simulation_id
        != expected_current
    ):
        raise ValueError(
            "Boundary identity is not synchronized with "
            "the current FEM preparation identity."
        )

    bridged_identity = replace(
        identity,
        run_id=(
            frozen_case_run_id
        ),
        job_name=(
            frozen_case_run_id
        ),
    )

    bridged_preparation = replace(
        bundle.preparation,
        identity=(
            bridged_identity
        ),
    )

    bridged_transfer = replace(
        bundle.transfer,
        simulation_id=(
            frozen_case_run_id
        ),
        job_name=(
            frozen_case_run_id
        ),
    )

    bridged_contact = replace(
        bundle.contact,
        simulation_id=(
            frozen_case_run_id
        ),
        solver_job_name=(
            frozen_case_run_id
        ),
    )

    bridged_boundary = replace(
        bundle.boundary,
        simulation_id=(
            frozen_case_run_id
        ),
    )

    bridged = replace(
        bundle,
        preparation=(
            bridged_preparation
        ),
        transfer=(
            bridged_transfer
        ),
        contact=(
            bridged_contact
        ),
        boundary=(
            bridged_boundary
        ),
    )

    if (
        bridged
        .preparation
        .identity
        .case_hash
        != case_hash
        or bridged
        .preparation
        .identity
        .resolution_hash
        != resolution_hash
    ):
        raise RuntimeError(
            "Frozen-lineage bridge altered governed "
            "case/resolution provenance."
        )

    return bridged



def derive_reaction_observable_revision_identity(
    *,
    case_run_id: str,
) -> ReactionObservableRevisionIdentity:
    """Derive a fresh sibling without inventing a calibration attempt."""

    normalized = case_run_id.strip()

    if not normalized:
        raise ValueError(
            "Case run ID must not be blank."
        )

    if not normalized.startswith(
        "trm_fem_"
    ):
        raise ValueError(
            "Case run ID must use the governed "
            "'trm_fem_' prefix."
        )

    if any(
        character.isspace()
        for character in normalized
    ):
        raise ValueError(
            "Case run ID must not contain whitespace."
        )

    source_trial_run_id = (
        f"{normalized}_cal_01_wsv21"
    )

    revision_trial_run_id = (
        f"{source_trial_run_id}_"
        f"{REACTION_OBSERVABLE_REVISION_TAG}"
    )

    return ReactionObservableRevisionIdentity(
        case_run_id=normalized,
        source_trial_run_id=source_trial_run_id,
        revision_trial_run_id=revision_trial_run_id,
        trial_index=1,
        revision_tag=(
            REACTION_OBSERVABLE_REVISION_TAG
        ),
    )


def certify_named_reaction_observability(
    *,
    constrained_reaction_sets: tuple[str, ...],
    observable_reaction_sets: tuple[str, ...],
) -> NamedReactionObservability:
    """Require explicit reaction output for every constrained carrier."""

    constrained = _normalize_names(
        constrained_reaction_sets
    )

    observable = _normalize_names(
        observable_reaction_sets
    )

    if not constrained:
        raise ValueError(
            "At least one constrained reaction set "
            "is required."
        )

    applicability = (
        classify_production_doe_equilibrium_applicability(
            constrained_reaction_sets=constrained,
            reaction_observable_sets=observable,
        )
    )

    missing = tuple(
        applicability.missing_reaction_sets
    )

    fully_observable = (
        applicability.applicability
        is ProductionDoeEquilibriumApplicability.FULL_SYSTEM_OBSERVABLE
    )

    if not fully_observable:
        raise ValueError(
            "Named constrained reaction system is "
            "not fully observable; missing: "
            + ", ".join(missing)
        )

    if applicability.full_system_pass_claimed:
        raise RuntimeError(
            "Output observability must never manufacture "
            "an equilibrium PASS."
        )

    if applicability.tolerance_changed:
        raise RuntimeError(
            "Output observability must not change "
            "equilibrium tolerance."
        )

    if (
        applicability
        .additional_fem_authorized_by_classifier
    ):
        raise RuntimeError(
            "Observability classification must not "
            "authorize FEM execution."
        )

    return NamedReactionObservability(
        constrained_reaction_sets=constrained,
        observable_reaction_sets=observable,
        missing_reaction_sets=missing,
        fully_observable=True,
    )

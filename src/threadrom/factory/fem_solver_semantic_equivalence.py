"""Solver-semantic equivalence for governed FEM result reuse."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FemSolverSemanticEquivalenceResult:
    """Comparison of the operative CalculiX content of two decks."""

    left_path: Path
    right_path: Path
    left_semantic_sha256: str
    right_semantic_sha256: str
    left_line_count: int
    right_line_count: int
    equivalent: bool


def canonicalize_calculix_solver_text(
    text: str,
    *,
    symbol_aliases: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Return operative CalculiX lines with comments/aliases normalized.

    CalculiX comments and blank lines do not alter solver physics.
    Symbol aliases allow two governed writers to use different names
    for the same explicitly established semantic set.
    """

    aliases = {
        source.casefold(): target.casefold()
        for source, target in (
            symbol_aliases or {}
        ).items()
    }

    ordered_aliases = tuple(
        sorted(
            aliases.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )
    )

    lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("**"):
            continue

        line = line.casefold()

        for source, target in ordered_aliases:
            line = line.replace(
                source,
                target,
            )

        lines.append(line)

    return tuple(lines)


def _semantic_sha256(
    lines: tuple[str, ...],
) -> str:
    return hashlib.sha256(
        "\n".join(lines).encode("utf-8")
    ).hexdigest()


def compare_calculix_solver_decks(
    *,
    left_path: Path,
    right_path: Path,
    symbol_aliases: Mapping[str, str] | None = None,
) -> FemSolverSemanticEquivalenceResult:
    """Prove whether two CalculiX decks encode identical solver input."""

    for path in (
        left_path,
        right_path,
    ):
        if not path.exists():
            raise FileNotFoundError(
                f"CalculiX deck does not exist: {path}"
            )

        if path.stat().st_size <= 0:
            raise ValueError(
                f"CalculiX deck is empty: {path}"
            )

    left = canonicalize_calculix_solver_text(
        left_path.read_text(
            encoding="utf-8",
            errors="strict",
        ),
        symbol_aliases=symbol_aliases,
    )

    right = canonicalize_calculix_solver_text(
        right_path.read_text(
            encoding="utf-8",
            errors="strict",
        ),
        symbol_aliases=symbol_aliases,
    )

    left_hash = _semantic_sha256(left)
    right_hash = _semantic_sha256(right)

    return FemSolverSemanticEquivalenceResult(
        left_path=left_path,
        right_path=right_path,
        left_semantic_sha256=left_hash,
        right_semantic_sha256=right_hash,
        left_line_count=len(left),
        right_line_count=len(right),
        equivalent=(
            left == right
            and left_hash == right_hash
        ),
    )

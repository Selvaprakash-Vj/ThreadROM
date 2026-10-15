"""Runtime hardening boundary for the generic governed wave runner.

This module exists specifically to make the production execution entry
safe on Windows and under redirected logging.

It does not:
- create execution authority,
- change a wave contract,
- recover stale jobs,
- certify physics,
- close a wave,
- admit ROM data.

The execution engine remains the Slice-3 generic governed wave runner.
"""

from __future__ import annotations

import sys

from pathlib import Path
from typing import Any

from threadrom.factory.governed_wave_runner import (
    build_governed_wave_runner,
)


def configure_utf8_stream(
    stream,
) -> None:
    """Make one text stream Unicode-safe or fail closed."""

    reconfigure = getattr(
        stream,
        "reconfigure",
        None,
    )

    if callable(
        reconfigure
    ):
        reconfigure(
            encoding="utf-8",
            errors="backslashreplace",
        )
        return

    encoding = (
        getattr(
            stream,
            "encoding",
            None,
        )
        or ""
    ).lower().replace(
        "_",
        "-",
    )

    if encoding not in {
        "utf-8",
        "utf8",
    }:
        raise RuntimeError(
            "Text stream cannot be proven UTF-8 safe."
        )


def configure_process_stdio(
    *,
    stdout=None,
    stderr=None,
) -> None:
    """Install the Unicode-safe production console boundary."""

    if stdout is None:
        stdout = sys.stdout

    if stderr is None:
        stderr = sys.stderr

    configure_utf8_stream(
        stdout
    )

    configure_utf8_stream(
        stderr
    )


def normalize_runner_status(
    value: Any,
) -> int:
    if value is None:
        return 0

    if (
        type(
            value
        )
        is not int
    ):
        raise RuntimeError(
            "Governed wave runner returned "
            "an invalid process status."
        )

    return value


def run_governed_wave_entrypoint(
    *,
    repository_root: Path,
    contract,
    execute: bool = False,
    stdout=None,
    stderr=None,
) -> int:
    """Run preflight or one explicitly authorized generic campaign.

    execute=False is always the default. Merely constructing a contract
    or calling this entrypoint never grants execution authority.
    """

    if type(
        execute
    ) is not bool:
        raise TypeError(
            "execute must be bool."
        )

    root = Path(
        repository_root
    ).resolve(
        strict=True
    )

    configure_process_stdio(
        stdout=stdout,
        stderr=stderr,
    )

    runner = build_governed_wave_runner(
        repository_root=root,
        contract=contract,
    )

    if execute:
        result = runner.execute()
    else:
        result = runner.preflight()

    return normalize_runner_status(
        result
    )
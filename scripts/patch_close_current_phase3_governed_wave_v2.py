from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(r"D:\ThreadROM")

V1 = (
    ROOT
    / "scripts"
    / "close_current_phase3_governed_wave_v1.py"
)

V2 = (
    ROOT
    / "scripts"
    / "close_current_phase3_governed_wave_v2.py"
)

EXPECTED_V1_SHA = (
    "320949926e94a0e34974e038d26bb0f0b59b4a1dbdeaee01599fe455fe34e72c"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


if sha256(V1) != EXPECTED_V1_SHA:
    raise RuntimeError(
        "Pinned closer V1 SHA drift."
    )

if V2.exists():
    raise RuntimeError(
        "Closer V2 already exists."
    )


text = V1.read_text(
    encoding="utf-8-sig"
)


old = '''database_path = (
    contract.factory_database_path
)


if not database_path.is_file():
'''


new = '''# --------------------------------------------------------------------------------------------------------------
# Materialize the contract's platform-neutral PurePosixPath only at the
# filesystem I/O boundary.
# --------------------------------------------------------------------------------------------------------------

database_locator = (
    contract.factory_database_path
)


if database_locator.is_absolute():

    raise RuntimeError(
        "Governed factory database locator "
        "must remain repository-relative."
    )


database_path = (
    ROOT.joinpath(
        *database_locator.parts
    ).resolve()
)


try:

    database_path.relative_to(
        ROOT
    )

except ValueError as exc:

    raise RuntimeError(
        "Governed factory database escaped "
        "repository root."
    ) from exc


if not database_path.is_file():
'''


count = text.count(
    old
)

if count != 1:
    raise RuntimeError(
        "Expected exactly one factory-database "
        f"path-materialization seam; found {count}."
    )


text = text.replace(
    old,
    new,
    1,
)


V2.write_text(
    text,
    encoding="utf-8",
    newline="\n",
)


print(
    "PASS: closer V1 pinned and preserved."
)

print(
    "PASS: PurePosixPath -> Windows Path "
    "materialization installed."
)

print(
    "V2    :",
    V2,
)

print(
    "SHA256:",
    sha256(
        V2
    ),
)

from __future__ import annotations

import ast
import hashlib
import textwrap

from pathlib import Path


ROOT = Path(r"D:\ThreadROM").resolve()

SOURCE = (
    ROOT
    / "src"
    / "threadrom"
    / "factory"
    / "governed_wave_runner.py"
)

BACKUP = SOURCE.with_suffix(
    ".py.pre_initial_trial_handoff_v1"
)

EXPECTED_SHA = (
    "c7e7c6ab3c15e9a2047b2a0fe767cd"
    "1412d34bbddf735362d66934d5d4e837df"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as stream:
        for chunk in iter(
            lambda: stream.read(8 * 1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def line_offsets(text: str) -> list[int]:
    result = [0]
    position = 0

    for line in text.splitlines(keepends=True):
        position += len(line)
        result.append(position)

    return result


def absolute_span(
    node: ast.AST,
    offsets: list[int],
) -> tuple[int, int]:

    start = (
        offsets[node.lineno - 1]
        + node.col_offset
    )

    end = (
        offsets[node.end_lineno - 1]
        + node.end_col_offset
    )

    return start, end


def function_nodes(
    tree: ast.AST,
    name: str,
) -> list[ast.FunctionDef]:

    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
        and node.name == name
    ]


def is_trial_index_ge_2(
    node: ast.AST,
) -> bool:

    if not isinstance(node, ast.Compare):
        return False

    if (
        len(node.ops) != 1
        or not isinstance(
            node.ops[0],
            ast.GtE,
        )
        or len(node.comparators) != 1
    ):
        return False

    right = node.comparators[0]

    if (
        not isinstance(right, ast.Constant)
        or right.value != 2
    ):
        return False

    left = node.left

    return (
        isinstance(left, ast.Attribute)
        and left.attr == "trial_index"
        and isinstance(left.value, ast.Name)
        and left.value.id == "trial"
    )


def compare_nodes(
    function: ast.FunctionDef,
) -> list[ast.Compare]:

    return [
        node
        for node in ast.walk(function)
        if is_trial_index_ge_2(node)
    ]


source = SOURCE.read_text(
    encoding="utf-8"
)

require(
    sha256(SOURCE) == EXPECTED_SHA,
    "Runner source SHA does not match frozen Slice-3 runner.",
)

tree = ast.parse(source)
offsets = line_offsets(source)


prepare_nodes = function_nodes(
    tree,
    "prepare_governed_trial",
)

register_nodes = function_nodes(
    tree,
    "register_prepared_trial",
)

preflight_nodes = function_nodes(
    tree,
    "preflight",
)

execute_nodes = function_nodes(
    tree,
    "execute",
)


require(
    len(prepare_nodes) == 1,
    f"Expected one nested prepare_governed_trial; found {len(prepare_nodes)}.",
)

require(
    len(register_nodes) == 1,
    f"Expected one nested register_prepared_trial; found {len(register_nodes)}.",
)

# There is one internal campaign preflight/execute plus the public class
# wrappers. Select the large nested campaign functions by source length.
preflight = max(
    preflight_nodes,
    key=lambda node: (
        node.end_lineno - node.lineno
    ),
)

execute = max(
    execute_nodes,
    key=lambda node: (
        node.end_lineno - node.lineno
    ),
)

prepare = prepare_nodes[0]
register = register_nodes[0]


prepare_guards = compare_nodes(prepare)
preflight_guards = compare_nodes(preflight)
execute_guards = compare_nodes(execute)


require(
    len(prepare_guards) == 1,
    "Expected exactly one CAL_02+ guard in prepare_governed_trial.",
)

require(
    len(preflight_guards) == 1,
    "Expected exactly one CAL_01 refusal guard in campaign preflight.",
)

require(
    len(execute_guards) == 1,
    "Expected exactly one CAL_01 refusal guard in campaign execute.",
)


# ----------------------------------------------------------------------
# The immutable CAL_01 reuse seam.
#
# Critical invariant:
#   - NEVER regenerate Trial 1.
#   - only reuse the exact preparation/deck already frozen for the wave.
#   - only a durable PREPARED registry job is executable through this seam.
# ----------------------------------------------------------------------

function_indent = " " * prepare.col_offset

helper = textwrap.indent(
    textwrap.dedent(
        r'''
def existing_prepared_trial1_artifacts(
    context: dict,
    trial: PreloadCalibrationTrial,
) -> tuple[Path, Path]:
    """Resolve an already-frozen PREPARED CAL_01 without regenerating it."""

    require(
        trial.trial_index == 1,
        "Initial-trial reuse requested for non-CAL_01 work.",
    )

    require(
        trial.run_id
        == context["trial1"].run_id,
        f"{context['case_id']}: CAL_01 run identity drift.",
    )

    require(
        trial.run_id
        == f"{context['case_run_id']}_cal_01",
        f"{context['case_id']}: canonical CAL_01 identity drift.",
    )

    preparation = context["preparation"]

    prep_path = Path(
        context["preparation_path"]
    )

    if not prep_path.is_absolute():
        prep_path = ROOT / prep_path

    prep_path = prep_path.resolve()

    require(
        prep_path.is_file(),
        f"{context['case_id']}: frozen Trial-1 preparation record missing.",
    )

    deck = preparation.get("deck")

    require(
        isinstance(deck, dict),
        f"{context['case_id']}: Trial-1 deck binding missing.",
    )

    relative_path = deck.get(
        "relative_path"
    )

    require(
        isinstance(relative_path, str)
        and bool(relative_path.strip()),
        f"{context['case_id']}: Trial-1 deck path missing.",
    )

    deck_path = (
        ROOT
        / relative_path
    ).resolve()

    try:
        deck_path.relative_to(ROOT)
    except ValueError as exc:
        raise RuntimeError(
            f"{context['case_id']}: Trial-1 deck escapes repository."
        ) from exc

    require(
        deck_path.is_file()
        and deck_path.stat().st_size > 0,
        f"{context['case_id']}: frozen CAL_01 deck missing or empty.",
    )

    actual_deck_sha = sha256(
        deck_path
    )

    preparation_deck_sha = deck.get(
        "sha256"
    )

    prepared_row_deck_sha = (
        context[
            "prepared_row"
        ][
            "deck_sha256"
        ]
    )

    require(
        actual_deck_sha
        == preparation_deck_sha
        == prepared_row_deck_sha,
        f"{context['case_id']}: frozen CAL_01 deck SHA drift.",
    )

    expected_directory = run_dir(
        context,
        trial.run_id,
    )

    require(
        deck_path.parent.resolve()
        == expected_directory.resolve(),
        f"{context['case_id']}: frozen CAL_01 directory drift.",
    )

    manifest_path = (
        expected_directory
        / "fem_run_manifest.json"
    )

    require(
        not manifest_path.exists(),
        (
            f"{context['case_id']}: CAL_01 already has a manifest; "
            "duplicate execution forbidden."
        ),
    )

    for suffix in (
        ".dat",
        ".frd",
        ".sta",
        ".cvg",
        ".rout",
    ):
        artifact = (
            expected_directory
            / f"{trial.run_id}{suffix}"
        )

        require(
            not artifact.exists(),
            (
                f"{context['case_id']}: CAL_01 already has "
                f"{suffix} solver evidence; duplicate execution forbidden."
            ),
        )

    registry = FemFactoryRegistry(
        FACTORY_DB
    )

    record = registry.get_job(
        case_hash=context[
            "case_hash"
        ],
        trial_index=1,
    )

    require(
        record is not None,
        f"{context['case_id']}: CAL_01 absent from factory registry.",
    )

    require(
        record.case_id
        == context[
            "case_id"
        ],
        f"{context['case_id']}: CAL_01 registry case identity drift.",
    )

    require(
        record.run_id
        == trial.run_id,
        f"{context['case_id']}: CAL_01 registry run identity drift.",
    )

    require(
        record.priority
        is FemFactoryPriority.HIGH_INFORMATION_DOE,
        f"{context['case_id']}: CAL_01 registry priority drift.",
    )

    require(
        record.state
        is FemFactoryJobState.PREPARED,
        (
            f"{context['case_id']}: unresolved CAL_01 must be PREPARED; "
            f"found {record.state.value}."
        ),
    )

    require(
        record.manifest_path is None,
        f"{context['case_id']}: PREPARED CAL_01 unexpectedly has manifest.",
    )

    require(
        record.acceptance_record is None,
        f"{context['case_id']}: PREPARED CAL_01 unexpectedly has acceptance.",
    )

    require(
        record.failure_category is None
        and record.failure_message is None,
        f"{context['case_id']}: PREPARED CAL_01 carries failure state.",
    )

    require(
        record.lease_owner is None,
        f"{context['case_id']}: PREPARED CAL_01 already has a lease owner.",
    )

    registry_preparation = record.preparation_record

    require(
        isinstance(
            registry_preparation,
            str,
        )
        and bool(
            registry_preparation.strip()
        ),
        f"{context['case_id']}: CAL_01 registry preparation binding missing.",
    )

    registry_prep_path = Path(
        registry_preparation
    )

    if not registry_prep_path.is_absolute():
        registry_prep_path = (
            ROOT
            / registry_prep_path
        )

    require(
        registry_prep_path.resolve()
        == prep_path,
        f"{context['case_id']}: CAL_01 preparation binding drift.",
    )

    return (
        deck_path,
        prep_path,
    )


def trial1_reuse_ready(
    context: dict,
    trial: PreloadCalibrationTrial,
) -> bool:
    """Fail-closed validation used by preflight/execute mixed-state handoff."""

    if trial.trial_index != 1:
        return False

    existing_prepared_trial1_artifacts(
        context,
        trial,
    )

    return True
'''
    ).strip("\n"),
    function_indent,
) + "\n\n"


# ----------------------------------------------------------------------
# prepare_governed_trial:
# reuse CAL_01; retain original CAL_02+ guard unchanged.
# ----------------------------------------------------------------------

prepare_guard = prepare_guards[0]

prepare_guard_statement = next(
    node
    for node in prepare.body
    if (
        isinstance(
            node,
            ast.Expr,
        )
        and isinstance(
            node.value,
            ast.Call,
        )
        and any(
            candidate is prepare_guard
            for candidate
            in ast.walk(node)
        )
    )
)

prepare_insert_offset = offsets[
    prepare_guard_statement.lineno - 1
]

body_indent = " " * (
    prepare.col_offset + 4
)

prepare_branch = textwrap.indent(
    textwrap.dedent(
        '''
if trial.trial_index == 1:
    return existing_prepared_trial1_artifacts(
        context,
        trial,
    )

'''
    ),
    body_indent,
)


# ----------------------------------------------------------------------
# register_prepared_trial:
# Trial 1 already exists in registry. Verify and reuse it.
# CAL_02+ retains original register/transition behavior.
# ----------------------------------------------------------------------

register_first_statement = register.body[0]

register_insert_offset = offsets[
    register_first_statement.lineno - 1
]

register_body_indent = " " * (
    register.col_offset + 4
)

register_branch = textwrap.indent(
    textwrap.dedent(
        '''
if trial.trial_index == 1:
    existing_prepared_trial1_artifacts(
        context,
        trial,
    )

    record = registry.get_job(
        case_hash=context["case_hash"],
        trial_index=1,
    )

    require(
        record is not None
        and record.state
        is FemFactoryJobState.PREPARED,
        (
            f"{trial.run_id}: existing CAL_01 registry "
            "job is not reusable PREPARED work."
        ),
    )

    print(
        f"REUSED PREPARED CAL_01 : {trial.run_id}",
        flush=True,
    )

    return record

'''
    ),
    register_body_indent,
)


# ----------------------------------------------------------------------
# Preflight + execute:
# CAL_02+ remains ordinary adaptive work.
# CAL_01 is legal ONLY if the frozen-prepared reuse gate passes.
# ----------------------------------------------------------------------

edits: list[
    tuple[int, int, str]
] = []


for guard in (
    preflight_guards[0],
    execute_guards[0],
):
    start, end = absolute_span(
        guard,
        offsets,
    )

    original = source[
        start:end
    ]

    require(
        "trial.trial_index" in original
        and "2" in original,
        "Unexpected adaptive CAL_01 guard source.",
    )

    replacement = (
        "("
        + original
        + " or trial1_reuse_ready(context, trial))"
    )

    edits.append(
        (
            start,
            end,
            replacement,
        )
    )


# Insert helper before prepare_governed_trial.
helper_offset = offsets[
    prepare.lineno - 1
]

edits.append(
    (
        helper_offset,
        helper_offset,
        helper,
    )
)

edits.append(
    (
        prepare_insert_offset,
        prepare_insert_offset,
        prepare_branch,
    )
)

edits.append(
    (
        register_insert_offset,
        register_insert_offset,
        register_branch,
    )
)


# Apply against original source in descending byte/character position.
patched = source

for start, end, replacement in sorted(
    edits,
    key=lambda item: item[0],
    reverse=True,
):
    patched = (
        patched[:start]
        + replacement
        + patched[end:]
    )


require(
    patched != source,
    "Patch produced no source change.",
)

require(
    patched.count(
        "def existing_prepared_trial1_artifacts"
    )
    == 1,
    "Initial-Trial artifact helper insertion drift.",
)

require(
    patched.count(
        "def trial1_reuse_ready"
    )
    == 1,
    "Initial-Trial readiness helper insertion drift.",
)

require(
    patched.count(
        "trial1_reuse_ready(context, trial)"
    )
    == 2,
    "Expected exactly two supervisor CAL_01 handoff gates.",
)

# The original adaptive-preparation prohibition MUST remain.
require(
    (
        "Existing CAL_01 must be reused; "
        in patched
    ),
    "CAL_01 regeneration guard was accidentally removed.",
)


# Syntax gate before publication.
compile(
    patched,
    str(SOURCE),
    "exec",
)


if BACKUP.exists():
    require(
        sha256(BACKUP)
        == EXPECTED_SHA,
        "Existing backup does not match frozen pre-patch runner.",
    )
else:
    BACKUP.write_bytes(
        SOURCE.read_bytes()
    )


SOURCE.write_text(
    patched,
    encoding="utf-8",
    newline="\n",
)


new_sha = sha256(
    SOURCE
)


print(
    "PRE-PATCH SHA :",
    EXPECTED_SHA,
)

print(
    "POST-PATCH SHA:",
    new_sha,
)

print(
    "BACKUP        :",
    BACKUP.relative_to(ROOT),
)

print(
    "PASS: syntax compiled before publication."
)

print(
    "PASS: CAL_01 regeneration guard preserved."
)

print(
    "PASS: mixed-state CAL_01 reuse seam installed."
)
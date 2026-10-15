"""Deterministically extract the generic governed wave runner.

The frozen W02 autonomous runner is used only as the already-proven common
implementation source. Slice-3 audits established that W01 and W02 contain
the same 30-function engine after wave-label normalization.

This builder:
- SHA-pins the frozen W02 implementation source;
- removes historical wave bindings;
- replaces them with GovernedWaveExecutionContract values;
- replaces the one historical authorization variation with the generic
  authorization validator;
- wraps the engine in an instance-local factory so no mutable global
  wave configuration is shared between runner instances.

Historical W01/W02 runners are never modified.
"""

from __future__ import annotations

import argparse
import ast
import hashlib

from pathlib import Path


ROOT = Path(r"D:\ThreadROM").resolve()

SOURCE = (
    ROOT
    / "scripts"
    / "run_phase3_diversified_w02_adaptive_factory.py"
)

OUTPUT = (
    ROOT
    / "src"
    / "threadrom"
    / "factory"
    / "governed_wave_runner.py"
)

EXPECTED_SOURCE_SHA256 = (
    "f0fbe35a4c0e4ffc6368d49ab3b42a86"
    "2be58ad077e3e490b538e4e4be53197d"
)


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(
            message
        )


def sha256_bytes(
    payload: bytes,
) -> str:
    return hashlib.sha256(
        payload
    ).hexdigest()


def sha256_file(
    path: Path,
) -> str:
    return sha256_bytes(
        path.read_bytes()
    )


def assignment_names(
    node: ast.AST,
) -> tuple[str, ...]:
    targets = []

    if isinstance(
        node,
        ast.Assign,
    ):
        targets.extend(
            node.targets
        )

    elif isinstance(
        node,
        ast.AnnAssign,
    ):
        targets.append(
            node.target
        )

    names = []

    for target in targets:
        if isinstance(
            target,
            ast.Name,
        ):
            names.append(
                target.id
            )

    return tuple(
        names
    )


def generic_source() -> str:
    require(
        SOURCE.is_file(),
        f"Frozen W02 source missing: {SOURCE}",
    )

    actual_source_sha = sha256_file(
        SOURCE
    )

    require(
        actual_source_sha
        == EXPECTED_SOURCE_SHA256,
        (
            "Frozen W02 source SHA drift. "
            f"Expected {EXPECTED_SOURCE_SHA256}, "
            f"found {actual_source_sha}."
        ),
    )

    source = SOURCE.read_text(
        encoding="utf-8-sig"
    )

    lines = source.splitlines()

    tree = ast.parse(
        source,
        filename=str(
            SOURCE
        ),
    )

    replacements: list[
        tuple[
            int,
            int,
            str,
        ]
    ] = []

    required_assignments = {
        "ROOT": (
            '''ROOT = repository_root.resolve()

CAMPAIGN_ID = contract.campaign_id
WAVE_TOKEN = contract.wave_token
WAVE_ID = contract.wave_id

ADAPTIVE_PREPARATION_FILENAME = (
    contract.adaptive_preparation_filename
)
ADAPTIVE_PREPARATION_SCHEMA = (
    contract.adaptive_preparation_schema
)
ADAPTIVE_PREPARATION_DISPOSITION = (
    contract.adaptive_preparation_disposition
)
WORKER_PREFIX = contract.worker_prefix

PHYSICS_ASSESSMENT_FILENAME = (
    contract.physics_assessment_filename
)
PHYSICS_ASSESSMENT_SCHEMA = (
    contract.physics_assessment_schema
)
NONLINEAR_PROGRESS_FILENAME = (
    contract.nonlinear_progress_filename
)
EXTERNAL_TOTAL_FORCE_FILENAME = (
    contract.external_total_force_filename
)
EXTERNAL_EQUILIBRIUM_FILENAME = (
    contract.external_equilibrium_filename
)

PREFLIGHT_TITLE = contract.preflight_title
EXECUTION_TITLE = contract.execution_title
COMPLETION_MESSAGE = contract.completion_message'''
        ),
        "CAMPAIGN_ROOT": (
            '''CAMPAIGN_ROOT = (
        ROOT
        / Path(
            contract.campaign_root.as_posix()
        )
    )'''
        ),
        "SOLVER_ROOT": (
            '''SOLVER_ROOT = (
        ROOT
        / Path(
            contract.solver_root.as_posix()
        )
    )'''
        ),
        "FACTORY_ROOT": (
            '''FACTORY_ROOT = (
        ROOT
        / Path(
            contract.factory_root.as_posix()
        )
    )'''
        ),
        "FACTORY_DB": (
            '''FACTORY_DB = (
        ROOT
        / Path(
            contract.factory_database_path.as_posix()
        )
    )'''
        ),
        "ADMISSION_LOCK": (
            '''ADMISSION_LOCK = (
        ROOT
        / Path(
            contract.admission_lock_path.as_posix()
        )
    )'''
        ),
        "AUTH_PATH": (
            '''AUTH_PATH = (
        ROOT
        / Path(
            contract.owner_authorization_path.as_posix()
        )
    )'''
        ),
        "EXPECTED_AUTH_SHA256": (
            '''EXPECTED_AUTH_SHA256 = (
        contract.expected_owner_authorization_sha256
    )'''
        ),
        "PREP_INDEX_PATH": (
            '''PREP_INDEX_PATH = (
        ROOT
        / Path(
            contract.preparation_index_path.as_posix()
        )
    )'''
        ),
        "EXPECTED_PREP_INDEX_SHA256": (
            '''EXPECTED_PREP_INDEX_SHA256 = (
        contract.expected_preparation_index_sha256
    )'''
        ),
        "SCRIPT_RELATIVE_PATH": (
            '''SCRIPT_RELATIVE_PATH = (
        "src/threadrom/factory/"
        "governed_wave_runner.py"
    )'''
        ),
        "MAXIMUM_CONCURRENT_CCX": (
            '''MAXIMUM_CONCURRENT_CCX = (
        contract.maximum_concurrent_solver_slots
    )'''
        ),
        "MAXIMUM_TRIALS": (
            '''MAXIMUM_TRIALS = (
        contract.maximum_trial_index
    )'''
        ),
        "EXPECTED_CASE_COUNT": (
            '''EXPECTED_CASE_COUNT = (
        contract.authorized_case_count
    )'''
        ),
    }

    found_assignments = set()

    function_names = []

    for node in tree.body:
        if isinstance(
            node,
            ast.ImportFrom,
        ) and node.module == "__future__":
            replacements.append(
                (
                    node.lineno,
                    node.end_lineno,
                    "",
                )
            )

            continue

        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            function_names.append(
                node.name
            )

            if (
                node.name
                == "verify_owner_authorization"
            ):
                replacements.append(
                    (
                        node.lineno,
                        node.end_lineno,
                        '''def verify_owner_authorization() -> dict:
    verified = (
        load_and_verify_wave_owner_authorization(
            repository_root=ROOT,
            contract=contract,
        )
    )

    return verified.raw_payload''',
                    )
                )

            continue

        for name in assignment_names(
            node
        ):
            replacement = (
                required_assignments.get(
                    name
                )
            )

            if replacement is None:
                continue

            require(
                name not in found_assignments,
                (
                    "Duplicate top-level assignment "
                    f"for {name}."
                ),
            )

            found_assignments.add(
                name
            )

            replacements.append(
                (
                    node.lineno,
                    node.end_lineno,
                    replacement,
                )
            )

    # EXPECTED_CASE_COUNT existed in the historical runner but keep the
    # extractor tolerant if an equivalent count was inlined by a future
    # source-preserving refactor.
    mandatory = (
        set(
            required_assignments
        )
        - {
            "EXPECTED_CASE_COUNT",
        }
    )

    missing = (
        mandatory
        - found_assignments
    )

    require(
        not missing,
        (
            "Required W02 binding assignments missing: "
            f"{sorted(missing)!r}"
        ),
    )

    # Apply line-range replacements from the end of the file backwards.
    for (
        start,
        end,
        replacement,
    ) in sorted(
        replacements,
        key=lambda item: item[0],
        reverse=True,
    ):
        lines[
            start - 1
            : end
        ] = (
            replacement.splitlines()
            if replacement
            else []
        )

    body = "\n".join(
        lines
    )

    # Normalize historical wave literals using Python AST
    # constant identity rather than raw source-line matching.
    #
    # This safely handles adjacent string literals split across lines
    # and is independent of console encoding for punctuation/emoji.

    worker_source = "\n".join(
        (
            "    worker_id = (",
            '        "TRM-DDOE-W02-adaptive-"',
            '        f"worker-{worker_number:02d}"',
            "    )",
        )
    )

    worker_generic = "\n".join(
        (
            "    worker_id = (",
            "        WORKER_PREFIX",
            '        + f"worker-{worker_number:02d}"',
            "    )",
        )
    )

    worker_count = body.count(
        worker_source
    )

    require(
        worker_count == 1,
        (
            "Historical worker-id structure drift: "
            f"expected 1, found {worker_count}."
        ),
    )

    body = body.replace(
        worker_source,
        worker_generic,
        1,
    )

    normalized_tree = ast.parse(
        body,
        filename="<generic-wave-normalization>",
    )

    exact_literal_replacements = {
        (
            "threadrom.phase3_diversified_"
            "w02_adaptive_preparation.v1"
        ): "ADAPTIVE_PREPARATION_SCHEMA",

        "W02_ADAPTIVE_TRIAL_PREPARATION_PASS": (
            "ADAPTIVE_PREPARATION_DISPOSITION"
        ),

        "w02_adaptive_preparation.json": (
            "ADAPTIVE_PREPARATION_FILENAME"
        ),

        "w02_governed_full_physics_assessment_v2.json": (
            "PHYSICS_ASSESSMENT_FILENAME"
        ),

        "w02_nonlinear_progress.json": (
            "NONLINEAR_PROGRESS_FILENAME"
        ),

        "w02_external_translational_total_force.json": (
            "EXTERNAL_TOTAL_FORCE_FILENAME"
        ),

        "w02_external_translational_equilibrium.json": (
            "EXTERNAL_EQUILIBRIUM_FILENAME"
        ),

        (
            "threadrom.phase3_diversified_"
            "w02_full_physics_assessment.v2"
        ): "PHYSICS_ASSESSMENT_SCHEMA",

        "TRM-DDOE-001-W02": "WAVE_ID",
        "TRM-DDOE-001": "CAMPAIGN_ID",
        "W02": "WAVE_TOKEN",

        "Authorized W02 case count drift.": (
            '"Authorized governed-wave case count drift."'
        ),

        "W02 authorization scope broadened.": (
            '"Governed-wave authorization scope broadened."'
        ),

        "W02 Trial-1 preparation index drift.": (
            '"Governed-wave Trial-1 preparation index drift."'
        ),

        (
            "W02 must contain exactly four "
            "prepared Trial-1 rows."
        ): (
            '"Governed-wave prepared Trial-1 row count drift."'
        ),

        "Duplicate W02 case identity.": (
            '"Duplicate governed-wave case identity."'
        ),

        (
            "Factory claimed a PREPARED job outside "
            "the current autonomous W02 execution set: "
        ): (
            '"Factory claimed a PREPARED job outside '
            'the current governed-wave execution set: "'
        ),
    }

    ast_operations = []

    for node in ast.walk(
        normalized_tree
    ):
        if not (
            isinstance(
                node,
                ast.Constant,
            )
            and isinstance(
                node.value,
                str,
            )
        ):
            continue

        value = node.value
        replacement = None

        if (
            "TRM-DDOE-001-W02"
            in value
            and (
                "ALL FOUR CASES GOVERNED "
                "FULL-PHYSICS ACCEPTED"
            )
            in value
        ):
            replacement = (
                "COMPLETION_MESSAGE"
            )

        elif (
            "W02 AUTONOMOUS ADAPTIVE FACTORY PREFLIGHT"
            in value
        ):
            replacement = (
                "PREFLIGHT_TITLE"
            )

        elif (
            "W02 AUTONOMOUS ADAPTIVE FACTORY"
            in value
        ):
            replacement = (
                "EXECUTION_TITLE"
            )

        else:
            replacement = (
                exact_literal_replacements.get(
                    value
                )
            )

        if replacement is None:
            continue

        segment = ast.get_source_segment(
            body,
            node,
        )

        require(
            segment is not None,
            (
                "Unable to recover historical "
                "literal source segment."
            ),
        )

        ast_operations.append(
            (
                len(segment),
                segment,
                replacement,
                value,
            )
        )

    require(
        ast_operations,
        (
            "No historical wave literals were "
            "identified for normalization."
        ),
    )

    for (
        _,
        segment,
        replacement,
        value,
    ) in sorted(
        ast_operations,
        key=lambda item: item[0],
        reverse=True,
    ):
        require(
            segment in body,
            (
                "Historical AST source segment "
                "disappeared before replacement: "
                f"{value!r}"
            ),
        )

        body = body.replace(
            segment,
            replacement,
            1,
        )

    body = body.replace(
        "# Preserve W02-local compatibility aliases.",
        "# Preserve wave-local compatibility aliases.",
    )

    # Historical script main()/argparse functions may remain available as
    # closures, but their __main__ guard must never execute inside the
    # instance factory.
    body = body.replace(
        '''if __name__ == "__main__":
    main()''',
        "",
    )

    require(
        "W02" not in body
        and "w02" not in body,
        (
            "Historical W02 token leaked into "
            "generic engine."
        ),
    )

    require(
        "W01" not in body
        and "w01" not in body,
        (
            "Historical W01 token leaked into "
            "generic engine."
        ),
    )

    require(
        "def preflight(" in body,
        "Generic engine lost preflight().",
    )

    require(
        "def execute(" in body,
        "Generic engine lost execute().",
    )

    require(
        "def recover_calibration_state(" in body,
        (
            "Generic engine lost "
            "recover_calibration_state()."
        ),
    )

    require(
        "def prepare_governed_trial(" in body,
        (
            "Generic engine lost "
            "prepare_governed_trial()."
        ),
    )

    require(
        "def assess_full_physics(" in body,
        (
            "Generic engine lost "
            "assess_full_physics()."
        ),
    )

    # The historical source contains 30 top-level functions.
    require(
        len(
            function_names
        )
        == 30,
        (
            "Frozen engine function-count drift: "
            f"{len(function_names)}."
        ),
    )

    indented = "\n".join(
        (
            "    " + line
            if line
            else ""
        )
        for line in body.splitlines()
    )

    function_mapping = "\n".join(
        (
            f'        "{name}": {name},'
        )
        for name in function_names
    )

    header = '''"""Generic governed diversified-DOE wave execution engine.

GENERATED deterministically by:
scripts/build_phase3_generic_governed_wave_runner_v1.py

Do not hand-edit this file. Rebuild it from the SHA-pinned historical common
engine and the governed Slice-3 parameterization rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from threadrom.factory.governed_wave_contract import (
    GovernedWaveExecutionContract,
)
from threadrom.factory.governed_wave_owner_authorization import (
    load_and_verify_wave_owner_authorization,
)


@dataclass(frozen=True, slots=True)
class GovernedWaveRunner:
    """Configured instance of the generic governed wave engine."""

    repository_root: Path
    contract: GovernedWaveExecutionContract
    _functions: Mapping[
        str,
        Callable[..., Any],
    ]

    @property
    def available_functions(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                self._functions
            )
        )

    def call(
        self,
        name: str,
        /,
        *args,
        **kwargs,
    ):
        try:
            function = self._functions[
                name
            ]
        except KeyError as error:
            raise KeyError(
                f"Unknown governed-wave runner function: {name}"
            ) from error

        return function(
            *args,
            **kwargs,
        )

    def build_case_contexts(
        self,
    ):
        return self.call(
            "build_case_contexts"
        )

    def preflight(
        self,
    ):
        self.call(
            "verify_owner_authorization"
        )

        contexts = (
            self.build_case_contexts()
        )

        return self.call(
            "preflight",
            contexts,
        )

    def execute(
        self,
    ):
        self.call(
            "verify_owner_authorization"
        )

        contexts = (
            self.build_case_contexts()
        )

        return self.call(
            "execute",
            contexts,
        )


def build_governed_wave_runner(
    *,
    repository_root: Path,
    contract: GovernedWaveExecutionContract,
) -> GovernedWaveRunner:
    """Create one isolated generic governed-wave engine instance."""

'''

    footer = f'''

    functions = MappingProxyType(
        {{
{function_mapping}
        }}
    )

    return GovernedWaveRunner(
        repository_root=ROOT,
        contract=contract,
        _functions=functions,
    )
'''

    generated = (
        header
        + indented
        + footer
    )

    # Compile before allowing persistence.
    compile(
        generated,
        str(
            OUTPUT
        ),
        "exec",
    )

    return generated


def write_mode() -> None:
    generated = generic_source()

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        generated,
        encoding="utf-8",
        newline="\n",
    )

    print()
    print("=" * 110)
    print("GENERIC GOVERNED WAVE RUNNER — GENERATED")
    print("=" * 110)
    print(
        "Frozen source SHA :",
        EXPECTED_SOURCE_SHA256,
    )
    print(
        "Output            :",
        OUTPUT.relative_to(
            ROOT
        ),
    )
    print(
        "Output SHA-256    :",
        sha256_file(
            OUTPUT
        ),
    )
    print(
        "Historical runners: UNTOUCHED"
    )
    print("=" * 110)


def check_mode() -> None:
    require(
        OUTPUT.is_file(),
        "Generic governed-wave runner has not been generated.",
    )

    expected = generic_source()

    actual = OUTPUT.read_text(
        encoding="utf-8-sig"
    )

    require(
        actual == expected,
        (
            "Generated generic governed-wave "
            "runner is not deterministic."
        ),
    )

    print()
    print("=" * 110)
    print("GENERIC GOVERNED WAVE RUNNER — REBUILD CHECK PASS")
    print("=" * 110)
    print(
        "Output SHA-256 :",
        sha256_file(
            OUTPUT
        ),
    )
    print(
        "Deterministic  : PASS"
    )
    print("=" * 110)


def main() -> None:
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group(
        required=True
    )

    group.add_argument(
        "--write",
        action="store_true",
    )

    group.add_argument(
        "--check",
        action="store_true",
    )

    args = parser.parse_args()

    if args.write:
        write_mode()
    else:
        check_mode()


if __name__ == "__main__":
    main()

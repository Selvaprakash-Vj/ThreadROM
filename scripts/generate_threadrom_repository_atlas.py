#!/usr/bin/env python3
"""Build a source-grounded navigation atlas for the ThreadROM repository.

This tool only reads repository files and Git's file inventory. It never
imports project modules, opens FEM result data, or executes simulations.
"""

from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from datetime import date
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import quote


ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "docs/THREADROM_REPOSITORY_ATLAS.md"

ALLOWED_EXTENSIONS = {
    ".py", ".toml", ".md", ".json", ".yaml", ".yml",
    ".ini", ".cfg", ".ps1", ".sh", ".txt",
}
ROOT_FILES = {
    "README.md", "pyproject.toml", "pytest.ini",
    "setup.cfg", "requirements.txt", "Makefile",
}
SCOPED_DIRECTORIES = {
    "src", "scripts", "tests", "config", "docs",
}

# Navigation notes are curated. They are NOT mechanically inferred
# from filename spelling or proof of any particular physics claim.
WORKFLOWS = (
    (
        "Understand the current engineering status",
        (
            "README.md",
            "docs/THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md",
            "config/phase3_production_doe.toml",
        ),
        "Scope, six-gate qualification, current limitations and roadmap.",
    ),
    (
        "Change canonical case or material resolution",
        (
            "src/threadrom/case/contract.py",
            "src/threadrom/case/resolver.py",
            "src/threadrom/materials/catalog.py",
            "src/threadrom/materials/resolver.py",
            "src/threadrom/case/preflight_rules.py",
        ),
        "Review case contracts, material identity and preflight together.",
    ),
    (
        "Trace the analytical prediction",
        (
            "src/threadrom/factory/analytical_adapter.py",
            "src/threadrom/engineering/analytical_joint_loader.py",
            "src/threadrom/engineering/analytical_bolt_mechanics.py",
            "src/threadrom/engineering/analytical_member_mechanics.py",
        ),
        "Check the resolved inputs and each engineering calculation.",
    ),
    (
        "Change threaded geometry or assembly registration",
        (
            "src/threadrom/geometry/complete_joint_assembly.py",
            "src/threadrom/geometry/complete_nut.py",
            "src/threadrom/geometry/canonical_screw_geometry.py",
            "tests/unit/test_thread_registration.py",
        ),
        "Review geometry and thread-registration tests before modifying CAD.",
    ),
    (
        "Trace a prepared DOE case",
        (
            "scripts/prepare_phase3_production_doe_case.py",
            "src/threadrom/factory/fem_case_preparation.py",
            "src/threadrom/factory/governed_fem_physical_preparation.py",
            "src/threadrom/factory/geometry_identity.py",
            "src/threadrom/factory/mesh_identity.py",
        ),
        "Follow case identity, CAD, grouped mesh and preparation records.",
    ),
    (
        "Trace FEM transfer, materials and actual deck cards",
        (
            "src/threadrom/factory/fem_case_definition_bundle.py",
            "src/threadrom/solver/complete_joint_calculix_transfer.py",
            "src/threadrom/factory/fem_production_deck.py",
            "tests/unit/test_governed_two_group_actual_deck.py",
            "tests/unit/test_governed_two_group_elastic_transfer.py",
        ),
        "The two-group elastic transfer is software-qualified, not a "
        "mixed-material physics certificate.",
    ),
    (
        "Investigate initial launch authorization or concurrent solves",
        (
            "src/threadrom/factory/governed_fem_initial_launch_authorization.py",
            "src/threadrom/factory/production_doe_launch_fence.py",
            "scripts/run_phase3_production_doe_trial1_case.py",
            "tests/unit/test_governed_fem_initial_launch_reservation.py",
        ),
        "Inspect approval pins and durable launch reservation; no blanket "
        "solver authorization follows from a passing regression.",
    ),
    (
        "Investigate adaptive calibration and warm starts",
        (
            "src/threadrom/factory/adaptive_fem_c01_live_port.py",
            "src/threadrom/factory/fem_calibration_knowledge.py",
            "scripts/prepare_phase3_production_doe_next_calibration_trial.py",
            "scripts/run_phase3_production_doe_calibration_trial_case.py",
            "scripts/run_phase3_production_doe_adaptive_campaign.py",
        ),
        "Use existing case-specific evidence and governed continuation.",
    ),
    (
        "Recover an interrupted or historical FEM trial",
        (
            "src/threadrom/factory/governed_fem_initial_live_port.py",
            "src/threadrom/factory/production_doe_trial_history.py",
            "src/threadrom/factory/production_doe_case_registry.py",
            "tests/unit/test_governed_fem_initial_lifecycle_dry_run.py",
        ),
        "Separate preparation, solver execution and engineering acceptance.",
    ),
    (
        "Review campaign scope and case membership",
        (
            "src/threadrom/factory/governed_fem_campaign.py",
            "src/threadrom/factory/governed_fem_campaign_context.py",
            "src/threadrom/factory/governed_fem_case_resolution.py",
            "config/phase3_production_doe.toml",
        ),
        "Use frozen design membership. Do not open sealed holdout case data.",
    ),
)

EVIDENCE_PATHS = (
    (
        "Frozen C01 policy",
        "config/phase3_production_doe.toml",
        "Authoritative declared campaign envelope and exclusions.",
    ),
    (
        "C01 manifest",
        "simulations/staging/phase3_cp8_production_doe/"
        "TRM-PDOE-C01/production_doe_campaign_manifest.json",
        "Frozen design membership; holdout content remains sealed.",
    ),
    (
        "Prepared case records",
        "simulations/staging/phase3_cp8_production_doe/"
        "TRM-PDOE-C01/prepared_cases/",
        "Case-local geometry, mesh and preparation provenance.",
    ),
    (
        "Solver preparation and trial records",
        "simulations/staging/phase3_cp8_production_doe/"
        "TRM-PDOE-C01/solver_preparation/",
        "Trial directories. A prepared deck is not a completed solver run.",
    ),
    (
        "D-BND-001 Trial 1",
        "simulations/staging/phase3_cp8_production_doe/"
        "TRM-PDOE-C01/solver_preparation/"
        "trm_fem_a5e86e9150fb/trm_fem_a5e86e9150fb_cal_01/",
        "Previously recovered evidence; do not relaunch by default.",
    ),
    (
        "D-BND-001 Trial 2",
        "simulations/staging/phase3_cp8_production_doe/"
        "TRM-PDOE-C01/solver_preparation/"
        "trm_fem_a5e86e9150fb/trm_fem_a5e86e9150fb_cal_02/",
        "Previously recovered evidence; case physics still requires "
        "its authoritative case-specific disposition.",
    ),
)

IMPORTANT = (
    "A source docstring describes intended module purpose, not verified "
    "physical correctness.",
    "A static import identifies a direct source reference, not proof "
    "that a test covers a behaviour.",
    "Dynamic imports, runtime-composed paths, command-line invocation "
    "and external dependencies may not appear in the static index.",
    "The atlas includes non-ignored, Git-tracked/untracked repository files "
    "in the selected code/config/documentation scopes. It does not "
    "recursively index simulation artifacts or ignored environments.",
    "Exact case/trial status comes from authoritative governed evidence, "
    "not an atlas link, run manifest alone or historical progress note.",
    "No listing here opens sealed holdout records, grants a solver "
    "authorization or certifies ROM applicability.",
)


def git_files() -> list[str]:
    proc = subprocess.run(
        [
            "git", "ls-files", "--cached", "--others",
            "--exclude-standard", "-z",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Git file inventory failed: "
            + proc.stderr.decode("utf-8", "replace")
        )

    result = set()
    for entry in proc.stdout.decode("utf-8", "surrogateescape").split("\0"):
        if not entry:
            continue
        relative = Path(entry)
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(f"Unsafe Git-listed path: {entry}")
        path = ROOT / relative
        if not path.is_file() or path.is_symlink():
            continue
        if entry == "docs/THREADROM_REPOSITORY_ATLAS.md":
            continue  # Avoid indexing or fingerprinting the atlas itself.
        if (
            relative.parts[0] not in SCOPED_DIRECTORIES
            and entry not in ROOT_FILES
        ):
            continue
        if (
            path.suffix.lower() not in ALLOWED_EXTENSIONS
            and entry not in ROOT_FILES
        ):
            continue
        result.add(relative.as_posix())

    return sorted(result)


def link(relative: str, *, from_docs: bool = True) -> str:
    prefix = "../" if from_docs else ""
    return quote(prefix + relative, safe="/._-")


def md_link(relative: str, label: str | None = None) -> str:
    text = (label or relative).replace("|", "\\|")
    return f"[`{text}`]({link(relative)})"


def module_name(relative: str) -> str | None:
    path = Path(relative)
    parts = path.parts

    if not (
        relative.endswith(".py")
        and parts[0] in {"src", "scripts", "tests"}
    ):
        return None

    pieces = list(parts[1:] if parts[0] == "src" else parts)
    pieces[-1] = Path(pieces[-1]).stem

    if pieces[-1] == "__init__":
        pieces.pop()

    return ".".join(pieces) or None


def imported_modules(
    tree: ast.Module,
    current: str,
    module_paths: dict[str, str],
    *,
    is_package: bool,
) -> set[str]:
    imports = set()
    package = (
        current if is_package
        else current.rpartition(".")[0]
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if name in module_paths:
                    imports.add(name)

        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".") if package else []
                ascend = node.level - 1
                if ascend > len(parts):
                    continue
                base_parts = (
                    parts[:len(parts) - ascend]
                    if ascend else parts
                )
                if node.module:
                    base_parts.extend(node.module.split("."))
                base = ".".join(base_parts)
            else:
                base = node.module or ""

            if base in module_paths:
                imports.add(base)

            for alias in node.names:
                candidate = (
                    f"{base}.{alias.name}"
                    if base else alias.name
                )
                if candidate in module_paths:
                    imports.add(candidate)

    imports.discard(current)
    return imports


def source_symbols(tree: ast.Module) -> str:
    symbols = []
    for node in tree.body:
        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            continue
        if node.name.startswith("_"):
            continue
        symbols.append(f"`{node.name}`")

    if not symbols:
        return "—"

    displayed = ", ".join(symbols[:7])
    if len(symbols) > 7:
        displayed += f" … (+{len(symbols) - 7})"
    return displayed


def short_docstring(tree: ast.Module) -> str:
    value = ast.get_docstring(tree) or ""
    summary = " ".join(value.split()).strip()
    if not summary:
        return "No module docstring; inspect its exported symbols."
    return (
        summary[:137] + "…"
        if len(summary) > 140 else summary
    ).replace("|", "\\|")


def read_python_inventory(files: list[str]):
    python_files = [
        path for path in files if path.endswith(".py")
    ]
    module_paths = {}

    for relative in python_files:
        name = module_name(relative)
        if name:
            if name in module_paths:
                raise RuntimeError(
                    f"Duplicate module identity: {name}"
                )
            module_paths[name] = relative

    trees = {}
    descriptions = {}
    symbols = {}
    errors = []

    for relative in python_files:
        try:
            source = (ROOT / relative).read_text(
                encoding="utf-8-sig"
            )
            tree = ast.parse(source, filename=relative)
        except (OSError, SyntaxError, UnicodeError) as exc:
            errors.append(f"{relative}: {exc}")
            continue
        trees[relative] = tree
        descriptions[relative] = short_docstring(tree)
        symbols[relative] = source_symbols(tree)

    if errors:
        raise RuntimeError(
            "Python source could not be indexed safely:\n"
            + "\n".join(errors)
        )

    edges = defaultdict(set)
    reverse = defaultdict(set)

    for relative, tree in trees.items():
        name = module_name(relative)
        if not name:
            continue

        targets = imported_modules(
            tree,
            name,
            module_paths,
            is_package=Path(relative).name == "__init__.py",
        )
        for target in targets:
            imported_file = module_paths[target]
            edges[relative].add(imported_file)
            reverse[imported_file].add(relative)

    return trees, descriptions, symbols, edges, reverse


def links_list(values: set[str], limit: int = 8) -> str:
    items = sorted(values)
    if not items:
        return "None found statically"
    displayed = ", ".join(
        md_link(path, Path(path).name)
        for path in items[:limit]
    )
    if len(items) > limit:
        displayed += f" … (+{len(items) - limit})"
    return displayed


def section_for(relative: str) -> str:
    parts = Path(relative).parts
    if parts[0] == "src":
        return (
            "Source — " + parts[2]
            if len(parts) > 2 else "Source — root"
        )
    if parts[0] == "tests":
        return (
            "Tests — " + parts[1]
            if len(parts) > 1 else "Tests"
        )
    if parts[0] == "scripts":
        return "Runnable scripts and maintenance tools"
    if parts[0] == "config":
        return "Configuration"
    if parts[0] == "docs":
        return "Documentation"
    return "Repository entry points"


def render() -> str:
    files = git_files()
    included = set(files)

    (
        trees,
        descriptions,
        symbols,
        edges,
        reverse,
    ) = read_python_inventory(files)

    sections = defaultdict(list)
    for relative in files:
        sections[section_for(relative)].append(relative)

    lines = [
        "# ThreadROM — Repository Atlas",
        "",
        "**Purpose:** Find the file, symbol, dependency, test or evidence "
        "location needed for a specific ThreadROM task.",
        "",
        "**Generated by:** " +
        md_link(
            "scripts/generate_threadrom_repository_atlas.py"
        ),
        "",
        "**Companion engineering reference:** " +
        md_link(
            "docs/THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md"
        ),
        "",
        "> Generated index. Do not edit this file manually. Edit source "
        "module docstrings or the generator's curated workflow map, "
        "then regenerate deliberately. This atlas is a navigation aid, "
        "not a physics certificate.",
        "",
        "## 1. How to use this atlas",
        "",
        "Start with the workflow table below. Follow the linked source "
        "file, then inspect its public symbols, static dependencies and "
        "directly referencing tests in the inventory.",
        "",
        "Search for a symbol in the inventory before searching the "
        "entire repository. If a file has no docstring, its purpose "
        "is deliberately left unasserted rather than guessed.",
        "",
        "The authoritative engineering progress and qualification "
        "boundaries remain in the companion reference. Do not "
        "interpret the presence of a test, manifest or deck as "
        "independent physics acceptance.",
        "",
        "## 2. Where do I go for a given task?",
        "",
        "| Task | Start here | Navigation note |",
        "|---|---|---|",
    ]

    for task, paths, note in WORKFLOWS:
        present = [
            path for path in paths if path in included
        ]
        missing = [
            path for path in paths if path not in included
        ]
        references = (
            ", ".join(
                md_link(path, Path(path).name)
                for path in present
            )
            if present else "**No listed file found**"
        )
        if missing:
            references += (
                "; **check missing paths:** "
                + ", ".join(f"`{path}`" for path in missing)
            )
        lines.append(f"| {task} | {references} | {note} |")

    lines.extend([
        "",
        "## 3. Architecture and qualification boundaries",
        "",
        "```text",
        "Canonical case + material resolution",
        "    -> analytical engineering and preflight",
        "    -> parameter-driven CAD and mesh preparation",
        "    -> governed FEM definition + deck generation",
        "    -> authorization / launch fence / adaptive execution",
        "    -> recovered trial evidence + engineering disposition",
        "    -> certified dataset (Phase 3 work still required)",
        "    -> ROM-specific extraction / training / evaluation (Phase 4)",
        "```",
        "",
        "The arrows describe responsibility boundaries, not a claim "
        "that every interface or Phase-4 subsystem is implemented.",
        "",
        "The six factory qualification gates are closed within "
        "the documented bounded C01 preparation/software scope. "
        "DOE physics certification, complete dataset freeze, "
        "general metric-size FEM qualification and Phase-4 ROM "
        "training are separate milestones.",
        "",
        "## 4. Frozen C01 evidence navigation",
        "",
        "These are known locations, **not** assertions that every "
        "record they may contain is an accepted physics sample. "
        "The generator checks whether these paths exist but does "
        "not read simulation results or holdout contents.",
        "",
        "| Evidence or reference | Path | Meaning |",
        "|---|---|---|",
    ])

    for label, relative, note in EVIDENCE_PATHS:
        present = (ROOT / relative).exists()
        display = (
            md_link(relative)
            if present and (ROOT / relative).is_file()
            else f"`{relative}`"
        )
        status = "Present" if present else "Not found at this path"
        lines.append(
            f"| {label} | {display} ({status}) | {note} |"
        )

    lines.extend([
        "",
        "### Existing-evidence interpretation",
        "",
        "- `A00`–`A03`: existing-evidence binding review, "
        "not automatic new solves.",
        "- `D-BND-004`: solver-preparation records reuse "
        "`D-BND-002` geometry/mesh evidence; absence of its "
        "case-local preparation record is not a reason to remesh.",
        "- A prepared-only trial directory must not be counted as "
        "a completed or physically accepted FEM run.",
        "- Historical trial evidence may have authoritative records "
        "outside a particular expected trial-directory filename.",
        "",
        "## 5. Complete selected repository file inventory",
        "",
        "The tables below are derived from Git-listed non-ignored "
        "source, script, test, config and documentation files. "
        "A module's description is its actual source docstring "
        "when present. `Public symbols` lists top-level functions "
        "and classes; it is not a complete call graph.",
        "",
        f"**Indexed files:** {len(files)}; "
        f"Python modules parsed: {len(trees)}.",
        "",
    ])

    order = {
        "Repository entry points": 0,
        "Documentation": 1,
        "Configuration": 2,
        "Runnable scripts and maintenance tools": 3,
    }

    for section in sorted(
        sections,
        key=lambda name: (
            order.get(name, 4 if name.startswith("Source") else 5),
            name,
        ),
    ):
        group = sections[section]
        lines.extend([
            f"### {section} ({len(group)})",
            "",
        ])

        is_python_group = any(
            path.endswith(".py") for path in group
        )

        if is_python_group:
            lines.extend([
                "| File | Purpose from source | Public symbols |",
                "|---|---|---|",
            ])
            for relative in group:
                if relative.endswith(".py"):
                    desc = descriptions[relative]
                    exports = symbols[relative]
                else:
                    desc = "Non-Python resource; see linked file."
                    exports = "—"
                lines.append(
                    f"| {md_link(relative)} | {desc} | "
                    f"{exports} |"
                )
        else:
            lines.extend([
                "| File | Classification |",
                "|---|---|",
            ])
            for relative in group:
                lines.append(
                    f"| {md_link(relative)} | "
                    f"{section}; inspect the linked file for "
                    "its exact contents. |"
                )

        lines.append("")

    lines.extend([
        "## 6. Static source-dependency and test-reference index",
        "",
        "This index is computed from Python `import` and "
        "`from ... import ...` syntax. It reports **direct static "
        "references**, not runtime calls, behavioural test coverage "
        "or the entire transitive dependency graph.",
        "",
    ])

    sources = sorted(
        path for path in trees
        if path.startswith("src/threadrom/")
    )

    for relative in sources:
        imported = edges.get(relative, set())
        users = reverse.get(relative, set())
        direct_tests = {
            path for path in users if path.startswith("tests/")
        }
        other_users = users - direct_tests

        lines.extend([
            f"### {md_link(relative)}",
            "",
            f"- Module: `{module_name(relative)}`",
            f"- Direct in-repository imports: "
            f"{links_list(imported)}",
            f"- Directly importing tests: "
            f"{links_list(direct_tests)}",
            f"- Other direct importers: "
            f"{links_list(other_users)}",
            "",
        ])

    lines.extend([
        "## 7. Caveats and upkeep",
        "",
    ])

    for item in IMPORTANT:
        lines.append(f"- {item}")

    lines.extend([
        "",
        "### Maintaining this document",
        "",
        "From the repository root:",
        "",
        "```powershell",
        r".\.venv\Scripts\python.exe "
        r".\scripts\generate_threadrom_repository_atlas.py --check",
        "```",
        "",
        "`--check` compares a fresh render with this document "
        "without changing files. If it differs, review the "
        "repository changes, then deliberately regenerate after "
        "preserving the previous version.",
        "",
        "The generator refuses to overwrite an existing atlas with "
        "`--write`; it does not commit, launch simulations or "
        "modify historical evidence.",
        "",
        "**Future enhancement:** Maintain curated descriptions for "
        "high-value entry points where module docstrings are absent "
        "or incomplete, and review static import references alongside "
        "the actual tests before modifying critical execution paths.",
        "",
    ])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--write",
        action="store_true",
        help="Create a new atlas; refuse an existing target.",
    )
    mode.add_argument(
        "--check",
        action="store_true",
        help="Compare against the existing atlas without writing.",
    )
    args = parser.parse_args()

    if not (
        (ROOT / ".git").exists()
        and (ROOT / "src/threadrom").is_dir()
        and (ROOT / "docs/THREADROM_PHASE3_FACTORY_AND_ROM_ROADMAP.md").is_file()
    ):
        raise RuntimeError(
            "Expected ThreadROM repository and engineering reference."
        )

    result = render()
    data = result.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()

    if args.check:
        if not ATLAS.is_file():
            raise RuntimeError(
                "Atlas missing; cannot verify reproducibility."
            )
        if ATLAS.read_bytes() != data:
            raise RuntimeError(
                "Atlas differs from current source inventory. "
                "Review changes before deliberately regenerating."
            )
        print("ATLAS REGENERATION CHECK: PASS")
    else:
        ATLAS.parent.mkdir(parents=True, exist_ok=True)
        with ATLAS.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        print("ATLAS CREATED:", ATLAS)

    print("SHA256:", digest)
    print("Document lines:", len(result.splitlines()))
    print("Repository imports and symbols: AST-derived")
    print("Simulation/holdout content opened: 0")
    print("CAD/mesh/FEM executions: 0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ATLAS ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
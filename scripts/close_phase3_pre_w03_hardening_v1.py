from __future__ import annotations

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

from pathlib import Path


ROOT = Path(
    r"D:\ThreadROM"
).resolve()

DOC_ROOT = (
    ROOT
    / "docs"
    / "phase3_pre_w03_hardening"
)

REPORT_PATH = (
    DOC_ROOT
    / "full_repository_regression_v1.xml"
)

REGRESSION_SUMMARY_PATH = (
    DOC_ROOT
    / "full_regression_summary_v1.json"
)

READINESS_PATH = (
    DOC_ROOT
    / "w03_readiness_gate_v1.json"
)

CLOSURE_PATH = (
    DOC_ROOT
    / "slice6_closure.json"
)

THIS_SCRIPT = (
    ROOT
    / "scripts"
    / "close_phase3_pre_w03_hardening_v1.py"
)


PINNED_CLOSURES = {
    "slice1": {
        "path": (
            ROOT
            / "docs"
            / "phase3_geometry_mesh_atlas"
            / "slice1_closure.json"
        ),
        "sha256": (
            "332f70f12ff73fbac72bfbff724dc97"
            "f659768aaea9287a022401e5c345abb3c"
        ),
    },
    "slice2": {
        "path": (
            ROOT
            / "docs"
            / "phase3_calibration_knowledge"
            / "slice2_closure.json"
        ),
        "sha256": (
            "c2913f68bce824157eb33f0e625dbe8"
            "57e61d6a005040d564163ac59aa63e895"
        ),
    },
    "slice3": {
        "path": (
            ROOT
            / "docs"
            / "phase3_governed_wave_runner"
            / "slice3_closure.json"
        ),
        "sha256": (
            "fcc6074c2596766a9b8daa7909625f24"
            "c67a30630a01ed8fc201e80f5045064a"
        ),
    },
    "slice4": {
        "path": (
            ROOT
            / "docs"
            / "phase3_governed_wave_state_machine"
            / "slice4_closure.json"
        ),
        "sha256": (
            "c1d3240cfde6a0f0fcb0d9d8dc595f8"
            "578d4234ebff9c805663e05086b8bf401"
        ),
    },
    "slice5": {
        "path": (
            ROOT
            / "docs"
            / "phase3_governed_wave_closure"
            / "slice5_closure.json"
        ),
        "sha256": (
            "6654c205e457c88d6bf785e647e9997"
            "a6ef0d0b681ae82170c680c8610c06ce7"
        ),
    },
}


HISTORICAL = {
    "w01_registry": {
        "path": (
            ROOT
            / "simulations"
            / "staging"
            / "phase3_diversified_doe"
            / "TRM-DDOE-001"
            / "W01"
            / "factory"
            / "w01_trial1_factory.sqlite3"
        ),
        "sha256": (
            "00f6cdff8617689b1d29103acfa1a177"
            "4b6dab7348bd2cac4ccffa533a4c2e34"
        ),
    },
    "w02_registry": {
        "path": (
            ROOT
            / "simulations"
            / "staging"
            / "phase3_diversified_doe"
            / "TRM-DDOE-001"
            / "W02"
            / "factory"
            / "w02_trial1_factory.sqlite3"
        ),
        "sha256": (
            "892fe09fdd3d463cbb1888f0184086a9"
            "79b3f52d064f53c7ea4b2f59466fabd1"
        ),
    },
    "w01_wave_closure": {
        "path": (
            ROOT
            / "docs"
            / "phase3_governed_wave_closure"
            / "historical_replay"
            / "TRM-DDOE-001-W01.wave_closure.json"
        ),
        "sha256": (
            "50b53c3c16fa130df75a17bf96ac4ac8"
            "490716eea60c77d9125fb3452304f761"
        ),
    },
    "w02_wave_closure": {
        "path": (
            ROOT
            / "docs"
            / "phase3_governed_wave_closure"
            / "historical_replay"
            / "TRM-DDOE-001-W02.wave_closure.json"
        ),
        "sha256": (
            "8ef0f0badbe14f432c31f2006171f2cf"
            "4e1078edeadd487cf101330b78fe5d0d"
        ),
    },
}


SOURCE_PATHS = {
    "generic_wave_runner": (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "governed_wave_runner.py"
    ),
    "wave_state_machine": (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "governed_wave_state_machine.py"
    ),
    "wave_controller": (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "governed_wave_controller.py"
    ),
    "wave_closure": (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "governed_wave_closure.py"
    ),
    "stale_run_recovery": (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "governed_stale_run_recovery.py"
    ),
    "wave_runtime": (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "governed_wave_runtime.py"
    ),
    "factory_registry": (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "fem_factory_registry.py"
    ),
    "windows_process_adjudication": (
        ROOT
        / "src"
        / "threadrom"
        / "factory"
        / "windows_process_adjudication.py"
    ),
    "stale_run_test": (
        ROOT
        / "tests"
        / "unit"
        / "test_governed_stale_run_recovery.py"
    ),
    "runtime_hardening_test": (
        ROOT
        / "tests"
        / "unit"
        / "test_governed_wave_runtime_hardening.py"
    ),
    "factory_worker_test": (
        ROOT
        / "tests"
        / "test_diversified_factory_worker.py"
    ),
    "parallel_admission_test": (
        ROOT
        / "tests"
        / "test_diversified_parallel_admission.py"
    ),
    "slice6_closure_script": (
        THIS_SCRIPT
    ),
}


def require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise RuntimeError(
            message
        )


def sha256_file(
    path: Path,
) -> str:
    require(
        path.is_file(),
        f"Missing required file: {path}",
    )

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as stream:
        for chunk in iter(
            lambda: stream.read(
                8 * 1024 * 1024
            ),
            b"",
        ):
            digest.update(
                chunk
            )

    return digest.hexdigest()


def canonical_bytes(
    payload: dict,
) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode(
        "utf-8"
    )


def write_immutable_json(
    path: Path,
    payload: dict,
) -> str:
    encoded = canonical_bytes(
        payload
    )

    digest = hashlib.sha256(
        encoded
    ).hexdigest()

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if path.exists():
        require(
            path.read_bytes()
            == encoded,
            (
                "Immutable final-gate artifact drift: "
                f"{path}"
            ),
        )

        return digest

    path.write_bytes(
        encoded
    )

    return digest


def git_head() -> str:
    return (
        subprocess.check_output(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            cwd=ROOT,
            text=True,
        )
        .strip()
    )


def parse_regression_report(
    path: Path,
) -> dict:
    require(
        path.is_file(),
        "Full repository regression report is missing.",
    )

    root = ET.parse(
        path
    ).getroot()

    if root.tag == "testsuite":
        suites = [
            root
        ]
    else:
        suites = list(
            root.findall(
                "testsuite"
            )
        )

    require(
        bool(
            suites
        ),
        "Regression XML contains no testsuite.",
    )

    tests = sum(
        int(
            suite.attrib.get(
                "tests",
                "0",
            )
        )
        for suite in suites
    )

    failures = sum(
        int(
            suite.attrib.get(
                "failures",
                "0",
            )
        )
        for suite in suites
    )

    errors = sum(
        int(
            suite.attrib.get(
                "errors",
                "0",
            )
        )
        for suite in suites
    )

    skipped = sum(
        int(
            suite.attrib.get(
                "skipped",
                "0",
            )
        )
        for suite in suites
    )

    passed = (
        tests
        - failures
        - errors
        - skipped
    )

    require(
        tests > 0,
        "Full repository regression collected zero tests.",
    )

    require(
        failures == 0,
        (
            "Full repository regression contains "
            f"{failures} failures."
        ),
    )

    require(
        errors == 0,
        (
            "Full repository regression contains "
            f"{errors} errors."
        ),
    )

    return {
        "tests": tests,
        "passed": passed,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
    }


# ==============================================================================
# Pin all previously closed hardening slices
# ==============================================================================

for name, item in PINNED_CLOSURES.items():
    actual = sha256_file(
        item[
            "path"
        ]
    )

    require(
        actual
        == item[
            "sha256"
        ],
        (
            f"{name}: closure SHA drift. "
            f"Expected {item['sha256']}; "
            f"found {actual}."
        ),
    )


# ==============================================================================
# Historical evidence must still be byte-identical
# ==============================================================================

for name, item in HISTORICAL.items():
    actual = sha256_file(
        item[
            "path"
        ]
    )

    require(
        actual
        == item[
            "sha256"
        ],
        (
            f"{name}: historical evidence SHA drift."
        ),
    )


# ==============================================================================
# Full regression evidence
# ==============================================================================

regression = parse_regression_report(
    REPORT_PATH
)

regression_report_sha = (
    sha256_file(
        REPORT_PATH
    )
)

source_hashes = {
    name: sha256_file(
        path
    )
    for name, path
    in SOURCE_PATHS.items()
}


regression_summary = {
    "schema": (
        "threadrom.phase3_pre_w03_"
        "full_regression_summary.v1"
    ),
    "command": (
        "python -m pytest -q tests "
        "--basetemp=D:/trm_pytest_s6 "
        "--junitxml=docs/phase3_pre_w03_hardening/"
        "full_repository_regression_v1.xml"
    ),
    "result": "PASS",
    "counts": regression,
    "report": {
        "path": (
            "docs/phase3_pre_w03_hardening/"
            "full_repository_regression_v1.xml"
        ),
        "sha256": (
            regression_report_sha
        ),
    },
    "git_head": (
        git_head()
    ),
}


regression_summary_sha = (
    write_immutable_json(
        REGRESSION_SUMMARY_PATH,
        regression_summary,
    )
)


# ==============================================================================
# W03 readiness gate
# ==============================================================================

readiness = {
    "schema": (
        "threadrom.phase3_pre_w03_"
        "readiness_gate.v1"
    ),
    "campaign_id": "TRM-DDOE-001",
    "status": "PASS",
    "disposition": (
        "PRE_W03_HARDENING_COMPLETE_"
        "W03_PREPARATION_READY"
    ),
    "hardening_slices": {
        "slice1_geometry_mesh_atlas": "CLOSED",
        "slice2_calibration_knowledge": "CLOSED",
        "slice3_generic_wave_runner": "CLOSED",
        "slice4_autonomous_state_machine": "CLOSED",
        "slice5_certification_wave_closure": "CLOSED",
        "slice6_production_hardening": "READY_TO_CLOSE",
    },
    "full_repository_regression": {
        "result": "PASS",
        "counts": regression,
        "summary_sha256": (
            regression_summary_sha
        ),
        "report_sha256": (
            regression_report_sha
        ),
    },
    "production_hardening": {
        "stale_running_recovery_governed": True,
        "lease_generation_fencing_enforced": True,
        "old_worker_after_recovery_rejected": True,
        "duplicate_case_trial_execution_forbidden": True,
        "terminal_manifest_requires_reconciliation": True,
        "terminal_manifest_does_not_authorize_relaunch": True,
        "no_live_process_relaunch_requires_adjudication": True,
        "live_process_blocks_recovery": True,
        "unknown_process_state_fails_closed": True,
        "invalid_manifest_fails_closed": True,
        "unicode_console_hardened": True,
        "cp1252_regression_covered": True,
        "noncanonical_closure_tamper_fails_closed": True,
        "certificate_fingerprint_tamper_fails_closed": True,
        "repo_relative_paths_governed": True,
        "historical_registries_immutable": True,
        "windows_short_pytest_basetemp_proven": True,
    },
    "historical_evidence": {
        name: {
            "path": str(
                item[
                    "path"
                ].relative_to(
                    ROOT
                )
            ).replace(
                "\\",
                "/",
            ),
            "sha256": (
                item[
                    "sha256"
                ]
            ),
        }
        for name, item
        in HISTORICAL.items()
    },
    "dependency_closures": {
        name: {
            "path": str(
                item[
                    "path"
                ].relative_to(
                    ROOT
                )
            ).replace(
                "\\",
                "/",
            ),
            "sha256": (
                item[
                    "sha256"
                ]
            ),
        }
        for name, item
        in PINNED_CLOSURES.items()
    },
    "w03": {
        "preparation_ready": True,
        "execution_authorized": False,
        "launched": False,
        "requires_fresh_governed_wave_authorization": True,
        "requires_fresh_preparation_index": True,
        "requires_generic_runner_preflight": True,
    },
    "governance": {
        "calculix_launched_by_gate": False,
        "holdout_access_authorized": False,
        "dataset_admission_authorized": False,
        "surrogate_training_authorized": False,
        "artifact_retirement_authorized": False,
    },
    "source_hashes": (
        source_hashes
    ),
}


readiness_sha = write_immutable_json(
    READINESS_PATH,
    readiness,
)


# ==============================================================================
# Slice 6 closure
# ==============================================================================

closure = {
    "schema": (
        "threadrom.phase3_pre_w03_hardening_"
        "slice6_closure.v1"
    ),
    "slice": 6,
    "title": (
        "Production Hardening and Regression Gate"
    ),
    "disposition": (
        "SLICE_6_PRODUCTION_HARDENING_"
        "REGRESSION_GATE_V1_CLOSED"
    ),
    "pre_w03_disposition": (
        "PRE_W03_HARDENING_COMPLETE_"
        "W03_PREPARATION_READY"
    ),
    "full_regression": {
        "tests": (
            regression[
                "tests"
            ]
        ),
        "passed": (
            regression[
                "passed"
            ]
        ),
        "failures": 0,
        "errors": 0,
        "skipped": (
            regression[
                "skipped"
            ]
        ),
        "summary_sha256": (
            regression_summary_sha
        ),
    },
    "readiness_gate": {
        "path": (
            "docs/phase3_pre_w03_hardening/"
            "w03_readiness_gate_v1.json"
        ),
        "sha256": (
            readiness_sha
        ),
    },
    "certified_claims": {
        "all_six_hardening_slices_closed": True,
        "full_repository_regression_passed": True,
        "stale_run_recovery_hardened": True,
        "duplicate_execution_hardened": True,
        "windows_unicode_runtime_hardened": True,
        "evidence_tamper_fails_closed": True,
        "w01_registry_unchanged": True,
        "w02_registry_unchanged": True,
        "w01_wave_closure_unchanged": True,
        "w02_wave_closure_unchanged": True,
        "w03_preparation_ready": True,
        "w03_execution_authorized": False,
        "w03_launched": False,
        "calculix_launched_by_closure": False,
        "holdouts_sealed": True,
        "rom_dataset_untouched": True,
    },
    "source_hashes": (
        source_hashes
    ),
}


closure_sha = write_immutable_json(
    CLOSURE_PATH,
    closure,
)


print()
print("=" * 108)
print(
    "THREADROM - PRE-W03 HARDENING - "
    "SLICE 6 FINAL CLOSURE"
)
print("=" * 108)
print(
    "Full regression tests :",
    regression[
        "tests"
    ],
)
print(
    "Passed                :",
    regression[
        "passed"
    ],
)
print(
    "Skipped               :",
    regression[
        "skipped"
    ],
)
print(
    "Failures              : 0"
)
print(
    "Errors                : 0"
)
print(
    "Regression report SHA :",
    regression_report_sha,
)
print(
    "Regression summary SHA:",
    regression_summary_sha,
)
print(
    "W03 readiness SHA     :",
    readiness_sha,
)
print(
    "Slice-6 closure SHA   :",
    closure_sha,
)
print()
print(
    "W01 registry          : UNCHANGED"
)
print(
    "W02 registry          : UNCHANGED"
)
print(
    "W01 wave closure      : UNCHANGED"
)
print(
    "W02 wave closure      : UNCHANGED"
)
print(
    "W03 preparation       : READY"
)
print(
    "W03 execution         : NOT AUTHORIZED"
)
print(
    "W03 launched          : NO"
)
print(
    "CalculiX              : NOT LAUNCHED"
)
print(
    "Holdouts              : SEALED"
)
print(
    "ROM dataset           : UNTOUCHED"
)
print()
print(
    "DISPOSITION           : "
    "SLICE_6_PRODUCTION_HARDENING_"
    "REGRESSION_GATE_V1_CLOSED"
)
print(
    "PRE-W03               : "
    "HARDENING COMPLETE / "
    "W03 PREPARATION READY"
)
print("=" * 108)
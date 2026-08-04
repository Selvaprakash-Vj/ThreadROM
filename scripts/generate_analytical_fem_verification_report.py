"""Generate the governed analytical-to-FEM verification matrix."""

from pathlib import Path

from threadrom.engineering.analytical_fem_verification import (
    load_analytical_fem_verification_definition,
)
from threadrom.engineering.analytical_fem_verification_result import (
    build_analytical_fem_verification_result,
    write_analytical_fem_verification_artifacts,
)


def main() -> None:
    """Generate the governed verification artifacts."""

    root = Path(__file__).resolve().parents[1]

    definition = load_analytical_fem_verification_definition(
        root / "config" / "analytical_fem_verification.toml"
    )

    result = build_analytical_fem_verification_result(definition)

    json_path, report_path = write_analytical_fem_verification_artifacts(
        root,
        result,
    )

    print("ANALYTICAL-TO-FEM VERIFICATION MATRIX: GENERATED")
    print(f"Overall status: {result.overall_status}")
    print(f"Resolved targets: {result.resolved_target_count}")
    print(f"Unresolved targets: {result.unresolved_target_count}")
    print(f"JSON: {json_path}")
    print(f"Report: {report_path}")


if __name__ == "__main__":
    main()

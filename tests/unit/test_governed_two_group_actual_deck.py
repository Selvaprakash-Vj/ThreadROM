"""Two-group material transfer through the real production-deck test.

Only the member properties are synthetically substituted. This is a
software-path regression, not material-variation FEM certification.
"""

from dataclasses import asdict, is_dataclass, replace
import importlib.util
import inspect
import json
from pathlib import Path
from unittest.mock import patch

import pytest


TEST_DIRECTORY = Path(__file__).resolve().parent
EXISTING_TEST = (
    TEST_DIRECTORY / "test_phase3_fem_production_deck.py"
)


def _load_existing_test():
    spec = importlib.util.spec_from_file_location(
        "_threadrom_existing_real_deck_test",
        EXISTING_TEST,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Existing real-deck test cannot be loaded.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    test = module.test_real_production_deck_uses_resolved_guidance
    signature = inspect.signature(test)

    if tuple(signature.parameters) != ("tmp_path",):
        raise RuntimeError(
            "Existing real-deck test fixture contract changed: "
            + str(signature)
        )

    return module, test


def _deck_materials(path):
    cards = {}
    sections = {}
    current = None
    waiting_for_elastic = False

    with Path(path).open(
        "r", encoding="utf-8-sig"
    ) as stream:
        for line in stream:
            value = line.strip()
            upper = value.upper()

            if upper.startswith("**") or not value:
                continue

            if upper.startswith("*MATERIAL,"):
                fields = [
                    part.strip()
                    for part in upper.split(",")
                ]
                names = [
                    part.split("=", 1)[1]
                    for part in fields
                    if part.startswith("NAME=")
                ]
                if len(names) != 1 or names[0] in cards:
                    raise AssertionError(
                        "Duplicate or malformed material definition."
                    )
                current = names[0]
                cards[current] = None
                waiting_for_elastic = False

            elif upper.startswith("*ELASTIC"):
                if current is None or cards[current] is not None:
                    raise AssertionError(
                        "Unexpected elastic material card."
                    )
                waiting_for_elastic = True

            elif waiting_for_elastic and not upper.startswith("*"):
                properties = tuple(
                    float(part.strip())
                    for part in value.split(",")
                )
                if len(properties) != 2:
                    raise AssertionError(
                        "Unexpected elastic-property record."
                    )
                cards[current] = properties
                waiting_for_elastic = False

            elif upper.startswith("*SOLID SECTION,"):
                fields = dict(
                    part.strip().split("=", 1)
                    for part in upper.split(",")[1:]
                    if "=" in part
                )
                if "ELSET" in fields and "MATERIAL" in fields:
                    sections[fields["ELSET"]] = fields["MATERIAL"]

    if not cards or any(value is None for value in cards.values()):
        raise AssertionError(
            "Incomplete production-deck elastic material cards."
        )

    return cards, sections


def test_real_deck_uses_two_distinct_material_groups(
    tmp_path,
):
    module, existing_test = _load_existing_test()

    original_bundle = module.build_generic_fem_definition_bundle
    original_writer = module.write_fem_production_deck

    observations = {}

    for mode in ("original", "mixed"):
        output_dir = tmp_path / mode
        output_dir.mkdir()

        def bundle_wrapper(resolved, **kwargs):
            if mode == "mixed":
                if (
                    not is_dataclass(resolved)
                    or len(resolved.member_materials) != 2
                    or not all(
                        is_dataclass(material)
                        for material in resolved.member_materials
                    )
                ):
                    raise AssertionError(
                        "Resolved material contract changed."
                    )

                members = tuple(
                    replace(
                        material,
                        youngs_modulus_mpa=70000.0,
                        poissons_ratio=0.33,
                    )
                    for material in resolved.member_materials
                )
                resolved = replace(
                    resolved,
                    member_materials=members,
                )

            bundle = original_bundle(resolved, **kwargs)
            observations.setdefault(mode, {})["bundle"] = bundle

            if mode == "mixed":
                assert (
                    bundle.preparation.physics.member_youngs_modulus_mpa
                    == 70000.0
                )
                assert (
                    bundle.preparation.physics.member_poissons_ratio
                    == 0.33
                )
                assert (
                    bundle.transfer.member_youngs_modulus_mpa
                    == 70000.0
                )
                assert (
                    bundle.transfer.member_poissons_ratio
                    == 0.33
                )

            # Exercise the production preparation's actual dataclass
            # fields through its JSON-compatible serialization shape.
            serialized = json.loads(
                json.dumps(
                    asdict(bundle.preparation.physics),
                    allow_nan=False,
                )
            )
            assert "member_youngs_modulus_mpa" in serialized
            assert "member_poissons_ratio" in serialized
            return bundle

        def writer_wrapper(**kwargs):
            result = original_writer(**kwargs)
            output = Path(kwargs["input_path"])
            assert output.is_file()
            observations.setdefault(mode, {})["deck"] = output
            observations[mode]["transfer"] = kwargs["transfer"]
            return result

        with (
            patch.object(
                module,
                "build_generic_fem_definition_bundle",
                side_effect=bundle_wrapper,
            ),
            patch.object(
                module,
                "write_fem_production_deck",
                side_effect=writer_wrapper,
            ),
        ):
            # Actual existing production-deck test and writer;
            # synthetic member properties in the mixed pass only.
            existing_test(output_dir)

        assert "deck" in observations[mode]
        assert "bundle" in observations[mode]

    baseline = observations["original"]
    mixed = observations["mixed"]

    baseline_cards, baseline_sections = _deck_materials(
        baseline["deck"]
    )
    mixed_cards, mixed_sections = _deck_materials(
        mixed["deck"]
    )

    for item in (baseline, mixed):
        transfer = item["transfer"]
        assert transfer.bolt_material_name != transfer.member_material_name
        assert transfer.nut_material_name != transfer.member_material_name

    transfer = mixed["transfer"]
    bolt_name = transfer.bolt_material_name.upper()
    nut_name = transfer.nut_material_name.upper()
    member_name = transfer.member_material_name.upper()

    expected_fastener = (
        transfer.youngs_modulus_mpa,
        transfer.poissons_ratio,
    )
    expected_members = (70000.0, 0.33)

    assert mixed_cards[bolt_name] == expected_fastener
    assert mixed_cards[nut_name] == expected_fastener
    assert mixed_cards[member_name] == expected_members

    baseline_transfer = baseline["transfer"]
    baseline_expected = (
        baseline_transfer.youngs_modulus_mpa,
        baseline_transfer.poissons_ratio,
    )
    assert baseline_cards == {
        baseline_transfer.bolt_material_name.upper():
            baseline_expected,
        baseline_transfer.nut_material_name.upper():
            baseline_expected,
        baseline_transfer.member_material_name.upper():
            baseline_expected,
    }

    assert baseline_sections == mixed_sections

    assert mixed_sections["BOLT"] == bolt_name
    assert mixed_sections["NUT"] == nut_name
    assert mixed_sections["HEAD_SIDE_MEMBER"] == member_name
    assert mixed_sections["NUT_SIDE_MEMBER"] == member_name

    print(
        "\nREAL DECK: fastener E/nu =",
        mixed_cards[bolt_name],
    )
    print(
        "REAL DECK: member E/nu =",
        mixed_cards[member_name],
    )
    print("REAL DECK: four section assignments verified")
    print("LEGACY DECK: original common-property cards verified")
    print("PREPARATION: member properties serialized")
    print("FEM solver executions: 0")

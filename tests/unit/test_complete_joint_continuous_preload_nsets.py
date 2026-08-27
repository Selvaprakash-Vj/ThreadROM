from threadrom.solver.complete_joint_continuous_preload import (
    render_calculix_node_set,
)


def test_render_calculix_node_set() -> None:
    text = render_calculix_node_set(
        name="BOLT_THERMAL",
        node_ids=(1, 2, 3, 5, 8),
    )

    assert text.startswith("*NSET, NSET=BOLT_THERMAL\n")
    assert "1, 2, 3, 5, 8" in text


def test_render_calculix_node_set_rejects_duplicate_ids() -> None:
    try:
        render_calculix_node_set(
            name="BOLT_THERMAL",
            node_ids=(1, 2, 2, 3),
        )
    except ValueError as error:
        assert "duplicate" in str(error).lower()
    else:
        raise AssertionError(
            "Duplicate node IDs must be rejected."
        )


def test_render_calculix_node_set_rejects_nonpositive_ids() -> None:
    try:
        render_calculix_node_set(
            name="BOLT_THERMAL",
            node_ids=(0, 1, 2),
        )
    except ValueError as error:
        assert "positive" in str(error).lower()
    else:
        raise AssertionError(
            "Non-positive CalculiX node IDs must be rejected."
        )
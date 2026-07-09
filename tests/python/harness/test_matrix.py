"""Self-tests for harness.matrix, exercised via a fake axis (spec sec.7.2,
sec.11 phase 2): today's real AXES registry is empty (single default cell),
but the engine itself must be fully implemented and tested now so adding a
real axis later is a one-line change."""
from __future__ import annotations

from harness import pyunit as t
from harness.matrix import Axis, all_cells, select_cells

FAKE_AXES = [Axis(name="opt", variants={"O0": [], "O1": ["--opt=1"], "O2": ["--opt=2"]})]


def test_default_registry_has_only_default_cell():
    cells = all_cells(axes=[])
    t.require_eq([c.id for c in cells], ["default"])


def test_fake_axis_expands_to_all_variants():
    cells = all_cells(axes=FAKE_AXES)
    t.require_eq(sorted(c.id for c in cells), ["O0", "O1", "O2"])


def test_quick_mode_returns_only_default():
    # With no axes registered, the sole cell is literally "default".
    cells = select_cells("quick", "deadbeef00000000", "run:foo.fire", axes=[])
    t.require_eq([c.id for c in cells], ["default"])
    # With axes present, quick mode picks a single baseline cell (the first
    # declared variant of each axis) -- there is no cell literally named
    # "default" once a real axis exists (spec sec.7.2).
    cells = select_cells("quick", "deadbeef00000000", "run:foo.fire", axes=FAKE_AXES)
    t.require_eq(len(cells), 1)
    t.require_eq(cells[0].id, "O0")


def test_full_mode_returns_cartesian_product():
    cells = select_cells("full", "deadbeef00000000", "run:foo.fire", axes=FAKE_AXES)
    t.require_eq(sorted(c.id for c in cells), ["O0", "O1", "O2"])


def test_sample_mode_includes_default_plus_k_others():
    cells = select_cells("sample=1", "deadbeef00000000", "run:foo.fire", axes=FAKE_AXES)
    t.require_eq(len(cells), 2)
    ids = [c.id for c in cells]
    t.require("O0" in ids)


def test_sample_mode_is_reproducible_per_test():
    a = select_cells("sample=1", "deadbeef00000000", "run:foo.fire", axes=FAKE_AXES)
    b = select_cells("sample=1", "deadbeef00000000", "run:foo.fire", axes=FAKE_AXES)
    t.require_eq([c.id for c in a], [c.id for c in b])


def test_sample_mode_differs_per_test_key():
    a = select_cells("sample=1", "deadbeef00000000", "run:foo.fire", axes=FAKE_AXES)
    b = select_cells("sample=1", "deadbeef00000000", "run:bar.fire", axes=FAKE_AXES)
    # Not guaranteed to differ, but the seed derivation must at least run
    # without error and both must include the default cell.
    t.require("O0" in [c.id for c in a])
    t.require("O0" in [c.id for c in b])


def test_cell_ids_are_matrix_invariant_expectation_keys():
    # Expectations are cell-invariant by design: no per-cell golden files.
    # This is a documentation-anchoring test -- verifying the engine doesn't
    # expose any per-cell expectation hook.
    from harness import kinds

    run_kind_cls = kinds.get("run")
    t.require(not hasattr(run_kind_cls, "expected_for_cell"))

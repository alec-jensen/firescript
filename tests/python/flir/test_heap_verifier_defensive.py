"""Unit tests for defensive/unreachable-from-source guards in
firescript/flir/heap_verifier.py (the Tier-2 heap-token verifier).

Each guard here is unreachable through the normal compile pipeline because
a caller-side invariant already rules it out:

- `_meet_states([])`: forward_dataflow (firescript/ir_analysis.py) only
  calls `meet(pred_outs)` when `pred_outs` is non-empty; for zero
  predecessors it substitutes `bottom` directly. So the empty-list branch
  in `_meet_states` can never fire via the dataflow driver.
- `_HeapChecker.run()`'s `if not self.function.blocks: return`: the only
  caller, `verify_heap_lifecycle`, is only invoked by flir/verifier.py's
  Tier-1 pass when `function.blocks` is already truthy (see verifier.py's
  `and function.blocks` guard before dispatching to Tier-2).
- The `if block.id not in self.cfg.reachable: continue` loop in `run()`:
  Tier-1's FLIRV-S1 rule rejects any module containing an unreachable
  block before Tier-2 ever runs, so a real CFG passed to `_HeapChecker`
  never has blocks outside `cfg.reachable`.
- `_ident_text`'s `kind == "slot"` branch: every Identifier this module
  constructs is tagged `"temp"` (see `_identifier_of`); no code path ever
  builds a `("slot", ...)` tuple, so that branch of `_ident_text` is dead
  under the module's own usage, despite the docstring's discussion of
  "slot" identities.

These are all driven directly against the internal classes/functions per
the project's established pattern for covering defensive guards that
cannot be reached from real .fire source."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from ir_analysis import CFG  # noqa: E402
from flir.heap_verifier import _HeapChecker, _meet_states, _State  # noqa: E402
from flir.ir import FLIRFunction, FLIRModule, Ret  # noqa: E402


def _make_checker(function: FLIRFunction, cfg: CFG) -> _HeapChecker:
    module = FLIRModule("firescript")
    return _HeapChecker(module, function, {}, {}, cfg, {}, [])


def test_meet_states_of_empty_list_returns_default_state():
    result = _meet_states([])
    t.require(isinstance(result, _State), "expected a _State instance")
    t.require(result.tokens == {}, f"expected no tokens, got {result.tokens}")
    t.require(result.slot_alias == {}, f"expected no slot_alias, got {result.slot_alias}")


def test_run_on_function_with_no_blocks_returns_immediately():
    function = FLIRFunction("empty_fn")
    cfg = CFG([], "L0", {})
    checker = _make_checker(function, cfg)
    # Must not raise (e.g. by indexing function.blocks[0]) and must leave
    # violations empty.
    checker.run()
    t.require(checker.violations == [], f"expected no violations, got {checker.violations}")


def test_run_skips_block_not_in_cfg_reachable():
    function = FLIRFunction("fn_with_unreachable_block")
    entry = function.new_block()
    entry.add(Ret())
    orphan = function.new_block()
    orphan.add(Ret())
    # Hand-build a CFG where only `entry` is reachable, even though
    # `orphan` is present in function.blocks -- this can't happen via the
    # real pipeline (Tier-1's FLIRV-S1 would reject it first), but directly
    # exercises the `continue` guard in _HeapChecker.run().
    cfg = CFG([entry.id, orphan.id], entry.id, {entry.id: [], orphan.id: []})
    checker = _make_checker(function, cfg)
    checker.run()  # must not raise despite `orphan` missing from in_states
    t.require(checker.violations == [], f"expected no violations, got {checker.violations}")


def test_ident_text_slot_kind_branch():
    function = FLIRFunction("fn")
    cfg = CFG([], "L0", {})
    checker = _make_checker(function, cfg)
    text = checker._ident_text(("slot", "counter"))
    t.require(text == "slot 'counter'", f"unexpected ident text: {text!r}")

"""Unit tests for firescript/ir_analysis.py, the shared CFG/dominance/
dataflow machinery both fir/verifier.py and flir/verifier.py build on.
Placed alongside the fir/ unit tests (ir_analysis.py has no fir/flir
prefix of its own -- it's imported directly as `ir_analysis` by both
levels' verifiers and ownership checkers)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from ir_analysis import build_cfg, compute_dominators, dominates  # noqa: E402


def test_dominates_returns_false_for_node_missing_from_idom():
    # A node absent from `idom` (e.g. one unreachable from cfg.entry, so
    # compute_dominators never assigned it an immediate dominator) can
    # never be shown to dominate, or be dominated by, anything.
    cfg = build_cfg(["A", "B"], "A", lambda b: {"A": ["B"], "B": []}[b])
    idom = compute_dominators(cfg)
    t.require("C" not in idom, "test setup: C must be absent from idom")
    t.require(dominates(idom, "C", "B") is False, "unknown 'a' should not dominate")
    t.require(dominates(idom, "A", "C") is False, "nothing should dominate an unknown 'b'")


def test_dominates_breaks_out_of_a_cyclic_idom_chain():
    # dominates() walks idom[node] up to the root; a well-formed idom map
    # from compute_dominators() is always acyclic (a tree rooted at
    # idom[entry] == entry), so this cyclic map is synthetic -- but
    # dominates() is a general-purpose helper over any idom mapping, and
    # must not infinite-loop if handed a malformed one.
    idom = {"A": "A", "B": "C", "C": "B"}  # B and C point at each other, never reaching "A"
    t.require(dominates(idom, "A", "B") is False, "cyclic chain must terminate via the seen-guard, not dominate")


def test_compute_dominators_basic_diamond():
    # entry -> then/else -> join; join's idom is entry (the two branches
    # don't dominate each other, so the intersection is their common
    # ancestor).
    successors = {"entry": ["then", "else"], "then": ["join"], "else": ["join"], "join": []}
    cfg = build_cfg(list(successors), "entry", lambda b: successors[b])
    idom = compute_dominators(cfg)
    t.require_eq(idom["entry"], "entry")
    t.require_eq(idom["then"], "entry")
    t.require_eq(idom["else"], "entry")
    t.require_eq(idom["join"], "entry")
    t.require(dominates(idom, "entry", "join"), "entry should dominate join")
    t.require(not dominates(idom, "then", "join"), "then alone should not dominate join")

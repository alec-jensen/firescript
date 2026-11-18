"""Edge-case unit tests for the shared CFG/dominance/dataflow machinery in
firescript/ir_analysis.py (CFG construction and reverse postorder,
compute_dominators on joins and loops, dominates/instruction_dominates
boundaries, forward_dataflow fixpoint behavior, Violation formatting) plus
the small FLIR pieces they exercise (FLIRStruct.finalize/field, jmp/null/
float constant formatting, textual dump of entry/externs/globals)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from flir.ir import (  # noqa: E402
    ConstFloat,
    ConstNull,
    F64,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    I32,
    I64,
    Jmp,
    Ret,
    VOID,
    ptr_to,
)
from flir.textual import dump_flir_module  # noqa: E402
from ir_analysis import (  # noqa: E402
    Violation,
    build_cfg,
    compute_dominators,
    dominates,
    forward_dataflow,
    instruction_dominates,
)


def _cfg(edges: dict[str, list[str]], order: list[str], entry: str = "A"):
    return build_cfg(order, entry, lambda b: edges.get(b, []))


DIAMOND = {"A": ["B", "C"], "B": ["D"], "C": ["D"], "D": []}
LOOP = {"A": ["H"], "H": ["B", "X"], "B": ["H"], "X": []}


# -- CFG / reverse postorder -----------------------------------------------------

def test_cfg_predecessors_follow_declaration_order():
    cfg = _cfg(DIAMOND, ["A", "B", "C", "D"])
    t.require_eq(cfg.predecessors["D"], ["B", "C"])
    t.require_eq(cfg.predecessors["A"], [])


def test_cfg_rpo_puts_entry_first_and_join_after_both_branches():
    cfg = _cfg(DIAMOND, ["A", "B", "C", "D"])
    t.require_eq(cfg.rpo[0], "A")
    t.require(cfg.rpo.index("D") > cfg.rpo.index("B") and cfg.rpo.index("D") > cfg.rpo.index("C"))


def test_cfg_unreachable_block_is_excluded_from_reachable_but_listed_last_in_rpo():
    cfg = _cfg({"A": ["B"], "B": [], "Z": ["B"]}, ["A", "B", "Z"])
    t.require_eq(cfg.reachable, {"A", "B"})
    t.require_eq(cfg.rpo[-1], "Z")
    t.require_eq(cfg.predecessors["B"], ["A", "Z"])


def test_cfg_with_entry_missing_from_block_ids_has_nothing_reachable():
    cfg = _cfg({}, ["X", "Y"], entry="A")
    t.require_eq(cfg.reachable, set())
    t.require_eq(cfg.rpo, ["X", "Y"])


def test_cfg_edges_to_unknown_blocks_are_ignored_for_predecessors():
    cfg = _cfg({"A": ["B", "ghost"], "B": []}, ["A", "B"])
    t.require_eq(cfg.predecessors, {"A": [], "B": ["A"]})


def test_cfg_rpo_is_deterministic_across_builds():
    first = _cfg(LOOP, ["A", "H", "B", "X"]).rpo
    for _ in range(5):
        t.require_eq(_cfg(LOOP, ["A", "H", "B", "X"]).rpo, first)


# -- dominators ---------------------------------------------------------------------------

def test_dominators_of_diamond_join_is_the_branch_point():
    idom = compute_dominators(_cfg(DIAMOND, ["A", "B", "C", "D"]))
    t.require_eq(idom, {"A": "A", "B": "A", "C": "A", "D": "A"})


def test_dominators_of_loop_header_and_body():
    idom = compute_dominators(_cfg(LOOP, ["A", "H", "B", "X"]))
    t.require_eq(idom["H"], "A")
    t.require_eq(idom["B"], "H")
    t.require_eq(idom["X"], "H")


def test_dominators_omit_unreachable_blocks():
    idom = compute_dominators(_cfg({"A": ["B"], "B": [], "Z": ["B"]}, ["A", "B", "Z"]))
    t.require("Z" not in idom)
    t.require_eq(idom["B"], "A")


def test_dominators_nested_diamond_intersects_up_the_tree():
    edges = {"A": ["B", "E"], "B": ["C", "D"], "C": ["F"], "D": ["F"], "E": ["G"], "F": ["G"], "G": []}
    idom = compute_dominators(_cfg(edges, ["A", "B", "C", "D", "E", "F", "G"]))
    t.require_eq(idom["F"], "B")
    t.require_eq(idom["G"], "A")


def test_dominates_is_reflexive_even_for_unknown_blocks():
    idom = compute_dominators(_cfg(DIAMOND, ["A", "B", "C", "D"]))
    t.require(dominates(idom, "B", "B"))
    t.require(dominates(idom, "nowhere", "nowhere"))


def test_dominates_false_when_either_block_is_not_in_idom():
    idom = compute_dominators(_cfg(DIAMOND, ["A", "B", "C", "D"]))
    t.require(not dominates(idom, "A", "nowhere"))
    t.require(not dominates(idom, "nowhere", "A"))


def test_dominates_ancestor_yes_sibling_no():
    idom = compute_dominators(_cfg(DIAMOND, ["A", "B", "C", "D"]))
    t.require(dominates(idom, "A", "D"))
    t.require(not dominates(idom, "B", "D"))
    t.require(not dominates(idom, "B", "C"))
    t.require(not dominates(idom, "D", "A"))


def test_instruction_dominates_same_block_orders_by_index_strictly():
    idom = compute_dominators(_cfg(DIAMOND, ["A", "B", "C", "D"]))
    t.require(instruction_dominates(idom, "B", 0, "B", 1))
    t.require(not instruction_dominates(idom, "B", 1, "B", 1))
    t.require(not instruction_dominates(idom, "B", 2, "B", 1))


def test_instruction_dominates_across_blocks_ignores_indices():
    idom = compute_dominators(_cfg(DIAMOND, ["A", "B", "C", "D"]))
    t.require(instruction_dominates(idom, "A", 99, "D", 0))
    t.require(not instruction_dominates(idom, "B", 0, "D", 5))


# -- forward dataflow --------------------------------------------------------------------------

def _reaching(cfg, gen: dict[str, frozenset]):
    """May-reach analysis over frozensets of block ids (union meet)."""
    def transfer(b, state):
        return state | gen.get(b, frozenset())

    def meet(states):
        out = frozenset()
        for s in states:
            out = out | s
        return out

    return forward_dataflow(cfg, transfer, meet, frozenset(), frozenset())


def test_forward_dataflow_diamond_join_merges_both_branches():
    cfg = _cfg(DIAMOND, ["A", "B", "C", "D"])
    ins, outs = _reaching(cfg, {"A": frozenset("a"), "B": frozenset("b"), "C": frozenset("c")})
    t.require_eq(ins["D"], frozenset("abc"))
    t.require_eq(ins["A"], frozenset())
    t.require_eq(outs["D"], frozenset("abc"))


def test_forward_dataflow_loop_reaches_fixpoint_through_back_edge():
    cfg = _cfg(LOOP, ["A", "H", "B", "X"])
    ins, _outs = _reaching(cfg, {"B": frozenset("b")})
    # B's facts flow around the back edge into the loop header and exit.
    t.require_eq(ins["H"], frozenset("b"))
    t.require_eq(ins["X"], frozenset("b"))


def test_forward_dataflow_covers_only_reachable_blocks():
    cfg = _cfg({"A": ["B"], "B": [], "Z": ["B"]}, ["A", "B", "Z"])
    ins, outs = _reaching(cfg, {"Z": frozenset("z"), "A": frozenset("a")})
    t.require_eq(set(ins), {"A", "B"})
    t.require_eq(set(outs), {"A", "B"})
    t.require_eq(ins["B"], frozenset("a"))  # the unreachable pred contributes nothing


def test_forward_dataflow_entry_uses_entry_state_not_meet_of_back_edge_preds():
    edges = {"A": ["B"], "B": ["A"]}
    cfg = _cfg(edges, ["A", "B"])
    seed = frozenset("s")

    def transfer(b, state):
        return state | frozenset(b.lower())

    def meet(states):
        out = frozenset()
        for s in states:
            out = out | s
        return out

    ins, _ = forward_dataflow(cfg, transfer, meet, seed, frozenset())
    t.require_eq(ins["A"], seed)
    t.require_eq(ins["B"], frozenset("sa"))


def test_forward_dataflow_single_block_cfg_uses_entry_state():
    """The lone entry block's in-state is the seed state and its out-state
    is the transfer of that seed."""
    cfg = _cfg({"A": []}, ["A"])
    ins, outs = _reaching(cfg, {"A": frozenset("a")})
    t.require_eq(ins, {"A": frozenset()})
    t.require_eq(outs, {"A": frozenset("a")})


# -- Violation -------------------------------------------------------------------------------------

def test_violation_location_levels():
    t.require_eq(Violation("R", "FLIR", "f", "m").location(), "f")
    t.require_eq(Violation("R", "FLIR", "f", "m", "L1").location(), "f/L1")
    t.require_eq(Violation("R", "FLIR", "f", "m", "L1", 3).location(), "f/L1[3]")
    # an instruction index without a block id is not shown
    t.require_eq(Violation("R", "FLIR", "f", "m", None, 3).location(), "f")


def test_violation_format_appends_instruction_text_only_when_present():
    plain = Violation("FLIRV-S1", "FLIR", "f", "boom", "L0", 1)
    t.require_eq(plain.format(), "FLIRV-S1 in f/L0[1]: boom")
    withtext = Violation("FLIRV-S1", "FLIR", "f", "boom", "L0", 1, "ret")
    t.require_eq(withtext.format(), "FLIRV-S1 in f/L0[1]: boom\n    ret")


# -- ir.py leftovers ---------------------------------------------------------------------------------

def test_struct_finalize_gives_empty_struct_size_one():
    s = FLIRStruct("Empty")
    s.finalize()
    t.require_eq(s.size, 1)


def test_struct_finalize_rounds_size_up_to_alignment():
    s = FLIRStruct("S")
    s.fields = [("a", I64, 0), ("b", I32, 8)]
    s.size = 12
    s.align = 8
    s.finalize()
    t.require_eq(s.size, 16)


def test_struct_field_lookup_returns_entry_and_raises_for_missing():
    s = FLIRStruct("S")
    s.fields = [("a", I32, 0), ("b", I64, 8)]
    t.require_eq(s.field("b"), ("b", I64, 8))
    try:
        s.field("nope")
        t.require(False, "no KeyError raised")
    except KeyError as e:
        t.require("has no field nope" in str(e), str(e))


def test_jmp_null_and_float_constant_formatting_via_dump():
    func = FLIRFunction("f", return_type=VOID)
    module = FLIRModule("firescript")
    module.add_function(func)
    entry, tail = func.new_block(), func.new_block()
    entry.add(ConstFloat("1.5", F64))
    entry.add(ConstNull())
    entry.add(Jmp(tail.id))
    tail.add(Ret())
    text = dump_flir_module(module)
    t.require("fconst.f64 1.5" in text, text)
    t.require("nullconst" in text, text)
    t.require(f"jmp {tail.id}" in text, text)


# -- textual dump of module-level declarations ----------------------------------------------------------

def test_dump_includes_entry_externs_and_globals_in_deterministic_order():
    module = FLIRModule("m")
    module.entry_function = "main"
    module.externs["Zeta"] = ("kernel32.dll", I32, [I64, ptr_to("i8")])
    module.externs["Alpha"] = ("user32.dll", VOID, [])
    module.globals.append(("greeting", ptr_to("i8"), '"hi"'))
    module.mutable_globals.append(("counter", I32))
    main = FLIRFunction("main", return_type=VOID)
    module.add_function(main)
    main.new_block().add(Ret())
    text = dump_flir_module(module)
    lines = text.splitlines()
    t.require_eq(lines[0], "flir module m")
    t.require_eq(lines[1], "entry @main")
    # externs are sorted by symbol name regardless of insertion order
    t.require_eq(lines[2], 'extern @Alpha() -> void from "user32.dll"')
    t.require_eq(lines[3], 'extern @Zeta(i64, ptr<i8>) -> i32 from "kernel32.dll"')
    t.require('global greeting: ptr<i8> = "hi"' in text, text)
    t.require("global mut counter: i32 = 0" in text, text)
    t.require_eq(dump_flir_module(module), text)


def test_dump_omits_entry_line_when_no_entry_function():
    module = FLIRModule("m")
    t.require_eq(dump_flir_module(module), "flir module m\n")

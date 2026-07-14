"""Additional unit tests for firescript/fir/ownership_verifier.py, filling
coverage gaps left by test_verifier_ownership.py: dataflow-merge behavior,
rarely hit branches in identifier resolution and enum-guard collection, and
a few pure helper functions.

Some cases here call the Tier-2 entry points (verify_ownership,
verify_generator_dominance, verify_enum_payload_guards) directly against a
hand-built FIRFunction/CFG/idom, bypassing FIRModule.validate() (which runs
the Tier-1 verifier first and would reject some of these hand-built
malformed operands, such as a bare Value() used as an instruction operand,
before Tier-2 ever ran). Tier-2 assumes Tier-1 already passed in the normal
pipeline, so exercising it directly like this is the only way to reach a
few defensive branches (e.g. `_safe_resolve`'s "<?>" fallback) that Tier-1
would otherwise always intercept first.
"""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from ir_analysis import build_cfg, compute_dominators  # noqa: E402
from fir import FIRBuilder, FIRFunction, FIRModule, TypeDef, make_simple  # noqa: E402
from fir.ir_module import EnumVariantDef  # noqa: E402
from fir.ir_types import GeneratorType  # noqa: E402
from fir.ir_node import (  # noqa: E402
    BinaryOpInst,
    BranchInst,
    CallInst,
    ConstructVariantInst,
    DeclareLocalInst,
    DropInst,
    ExtractPayloadFieldInst,
    ExtractTagInst,
    GenValueInst,
    IntLiteralInst,
    JumpInst,
    ReturnInst,
    Value,
)
from fir.ownership_verifier import (  # noqa: E402
    _StateDict,
    _ident_text,
    _meet_states,
    verify_enum_payload_guards,
    verify_generator_dominance,
    verify_no_shadowing,
    verify_ownership,
)

INT32 = make_simple("int32")
BOOL = make_simple("bool")


def _point_module() -> tuple[FIRModule, "TypeDef"]:
    module = FIRModule("firescript")
    point_t = make_simple("Point")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    return module, point_t


def _analyze(function: FIRFunction):
    """Build (cfg, idom, def_positions) directly, the way fir/verifier.py's
    _FunctionVerifier does, without running any Tier-1 checks."""
    block_ids = [b.id for b in function.blocks]
    entry = block_ids[0]

    def successors_of(bid: str) -> list[str]:
        block = next(b for b in function.blocks if b.id == bid)
        term = block.terminator
        if term is None:
            return []
        if isinstance(term, BranchInst):
            return [term.true_block, term.false_block]
        if isinstance(term, JumpInst):
            return [term.target_block]
        return []

    cfg = build_cfg(block_ids, entry, successors_of)
    idom = compute_dominators(cfg)
    def_positions: dict[int, tuple[str, int]] = {}
    for block in function.blocks:
        for idx, inst in enumerate(block.instructions):
            def_positions[id(inst)] = (block.id, idx)
        if block.terminator is not None:
            def_positions[id(block.terminator)] = (block.id, len(block.instructions))
    return cfg, idom, def_positions


# ---------------------------------------------------------------------------
# Pure helper functions, tested directly.
# ---------------------------------------------------------------------------

def test_meet_states_empty_list_returns_empty_dict():
    t.require_eq(_meet_states([]), {})


def test_state_dict_eq_compares_by_value():
    a = _StateDict({"x": 1})
    b = _StateDict({"x": 1})
    c = {"x": 1}
    t.require(a == b, "two _StateDicts with equal contents should compare equal")
    t.require(a == c, "_StateDict should compare equal to a plain dict with the same contents")
    t.require(not (a == "not a dict"), "_StateDict should not compare equal to a non-dict")


def test_ident_text_formats_temp_tuple_identifiers():
    # _identifier_of never actually produces these ("temp", ...) shapes
    # today (see ownership_verifier.py's long comment on expression-
    # temporary tracking being deliberately out of scope), but _ident_text
    # is a pure formatter that must still render them correctly if/when
    # that tracking is added -- exercised directly here.
    t.require_eq(_ident_text(("temp", ("block_0", 3))), "<temp block_0[3]>")
    t.require_eq(_ident_text(("temp", 7)), "<temp %7>")
    t.require_eq(_ident_text("plain_name"), "plain_name")


# ---------------------------------------------------------------------------
# Dataflow merge: divergent ownership state at a join point.
# ---------------------------------------------------------------------------

def test_o1_use_after_maybe_moved_on_some_paths():
    module, point_t = _point_module()
    func = FIRFunction("f", params=[("p", point_t)], param_modes=["own"], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    p = func.param_value("p")
    cond = b.bool_literal(True, BOOL)
    then_block = b.new_block()
    else_block = b.new_block()
    join_block = b.new_block()
    b.branch(cond, then_block.id, else_block.id)

    b.position_at(then_block)
    b.drop(p)
    b.jump(join_block.id)

    b.position_at(else_block)
    b.jump(join_block.id)

    b.position_at(join_block)
    # p is OWNED coming from else_block but MOVED coming from then_block;
    # the meet of those two states is MAYBE_MOVED (_meet_one), and this use
    # of p should be flagged as "possibly moved (on some paths)".
    b.load_field(p, "x", INT32)
    b.ret()

    try:
        module.validate()
        t.require(False, "no error raised (expected FIRV-O1)")
    except Exception as e:  # IRVerificationError
        violations = e.violations
        matches = [v for v in violations if v.rule_id == "FIRV-O1"]
        t.require(matches, f"FIRV-O1 not in: {violations}")
        t.require("possibly moved" in matches[0].message, matches[0].message)


# ---------------------------------------------------------------------------
# _identifier_of: anonymous instruction-result temporaries are untracked.
# ---------------------------------------------------------------------------

def test_drop_of_anonymous_temporary_is_untracked():
    module, point_t = _point_module()
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    # An Allocate result used directly as a Drop operand, never bound to a
    # local -- _identifier_of falls through every known-shape check (not a
    # ParamValue, not a LoadVar/LoadField/IndexArray/ExtractPayloadField)
    # and returns None, so this temporary isn't dataflow-tracked at all.
    anon = b.allocate(point_t, [one])
    b.drop(anon)
    b.ret()
    module.validate()  # must not raise


# ---------------------------------------------------------------------------
# CloneInst: FIRV-O6 for a non-owned operand (no existing test built a
# CloneInst at all before this).
# ---------------------------------------------------------------------------

def test_o6_clone_non_owned():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    cloned = b.clone(x)  # int32 is copyable, not owned
    b.ret(cloned)
    try:
        module.validate()
        t.require(False, "no error raised (expected FIRV-O6)")
    except Exception as e:
        t.require(any(v.rule_id == "FIRV-O6" for v in e.violations), e.violations)


# ---------------------------------------------------------------------------
# FIRV-O4: same identifier passed 'borrow_mut' more than once in one call.
# ---------------------------------------------------------------------------

def test_o4_borrow_mut_repeated_same_call():
    module, point_t = _point_module()
    callee = FIRFunction("callee", params=[("a", point_t), ("b", point_t)], param_modes=["borrow_mut", "borrow_mut"], return_type=None)
    module.add_function(callee)
    func = FIRFunction("f", params=[("p", point_t)], param_modes=["own"], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    p = func.param_value("p")
    b.call("callee", [p, p], ["borrow_mut", "borrow_mut"], None)
    b.drop(p)
    b.ret()
    try:
        module.validate()
        t.require(False, "no error raised (expected FIRV-O4)")
    except Exception as e:
        matches = [v for v in e.violations if v.rule_id == "FIRV-O4"]
        t.require(matches, e.violations)
        t.require("borrow_mut" in matches[0].message, matches[0].message)


# ---------------------------------------------------------------------------
# FIRV-O7: a local variable that shares a borrow parameter's name is still
# recognized as an alias of that borrow parameter when consumed.
# ---------------------------------------------------------------------------

def test_o7_borrow_param_consumed_via_shadowing_local():
    module = FIRModule("firescript")
    func = FIRFunction("f", params=[("p", INT32)], param_modes=["borrow"], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    # A local named "p", same as the borrow parameter -- also flags
    # FIRV-L3 (shadowing), which is fine; we only assert O7 is present.
    b.declare_local("p", INT32, one)
    shadowed = b.load_var("p", INT32)
    b.drop(shadowed)  # LoadVar("p") is consumed; "p" is also a borrow param name
    b.ret()
    try:
        module.validate()
        t.require(False, "no error raised (expected FIRV-O7)")
    except Exception as e:
        t.require(any(v.rule_id == "FIRV-O7" for v in e.violations), e.violations)


# ---------------------------------------------------------------------------
# _generator_identity: ParamValue branch (a generator passed as a
# borrow parameter, used directly with GenNext/GenValue).
# ---------------------------------------------------------------------------

def test_generator_identity_param_dominance_ok():
    module = FIRModule("firescript")
    gen_t = GeneratorType(INT32)
    func = FIRFunction("f", params=[("g", gen_t)], param_modes=["borrow"], return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    g = func.param_value("g")
    has_next = b.gen_next(g, BOOL)
    b.gen_value(g, INT32)
    b.ret(has_next)
    module.validate()  # must not raise: GenValue is dominated by GenNext on the same param


# ---------------------------------------------------------------------------
# Bypass-Tier-1 cases: hand-built instructions with operands Tier 1 would
# reject outright (a bare Value(), a mismatched arg_modes list, an
# unreachable block), exercised directly against the Tier-2 entry points.
# ---------------------------------------------------------------------------

def test_safe_resolve_fallback_for_unsupported_operand_kind():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    block = func.new_block()
    raw = Value()
    raw.result_type = INT32  # copyable -> Drop should flag FIRV-O5
    block.add_instruction(DropInst(raw))
    block.set_terminator(ReturnInst())
    cfg, idom, _ = _analyze(func)
    violations: list = []
    verify_ownership(module, func, cfg, idom, violations)
    matches = [v for v in violations if v.rule_id == "FIRV-O5"]
    t.require(matches, violations)
    # raw is neither a ParamValue nor a FIRValue, so _safe_resolve falls
    # back to "<?>" when formatting the violation's instruction text.
    t.require("<?>" in matches[0].instruction_text, matches[0].instruction_text)


def test_ownership_run_skips_unreachable_block_in_reporting_pass():
    module, point_t = _point_module()
    func = FIRFunction("f", params=[("p", point_t)], param_modes=["own"], return_type=None)
    module.add_function(func)
    entry = func.new_block()
    entry.add_instruction(DropInst(func.param_value("p")))
    entry.set_terminator(ReturnInst())

    # Never targeted by any Branch/Jump -- unreachable from entry, but still
    # present in function.blocks.
    orphan = func.new_block()
    orphan.add_instruction(DropInst(func.param_value("p")))  # would double-drop if visited
    orphan.set_terminator(ReturnInst())

    cfg, idom, _ = _analyze(func)
    violations: list = []
    verify_ownership(module, func, cfg, idom, violations)
    # run()'s final reporting pass explicitly skips blocks not in
    # cfg.reachable, so the orphan's Drop is never processed and no
    # violation (e.g. a spurious double-drop) should surface.
    t.require(violations == [], violations)


def test_process_call_bails_out_on_arg_mode_count_mismatch():
    module, point_t = _point_module()
    func = FIRFunction("f", params=[("p", point_t)], param_modes=["own"], return_type=None)
    module.add_function(func)
    block = func.new_block()
    p = func.param_value("p")
    call = CallInst("does_not_exist", [p], arg_modes=["own", "borrow"], return_type=None)  # 1 arg, 2 modes
    block.add_instruction(call)
    block.set_terminator(ReturnInst())
    cfg, idom, _ = _analyze(func)
    violations: list = []
    verify_ownership(module, func, cfg, idom, violations)
    # _process_call returns immediately on an arg/mode count mismatch
    # (already a Tier-1 FIRV-T5 case in the real pipeline), so p is never
    # consumed here -- it just leaks at the Return.
    t.require(any(v.rule_id == "FIRV-O3" for v in violations), violations)


def test_generator_identity_none_for_unsupported_operand_and_dominance_skips():
    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=None)
    module.add_function(func)
    block = func.new_block()
    raw = Value()
    raw.result_type = GeneratorType(INT32)
    block.add_instruction(GenValueInst(raw, INT32))
    block.set_terminator(ReturnInst())
    cfg, idom, def_positions = _analyze(func)
    violations: list = []
    verify_generator_dominance(func, idom, cfg, def_positions, violations)
    # raw is neither a ParamValue nor a FIRValue, so _generator_identity
    # returns None and the dominance check is skipped for this GenValue
    # entirely rather than flagging FIRV-G4.
    t.require(violations == [], violations)


def test_enum_guard_recognizes_tag_on_rhs_of_equality():
    module = FIRModule("firescript")
    module.add_type(TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A", [("v", INT32)])]))
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    block = func.new_block()
    ev = block.add_instruction(ConstructVariantInst(enum_t, "A", []))
    tag = block.add_instruction(ExtractTagInst(ev, INT32))
    zero = block.add_instruction(IntLiteralInst("0", INT32))
    # Literal on the left, ExtractTag on the right -- the mirror image of
    # the common "ExtractTag == literal" shape.
    cond = block.add_instruction(BinaryOpInst("==", zero, tag, BOOL))
    then_block = func.new_block()
    else_block = func.new_block()
    block.set_terminator(BranchInst(cond, then_block.id, else_block.id))
    epf = then_block.add_instruction(ExtractPayloadFieldInst(ev, "A", 0, INT32))
    then_block.set_terminator(ReturnInst(epf))
    else_block.set_terminator(ReturnInst(zero))

    cfg, idom, _ = _analyze(func)
    violations: list = []
    verify_enum_payload_guards(module, func, idom, cfg, violations)
    t.require(violations == [], violations)


def test_enum_guard_skips_non_literal_comparison_operand():
    module = FIRModule("firescript")
    module.add_type(TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A", [("v", INT32)])]))
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    ev = b.construct_variant(enum_t, "A", [])
    tag = b.extract_tag(ev, INT32)
    tag2 = b.extract_tag(ev, INT32)  # not an IntLiteral: guard collection must skip this branch
    cond = b.binary_op("==", tag, tag2, BOOL)
    then_block = b.new_block()
    else_block = b.new_block()
    b.branch(cond, then_block.id, else_block.id)
    b.position_at(then_block)
    b.ret(tag)
    b.position_at(else_block)
    b.ret(tag2)

    cfg, idom, _ = _analyze(func)
    violations: list = []
    verify_enum_payload_guards(module, func, idom, cfg, violations)
    # No ExtractPayloadField anywhere, so there's nothing to flag; this
    # just exercises the "comparison operand isn't an IntLiteral" skip in
    # the guard-collection loop without crashing.
    t.require(violations == [], violations)


def test_enum_guard_skips_unparseable_int_literal_text():
    module = FIRModule("firescript")
    module.add_type(TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A", [("v", INT32)])]))
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    block = func.new_block()
    ev = block.add_instruction(ConstructVariantInst(enum_t, "A", []))
    tag = block.add_instruction(ExtractTagInst(ev, INT32))
    # A hand-built IntLiteral whose text doesn't parse as an integer --
    # Tier 1 (FIRV-T12) would reject this in the real pipeline, so it's
    # only reachable here via the direct bypass.
    bad_lit = block.add_instruction(IntLiteralInst("not_a_number", INT32))
    cond = block.add_instruction(BinaryOpInst("==", tag, bad_lit, BOOL))
    then_block = func.new_block()
    else_block = func.new_block()
    block.set_terminator(BranchInst(cond, then_block.id, else_block.id))
    then_block.set_terminator(ReturnInst())
    else_block.set_terminator(ReturnInst())

    cfg, idom, _ = _analyze(func)
    violations: list = []
    verify_enum_payload_guards(module, func, idom, cfg, violations)
    t.require(violations == [], violations)


def test_enum_guard_ignores_extract_tag_of_unsupported_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    block = func.new_block()
    raw = Value()
    raw.result_type = make_simple("E")
    tag = block.add_instruction(ExtractTagInst(raw, INT32))
    zero = block.add_instruction(IntLiteralInst("0", INT32))
    cond = block.add_instruction(BinaryOpInst("==", tag, zero, BOOL))
    then_block = func.new_block()
    else_block = func.new_block()
    block.set_terminator(BranchInst(cond, then_block.id, else_block.id))
    then_block.set_terminator(ReturnInst())
    else_block.set_terminator(ReturnInst())

    cfg, idom, _ = _analyze(func)
    violations: list = []
    verify_enum_payload_guards(module, func, idom, cfg, violations)
    # ExtractTag's own operand (the enum value) isn't a Param/FIRValue, so
    # _generator_identity returns None for it and the branch is skipped as
    # a guard candidate entirely.
    t.require(violations == [], violations)


def test_enum_type_name_returns_none_for_operand_without_result_type():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    block = func.new_block()
    raw = Value()  # result_type defaults to None
    epf = block.add_instruction(ExtractPayloadFieldInst(raw, "A", 0, INT32))
    block.set_terminator(ReturnInst(epf))

    cfg, idom, _ = _analyze(func)
    violations: list = []
    verify_enum_payload_guards(module, func, idom, cfg, violations)
    # _enum_type_name returns None when the enum operand has no result
    # type at all, so the field access can never be resolved as guarded.
    t.require(any(v.rule_id == "FIRV-E1" for v in violations), violations)


# ---------------------------------------------------------------------------
# FIRV-L3 (verify_no_shadowing): unreachable-block skip, and the mirrored
# "second occurrence in block-list order actually dominates the first"
# case.
# ---------------------------------------------------------------------------

def test_l3_skips_declare_local_pair_in_unreachable_block():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    entry = func.new_block()
    entry.add_instruction(DeclareLocalInst("n", INT32))
    entry.set_terminator(ReturnInst())

    # Never targeted by any Branch/Jump -- unreachable from entry.
    orphan = func.new_block()
    orphan.add_instruction(DeclareLocalInst("n", INT32))
    orphan.set_terminator(ReturnInst())

    cfg, idom, _ = _analyze(func)
    violations: list = []
    verify_no_shadowing(func, idom, cfg, violations)
    # One of the two same-named DeclareLocals is in an unreachable block;
    # the pairwise dominance check skips any pair touching it, so no
    # FIRV-L3 is raised here even though both are named "n".
    t.require(violations == [], violations)


def test_l3_reports_earlier_list_position_when_later_position_dominates_it():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    entry = func.new_block()
    # Created (and thus positioned in function.blocks, which
    # decls_by_name traversal follows) before block_x, but control flow
    # actually visits block_x first: entry -> block_x -> block_y.
    block_y = func.new_block()
    block_x = func.new_block()

    b = FIRBuilder(func, entry)
    b.jump(block_x.id)

    b.position_at(block_x)
    one = b.int_literal("1", INT32)
    b.declare_local("n", INT32, one)
    b.jump(block_y.id)

    b.position_at(block_y)
    two = b.int_literal("2", INT32)
    b.declare_local("n", INT32, two)
    result = b.load_var("n", INT32)
    b.ret(result)

    cfg, idom, _ = _analyze(func)
    violations: list = []
    verify_no_shadowing(func, idom, cfg, violations)
    # decls_by_name["n"] is [(block_y, ...), (block_x, ...)] in block-list
    # order, but block_x actually dominates block_y in the real CFG -- the
    # mirrored `elif dominates(idom, b2, b1)` branch, reporting the
    # violation at the block_y (list-first) occurrence.
    matches = [v for v in violations if v.rule_id == "FIRV-L3"]
    t.require(matches, violations)
    t.require(matches[0].block_id == block_y.id, matches[0].block_id)

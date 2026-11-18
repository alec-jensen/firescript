"""Focused unit tests for individual decision points of the FLIR Tier-1
verifier (firescript/flir/verifier.py), complementing test_verifier_*.py:
branch/jmp target resolution, non-dominating slot declarations, parameter
slots, enum-variant field access, store-side alignment/type checks, the
null-check and narrow-int exemptions in FLIRV-T2 (valid and invalid sides),
pointer leniency, calls to module functions/externs, the Tier-1-before-
Tier-2 gating, and violation ordering/reporting. Each test corrupts exactly
one thing and asserts the specific rule/message; valid counterparts pin the
boundary."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from errors import IRVerificationError  # noqa: E402
from flir.ir import (  # noqa: E402
    BOOL,
    BinOp,
    Br,
    Call,
    ConstBool,
    ConstInt,
    ConstNull,
    ConstStr,
    Cvt,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    I8,
    I32,
    I64,
    Jmp,
    Load,
    PTR,
    PtrAdd,
    Ret,
    SlotDecl,
    SlotLoad,
    SlotStore,
    Store,
    U64,
    VOID,
    ptr_to,
)


def _violations(module: FLIRModule) -> list:
    try:
        module.validate()
    except IRVerificationError as e:
        return e.violations
    return []


def _expect(module: FLIRModule, rule_id: str, fragment: str = "") -> None:
    found = _violations(module)
    t.require(bool(found), f"no error raised (expected {rule_id})")
    t.require(
        any(v.rule_id == rule_id and fragment in v.message for v in found),
        f"{rule_id} / {fragment!r} not in: {[(v.rule_id, v.message) for v in found]}",
    )


def _expect_clean(module: FLIRModule) -> None:
    found = _violations(module)
    t.require(not found, f"unexpected violations: {[(v.rule_id, v.message) for v in found]}")


def _one_func(name="f", params=None, return_type=VOID):
    module = FLIRModule("firescript")
    func = FLIRFunction(name, params=params, return_type=return_type)
    module.add_function(func)
    return module, func, func.new_block()


def _box_struct(module: FLIRModule) -> None:
    """Box { a: i32 @0, b: i64 @8 }, size 16 align 8."""
    s = FLIRStruct("Box", kind="class")
    s.fields = [("a", I32, 0), ("b", I64, 8)]
    s.size = 16
    s.align = 8
    module.add_struct(s)


# -- S1: branch targets -------------------------------------------------------

def test_s1_jmp_to_missing_block_is_reported():
    module, _func, entry = _one_func()
    entry.add(Jmp("nowhere"))
    _expect(module, "FLIRV-S1", "branch target 'nowhere' does not exist")


def test_s1_br_false_target_missing_is_reported_even_if_true_target_exists():
    module, func, entry = _one_func()
    other = func.new_block()
    other.add(Ret())
    cond = entry.add(ConstBool(True))
    entry.add(Br(cond, other.id, "gone"))
    found = _violations(module)
    msgs = [v.message for v in found if v.rule_id == "FLIRV-S1"]
    t.require(msgs == ["branch target 'gone' does not exist"], str(msgs))


def test_s1_diamond_cfg_with_jmp_and_br_is_clean():
    module, func, entry = _one_func(return_type=I32)
    then_b, else_b, join = func.new_block(), func.new_block(), func.new_block()
    entry.add(SlotDecl("x", I32))
    cond = entry.add(ConstBool(True))
    entry.add(Br(cond, then_b.id, else_b.id))
    then_b.add(SlotStore("x", then_b.add(ConstInt("1", I32))))
    then_b.add(Jmp(join.id))
    else_b.add(SlotStore("x", else_b.add(ConstInt("2", I32))))
    else_b.add(Jmp(join.id))
    join.add(Ret(join.add(SlotLoad("x", I32))))
    _expect_clean(module)


# -- T5: slot declaration dominance and parameters ------------------------------

def test_t5_slot_declared_only_in_sibling_branch_does_not_dominate_use():
    module, func, entry = _one_func()
    then_b, else_b, join = func.new_block(), func.new_block(), func.new_block()
    cond = entry.add(ConstBool(True))
    entry.add(Br(cond, then_b.id, else_b.id))
    then_b.add(SlotDecl("x", I32))
    then_b.add(Jmp(join.id))
    else_b.add(Jmp(join.id))
    join.add(SlotLoad("x", I32))
    join.add(Ret())
    _expect(module, "FLIRV-T5", "no dominating parameter or slot declaration")


def test_t5_slot_used_before_its_declaration_in_same_block():
    module, _func, entry = _one_func()
    entry.add(SlotLoad("x", I32))
    entry.add(SlotDecl("x", I32))
    entry.add(Ret())
    _expect(module, "FLIRV-T5", "slotload('x') has no dominating")


def test_t5_parameter_name_needs_no_slot_declaration():
    module, _func, entry = _one_func(params=[("p", I32)], return_type=I32)
    entry.add(Ret(entry.add(SlotLoad("p", I32))))
    _expect_clean(module)


def test_t5_parameter_slotload_type_mismatch_is_reported():
    module, _func, entry = _one_func(params=[("p", I32)], return_type=I64)
    entry.add(Ret(entry.add(SlotLoad("p", I64))))
    _expect(module, "FLIRV-T5", "slotload('p') result type 'i64' does not match declared type 'i32'")


def test_t5_slot_pointer_pointee_difference_is_tolerated():
    module, _func, entry = _one_func()
    entry.add(SlotDecl("s", ptr_to("i8")))
    entry.add(SlotStore("s", entry.add(ConstNull())))
    entry.add(Ret())
    _expect_clean(module)


# -- T2: binop exemptions (valid and invalid sides) -------------------------------

def _binop_module(op, operand_type, lhs, rhs, result_type):
    module, _func, entry = _one_func()
    a = entry.add(lhs)
    b = entry.add(rhs)
    entry.add(BinOp(op, operand_type, a, b, result_type))
    entry.add(Ret())
    return module


def test_t2_eq_against_ptr_operand_is_accepted_as_null_check():
    module = _binop_module("eq", I32, ConstNull(), ConstNull(), BOOL)
    _expect_clean(module)


def test_t2_ne_against_ptr_operand_is_accepted_as_null_check():
    module = _binop_module("ne", I32, ConstInt("1", I32), ConstNull(), BOOL)
    _expect_clean(module)


def test_t2_ordering_comparison_with_ptr_operand_is_not_exempt():
    module = _binop_module("lt", I32, ConstInt("1", I32), ConstNull(), BOOL)
    _expect(module, "FLIRV-T2", "rhs type 'ptr' does not match operand_type 'i32'")


def test_t2_narrow_int_operand_feeds_wider_binop_without_cvt():
    module = _binop_module("add", I32, ConstInt("1", I8), ConstInt("2", I8), I32)
    _expect_clean(module)


def test_t2_wider_int_operand_into_narrower_binop_is_rejected():
    module = _binop_module("add", I32, ConstInt("1", I64), ConstInt("2", I32), I32)
    _expect(module, "FLIRV-T2", "lhs type 'i64' does not match operand_type 'i32'")


def test_t2_float_operand_into_int_binop_is_rejected():
    from flir.ir import ConstFloat, F64

    module = _binop_module("add", I32, ConstFloat("1.0", F64), ConstInt("2", I32), I32)
    _expect(module, "FLIRV-T2", "lhs type 'f64' does not match operand_type 'i32'")


def test_t2_logical_and_must_keep_operand_type():
    module = _binop_module("and", BOOL, ConstBool(True), ConstBool(False), I32)
    _expect(module, "FLIRV-T2", "binop 'and' result type 'i32' does not match operand_type 'bool'")


def test_t2_logical_and_preserving_operand_type_is_clean():
    module = _binop_module("or", BOOL, ConstBool(True), ConstBool(False), BOOL)
    _expect_clean(module)


def test_t2_cvt_between_u64_and_ptr_is_accepted():
    module, _func, entry = _one_func()
    addr = entry.add(ConstInt("4096", U64))
    p = entry.add(Cvt(addr, U64, PTR))
    entry.add(Cvt(p, PTR, U64))
    entry.add(Ret())
    _expect_clean(module)


# -- T3: ret ------------------------------------------------------------------------

def test_t3_ret_pointer_with_different_pointee_is_accepted():
    module, _func, entry = _one_func(return_type=ptr_to("Other"))
    entry.add(Ret(entry.add(ConstStr("s"))))
    _expect_clean(module)


def test_t3_ret_pointer_in_scalar_function_is_rejected():
    module, _func, entry = _one_func(return_type=I64)
    entry.add(Ret(entry.add(ConstNull())))
    _expect(module, "FLIRV-T3", "ret value type 'ptr' does not match declared return type 'i64'")


def test_t3_ret_of_valueless_operand_reports_only_t1():
    module, _func, entry = _one_func(return_type=I32)
    stray = entry.add(Call("fs_rt_stdout", [entry.add(ConstStr("x"))], VOID))
    t.require(stray is None)
    void_call = entry.instructions[-1]
    from flir.ir import FValue

    entry.add(Ret(FValue(void_call)))
    found = _violations(module)
    t.require([v.rule_id for v in found] == ["FLIRV-T1"], str([(v.rule_id, v.message) for v in found]))
    t.require("does not produce a value" in found[0].message)


# -- T4: calls to module functions and externs ------------------------------------------

def test_t4_call_to_module_function_argument_type_mismatch():
    module, func, entry = _one_func(name="caller")
    callee = FLIRFunction("callee", params=[("n", I32)], return_type=VOID)
    module.add_function(callee)
    callee.new_block().add(Ret())
    entry.add(Call("callee", [entry.add(ConstInt("1", I64))], VOID))
    entry.add(Ret())
    _expect(module, "FLIRV-T4", "call to function 'callee' argument 0 has type 'i64', expected 'i32'")


def test_t4_call_to_module_function_argument_count_mismatch():
    module, func, entry = _one_func(name="caller")
    callee = FLIRFunction("callee", params=[("n", I32)], return_type=VOID)
    module.add_function(callee)
    callee.new_block().add(Ret())
    entry.add(Call("callee", [], VOID))
    entry.add(Ret())
    _expect(module, "FLIRV-T4", "call to function 'callee' passes 0 argument(s), expected 1")


def test_t4_call_to_extern_accepts_pointer_with_any_pointee():
    module, _func, entry = _one_func()
    module.externs["WriteThing"] = ("kernel32.dll", I32, [ptr_to("i8")])
    entry.add(Call("WriteThing", [entry.add(ConstNull())], I32))
    entry.add(Ret())
    _expect_clean(module)


def test_t4_call_to_extern_result_type_mismatch():
    module, _func, entry = _one_func()
    module.externs["WriteThing"] = ("kernel32.dll", I32, [])
    entry.add(Call("WriteThing", [], I64))
    entry.add(Ret())
    _expect(module, "FLIRV-T4", "call to extern 'WriteThing' result type 'i64' does not match its return type 'i32'")


def test_t4_extern_shadowed_by_module_function_uses_module_signature():
    module, _func, entry = _one_func(name="caller")
    module.externs["dup"] = ("k.dll", I32, [I32])
    callee = FLIRFunction("dup", params=[], return_type=VOID)
    module.add_function(callee)
    callee.new_block().add(Ret())
    entry.add(Call("dup", [], VOID))
    entry.add(Ret())
    _expect_clean(module)


# -- M1/M2: field access on known structs ------------------------------------------------

def _enum_struct(module: FLIRModule) -> None:
    s = FLIRStruct("Shape", kind="enum")
    s.fields = [("tag", I32, 0)]
    s.variant_layouts = {"Circle": [("radius", I64, 8)], "Square": [("side", I32, 8)]}
    s.size = 16
    s.align = 8
    module.add_struct(s)


def test_m1_load_at_enum_variant_field_offset_is_accepted():
    module, _func, entry = _one_func(params=[("s", ptr_to("Shape"))], return_type=I64)
    _enum_struct(module)
    base = entry.add(SlotLoad("s", ptr_to("Shape")))
    entry.add(Ret(entry.add(Load(I64, base, 8))))
    _expect_clean(module)


def test_m1_load_at_enum_variant_offset_accepts_any_variants_type():
    module, _func, entry = _one_func(params=[("s", ptr_to("Shape"))], return_type=I32)
    _enum_struct(module)
    base = entry.add(SlotLoad("s", ptr_to("Shape")))
    entry.add(Ret(entry.add(Load(I32, base, 8))))
    _expect_clean(module)


def test_m1_load_at_enum_variant_offset_with_foreign_type_is_rejected():
    module, _func, entry = _one_func(params=[("s", ptr_to("Shape"))], return_type=U64)
    _enum_struct(module)
    base = entry.add(SlotLoad("s", ptr_to("Shape")))
    entry.add(Ret(entry.add(Load(U64, base, 8))))
    _expect(module, "FLIRV-M1", "does not match field type(s) i32, i64")


def test_m2_store_misaligned_offset_is_reported():
    module, _func, entry = _one_func(params=[("b", ptr_to("Box"))])
    _box_struct(module)
    base = entry.add(SlotLoad("b", ptr_to("Box")))
    entry.add(Store(I64, base, 4, entry.add(ConstInt("1", I64))))
    entry.add(Ret())
    _expect(module, "FLIRV-M2", "store offset 4 is misaligned for type 'i64' (align 8)")


def test_m1_store_at_offset_without_field_is_reported():
    module, _func, entry = _one_func(params=[("b", ptr_to("Box"))])
    _box_struct(module)
    base = entry.add(SlotLoad("b", ptr_to("Box")))
    entry.add(Store(I32, base, 4, entry.add(ConstInt("1", I32))))
    entry.add(Ret())
    _expect(module, "FLIRV-M1", "store at offset 4 into '%Box' does not land on a declared field")


def test_m1_store_field_type_mismatch_is_reported():
    module, _func, entry = _one_func(params=[("b", ptr_to("Box"))])
    _box_struct(module)
    base = entry.add(SlotLoad("b", ptr_to("Box")))
    entry.add(Store(I64, base, 0, entry.add(ConstInt("1", I64))))
    entry.add(Ret())
    _expect(module, "FLIRV-M1", "store type 'i64' at offset 0 into '%Box' does not match field type(s) i32")


def test_m1_store_matching_field_is_clean():
    module, _func, entry = _one_func(params=[("b", ptr_to("Box"))])
    _box_struct(module)
    base = entry.add(SlotLoad("b", ptr_to("Box")))
    entry.add(Store(I32, base, 0, entry.add(ConstInt("1", I32))))
    entry.add(Store(I64, base, 8, entry.add(ConstInt("1", I64))))
    entry.add(Ret())
    _expect_clean(module)


def test_m1_access_through_raw_pointer_is_not_checked():
    module, _func, entry = _one_func()
    base = entry.add(ConstNull())
    entry.add(Store(I32, base, 3, entry.add(ConstInt("1", I32))))
    entry.add(Ret())
    _expect_clean(module)


def test_m3_ptradd_with_zero_scale_is_reported_and_positive_scale_is_clean():
    module, _func, entry = _one_func()
    entry.add(PtrAdd(entry.add(ConstNull()), entry.add(ConstInt("1", I64)), 0))
    entry.add(Ret())
    _expect(module, "FLIRV-M3", "ptradd scale 0 is not positive")
    ok, _f, e2 = _one_func()
    e2.add(PtrAdd(e2.add(ConstNull()), e2.add(ConstInt("1", I64)), 8))
    e2.add(Ret())
    _expect_clean(ok)


# -- globals --------------------------------------------------------------------------------

def test_t6_gstore_to_mutable_global_with_matching_type_is_clean():
    from flir.ir import GlobalLoad, GlobalStore

    module, _func, entry = _one_func(return_type=I32)
    module.mutable_globals.append(("counter", I32))
    from flir.ir import ConstInt as CI

    entry.add(GlobalStore("counter", entry.add(CI("1", I32))))
    entry.add(Ret(entry.add(GlobalLoad("counter", I32))))
    _expect_clean(module)


# -- Tier gating and reporting --------------------------------------------------------------------

def test_tier2_is_skipped_for_function_with_tier1_violation():
    """A leaked token in the same function as a type error must not add an
    A4 cascade: Tier-2 only runs on functions Tier-1 accepted."""
    module, _func, entry = _one_func()
    entry.add(SlotDecl("s", ptr_to("i8")))
    src = entry.add(ConstStr("x"))
    entry.add(SlotStore("s", entry.add(Call("fs_rt_str_dup", [src], ptr_to("i8")))))
    entry.add(Ret(entry.add(ConstInt("1", I32))))  # T3: value in void function
    rules = {v.rule_id for v in _violations(module)}
    t.require(rules == {"FLIRV-T3"}, str(rules))


def test_tier2_runs_for_clean_function_alongside_flawed_sibling():
    module = FLIRModule("firescript")
    bad = FLIRFunction("bad", return_type=VOID)
    module.add_function(bad)
    bb = bad.new_block()
    bb.add(Ret(bb.add(ConstInt("1", I32))))
    leaky = FLIRFunction("leaky", return_type=VOID)
    module.add_function(leaky)
    lb = leaky.new_block()
    lb.add(SlotDecl("s", ptr_to("i8")))
    src = lb.add(ConstStr("x"))
    lb.add(SlotStore("s", lb.add(Call("fs_rt_str_dup", [src], ptr_to("i8")))))
    lb.add(Ret())
    found = _violations(module)
    t.require([(v.function_name, v.rule_id) for v in found] == [("bad", "FLIRV-T3"), ("leaky", "FLIRV-A4")], str([(v.function_name, v.rule_id) for v in found]))


def test_violations_are_reported_in_structure_order_with_first_offender_dump():
    module, func, entry = _one_func(name="first")
    entry.add(Jmp("missing"))
    second = FLIRFunction("second", return_type=VOID)
    module.add_function(second)
    sb = second.new_block()
    sb.add(Ret(sb.add(ConstInt("1", I32))))  # T3: value in void function
    try:
        module.validate()
        t.require(False, "expected error")
    except IRVerificationError as e:
        names = [v.function_name for v in e.violations]
        t.require(names == ["first", "second"], str(names))
        t.require("-- first offending function --" in str(e))
        t.require("func @first" in e.function_dump and "func @second" not in e.function_dump)


def test_module_level_violation_has_no_function_dump():
    module = FLIRModule("firescript")
    module.entry_function = "main"
    try:
        module.validate()
        t.require(False, "expected error")
    except IRVerificationError as e:
        t.require(e.function_dump == "")
        t.require("-- first offending function --" not in str(e))
        t.require(e.violations[0].rule_id == "FLIRV-S2")


def test_valid_entry_function_and_empty_module_are_clean():
    empty = FLIRModule("firescript")
    _expect_clean(empty)
    module, _func, entry = _one_func(name="main")
    entry.add(Ret())
    module.entry_function = "main"
    _expect_clean(module)

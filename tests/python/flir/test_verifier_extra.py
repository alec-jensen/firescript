"""Additional unit tests for firescript/flir/verifier.py, filling coverage
gaps left by test_verifier_structure.py/test_verifier_types.py: struct
layout edge cases (duplicate/overlapping names, enum tag/variant overlap),
S1 cases not yet covered (an empty function, an empty block), the
remaining T1-T6/M1-M3 branches, and the handful of small pure helper
functions (some of which turn out to be dead code -- see the note on
_resolve_struct_type below)."""
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
    Cvt,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    GlobalLoad,
    GlobalStore,
    I32,
    I64,
    Jmp,
    Load,
    Neg,
    Not,
    PtrAdd,
    Ret,
    SlotAddr,
    SlotDecl,
    SlotLoad,
    SlotStore,
    Store,
    U8,
    VOID,
    ptr_to,
    struct_type,
)
from flir.verifier import _binop_operand_ok, _ptr_lenient_eq, _resolve_struct_type, verify_flir_module  # noqa: E402


def _expect_rule(module: FLIRModule, rule_id: str) -> None:
    try:
        module.validate()
        t.require(False, f"no error raised (expected {rule_id})")
    except IRVerificationError as e:
        t.require(any(v.rule_id == rule_id for v in e.violations), f"{rule_id} not in: {e}")


def _simple_module() -> tuple[FLIRModule, FLIRFunction]:
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    return module, func


# ---------------------------------------------------------------------------
# Pure helper functions.
# ---------------------------------------------------------------------------

def test_resolve_struct_type_is_dead_code_but_correct_if_called():
    # _resolve_struct_type is defined in flir/verifier.py but never called
    # anywhere in the module (grep confirms no call site) -- it appears to
    # be a leftover from an earlier version of the M1 check. It's exercised
    # directly here rather than removed, per this test suite's test-only
    # scope; flagged in the coverage report as dead code found along the way.
    t.require(_resolve_struct_type(None) is None)
    t.require_eq(_resolve_struct_type(ptr_to("Point")), "Point")
    t.require(_resolve_struct_type(I32) is None)


def test_binop_operand_ok_narrowing():
    # A narrower actual int type feeding a wider declared operand_type is
    # allowed with no explicit Cvt (see the function's own docstring).
    t.require(_binop_operand_ok(U8, I32))
    t.require(not _binop_operand_ok(I64, I32))  # wider actual than declared: not ok
    t.require(not _binop_operand_ok(BOOL, I32))  # non-integer kinds: not ok


def test_ptr_lenient_eq_plain_type_equality():
    t.require(_ptr_lenient_eq(I32, I32))
    t.require(not _ptr_lenient_eq(I32, I64))
    t.require(_ptr_lenient_eq(None, I32))
    t.require(_ptr_lenient_eq(ptr_to("A"), ptr_to("B")))  # pointee is informational only


# ---------------------------------------------------------------------------
# S1: function with no blocks at all; a block with no instructions.
# ---------------------------------------------------------------------------

def test_s1_function_with_no_blocks():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)  # never call new_block()
    module.add_function(func)
    _expect_rule(module, "FLIRV-S1")


def test_s1_empty_block():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    empty = func.new_block()  # entry, but never given any instructions
    other = func.new_block()
    other.instructions.append(Ret())
    _expect_rule(module, "FLIRV-S1")


# ---------------------------------------------------------------------------
# S2: duplicate struct name, duplicate global name, global/mutable-global
# name collision, field referencing an unresolved struct.
# ---------------------------------------------------------------------------

def test_s2_duplicate_struct_name():
    module = FLIRModule("firescript")
    for _ in range(2):
        s = FLIRStruct("Dup", kind="class")
        s.size = 1
        s.align = 1
        module.add_struct(s)
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    _expect_rule(module, "FLIRV-S2")


def test_s2_duplicate_global_name():
    module = FLIRModule("firescript")
    module.globals.append(("g", I32, "0"))
    module.globals.append(("g", I32, "1"))
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    _expect_rule(module, "FLIRV-S2")


def test_s2_mutable_global_name_collides_with_immutable():
    module = FLIRModule("firescript")
    module.mutable_globals.append(("g", I32))
    module.mutable_globals.append(("g", I32))
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    _expect_rule(module, "FLIRV-S2")


def test_s2_field_references_unresolved_struct():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Bad", kind="class")
    struct.fields = [("f", struct_type("DoesNotExist"), 0)]
    struct.size = 8
    struct.align = 8
    module.add_struct(struct)
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    _expect_rule(module, "FLIRV-S2")


# ---------------------------------------------------------------------------
# S3: size not a multiple of align, field exceeding struct size, enum tag
# overlap, enum variant fields overlapping each other.
# ---------------------------------------------------------------------------

def test_s3_struct_size_not_multiple_of_align():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Bad", kind="class")
    struct.size = 5
    struct.align = 4
    module.add_struct(struct)
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    _expect_rule(module, "FLIRV-S3")


def test_s3_field_exceeds_struct_size():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Bad", kind="class")
    struct.fields = [("x", I32, 4)]  # [4, 8) exceeds a size-6 struct
    struct.size = 8
    struct.align = 4
    module.add_struct(struct)
    struct.size = 6  # shrink after the field was declared, to isolate this check
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    _expect_rule(module, "FLIRV-S3")


def test_s3_enum_variant_field_overlaps_tag():
    module = FLIRModule("firescript")
    struct = FLIRStruct("E", kind="enum")
    struct.fields = [("tag", I32, 0)]
    struct.variant_layouts = {"A": [("v", I32, 0)]}  # [0, 4) overlaps the tag
    struct.size = 8
    struct.align = 4
    module.add_struct(struct)
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    _expect_rule(module, "FLIRV-S3")


def test_s3_enum_variant_fields_overlap_each_other():
    module = FLIRModule("firescript")
    struct = FLIRStruct("E", kind="enum")
    struct.fields = [("tag", I32, 0)]
    struct.variant_layouts = {"A": [("x", I32, 4), ("y", I32, 4)]}  # both at offset 4
    struct.size = 12
    struct.align = 4
    module.add_struct(struct)
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    _expect_rule(module, "FLIRV-S3")


# ---------------------------------------------------------------------------
# T1: operand from a foreign function; operand that doesn't dominate its
# use; operand with no value (void).
# ---------------------------------------------------------------------------

def test_t1_operand_foreign_to_function_and_dump_fallback():
    module = FLIRModule("firescript")
    func_a = FLIRFunction("a", return_type=I32)
    module.add_function(func_a)
    block_a = func_a.new_block()
    foreign = block_a.add(ConstInt("1", I32))
    block_a.instructions.append(Ret(foreign))

    func_b = FLIRFunction("b", return_type=I32)
    module.add_function(func_b)
    block_b = func_b.new_block()
    block_b.instructions.append(Ret(foreign))  # value produced in func_a

    # This also exercises _format_first_offender's except-branch: dumping
    # func_b for the error report fails (dump_flir_module itself raises,
    # since `foreign` doesn't belong to func_b either), which must be
    # caught rather than propagate out of verify_flir_module.
    try:
        module.validate()
        t.require(False, "no error raised")
    except IRVerificationError as e:
        t.require(any(v.rule_id == "FLIRV-T1" for v in e.violations), e.violations)


def test_t1_operand_does_not_dominate_use():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    then_block = func.new_block()
    else_block = func.new_block()
    cond = entry.add(ConstBool(True))
    entry.instructions.append(Br(cond, then_block.id, else_block.id))
    # Defined only in then_block, used in else_block -- else_block isn't
    # dominated by then_block's definition.
    one = then_block.add(ConstInt("1", I32))
    then_block.instructions.append(Ret(one))
    else_block.instructions.append(Ret(one))
    _expect_rule(module, "FLIRV-T1")


def test_t1_operand_has_no_value_void():
    module = FLIRModule("firescript")
    callee = FLIRFunction("callee", return_type=VOID)
    module.add_function(callee)
    callee.new_block().instructions.append(Ret())
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    # Not `entry.add(...)`: a void-result Call's has_result() is False, so
    # add() would return None and we'd never get an FValue to pass to Ret
    # -- append the instruction directly and take its FValue via result().
    call_inst = Call("callee", [], VOID)
    entry.instructions.append(call_inst)
    entry.instructions.append(Ret(call_inst.result()))
    _expect_rule(module, "FLIRV-T1")


# ---------------------------------------------------------------------------
# T2: binop operand-type mismatches, unknown op, 'not'/'neg' type
# mismatches, cvt from/to type checks.
# ---------------------------------------------------------------------------

def test_t2_binop_lhs_type_mismatch():
    module, func = _simple_module()
    entry = func.new_block()
    a = entry.add(ConstInt("1", I64))  # i64, wider than declared i32
    b = entry.add(ConstInt("2", I32))
    bad = entry.add(BinOp("add", I32, a, b, I32))
    entry.instructions.append(Ret(bad))
    _expect_rule(module, "FLIRV-T2")


def test_t2_binop_rhs_type_mismatch():
    module, func = _simple_module()
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    b = entry.add(ConstInt("2", I64))
    bad = entry.add(BinOp("add", I32, a, b, I32))
    entry.instructions.append(Ret(bad))
    _expect_rule(module, "FLIRV-T2")


def test_t2_comparison_must_produce_bool():
    module, func = _simple_module()
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    b = entry.add(ConstInt("2", I32))
    bad = entry.add(BinOp("eq", I32, a, b, I32))  # comparisons must produce bool
    zero = entry.add(ConstInt("0", I32))
    entry.instructions.append(Ret(zero))
    _expect_rule(module, "FLIRV-T2")


def test_t2_unknown_binop():
    module, func = _simple_module()
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    b = entry.add(ConstInt("2", I32))
    entry.add(BinOp("frobnicate", I32, a, b, I32))
    zero = entry.add(ConstInt("0", I32))
    entry.instructions.append(Ret(zero))
    _expect_rule(module, "FLIRV-T2")


def test_t2_not_type_mismatch():
    module, func = _simple_module()
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    entry.add(Not(a))
    zero = entry.add(ConstInt("0", I32))
    entry.instructions.append(Ret(zero))
    _expect_rule(module, "FLIRV-T2")


def test_t2_neg_type_mismatch():
    module, func = _simple_module()
    entry = func.new_block()
    a = entry.add(ConstBool(True))
    bad = entry.add(Neg(a, I32))  # operand is bool, result declared i32
    entry.instructions.append(Ret(bad))
    _expect_rule(module, "FLIRV-T2")


def test_t2_cvt_from_type_not_scalar():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Point", kind="class")
    struct.fields = [("x", I32, 0)]
    struct.size = 4
    struct.align = 4
    module.add_struct(struct)
    func = FLIRFunction("f", params=[("p", ptr_to("Point"))], return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    p = entry.add(SlotLoad("p", ptr_to("Point")))
    bad = entry.add(Cvt(p, struct_type("Point"), I32))  # from_type is a struct, not scalar
    entry.instructions.append(Ret(bad))
    _expect_rule(module, "FLIRV-T2")


def test_t2_cvt_to_type_not_scalar():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Point", kind="class")
    struct.fields = [("x", I32, 0)]
    struct.size = 4
    struct.align = 4
    module.add_struct(struct)
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    entry.add(Cvt(a, I32, struct_type("Point")))  # to_type is a struct, not scalar
    entry.instructions.append(Ret())
    _expect_rule(module, "FLIRV-T2")


# ---------------------------------------------------------------------------
# T3: bare ret in a non-void function; ret carries a value in a void
# function.
# ---------------------------------------------------------------------------

def test_t3_bare_ret_in_nonvoid_function():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    func.new_block().instructions.append(Ret())  # no value
    _expect_rule(module, "FLIRV-T3")


def test_t3_ret_carries_value_in_void_function():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    one = entry.add(ConstInt("1", I32))
    entry.instructions.append(Ret(one))
    _expect_rule(module, "FLIRV-T3")


# ---------------------------------------------------------------------------
# T4: call argument type mismatch, call result type mismatch.
# ---------------------------------------------------------------------------

def test_t4_call_argument_type_mismatch():
    module = FLIRModule("firescript")
    callee = FLIRFunction("callee", params=[("x", I32)], return_type=VOID)
    callee.new_block().instructions.append(Ret())
    module.add_function(callee)
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    b = entry.add(ConstBool(True))  # bool, but callee expects i32
    entry.add(Call("callee", [b], VOID))
    entry.instructions.append(Ret())
    _expect_rule(module, "FLIRV-T4")


def test_t4_call_result_type_mismatch():
    module = FLIRModule("firescript")
    callee = FLIRFunction("callee", return_type=I32)
    callee_block = callee.new_block()
    zero = callee_block.add(ConstInt("0", I32))
    callee_block.instructions.append(Ret(zero))
    module.add_function(callee)
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    entry.add(Call("callee", [], BOOL))  # declares bool, callee returns i32
    entry.instructions.append(Ret())
    _expect_rule(module, "FLIRV-T4")


# ---------------------------------------------------------------------------
# T5: slotload/slotstore type mismatch against the declared slot type.
# ---------------------------------------------------------------------------

def test_t5_slotload_type_mismatch():
    module, func = _simple_module()
    entry = func.new_block()
    entry.add(SlotDecl("x", I32))
    bad = entry.add(SlotLoad("x", BOOL))  # declared i32, loaded as bool
    entry.instructions.append(Ret(bad))
    try:
        module.validate()
        t.require(False, "no error raised (expected FIRV-T5)")
    except IRVerificationError as e:
        t.require(any(v.rule_id == "FLIRV-T5" for v in e.violations), e.violations)


def test_t5_slotstore_type_mismatch():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    entry.add(SlotDecl("x", I32))
    b = entry.add(ConstBool(True))
    entry.add(SlotStore("x", b))  # declared i32, stored a bool
    entry.instructions.append(Ret())
    try:
        module.validate()
        t.require(False, "no error raised (expected FIRV-T5)")
    except IRVerificationError as e:
        t.require(any(v.rule_id == "FLIRV-T5" for v in e.violations), e.violations)


def test_slotaddr_accepts_declared_slot():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    entry.add(SlotDecl("x", I32))
    addr = entry.add(SlotAddr("x"))
    loaded = entry.add(Load(I32, addr, 0))
    entry.instructions.append(Ret(loaded))
    module.validate()  # must not raise


# ---------------------------------------------------------------------------
# T6: gload/gstore referencing an undeclared global; value type mismatch.
# ---------------------------------------------------------------------------

def test_t6_gload_undeclared_global():
    module, func = _simple_module()
    entry = func.new_block()
    bad = entry.add(GlobalLoad("nope", I32))
    entry.instructions.append(Ret(bad))
    _expect_rule(module, "FLIRV-T6")


def test_t6_gload_type_mismatch():
    module, func = _simple_module()
    module.globals.append(("g", I32, "0"))
    entry = func.new_block()
    bad = entry.add(GlobalLoad("g", BOOL))  # declared i32, loaded as bool
    zero = entry.add(ConstInt("0", I32))
    entry.instructions.append(Ret(zero))
    _expect_rule(module, "FLIRV-T6")


def test_t6_gstore_undeclared_global():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    v = entry.add(ConstInt("1", I32))
    entry.add(GlobalStore("nope", v))
    entry.instructions.append(Ret())
    _expect_rule(module, "FLIRV-T6")


def test_t6_gstore_value_type_mismatch():
    module = FLIRModule("firescript")
    module.mutable_globals.append(("g", I32))
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    b = entry.add(ConstBool(True))
    entry.add(GlobalStore("g", b))  # declared i32, stored a bool
    entry.instructions.append(Ret())
    _expect_rule(module, "FLIRV-T6")


# ---------------------------------------------------------------------------
# M1: load/store base is not a pointer.
# ---------------------------------------------------------------------------

def test_m1_load_base_non_pointer():
    module, func = _simple_module()
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    bad = entry.add(Load(I32, a, 0))  # base is i32, not a pointer
    entry.instructions.append(Ret(bad))
    _expect_rule(module, "FLIRV-M1")


def test_m1_store_base_non_pointer():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    v = entry.add(ConstInt("2", I32))
    entry.add(Store(I32, a, 0, v))  # base is i32, not a pointer
    entry.instructions.append(Ret())
    _expect_rule(module, "FLIRV-M1")


def test_store_value_type_mismatch():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Point", kind="class")
    struct.fields = [("x", I32, 0)]
    struct.size = 4
    struct.align = 4
    module.add_struct(struct)
    func = FLIRFunction("f", params=[("p", ptr_to("Point"))], return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    p = entry.add(SlotLoad("p", ptr_to("Point")))
    b = entry.add(ConstBool(True))
    entry.add(Store(I32, p, 0, b))  # declared value_type i32, actual operand is bool
    entry.instructions.append(Ret())
    _expect_rule(module, "FLIRV-T1")


def test_load_skips_further_checks_when_base_type_unresolved():
    module = FLIRModule("firescript")
    callee = FLIRFunction("callee", return_type=VOID)
    callee.new_block().instructions.append(Ret())
    module.add_function(callee)
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    call_inst = Call("callee", [], VOID)  # already flags its own FLIRV-T1
    entry.instructions.append(call_inst)
    void_val = call_inst.result()
    bad = entry.add(Load(I32, void_val, 0))  # base type unresolved: must not crash further
    entry.instructions.append(Ret(bad))
    try:
        module.validate()
        t.require(False, "no error raised")
    except IRVerificationError as e:
        # Just the void-operand FLIRV-T1 (twice: once for Load's own use of
        # void_val, once for Ret's use of Load's result) -- no FLIRV-M1
        # about a non-pointer base, since _check_load bails out early.
        t.require(any(v.rule_id == "FLIRV-T1" for v in e.violations), e.violations)
        t.require(not any(v.rule_id == "FLIRV-M1" for v in e.violations), e.violations)


def test_store_skips_further_checks_when_base_type_unresolved():
    module = FLIRModule("firescript")
    callee = FLIRFunction("callee", return_type=VOID)
    callee.new_block().instructions.append(Ret())
    module.add_function(callee)
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    call_inst = Call("callee", [], VOID)
    entry.instructions.append(call_inst)
    void_val = call_inst.result()
    v = entry.add(ConstInt("1", I32))
    entry.add(Store(I32, void_val, 0, v))  # base type unresolved: must not crash further
    entry.instructions.append(Ret())
    try:
        module.validate()
        t.require(False, "no error raised")
    except IRVerificationError as e:
        t.require(any(v.rule_id == "FLIRV-T1" for v in e.violations), e.violations)
        t.require(not any(v.rule_id == "FLIRV-M1" for v in e.violations), e.violations)


# ---------------------------------------------------------------------------
# M3: ptradd base is not a pointer.
# ---------------------------------------------------------------------------

def test_m3_ptradd_base_non_pointer():
    module, func = _simple_module()
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    idx = entry.add(ConstInt("0", I32))
    entry.add(PtrAdd(a, idx, 4))  # base is i32, not a pointer
    zero = entry.add(ConstInt("0", I32))
    entry.instructions.append(Ret(zero))
    _expect_rule(module, "FLIRV-M3")

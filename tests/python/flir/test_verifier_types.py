"""Unit tests for FLIR Tier-1 type/memory rules (FLIRV-T, FLIRV-M1-M3) in
firescript/flir/verifier.py. One negative case per rule id (spec section 9)."""
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
    ConstStr,
    Cvt,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    GlobalLoad,
    GlobalStore,
    I32,
    I64,
    Load,
    Neg,
    Not,
    PTR,
    PtrAdd,
    Ret,
    SlotAddr,
    SlotDecl,
    SlotLoad,
    SlotStore,
    Store,
    U32,
    VOID,
    ptr_to,
)


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


def test_t1_operand_from_unreachable_or_foreign_block():
    module, func = _simple_module()
    entry = func.new_block()
    dead = func.new_block()
    stray = dead.add(ConstInt("1", I32))  # never wired into the CFG
    entry.instructions.append(Ret(stray))
    dead_zero = dead.add(ConstInt("0", I32))
    dead.instructions.append(Ret(dead_zero))
    _expect_rule(module, "FLIRV-T1")


def test_t2_binop_result_type_mismatch():
    module, func = _simple_module()
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    b = entry.add(ConstInt("2", I32))
    bad = entry.add(BinOp("add", I32, a, b, BOOL))  # arithmetic must produce operand_type
    entry.instructions.append(Ret(a))
    _expect_rule(module, "FLIRV-T2")


def test_t2_not_requires_bool():
    module, func = _simple_module()
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    entry.add(Not(a))
    entry.instructions.append(Ret(a))
    _expect_rule(module, "FLIRV-T2")


def test_t2_cvt_from_type_mismatch():
    module, func = _simple_module()
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    entry.add(Cvt(a, I64, I32))  # a is actually I32, not I64
    entry.instructions.append(Ret(a))
    _expect_rule(module, "FLIRV-T2")


def test_t3_br_condition_not_bool():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    then_block = func.new_block()
    else_block = func.new_block()
    cond = entry.add(ConstInt("1", I32))
    entry.instructions.append(Br(cond, then_block.id, else_block.id))
    then_block.instructions.append(Ret())
    else_block.instructions.append(Ret())
    _expect_rule(module, "FLIRV-T3")


def test_t3_ret_type_mismatch():
    module, func = _simple_module()
    entry = func.new_block()
    s = entry.add(ConstStr("x"))
    entry.instructions.append(Ret(s))
    _expect_rule(module, "FLIRV-T3")


def test_t4_call_unresolved_callee():
    module, func = _simple_module()
    entry = func.new_block()
    entry.add(Call("does_not_exist", [], VOID))
    zero = entry.add(ConstInt("0", I32))
    entry.instructions.append(Ret(zero))
    _expect_rule(module, "FLIRV-T4")


def test_t4_call_argument_count_mismatch():
    module = FLIRModule("firescript")
    callee = FLIRFunction("callee", params=[("x", I32)], return_type=I32)
    callee_block = callee.new_block()
    callee_zero = callee_block.add(ConstInt("0", I32))
    callee_block.instructions.append(Ret(callee_zero))
    module.add_function(callee)
    caller = FLIRFunction("caller", return_type=I32)
    module.add_function(caller)
    entry = caller.new_block()
    result = entry.add(Call("callee", [], I32))
    entry.instructions.append(Ret(result))
    _expect_rule(module, "FLIRV-T4")


def test_t5_slotload_undeclared_slot():
    module, func = _simple_module()
    entry = func.new_block()
    v = entry.add(SlotLoad("nope", I32))
    entry.instructions.append(Ret(v))
    _expect_rule(module, "FLIRV-T5")


def test_t5_slot_declared_twice():
    module, func = _simple_module()
    entry = func.new_block()
    entry.add(SlotDecl("x", I32))
    entry.add(SlotDecl("x", I32))
    zero = entry.add(ConstInt("0", I32))
    entry.instructions.append(Ret(zero))
    _expect_rule(module, "FLIRV-T5")


def test_t6_gstore_to_readonly_global():
    module, func = _simple_module()
    module.globals.append(("g", I32, "0"))
    entry = func.new_block()
    v = entry.add(ConstInt("1", I32))
    entry.add(GlobalStore("g", v))
    entry.instructions.append(Ret(v))
    _expect_rule(module, "FLIRV-T6")


def test_m1_load_offset_not_a_field():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Point", kind="class")
    struct.fields = [("x", I32, 0), ("y", I32, 4)]
    struct.size = 8
    struct.align = 4
    module.add_struct(struct)
    func = FLIRFunction("f", params=[("p", ptr_to("Point"))], return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    p = SlotLoad("p", ptr_to("Point"))
    entry.instructions.append(p)
    p_val = p.result()
    bad = entry.add(Load(I32, p_val, 2))  # not a declared field offset
    entry.instructions.append(Ret(bad))
    _expect_rule(module, "FLIRV-M1")


def test_m1_load_type_mismatch_at_field_offset():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Point", kind="class")
    struct.fields = [("x", I32, 0), ("y", I32, 4)]
    struct.size = 8
    struct.align = 4
    module.add_struct(struct)
    func = FLIRFunction("f", params=[("p", ptr_to("Point"))], return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    p = entry.add(SlotLoad("p", ptr_to("Point")))
    entry.add(Load(BOOL, p, 0))  # field x is i32, not bool
    zero = entry.add(ConstInt("0", I32))
    entry.instructions.append(Ret(zero))
    _expect_rule(module, "FLIRV-M1")


def test_m3_ptradd_nonpositive_scale():
    module, func = _simple_module()
    entry = func.new_block()
    base = entry.add(ConstInt("0", I64))
    base_ptr = entry.add(Cvt(base, I64, PTR))
    idx = entry.add(ConstInt("0", I32))
    entry.add(PtrAdd(base_ptr, idx, 0))
    zero = entry.add(ConstInt("0", I32))
    entry.instructions.append(Ret(zero))
    _expect_rule(module, "FLIRV-M3")


def test_verifier_types_accepts_clean_module():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Point", kind="class")
    struct.fields = [("x", I32, 0), ("y", I32, 4)]
    struct.size = 8
    struct.align = 4
    module.add_struct(struct)

    func = FLIRFunction("sum_xy", params=[("p", ptr_to("Point"))], return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    p = entry.add(SlotLoad("p", ptr_to("Point")))
    x = entry.add(Load(I32, p, 0))
    y = entry.add(Load(I32, p, 4))
    total = entry.add(BinOp("add", I32, x, y, I32))
    entry.instructions.append(Ret(total))

    module.validate()  # must not raise

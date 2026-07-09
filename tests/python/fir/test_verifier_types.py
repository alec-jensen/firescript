"""Unit tests for FIR Tier-1 type rules (FIRV-T, FIRV-L1-L2, FIRV-G1-G3) in
firescript/fir/verifier.py. One negative case per rule id (spec section 9),
built directly with FIRBuilder rather than through the full compiler."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from errors import IRVerificationError  # noqa: E402
from fir import FIRBuilder, FIRFunction, FIRModule, TypeDef, make_simple  # noqa: E402
from fir.ir_module import EnumVariantDef  # noqa: E402
from fir.ir_node import BinaryOpInst, NullLiteralInst  # noqa: E402
from fir.ir_types import ArrayType, GeneratorType  # noqa: E402

INT32 = make_simple("int32")
BOOL = make_simple("bool")
STRING = make_simple("string")


def _expect_rule(module: FIRModule, rule_id: str) -> None:
    try:
        module.validate()
        t.require(False, f"no error raised (expected {rule_id})")
    except IRVerificationError as e:
        t.require(any(v.rule_id == rule_id for v in e.violations), f"{rule_id} not in: {e}")


def test_t1_arithmetic_operand_type_mismatch():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    y = b.bool_literal(True, BOOL)
    b.emit(BinaryOpInst("+", x, y, INT32))
    b.ret(x)
    _expect_rule(module, "FIRV-T1")


def test_t1_comparison_result_not_bool():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    y = b.int_literal("2", INT32)
    b.emit(BinaryOpInst("==", x, y, INT32))  # should be bool
    b.ret(x)
    _expect_rule(module, "FIRV-T1")


def test_t2_unary_bang_requires_bool():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    result = b.unary_op("!", x, BOOL)
    b.ret(result)
    _expect_rule(module, "FIRV-T2")


def test_t4_branch_condition_not_bool():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    then_block = b.new_block()
    else_block = b.new_block()
    cond = b.int_literal("1", INT32)
    b.branch(cond, then_block.id, else_block.id)
    b.position_at(then_block)
    b.ret()
    b.position_at(else_block)
    b.ret()
    _expect_rule(module, "FIRV-T4")


def test_t4_return_value_type_mismatch():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    s = b.string_literal("x", STRING)
    b.ret(s)
    _expect_rule(module, "FIRV-T4")


def test_t4_void_return_with_value():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    v = b.int_literal("1", INT32)
    b.ret(v)
    _expect_rule(module, "FIRV-T4")


def test_t4_nonvoid_return_without_value():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    b.ret()
    _expect_rule(module, "FIRV-T4")


def test_t5_call_argument_count_mismatch():
    module = FIRModule("firescript")
    callee = FIRFunction("callee", params=[("x", INT32)], return_type=INT32)
    module.add_function(callee)
    caller = FIRFunction("caller", return_type=INT32)
    module.add_function(caller)
    b = FIRBuilder(caller)
    result = b.call("callee", [], [], INT32)
    b.ret(result)
    _expect_rule(module, "FIRV-T5")


def test_t5_call_argument_type_mismatch():
    module = FIRModule("firescript")
    callee = FIRFunction("callee", params=[("x", INT32)], return_type=INT32)
    module.add_function(callee)
    caller = FIRFunction("caller", return_type=INT32)
    module.add_function(caller)
    b = FIRBuilder(caller)
    s = b.string_literal("x", STRING)
    result = b.call("callee", [s], ["own"], INT32)
    b.ret(result)
    _expect_rule(module, "FIRV-T5")


def test_t5_call_arg_mode_invalid():
    module = FIRModule("firescript")
    callee = FIRFunction("callee", params=[("x", INT32)], return_type=INT32)
    module.add_function(callee)
    caller = FIRFunction("caller", return_type=INT32)
    module.add_function(caller)
    b = FIRBuilder(caller)
    x = b.int_literal("1", INT32)
    result = b.call("callee", [x], ["not_a_mode"], INT32)
    b.ret(result)
    _expect_rule(module, "FIRV-T5")


def test_t7_load_field_unknown_field():
    module = FIRModule("firescript")
    point_t = make_simple("Point")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(point_t, [])
    bad = b.load_field(obj, "y", INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-T7")


def test_t7_load_field_on_enum_is_invalid():
    module = FIRModule("firescript")
    module.add_type(TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A")]))
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    ev = b.construct_variant(enum_t, "A", [])
    bad = b.load_field(ev, "x", INT32)
    b.ret(b.int_literal("0", INT32))
    _expect_rule(module, "FIRV-T7")


def test_t8_index_array_non_integer_index():
    module = FIRModule("firescript")
    array_t = ArrayType(INT32, 3)
    func = FIRFunction("f", params=[("arr", array_t)], return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    arr = func.param_value("arr")
    idx = b.string_literal("x", STRING)
    bad = b.index_array(arr, idx, INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-T8")


def test_t9_allocate_field_count_mismatch():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32), ("y", INT32)]))
    point_t = make_simple("Point")
    func = FIRFunction("f", return_type=point_t)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    obj = b.allocate(point_t, [one])  # missing "y"
    b.ret(obj)
    _expect_rule(module, "FIRV-T9")


def test_t10_construct_variant_unknown_variant():
    module = FIRModule("firescript")
    module.add_type(TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A")]))
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=enum_t)
    module.add_function(func)
    b = FIRBuilder(func)
    ev = b.construct_variant(enum_t, "NotAVariant", [])
    b.ret(ev)
    _expect_rule(module, "FIRV-T10")


def test_t11_extract_tag_on_non_enum():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    bad = b.extract_tag(x, INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-T11")


def test_t11_extract_payload_field_index_out_of_range():
    module = FIRModule("firescript")
    module.add_type(
        TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A", [("v", INT32)])])
    )
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    ev = b.construct_variant(enum_t, "A", [one])
    bad = b.extract_payload_field(ev, "A", 5, INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-T11")


def test_t12_int_literal_out_of_range():
    module = FIRModule("firescript")
    int8 = make_simple("int8")
    func = FIRFunction("f", return_type=int8)
    module.add_function(func)
    b = FIRBuilder(func)
    v = b.int_literal("200", int8)
    b.ret(v)
    _expect_rule(module, "FIRV-T12")


def test_t12_null_literal_non_nullable():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    n = b.emit(NullLiteralInst(STRING))  # STRING is not nullable
    b.ret(n)
    _expect_rule(module, "FIRV-T12")


def test_l1_load_var_never_declared():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    bad = b.load_var("nonexistent", INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-L1")


def test_l2_load_var_type_mismatch():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    b.declare_local("x", INT32, one)
    bad = b.load_var("x", STRING)  # declared int32, loaded as string
    b.ret(one)
    _expect_rule(module, "FIRV-L2")


def test_g1_yield_outside_generator():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    v = b.int_literal("1", INT32)
    b.yield_value(v)
    b.ret()
    _expect_rule(module, "FIRV-G1")


def test_g2_generator_return_with_value():
    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=GeneratorType(INT32), is_generator=True)
    module.add_function(func)
    b = FIRBuilder(func)
    v = b.int_literal("1", INT32)
    b.ret(v)
    _expect_rule(module, "FIRV-G2")


def test_g3_gen_new_non_generator_target():
    module = FIRModule("firescript")
    not_gen = FIRFunction("not_gen", return_type=INT32)
    module.add_function(not_gen)
    func = FIRFunction("f", return_type=GeneratorType(INT32))
    module.add_function(func)
    b = FIRBuilder(func)
    g = b.gen_new("not_gen", [], GeneratorType(INT32))
    b.ret(g)
    _expect_rule(module, "FIRV-G3")


def test_verifier_types_accepts_clean_generator():
    module = FIRModule("firescript")
    gen = FIRFunction("g", return_type=GeneratorType(INT32), is_generator=True)
    module.add_function(gen)
    gb = FIRBuilder(gen)
    one = gb.int_literal("1", INT32)
    gb.yield_value(one)
    gb.ret()

    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    g_val = b.gen_new("g", [], GeneratorType(INT32))
    has_next = b.gen_next(g_val, BOOL)
    value = b.gen_value(g_val, INT32)
    b.ret(value)

    module.validate()  # must not raise

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
from fir.ir_module import EnumVariantDef, GlobalConstant  # noqa: E402
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


def test_t1_arithmetic_operands_differing_types():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    y = b.string_literal("x", STRING)
    b.emit(BinaryOpInst("+", x, y, INT32))
    b.ret(x)
    _expect_rule(module, "FIRV-T1")


def test_t1_arithmetic_result_type_mismatch():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    y = b.int_literal("2", INT32)
    b.emit(BinaryOpInst("+", x, y, STRING))  # result should be int32
    b.ret(x)
    _expect_rule(module, "FIRV-T1")


def test_t1_string_concat_result_not_string():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    s1 = b.string_literal("a", STRING)
    s2 = b.string_literal("b", STRING)
    b.emit(BinaryOpInst("+", s1, s2, INT32))  # string '+' must produce string
    b.ret(b.int_literal("0", INT32))
    _expect_rule(module, "FIRV-T1")


def test_t1_logical_operand_not_bool():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    y = b.bool_literal(True, BOOL)
    result = b.emit(BinaryOpInst("&&", x, y, BOOL))
    b.ret(result)
    _expect_rule(module, "FIRV-T1")


def test_t2_unary_minus_result_type_mismatch():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    result = b.unary_op("-", x, STRING)  # result type must match operand type
    b.ret(x)
    _expect_rule(module, "FIRV-T2")


def test_t2_unary_minus_requires_numeric():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.bool_literal(True, BOOL)
    result = b.unary_op("-", x, BOOL)
    b.ret(result)
    _expect_rule(module, "FIRV-T2")


def test_t5_call_result_shape_mismatch():
    module = FIRModule("firescript")
    callee = FIRFunction("callee", return_type=None)
    module.add_function(callee)
    cb = FIRBuilder(callee)
    cb.ret()
    caller = FIRFunction("caller", return_type=INT32)
    module.add_function(caller)
    b = FIRBuilder(caller)
    result = b.call("callee", [], [], INT32)  # callee returns void, call claims int32
    b.ret(result)
    _expect_rule(module, "FIRV-T5")


def test_t6_method_call_argument_count_mismatch():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    method = FIRFunction("Point.get", params=[("this", point_t), ("n", INT32)], return_type=INT32)
    module.add_function(method)
    mb = FIRBuilder(method)
    mb.ret(mb.int_literal("0", INT32))
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(point_t, [b.int_literal("1", INT32)])
    result = b.method_call(obj, "get", [], [], INT32)  # missing "n" argument
    b.ret(result)
    _expect_rule(module, "FIRV-T6")


def test_t6_method_call_result_type_mismatch():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    method = FIRFunction("Point.get", params=[("this", point_t)], return_type=INT32)
    module.add_function(method)
    mb = FIRBuilder(method)
    mb.ret(mb.int_literal("0", INT32))
    func = FIRFunction("f", return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(point_t, [b.int_literal("1", INT32)])
    result = b.method_call(obj, "get", [], [], STRING)  # callee returns int32
    b.ret(result)
    _expect_rule(module, "FIRV-T6")


def test_t7_store_field_object_non_class_type():
    module = FIRModule("firescript")
    array_t = ArrayType(INT32, 3)
    func = FIRFunction("f", params=[("arr", array_t)], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    arr = func.param_value("arr")
    v = b.int_literal("2", INT32)
    b.store_field(arr, "y", v)  # array type has no fields
    b.ret()
    _expect_rule(module, "FIRV-T7")


def test_t7_store_field_on_enum_is_invalid():
    module = FIRModule("firescript")
    module.add_type(TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A")]))
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    ev = b.construct_variant(enum_t, "A", [])
    v = b.int_literal("1", INT32)
    b.store_field(ev, "x", v)
    b.ret()
    _expect_rule(module, "FIRV-T7")


def test_t7_store_field_value_type_mismatch():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(point_t, [b.int_literal("1", INT32)])
    bad = b.string_literal("x", STRING)
    b.store_field(obj, "x", bad)
    b.ret()
    _expect_rule(module, "FIRV-T7")


def test_t8_store_array_non_array_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    idx = b.int_literal("0", INT32)
    v = b.int_literal("2", INT32)
    b.store_array(x, idx, v)
    b.ret()
    _expect_rule(module, "FIRV-T8")


def test_t8_store_array_value_type_mismatch():
    module = FIRModule("firescript")
    array_t = ArrayType(INT32, 3)
    func = FIRFunction("f", params=[("arr", array_t)], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    arr = func.param_value("arr")
    idx = b.int_literal("0", INT32)
    bad = b.string_literal("x", STRING)
    b.store_array(arr, idx, bad)
    b.ret()
    _expect_rule(module, "FIRV-T8")


def test_t9_allocate_explicit_constructor_passed_args():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    ctor = FIRFunction("Point.Point", params=[("this", point_t), ("x", INT32)], return_type=None)
    module.add_function(ctor)
    cb = FIRBuilder(ctor)
    cb.ret()
    func = FIRFunction("f", return_type=point_t)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    obj = b.allocate(point_t, [one])  # bare Allocate must not carry args here
    b.ret(obj)
    _expect_rule(module, "FIRV-T9")


def test_t9_allocate_argument_type_mismatch():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    func = FIRFunction("f", return_type=point_t)
    module.add_function(func)
    b = FIRBuilder(func)
    bad = b.string_literal("x", STRING)
    obj = b.allocate(point_t, [bad])
    b.ret(obj)
    _expect_rule(module, "FIRV-T9")


def test_t10_construct_variant_payload_count_mismatch():
    module = FIRModule("firescript")
    module.add_type(
        TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A", [("v", INT32)])])
    )
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=enum_t)
    module.add_function(func)
    b = FIRBuilder(func)
    ev = b.construct_variant(enum_t, "A", [])  # missing payload value
    b.ret(ev)
    _expect_rule(module, "FIRV-T10")


def test_t10_construct_variant_payload_type_mismatch():
    module = FIRModule("firescript")
    module.add_type(
        TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A", [("v", INT32)])])
    )
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=enum_t)
    module.add_function(func)
    b = FIRBuilder(func)
    bad = b.string_literal("x", STRING)
    ev = b.construct_variant(enum_t, "A", [bad])
    b.ret(ev)
    _expect_rule(module, "FIRV-T10")


def test_t11_extract_payload_field_on_non_enum():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    bad = b.extract_payload_field(x, "A", 0, INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-T11")


def test_t11_extract_payload_field_unknown_variant():
    module = FIRModule("firescript")
    module.add_type(
        TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A", [("v", INT32)])])
    )
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    ev = b.construct_variant(enum_t, "A", [b.int_literal("1", INT32)])
    bad = b.extract_payload_field(ev, "NotAVariant", 0, INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-T11")


def test_t11_extract_payload_field_result_type_mismatch():
    module = FIRModule("firescript")
    module.add_type(
        TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A", [("v", INT32)])])
    )
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    ev = b.construct_variant(enum_t, "A", [b.int_literal("1", INT32)])
    bad = b.extract_payload_field(ev, "A", 0, STRING)  # payload field is int32
    b.ret(bad)
    _expect_rule(module, "FIRV-T11")


def test_l2_store_var_type_mismatch():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    b.declare_local("x", INT32, one)
    bad = b.string_literal("y", STRING)
    b.store_var("x", bad)
    b.ret()
    _expect_rule(module, "FIRV-L2")


def test_l1l2_load_var_of_global_constant_accepted():
    """LoadVar of a bare name that resolves to a global constant (not a
    local/param) must not trigger FIRV-L1, and its result type must match
    the constant's declared type."""
    module = FIRModule("firescript")
    module.add_constant(GlobalConstant("K", INT32, "42"))
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    v = b.load_var("K", INT32)
    b.ret(v)
    module.validate()  # must not raise


def test_t12_int_literal_unparseable_text():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    v = b.int_literal("not_a_number", INT32)
    b.ret(v)
    _expect_rule(module, "FIRV-T12")


def test_t12_int_literal_non_numeric_type():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    v = b.int_literal("1", BOOL)  # int literal typed as bool
    b.ret(v)
    _expect_rule(module, "FIRV-T12")


def test_g1_yield_value_type_mismatch():
    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=GeneratorType(INT32), is_generator=True)
    module.add_function(func)
    b = FIRBuilder(func)
    bad = b.string_literal("x", STRING)
    b.yield_value(bad)  # generator element type is int32
    b.ret()
    _expect_rule(module, "FIRV-G1")


def test_g3_gen_new_argument_count_mismatch():
    module = FIRModule("firescript")
    gen = FIRFunction("g", params=[("n", INT32)], return_type=GeneratorType(INT32), is_generator=True)
    module.add_function(gen)
    gb = FIRBuilder(gen)
    gb.yield_value(gen.param_value("n"))
    gb.ret()
    func = FIRFunction("f", return_type=GeneratorType(INT32))
    module.add_function(func)
    b = FIRBuilder(func)
    g_val = b.gen_new("g", [], GeneratorType(INT32))  # missing "n" argument
    b.ret(g_val)
    _expect_rule(module, "FIRV-G3")


def test_g3_gen_new_result_not_generator_type():
    module = FIRModule("firescript")
    gen = FIRFunction("g", return_type=GeneratorType(INT32), is_generator=True)
    module.add_function(gen)
    gb = FIRBuilder(gen)
    gb.yield_value(gb.int_literal("1", INT32))
    gb.ret()
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    g_val = b.gen_new("g", [], INT32)  # result type should be generator<int32>
    b.ret(g_val)
    _expect_rule(module, "FIRV-G3")


def test_g3_gen_new_element_type_mismatch():
    module = FIRModule("firescript")
    gen = FIRFunction("g", return_type=GeneratorType(INT32), is_generator=True)
    module.add_function(gen)
    gb = FIRBuilder(gen)
    gb.yield_value(gb.int_literal("1", INT32))
    gb.ret()
    func = FIRFunction("f", return_type=GeneratorType(STRING))
    module.add_function(func)
    b = FIRBuilder(func)
    g_val = b.gen_new("g", [], GeneratorType(STRING))  # generator's element is int32
    b.ret(g_val)
    _expect_rule(module, "FIRV-G3")


def test_g3_gen_next_non_generator_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    result = b.gen_next(x, BOOL)
    b.ret(result)
    _expect_rule(module, "FIRV-G3")


def test_g3_gen_value_non_generator_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    result = b.gen_value(x, INT32)
    b.ret(result)
    _expect_rule(module, "FIRV-G3")


def test_g3_gen_value_result_type_mismatch():
    module = FIRModule("firescript")
    gen = FIRFunction("g", return_type=GeneratorType(INT32), is_generator=True)
    module.add_function(gen)
    gb = FIRBuilder(gen)
    gb.yield_value(gb.int_literal("1", INT32))
    gb.ret()
    func = FIRFunction("f", return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    g_val = b.gen_new("g", [], GeneratorType(INT32))
    b.gen_next(g_val, BOOL)
    bad = b.gen_value(g_val, STRING)  # generator element type is int32
    b.ret(bad)
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

"""Additional unit tests for FIR Tier-1 type rules in firescript/fir/verifier.py,
covering branches not yet exercised by test_verifier_types.py: specific
sub-checks within already-tested rules (differing-types vs result-shape vs
arg-mode-count are each separate `if` branches sharing one rule id), and a
few D1/D2-fed None-operand early-return paths."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from errors import IRVerificationError  # noqa: E402
from fir import FIRBuilder, FIRFunction, FIRModule, TypeDef, make_simple  # noqa: E402
from fir.ir_module import EnumVariantDef  # noqa: E402
from fir.ir_node import BinaryOpInst, GenNewInst, ParamValue, UnaryOpInst, YieldInst  # noqa: E402
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


def test_t1_comparison_operands_differing_types():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    y = b.string_literal("s", STRING)
    result = b.emit(BinaryOpInst("==", x, y, BOOL))
    b.ret(result)
    _expect_rule(module, "FIRV-T1")


def test_t1_arithmetic_same_type_but_non_numeric():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.bool_literal(True, BOOL)
    y = b.bool_literal(False, BOOL)
    result = b.emit(BinaryOpInst("+", x, y, BOOL))
    b.ret(result)
    _expect_rule(module, "FIRV-T1")


def test_t2_unary_bang_result_not_bool():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.bool_literal(True, BOOL)
    result = b.emit(UnaryOpInst("!", x, INT32))
    b.ret(x)
    _expect_rule(module, "FIRV-T2")


def test_t2_unary_op_on_undominated_operand_is_lenient():
    # A ParamValue that doesn't name a real parameter resolves to None
    # (FIRV-D2), and _check_unary_op must skip its own type checks rather
    # than crash on a None operand type.
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    bogus = ParamValue("not_a_param", BOOL)
    b.emit(UnaryOpInst("!", bogus, BOOL))
    b.ret(b.bool_literal(True, BOOL))
    _expect_rule(module, "FIRV-D2")


def test_t5_call_arg_mode_count_mismatch():
    module = FIRModule("firescript")
    callee = FIRFunction("callee", params=[("x", INT32)], return_type=INT32)
    module.add_function(callee)
    caller = FIRFunction("caller", return_type=INT32)
    module.add_function(caller)
    b = FIRBuilder(caller)
    x = b.int_literal("1", INT32)
    # Two arg_modes for one argument: `[]` would fall back to the builder's
    # default (one "own" per arg), so mismatch the other way.
    result = b.call("callee", [x], ["own", "own"], INT32)
    b.ret(result)
    _expect_rule(module, "FIRV-T5")


def test_t5_call_result_type_mismatch():
    module = FIRModule("firescript")
    callee = FIRFunction("callee", return_type=INT32)
    cb = FIRBuilder(callee)
    cb.ret(cb.int_literal("0", INT32))
    module.add_function(callee)
    caller = FIRFunction("caller", return_type=STRING)
    module.add_function(caller)
    b = FIRBuilder(caller)
    result = b.call("callee", [], [], STRING)
    b.ret(result)
    _expect_rule(module, "FIRV-T5")


def test_t6_method_call_arg_mode_invalid():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    method = FIRFunction("Point.move", params=[("this", point_t), ("dx", INT32)], return_type=None)
    mb = FIRBuilder(method)
    mb.ret()
    module.add_function(method)

    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(point_t, [b.int_literal("1", INT32)])
    dx = b.int_literal("1", INT32)
    b.method_call(obj, "move", [dx], ["not_a_mode"], None)
    b.ret()
    _expect_rule(module, "FIRV-T6")


def test_t6_method_call_result_shape_mismatch():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    method = FIRFunction("Point.getX", params=[("this", point_t)], return_type=INT32)
    mb = FIRBuilder(method)
    mb.ret(mb.int_literal("0", INT32))
    module.add_function(method)

    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(point_t, [b.int_literal("1", INT32)])
    b.method_call(obj, "getX", [], [], None)  # void call site, non-void callee
    b.ret()
    _expect_rule(module, "FIRV-T6")


def test_t7_load_field_non_class_operand():
    # A SimpleType (e.g. int32) still resolves a "class name" (its own type
    # name) via _class_name_of, so LoadField on a plain scalar is lenient
    # (the class-name lookup just misses and _check_load_field returns
    # early) -- ArrayType is what actually has no class name at all.
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    arr = b.array_literal([b.int_literal("1", INT32)], ArrayType(INT32, size=1))
    bad = b.load_field(arr, "field", INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-T7")


def test_t7_load_field_result_type_mismatch():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    func = FIRFunction("f", return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(point_t, [b.int_literal("1", INT32)])
    bad = b.load_field(obj, "x", STRING)  # field is int32, declared string
    b.ret(bad)
    _expect_rule(module, "FIRV-T7")


def test_t7_store_field_unknown_field():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(point_t, [b.int_literal("1", INT32)])
    v = b.int_literal("2", INT32)
    b.store_field(obj, "not_a_field", v)
    b.ret()
    _expect_rule(module, "FIRV-T7")


def test_t8_index_array_result_type_mismatch():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    arr = b.array_literal([b.int_literal("1", INT32)], ArrayType(INT32, size=1))
    idx = b.int_literal("0", INT32)
    bad = b.index_array(arr, idx, STRING)  # elements are int32, declared string
    b.ret(bad)
    _expect_rule(module, "FIRV-T8")


def test_t8_store_array_index_non_integer():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    arr = b.array_literal([b.int_literal("1", INT32)], ArrayType(INT32, size=1))
    bad_idx = b.string_literal("nope", STRING)
    v = b.int_literal("2", INT32)
    b.store_array(arr, bad_idx, v)
    b.ret()
    _expect_rule(module, "FIRV-T8")


def test_g1_yield_value_from_undominated_operand_is_lenient():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=GeneratorType(INT32), is_generator=True)
    module.add_function(func)
    b = FIRBuilder(func)
    bogus = ParamValue("not_a_param", INT32)
    b.emit(YieldInst(bogus))
    b.ret()
    _expect_rule(module, "FIRV-D2")


def test_g3_gen_new_unresolved_generator_ref_is_lenient():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    gen_t = GeneratorType(INT32)
    b.emit(GenNewInst("does_not_exist", [], gen_t))
    b.ret()
    module.validate()  # unresolved generator_ref is not checked at Tier 1; must not raise


def test_g3_gen_next_must_produce_bool():
    module = FIRModule("firescript")
    gen_func = FIRFunction("gen", return_type=GeneratorType(INT32), is_generator=True)
    gb = FIRBuilder(gen_func)
    gb.yield_value(gb.int_literal("1", INT32))
    gb.ret()
    module.add_function(gen_func)

    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    gen = b.gen_new("gen", [], GeneratorType(INT32))
    bad = b.gen_next(gen, INT32)  # GenNext must produce bool
    b.ret(bad)
    _expect_rule(module, "FIRV-G3")


def test_g3_gen_value_from_undominated_operand_is_lenient():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    from fir.ir_node import GenValueInst

    bogus = ParamValue("not_a_param", GeneratorType(INT32))
    result = b.emit(GenValueInst(bogus, INT32))
    b.ret(result)
    _expect_rule(module, "FIRV-D2")

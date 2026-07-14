"""Additional unit tests for firescript/fir/verifier.py filling coverage gaps
left by test_verifier_structure.py / test_verifier_types.py: duplicate-name
(FIRV-S6) structural checks, type-def base-chain / generic-argument checks,
operand-resolution (FIRV-D1-D3) edge cases, and the remaining per-instruction
type-rule branches (Call/MethodCall/LoadField/StoreField/IndexArray/
StoreArray/Allocate/ConstructVariant/ExtractTag/ExtractPayloadField/Yield/
generator instructions) not already exercised elsewhere. Built directly with
FIRBuilder/hand-built IR objects per the pattern in test_verifier_types.py."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from errors import IRVerificationError  # noqa: E402
from fir import (  # noqa: E402
    ArrayType,
    FIRBuilder,
    FIRFunction,
    FIRModule,
    GeneratorType,
    GenericInstanceType,
    ParamValue,
    TypeDef,
    make_simple,
)
from fir.ir_module import EnumVariantDef, GlobalConstant  # noqa: E402
from fir.ir_node import (  # noqa: E402
    AllocateInst,
    BinaryOpInst,
    CallInst,
    ConstructVariantInst,
    DeclareLocalInst,
    GenNewInst,
    IntLiteralInst,
    LoadVarInst,
    MethodCallInst,
    NullLiteralInst,
    UnaryOpInst,
)

INT32 = make_simple("int32")
BOOL = make_simple("bool")
STRING = make_simple("string")


def _expect_rule(module: FIRModule, rule_id: str) -> None:
    try:
        module.validate()
        t.require(False, f"no error raised (expected {rule_id})")
    except IRVerificationError as e:
        t.require(any(v.rule_id == rule_id for v in e.violations), f"{rule_id} not in: {e}")


# -- FIRV-S6: duplicate top-level names -------------------------------------

def test_s6_duplicate_type_name():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Dup", "owned"))
    module.add_type(TypeDef("Dup", "owned"))
    _expect_rule(module, "FIRV-S6")


def test_s6_duplicate_function_name():
    module = FIRModule("firescript")
    f1 = FIRFunction("dup", return_type=None)
    FIRBuilder(f1).ret()
    f2 = FIRFunction("dup", return_type=None)
    FIRBuilder(f2).ret()
    module.add_function(f1)
    module.add_function(f2)
    _expect_rule(module, "FIRV-S6")


def test_s6_duplicate_constant_name():
    module = FIRModule("firescript")
    module.add_constant(GlobalConstant("DUP", INT32, "1"))
    module.add_constant(GlobalConstant("DUP", INT32, "2"))
    _expect_rule(module, "FIRV-S6")


# -- FIRV-S6: type-def structural rules --------------------------------------

def test_s6_enum_no_variants():
    module = FIRModule("firescript")
    module.add_type(TypeDef("E", "owned", kind="enum", variants=[]))
    _expect_rule(module, "FIRV-S6")


def test_s6_enum_has_base():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Base", "owned"))
    module.add_type(
        TypeDef("E", "owned", kind="enum", base="Base", variants=[EnumVariantDef("A")])
    )
    _expect_rule(module, "FIRV-S6")


def test_s6_unresolved_base():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Child", "owned", base="MissingBase"))
    _expect_rule(module, "FIRV-S6")


def test_s6_cyclic_base():
    module = FIRModule("firescript")
    module.add_type(TypeDef("A", "owned", base="B"))
    module.add_type(TypeDef("B", "owned", base="A"))
    _expect_rule(module, "FIRV-S6")


def test_s6_generic_type_reference_omits_args():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Pair", "owned", generic_params=["T", "U"]))
    module.add_type(TypeDef("Box", "owned", fields=[("p", make_simple("Pair"))]))
    _expect_rule(module, "FIRV-S6")


def test_s6_generic_instance_arg_count_mismatch():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Pair", "owned", generic_params=["T", "U"]))
    module.add_type(
        TypeDef(
            "Box2", "owned",
            fields=[("p", GenericInstanceType("Pair", [INT32]))],
        )
    )
    _expect_rule(module, "FIRV-S6")


def test_s6_generator_field_type_recurses_into_generic_check():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Pair", "owned", generic_params=["T", "U"]))
    module.add_type(
        TypeDef("Box3", "owned", fields=[("g", GeneratorType(make_simple("Pair")))])
    )
    _expect_rule(module, "FIRV-S6")


def test_verifier_accepts_clean_type_defs():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Base", "owned", fields=[("x", INT32)]))
    module.add_type(TypeDef("Child", "owned", base="Base", fields=[("y", INT32)]))
    module.validate()  # must not raise


# -- FIRV-D1/D2/D3: operand resolution ---------------------------------------

def test_d2_param_value_not_a_parameter():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    ghost = ParamValue("ghost", INT32)
    one = b.int_literal("1", INT32)
    b.emit(BinaryOpInst("+", ghost, one, INT32))
    b.ret(one)
    _expect_rule(module, "FIRV-D2")


def test_d1_operand_from_other_function():
    module = FIRModule("firescript")
    other = FIRFunction("other", return_type=INT32)
    module.add_function(other)
    ob = FIRBuilder(other)
    foreign_val = ob.int_literal("1", INT32)
    ob.ret(foreign_val)

    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    result = b.binary_op("+", foreign_val, foreign_val, INT32)
    b.ret(result)
    _expect_rule(module, "FIRV-D1")


def test_d1_unreachable_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    entry = b.current_block
    dead = b.new_block()
    b.position_at(dead)
    x = b.int_literal("1", INT32)
    b.ret()
    b.position_at(entry)
    result = b.binary_op("+", x, x, INT32)
    b.ret(result)
    _expect_rule(module, "FIRV-D1")


def test_d1_dominance_failure_sibling_branch():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    entry = b.current_block
    block_a = b.new_block()
    block_b = b.new_block()
    block_c = b.new_block()

    b.position_at(entry)
    cond = b.bool_literal(True, BOOL)
    b.branch(cond, block_a.id, block_b.id)

    b.position_at(block_a)
    x = b.int_literal("1", INT32)
    b.jump(block_c.id)

    b.position_at(block_b)
    y = b.binary_op("+", x, x, INT32)
    b.jump(block_c.id)

    b.position_at(block_c)
    b.ret(y)
    _expect_rule(module, "FIRV-D1")


def test_d1_unsupported_operand_kind():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    result = b.emit(BinaryOpInst("+", "not_a_value", one, INT32))
    b.ret(result)
    _expect_rule(module, "FIRV-D1")


def test_d3_void_operand_used_as_value():
    module = FIRModule("firescript")
    void_fn = FIRFunction("void_fn", return_type=None)
    module.add_function(void_fn)
    vb = FIRBuilder(void_fn)
    vb.ret()

    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    call_inst = CallInst("void_fn", [], [], None)
    b.emit(call_inst)
    void_val = call_inst.result()
    result = b.binary_op("+", void_val, void_val, INT32)
    b.ret(result)
    _expect_rule(module, "FIRV-D3")


def test_type_assignable_skips_check_on_invalid_operand():
    """_type_assignable(None, expected) returns True (line coverage for the
    'unresolved operand' early-out); the bogus operand still raises its own
    FIRV-D1, but no additional FIRV-T5 argument-type violation piles on."""
    module = FIRModule("firescript")
    callee = FIRFunction("callee", params=[("x", INT32)], return_type=INT32)
    module.add_function(callee)
    caller = FIRFunction("caller", return_type=INT32)
    module.add_function(caller)
    b = FIRBuilder(caller)
    call_inst = CallInst("callee", ["not_a_value"], ["own"], INT32)
    result = b.emit(call_inst)
    b.ret(result)
    _expect_rule(module, "FIRV-D1")


def test_type_assignable_array_size_mismatch():
    module = FIRModule("firescript")
    arr5 = ArrayType(INT32, 5)
    arr3 = ArrayType(INT32, 3)
    callee = FIRFunction("callee", params=[("arr", arr5)], return_type=INT32)
    module.add_function(callee)
    caller = FIRFunction("caller", params=[("small", arr3)], return_type=INT32)
    module.add_function(caller)
    b = FIRBuilder(caller)
    result = b.call("callee", [caller.param_value("small")], ["own"], INT32)
    b.ret(result)
    _expect_rule(module, "FIRV-T5")


# -- FIRV-T1: binary op remaining branches -----------------------------------

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


def test_t1_logical_result_not_bool():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.bool_literal(True, BOOL)
    y = b.bool_literal(False, BOOL)
    result = b.emit(BinaryOpInst("&&", x, y, INT32))
    b.ret(result)
    _expect_rule(module, "FIRV-T1")


def test_t1_string_concat_result_not_string():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.string_literal("a", STRING)
    y = b.string_literal("b", STRING)
    result = b.emit(BinaryOpInst("+", x, y, INT32))
    b.ret(result)
    _expect_rule(module, "FIRV-T1")


def test_t1_arithmetic_requires_numeric():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.string_literal("a", STRING)
    y = b.string_literal("b", STRING)
    result = b.emit(BinaryOpInst("-", x, y, STRING))
    b.ret(result)
    _expect_rule(module, "FIRV-T1")


def test_t1_arithmetic_result_type_mismatch():
    module = FIRModule("firescript")
    int64 = make_simple("int64")
    func = FIRFunction("f", return_type=int64)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    y = b.int_literal("2", INT32)
    result = b.emit(BinaryOpInst("+", x, y, int64))
    b.ret(result)
    _expect_rule(module, "FIRV-T1")


# -- FIRV-T2: unary op remaining branches ------------------------------------

def test_t2_unary_minus_requires_numeric():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.string_literal("a", STRING)
    result = b.unary_op("-", x, STRING)
    b.ret(result)
    _expect_rule(module, "FIRV-T2")


def test_t2_unary_minus_result_type_mismatch():
    module = FIRModule("firescript")
    int64 = make_simple("int64")
    func = FIRFunction("f", return_type=int64)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    result = b.unary_op("-", x, int64)
    b.ret(result)
    _expect_rule(module, "FIRV-T2")


# -- FIRV-T5: Call remaining branches -----------------------------------------

def test_t5_call_arg_modes_count_mismatch():
    module = FIRModule("firescript")
    callee = FIRFunction("callee", params=[("x", INT32)], return_type=INT32)
    module.add_function(callee)
    caller = FIRFunction("caller", return_type=INT32)
    module.add_function(caller)
    b = FIRBuilder(caller)
    x = b.int_literal("1", INT32)
    result = b.emit(CallInst("callee", [x], ["own", "own"], INT32))
    b.ret(result)
    _expect_rule(module, "FIRV-T5")


def test_t5_call_result_shape_mismatch():
    module = FIRModule("firescript")
    callee = FIRFunction("callee", return_type=INT32)
    cb = FIRBuilder(callee)
    cb.ret(cb.int_literal("1", INT32))
    module.add_function(callee)
    caller = FIRFunction("caller", return_type=None)
    module.add_function(caller)
    b = FIRBuilder(caller)
    b.emit(CallInst("callee", [], [], None))  # void result vs non-void callee
    b.ret()
    _expect_rule(module, "FIRV-T5")


def test_t5_call_result_type_mismatch():
    module = FIRModule("firescript")
    callee = FIRFunction("callee", return_type=INT32)
    cb = FIRBuilder(callee)
    cb.ret(cb.int_literal("1", INT32))
    module.add_function(callee)
    caller = FIRFunction("caller", return_type=STRING)
    module.add_function(caller)
    b = FIRBuilder(caller)
    result = b.call("callee", [], [], STRING)
    b.ret(result)
    _expect_rule(module, "FIRV-T5")


# -- FIRV-T6: MethodCall ------------------------------------------------------

def _widget_module():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Widget", "owned", fields=[("x", INT32)]))
    widget_t = make_simple("Widget")
    getx = FIRFunction(
        "Widget.getX", params=[("this", widget_t)], return_type=INT32, param_modes=["borrow"]
    )
    gb = FIRBuilder(getx)
    gb.ret(gb.int_literal("0", INT32))
    module.add_function(getx)
    setx = FIRFunction(
        "Widget.setX", params=[("this", widget_t), ("v", INT32)], return_type=None,
        param_modes=["borrow", "own"],
    )
    sb = FIRBuilder(setx)
    sb.ret()
    module.add_function(setx)
    return module, widget_t


def test_t6_method_call_arg_modes_count_mismatch():
    module, widget_t = _widget_module()
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(widget_t, [b.int_literal("0", INT32)])
    extra = b.int_literal("1", INT32)
    # MethodCallInst.__init__ replaces a falsy (empty) arg_modes with a
    # matching-length default, so the mismatch must use a non-empty list.
    result = b.emit(MethodCallInst(obj, "getX", [extra], ["own", "own"], INT32))
    b.ret(result)
    _expect_rule(module, "FIRV-T6")


def test_t6_method_call_arg_mode_invalid():
    module, widget_t = _widget_module()
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(widget_t, [b.int_literal("0", INT32)])
    v = b.int_literal("1", INT32)
    b.method_call(obj, "setX", [v], ["not_a_mode"], None)
    b.ret()
    _expect_rule(module, "FIRV-T6")


def test_t6_method_call_receiver_non_class():
    module = FIRModule("firescript")
    array_t = ArrayType(INT32, 3)
    func = FIRFunction(
        "f", params=[("arr", array_t)], return_type=None, param_modes=["borrow"]
    )
    module.add_function(func)
    b = FIRBuilder(func)
    b.method_call(func.param_value("arr"), "foo", [], [], None)
    b.ret()
    module.validate()  # class_name is None for ArrayType -> intrinsic, must not raise


def test_t6_method_call_unresolved_intrinsic_method():
    module, widget_t = _widget_module()
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(widget_t, [b.int_literal("0", INT32)])
    b.method_call(obj, "notAMethod", [], [], None)
    b.ret()
    module.validate()  # unresolved method -> not checked further, must not raise


def test_t6_method_call_arg_count_mismatch():
    module, widget_t = _widget_module()
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(widget_t, [b.int_literal("0", INT32)])
    extra = b.int_literal("1", INT32)
    result = b.method_call(obj, "getX", [extra], ["own"], INT32)
    b.ret(result)
    _expect_rule(module, "FIRV-T6")


def test_t6_method_call_arg_type_mismatch():
    module, widget_t = _widget_module()
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(widget_t, [b.int_literal("0", INT32)])
    s = b.string_literal("x", STRING)
    b.method_call(obj, "setX", [s], ["own"], None)
    b.ret()
    _expect_rule(module, "FIRV-T6")


def test_t6_method_call_result_shape_mismatch():
    module, widget_t = _widget_module()
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(widget_t, [b.int_literal("0", INT32)])
    b.method_call(obj, "getX", [], [], None)  # void call result, non-void callee
    b.ret()
    _expect_rule(module, "FIRV-T6")


def test_t6_method_call_result_type_mismatch():
    module, widget_t = _widget_module()
    func = FIRFunction("f", return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(widget_t, [b.int_literal("0", INT32)])
    result = b.method_call(obj, "getX", [], [], STRING)
    b.ret(result)
    _expect_rule(module, "FIRV-T6")


def test_resolve_method_traverses_base_chain():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Base", "owned", fields=[("x", INT32)]))
    module.add_type(TypeDef("Derived", "owned", base="Base"))
    base_foo = FIRFunction(
        "Base.foo", params=[("this", make_simple("Base"))], return_type=INT32,
        param_modes=["borrow"],
    )
    fb = FIRBuilder(base_foo)
    fb.ret(fb.int_literal("1", INT32))
    module.add_function(base_foo)

    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(make_simple("Derived"), [b.int_literal("0", INT32)])
    result = b.method_call(obj, "foo", [], [], INT32)
    b.ret(result)
    module.validate()  # resolved via base chain, must not raise


# -- FIRV-T7: LoadField / StoreField remaining branches ----------------------

def test_t7_load_field_invalid_object_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    ghost = ParamValue("ghost", make_simple("Point"))
    bad = b.load_field(ghost, "x", INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-D2")


def test_t7_load_field_non_class_operand():
    module = FIRModule("firescript")
    array_t = ArrayType(INT32, 3)
    func = FIRFunction("f", params=[("arr", array_t)], return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    bad = b.load_field(func.param_value("arr"), "x", INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-T7")


def test_t7_load_field_result_type_mismatch():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    func = FIRFunction("f", return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(point_t, [b.int_literal("0", INT32)])
    bad = b.load_field(obj, "x", STRING)
    b.ret(bad)
    _expect_rule(module, "FIRV-T7")


def test_t7_store_field_invalid_object_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    ghost = ParamValue("ghost", make_simple("Point"))
    one = b.int_literal("1", INT32)
    b.store_field(ghost, "x", one)
    b.ret()
    _expect_rule(module, "FIRV-D2")


def test_t7_store_field_non_class_operand():
    module = FIRModule("firescript")
    array_t = ArrayType(INT32, 3)
    func = FIRFunction("f", params=[("arr", array_t)], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    b.store_field(func.param_value("arr"), "x", one)
    b.ret()
    _expect_rule(module, "FIRV-T7")


def test_t7_store_field_unregistered_class():
    module = FIRModule("firescript")
    unknown_t = make_simple("UnknownClass")
    func = FIRFunction(
        "f", params=[("obj", unknown_t)], return_type=None, param_modes=["borrow"]
    )
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    b.store_field(func.param_value("obj"), "x", one)
    b.ret()
    module.validate()  # class not registered -> not checked further, must not raise


def test_t7_store_field_on_enum_is_invalid():
    module = FIRModule("firescript")
    module.add_type(TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A")]))
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    ev = b.construct_variant(enum_t, "A", [])
    one = b.int_literal("1", INT32)
    b.store_field(ev, "x", one)
    b.ret()
    _expect_rule(module, "FIRV-T7")


def test_t7_store_field_unknown_field():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(point_t, [b.int_literal("0", INT32)])
    one = b.int_literal("1", INT32)
    b.store_field(obj, "y", one)
    b.ret()
    _expect_rule(module, "FIRV-T7")


def test_t7_store_field_value_type_mismatch():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(point_t, [b.int_literal("0", INT32)])
    s = b.string_literal("bad", STRING)
    b.store_field(obj, "x", s)
    b.ret()
    _expect_rule(module, "FIRV-T7")


# -- FIRV-T8: IndexArray / StoreArray remaining branches ---------------------

def test_t8_index_array_non_array_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    idx = b.int_literal("0", INT32)
    bad = b.index_array(x, idx, INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-T8")


def test_t8_index_array_result_type_mismatch():
    module = FIRModule("firescript")
    array_t = ArrayType(INT32, 3)
    func = FIRFunction("f", params=[("arr", array_t)], return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    idx = b.int_literal("0", INT32)
    bad = b.index_array(func.param_value("arr"), idx, STRING)
    b.ret(bad)
    _expect_rule(module, "FIRV-T8")


def test_t8_store_array_non_array_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    idx = b.int_literal("0", INT32)
    val = b.int_literal("5", INT32)
    b.store_array(x, idx, val)
    b.ret()
    _expect_rule(module, "FIRV-T8")


def test_t8_store_array_value_type_mismatch():
    module = FIRModule("firescript")
    array_t = ArrayType(INT32, 3)
    func = FIRFunction("f", params=[("arr", array_t)], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    idx = b.int_literal("0", INT32)
    val = b.string_literal("bad", STRING)
    b.store_array(func.param_value("arr"), idx, val)
    b.ret()
    _expect_rule(module, "FIRV-T8")


def test_t8_store_array_index_non_integer():
    module = FIRModule("firescript")
    array_t = ArrayType(INT32, 3)
    func = FIRFunction("f", params=[("arr", array_t)], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    idx = b.string_literal("x", STRING)
    val = b.int_literal("5", INT32)
    b.store_array(func.param_value("arr"), idx, val)
    b.ret()
    _expect_rule(module, "FIRV-T8")


# -- FIRV-T9: Allocate remaining branches -------------------------------------

def test_t9_allocate_with_explicit_ctor_rejects_args():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Foo", "owned", fields=[("x", INT32)]))
    foo_t = make_simple("Foo")
    ctor = FIRFunction("Foo.Foo", params=[("this", foo_t), ("x", INT32)], return_type=None)
    cb = FIRBuilder(ctor)
    cb.ret()
    module.add_function(ctor)

    func = FIRFunction("f", return_type=foo_t)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    obj = b.allocate(foo_t, [one])  # bare Allocate must not carry args when a ctor exists
    b.ret(obj)
    _expect_rule(module, "FIRV-T9")


def test_t9_allocate_argument_type_mismatch():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32), ("y", INT32)]))
    point_t = make_simple("Point")
    func = FIRFunction("f", return_type=point_t)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    s = b.string_literal("bad", STRING)
    obj = b.allocate(point_t, [one, s])
    b.ret(obj)
    _expect_rule(module, "FIRV-T9")


# -- FIRV-T10: ConstructVariant remaining branches ---------------------------

def test_t10_construct_variant_payload_count_mismatch():
    module = FIRModule("firescript")
    module.add_type(
        TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A", [("v", INT32)])])
    )
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=enum_t)
    module.add_function(func)
    b = FIRBuilder(func)
    ev = b.construct_variant(enum_t, "A", [])  # missing the payload value
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
    s = b.string_literal("bad", STRING)
    ev = b.construct_variant(enum_t, "A", [s])
    b.ret(ev)
    _expect_rule(module, "FIRV-T10")


# -- FIRV-T11: ExtractTag / ExtractPayloadField remaining branches -----------

def test_t11_extract_tag_invalid_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    ghost = ParamValue("ghost", make_simple("E"))
    bad = b.extract_tag(ghost, INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-D2")


def test_t11_extract_payload_field_invalid_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    ghost = ParamValue("ghost", make_simple("E"))
    bad = b.extract_payload_field(ghost, "A", 0, INT32)
    b.ret(bad)
    _expect_rule(module, "FIRV-D2")


def test_t11_extract_payload_field_non_enum():
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
    bad = b.extract_payload_field(ev, "A", 0, STRING)
    b.ret(bad)
    _expect_rule(module, "FIRV-T11")


# -- FIRV-L2: StoreVar / declared-type-None edge case ------------------------

def test_l2_store_var_type_mismatch():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    b.declare_local("x", INT32, one)
    s = b.string_literal("bad", STRING)
    b.store_var("x", s)
    b.ret()
    _expect_rule(module, "FIRV-L2")


def test_var_access_declared_type_none_is_skipped():
    """A DeclareLocal with var_type=None (never produced by the real
    lowering pipeline, but not structurally forbidden) short-circuits
    LoadVar's type check (verifier.py line 798-799) rather than crashing on
    .render(). Paired with an unrelated FIRV-T12 violation elsewhere in the
    same function so Tier 1 fails and the (unrelated) Tier-2 ownership pass
    -- which does assume a well-typed local and is not this rule's concern
    -- never runs against the None-typed local."""
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    b.emit(DeclareLocalInst("x", None, one))
    b.emit(LoadVarInst("x", None))
    b.emit(NullLiteralInst(STRING))  # unrelated FIRV-T12: STRING is not nullable
    b.ret()
    _expect_rule(module, "FIRV-T12")


# -- FIRV-G1: Yield remaining branches ----------------------------------------

def test_g1_yield_invalid_operand():
    module = FIRModule("firescript")
    gen_t = GeneratorType(INT32)
    func = FIRFunction("g", return_type=gen_t, is_generator=True)
    module.add_function(func)
    b = FIRBuilder(func)
    ghost = ParamValue("ghost", INT32)
    b.yield_value(ghost)
    b.ret()
    _expect_rule(module, "FIRV-D2")


def test_g1_yield_value_type_mismatch():
    module = FIRModule("firescript")
    gen_t = GeneratorType(INT32)
    func = FIRFunction("g", return_type=gen_t, is_generator=True)
    module.add_function(func)
    b = FIRBuilder(func)
    s = b.string_literal("bad", STRING)
    b.yield_value(s)
    b.ret()
    _expect_rule(module, "FIRV-G1")


# -- FIRV-G3: generator instructions ------------------------------------------

def test_g3_gen_new_unresolved_callee():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=GeneratorType(INT32))
    module.add_function(func)
    b = FIRBuilder(func)
    g = b.gen_new("does_not_exist", [], GeneratorType(INT32))
    b.ret(g)
    module.validate()  # unresolved generator ref -> not checked further, must not raise


def test_g3_gen_new_arg_count_mismatch():
    module = FIRModule("firescript")
    gen = FIRFunction("g", params=[("n", INT32)], return_type=GeneratorType(INT32), is_generator=True)
    module.add_function(gen)
    gb = FIRBuilder(gen)
    gb.yield_value(gb.int_literal("1", INT32))
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
    g_val = b.emit(GenNewInst("g", [], INT32))  # result type should be a GeneratorType
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
    g_val = b.gen_new("g", [], GeneratorType(STRING))  # generator yields int32, not string
    b.ret(g_val)
    _expect_rule(module, "FIRV-G3")


def test_g3_gen_next_non_generator_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    has_next = b.gen_next(x, BOOL)
    b.ret(has_next)
    _expect_rule(module, "FIRV-G3")


def test_g3_gen_next_result_not_bool():
    module = FIRModule("firescript")
    gen = FIRFunction("g", return_type=GeneratorType(INT32), is_generator=True)
    module.add_function(gen)
    gb = FIRBuilder(gen)
    gb.yield_value(gb.int_literal("1", INT32))
    gb.ret()

    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    g_val = b.gen_new("g", [], GeneratorType(INT32))
    has_next = b.gen_next(g_val, INT32)  # should be bool
    b.ret(has_next)
    _expect_rule(module, "FIRV-G3")


def test_g3_gen_value_invalid_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    ghost = ParamValue("ghost", GeneratorType(INT32))
    val = b.gen_value(ghost, INT32)
    b.ret(val)
    _expect_rule(module, "FIRV-D2")


def test_g3_gen_value_non_generator_operand():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    val = b.gen_value(x, INT32)
    b.ret(val)
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
    val = b.gen_value(g_val, STRING)  # generator element type is int32
    b.ret(val)
    _expect_rule(module, "FIRV-G3")


# -- FIRV-S3: terminator instruction found mid-stream ------------------------

def test_s3_terminator_found_in_instruction_stream():
    from fir.ir_node import ReturnInst

    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    # Directly append a Terminator into the instruction list (bypassing
    # set_terminator, which real lowering always uses) to exercise the
    # defensive FIRV-S3 "terminator in instruction stream" check.
    b.current_block.instructions.append(ReturnInst(None))
    b.ret()
    _expect_rule(module, "FIRV-S3")


# -- FIRV-S6: ArrayType-wrapped generic type reference -----------------------

def test_s6_array_wrapped_generic_type_reference_omits_args():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Pair", "owned", generic_params=["T", "U"]))
    module.add_type(
        TypeDef("Box4", "owned", fields=[("items", ArrayType(make_simple("Pair"), 3))])
    )
    _expect_rule(module, "FIRV-S6")


# -- FIRV-T1: comparison operand type mismatch --------------------------------

def test_t1_comparison_operand_type_mismatch():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    s = b.string_literal("x", STRING)
    result = b.emit(BinaryOpInst("==", x, s, BOOL))
    b.ret(result)
    _expect_rule(module, "FIRV-T1")


# -- FIRV-T2/D2: unary op operand edge cases ----------------------------------

def test_t2_unary_op_invalid_operand_is_skipped():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    ghost = ParamValue("ghost", BOOL)
    result = b.emit(UnaryOpInst("!", ghost, BOOL))
    b.ret(result)
    _expect_rule(module, "FIRV-D2")


def test_t2_unary_bang_result_not_bool():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.bool_literal(True, BOOL)
    result = b.emit(UnaryOpInst("!", x, INT32))
    b.ret(result)
    _expect_rule(module, "FIRV-T2")


# -- FIRV-T4: Return with an invalid operand ----------------------------------

def test_t4_return_invalid_operand_is_skipped():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    ghost = ParamValue("ghost", INT32)
    b.ret(ghost)
    _expect_rule(module, "FIRV-D2")


# -- FIRV-T9/T10: Allocate / ConstructVariant on an unregistered type --------

def test_t9_allocate_unregistered_class_not_checked_further():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=make_simple("UnknownClass"))
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.emit(AllocateInst(make_simple("UnknownClass"), []))
    b.ret(obj)
    module.validate()  # class not registered -> not checked further, must not raise


def test_t10_construct_variant_unregistered_enum_not_checked_further():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=make_simple("UnknownEnum"))
    module.add_function(func)
    b = FIRBuilder(func)
    ev = b.emit(ConstructVariantInst(make_simple("UnknownEnum"), "A", []))
    b.ret(ev)
    module.validate()  # enum not registered -> not checked further, must not raise


# -- FIRV-T12: IntLiteral remaining branches ----------------------------------

def test_t12_int_literal_does_not_parse():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    bad = b.emit(IntLiteralInst("not_a_number", INT32))
    b.ret(bad)
    _expect_rule(module, "FIRV-T12")


def test_t12_int_literal_non_numeric_type():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=BOOL)
    module.add_function(func)
    b = FIRBuilder(func)
    bad = b.emit(IntLiteralInst("1", BOOL))
    b.ret(bad)
    _expect_rule(module, "FIRV-T12")

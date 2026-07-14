"""Unit tests for FIR verifier rules not covered elsewhere: S1 (function
must have at least one block), S6 (module-level structural checks --
duplicate names, enum shape, type-reference resolution), D1-D3 (operand
resolution), and T6 (method-call argument/return checks). One negative
case per distinct branch, built directly with FIRBuilder like the sibling
test_verifier_*.py files."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from errors import IRVerificationError  # noqa: E402
from fir import FIRBuilder, FIRFunction, FIRModule, TypeDef, make_simple  # noqa: E402
from fir.ir_module import EnumVariantDef  # noqa: E402
from fir.ir_node import MethodCallInst, ParamValue  # noqa: E402
from fir.ir_types import ArrayType, GenericInstanceType  # noqa: E402

INT32 = make_simple("int32")
BOOL = make_simple("bool")
STRING = make_simple("string")


def _expect_rule(module: FIRModule, rule_id: str) -> None:
    try:
        module.validate()
        t.require(False, f"no error raised (expected {rule_id})")
    except IRVerificationError as e:
        t.require(any(v.rule_id == rule_id for v in e.violations), f"{rule_id} not in: {e}")


def test_s1_function_with_no_blocks():
    module = FIRModule("firescript")
    func = FIRFunction("empty", return_type=None)
    module.add_function(func)
    # No FIRBuilder used -> func.blocks stays empty.
    _expect_rule(module, "FIRV-S1")


def test_s6_duplicate_type_name():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    module.add_type(TypeDef("Point", "owned", fields=[("y", INT32)]))
    _expect_rule(module, "FIRV-S6")


def test_s6_duplicate_function_name():
    module = FIRModule("firescript")
    f1 = FIRFunction("f", return_type=None)
    b1 = FIRBuilder(f1)
    b1.ret()
    module.add_function(f1)
    f2 = FIRFunction("f", return_type=None)
    b2 = FIRBuilder(f2)
    b2.ret()
    module.add_function(f2)
    _expect_rule(module, "FIRV-S6")


def test_s6_duplicate_constant_name():
    from fir.ir_module import GlobalConstant

    module = FIRModule("firescript")
    module.add_constant(GlobalConstant("C", INT32, "1"))
    module.add_constant(GlobalConstant("C", INT32, "2"))
    _expect_rule(module, "FIRV-S6")


def test_s6_enum_with_no_variants():
    module = FIRModule("firescript")
    module.add_type(TypeDef("E", "owned", kind="enum", variants=[]))
    _expect_rule(module, "FIRV-S6")


def test_s6_enum_must_not_have_base():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Base", "owned", kind="enum", variants=[EnumVariantDef("A")]))
    module.add_type(
        TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("B")], base="Base")
    )
    _expect_rule(module, "FIRV-S6")


def test_s6_unresolved_base_type():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Child", "owned", fields=[], base="NoSuchBase"))
    _expect_rule(module, "FIRV-S6")


def test_s6_cyclic_base_chain():
    module = FIRModule("firescript")
    module.add_type(TypeDef("A", "owned", fields=[], base="B"))
    module.add_type(TypeDef("B", "owned", fields=[], base="A"))
    _expect_rule(module, "FIRV-S6")


def test_s6_generic_type_reference_missing_arguments():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Box", "owned", fields=[], generic_params=["T"]))
    box_field_t = make_simple("Box")  # references Box without <T> arguments
    module.add_type(TypeDef("Holder", "owned", fields=[("b", box_field_t)]))
    _expect_rule(module, "FIRV-S6")


def test_s6_generic_instance_wrong_arg_count():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Pair", "owned", fields=[], generic_params=["T", "U"]))
    bad_instance = GenericInstanceType("Pair", [INT32])  # only 1 arg, needs 2
    module.add_type(TypeDef("Holder", "owned", fields=[("p", bad_instance)]))
    _expect_rule(module, "FIRV-S6")


def test_s6_array_element_type_unresolved():
    module = FIRModule("firescript")
    unresolved = make_simple("NoSuchType")
    arr_t = ArrayType(unresolved, size=3)
    module.add_type(TypeDef("Holder", "owned", fields=[("arr", arr_t)]))
    # Unresolved plain names are lenient (see _check_type_reference comment),
    # so this must NOT raise -- it documents that leniency rather than a bug.
    module.validate()


def test_d1_operand_of_unsupported_kind():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    bad = MethodCallInst(object(), "whatever", [], [], INT32)  # type: ignore[arg-type]
    b.emit(bad)
    b.ret(x)
    _expect_rule(module, "FIRV-D1")


def test_d2_param_value_not_a_real_parameter():
    module = FIRModule("firescript")
    func = FIRFunction("f", params=[("a", INT32)], return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    bogus = ParamValue("not_a_param", INT32)
    b.ret(bogus)
    _expect_rule(module, "FIRV-D2")


def test_t6_method_call_argument_count_mismatch():
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
    b.method_call(obj, "move", [], [], None)  # missing the 'dx' argument
    b.ret()
    _expect_rule(module, "FIRV-T6")


def test_t6_method_call_argument_type_mismatch():
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
    s = b.string_literal("nope", STRING)
    b.method_call(obj, "move", [s], ["own"], None)
    b.ret()
    _expect_rule(module, "FIRV-T6")


def test_t6_method_call_result_type_mismatch():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    point_t = make_simple("Point")
    method = FIRFunction("Point.getX", params=[("this", point_t)], return_type=INT32)
    mb = FIRBuilder(method)
    mb.ret(mb.int_literal("0", INT32))
    module.add_function(method)

    func = FIRFunction("f", return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    obj = b.allocate(point_t, [b.int_literal("1", INT32)])
    # Declared result type (string) doesn't match callee's actual return (int32).
    result = b.method_call(obj, "getX", [], [], STRING)
    b.ret(result)
    _expect_rule(module, "FIRV-T6")


def test_t6_method_call_arg_mode_count_mismatch():
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
    # Two arg_modes for a single argument: `[]` would fall back to the
    # builder's default (one "own" per arg), so mismatch the other way.
    b.method_call(obj, "move", [dx], ["own", "own"], None)
    b.ret()
    _expect_rule(module, "FIRV-T6")

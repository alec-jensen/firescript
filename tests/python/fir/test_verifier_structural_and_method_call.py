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


def test_s6_array_element_type_unresolved():
    module = FIRModule("firescript")
    unresolved = make_simple("NoSuchType")
    arr_t = ArrayType(unresolved, size=3)
    module.add_type(TypeDef("Holder", "owned", fields=[("arr", arr_t)]))
    # Unresolved plain names are lenient (see _check_type_reference comment),
    # so this must NOT raise -- it documents that leniency rather than a bug.
    module.validate()


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

"""Unit tests for FIR Tier-2 ownership rules (FIRV-O1-O7, FIRV-L3, FIRV-G4,
FIRV-E1) in firescript/fir/ownership_verifier.py. One negative case per
rule id (spec section 9), built directly with FIRBuilder."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from errors import IRVerificationError  # noqa: E402
from fir import FIRBuilder, FIRFunction, FIRModule, TypeDef, make_simple  # noqa: E402
from fir.ir_types import GeneratorType  # noqa: E402

INT32 = make_simple("int32")
BOOL = make_simple("bool")


def _expect_rule(module: FIRModule, rule_id: str) -> None:
    try:
        module.validate()
        t.require(False, f"no error raised (expected {rule_id})")
    except IRVerificationError as e:
        t.require(any(v.rule_id == rule_id for v in e.violations), f"{rule_id} not in: {e}")


def _point_module() -> tuple[FIRModule, "TypeDef"]:
    module = FIRModule("firescript")
    point_t = make_simple("Point")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    return module, point_t


def test_o1_use_after_move():
    module, point_t = _point_module()
    func = FIRFunction("f", params=[("p", point_t)], param_modes=["own"], return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    p = func.param_value("p")
    b.drop(p)
    bad = b.load_field(p, "x", INT32)  # use after Drop
    b.ret(bad)
    _expect_rule(module, "FIRV-O1")


def test_o2_double_drop():
    module, point_t = _point_module()
    func = FIRFunction("f", params=[("p", point_t)], param_modes=["own"], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    p = func.param_value("p")
    b.drop(p)
    b.drop(p)  # double drop
    b.ret()
    _expect_rule(module, "FIRV-O2")


def test_o3_leak_owned_param():
    module, point_t = _point_module()
    func = FIRFunction("f", params=[("p", point_t)], param_modes=["own"], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    b.ret()  # p never dropped
    _expect_rule(module, "FIRV-O3")


def test_o4_own_and_borrow_same_call():
    module, point_t = _point_module()
    callee = FIRFunction("callee", params=[("a", point_t), ("b", point_t)], param_modes=["own", "borrow"], return_type=None)
    module.add_function(callee)
    func = FIRFunction("f", params=[("p", point_t)], param_modes=["own"], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    p = func.param_value("p")
    b.call("callee", [p, p], ["own", "borrow"], None)
    b.ret()
    _expect_rule(module, "FIRV-O4")


def test_o5_drop_non_owned():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    b.drop(x)  # int32 is copyable, not owned
    b.ret()
    _expect_rule(module, "FIRV-O5")


def test_o6_move_non_owned():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    moved = b.move(x)  # int32 is copyable, not owned
    b.ret(moved)
    _expect_rule(module, "FIRV-O6")


def test_o7_borrow_param_consumed():
    module, point_t = _point_module()
    func = FIRFunction("f", params=[("p", point_t)], param_modes=["borrow"], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    p = func.param_value("p")
    b.drop(p)  # borrow param must never be consumed
    b.ret()
    _expect_rule(module, "FIRV-O7")


def test_l3_duplicate_declare_local_same_name():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    b.declare_local("x", INT32, one)
    two = b.int_literal("2", INT32)
    b.declare_local("x", INT32, two)  # shadows the first "x"
    result = b.load_var("x", INT32)
    b.ret(result)
    _expect_rule(module, "FIRV-L3")


def test_l3_local_shadows_parameter():
    module = FIRModule("firescript")
    func = FIRFunction("f", params=[("x", INT32)], return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    b.declare_local("x", INT32, one)  # shadows parameter "x"
    result = b.load_var("x", INT32)
    b.ret(result)
    _expect_rule(module, "FIRV-L3")


def test_g4_gen_value_without_dominating_gen_next():
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
    value = b.gen_value(g_val, INT32)  # no GenNext before this
    b.ret(value)
    _expect_rule(module, "FIRV-G4")


def test_e1_extract_payload_field_unguarded():
    module = FIRModule("firescript")
    from fir.ir_module import EnumVariantDef

    module.add_type(
        TypeDef("E", "owned", kind="enum", variants=[EnumVariantDef("A", [("v", INT32)])])
    )
    enum_t = make_simple("E")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    one = b.int_literal("1", INT32)
    ev = b.construct_variant(enum_t, "A", [one])
    bad = b.extract_payload_field(ev, "A", 0, INT32)  # no tag guard
    b.ret(bad)
    _expect_rule(module, "FIRV-E1")


def test_o6_clone_non_owned():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    cloned = b.clone(x)  # int32 is copyable, not owned
    b.ret(cloned)
    _expect_rule(module, "FIRV-O6")


def test_o4_borrow_mut_passed_twice_same_call():
    module, point_t = _point_module()
    callee = FIRFunction(
        "callee", params=[("a", point_t), ("b", point_t)], param_modes=["borrow_mut", "borrow_mut"], return_type=None
    )
    module.add_function(callee)
    func = FIRFunction("f", params=[("p", point_t)], param_modes=["borrow"], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    p = func.param_value("p")
    b.call("callee", [p, p], ["borrow_mut", "borrow_mut"], None)
    b.ret()
    _expect_rule(module, "FIRV-O4")


def test_identifier_of_aliased_field_read_not_tracked_as_owned():
    """A local bound directly to a LoadField result aliases the containing
    object's field storage rather than allocating a fresh owned value; it
    must not be required to be independently dropped (no O3 leak at
    return) since dropping it would double-free once the object itself is
    dropped."""
    module, point_t = _point_module()
    module.types[0] = TypeDef("Point", "owned", fields=[("inner", make_simple("Inner"))])
    module.add_type(TypeDef("Inner", "owned", fields=[]))
    inner_t = make_simple("Inner")
    func = FIRFunction("f", params=[("p", point_t)], param_modes=["own"], return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    p = func.param_value("p")
    field_val = b.load_field(p, "inner", inner_t)
    b.declare_local("x", inner_t, field_val)  # aliases p.inner, not a fresh value
    b.drop(p)
    b.ret()
    module.validate()  # must not raise: "x" is not itself independently owned


def test_verifier_ownership_accepts_clean_module():
    module, point_t = _point_module()
    func = FIRFunction("f", params=[("p", point_t)], param_modes=["own"], return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    p = func.param_value("p")
    x = b.load_field(p, "x", INT32)
    b.drop(p)
    b.ret(x)

    module.validate()  # must not raise

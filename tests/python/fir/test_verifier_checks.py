"""Gap-filling unit tests for firescript/fir/verifier.py (Tier 1): the
generic-parameter "treat as unknown" skips, the nullable-assignment rule,
array-size assignability in call/construct arguments, and the
ArrayAlloc / ArrayCopy type checks (FIRV-T8). Each test builds a tiny FIR
module by hand, corrupts exactly one thing, and asserts the specific rule
id; valid-boundary twins confirm the rule is not over-eager."""
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
    GenericInstanceType,
    TypeDef,
    make_simple,
)

INT32 = make_simple("int32")
INT64 = make_simple("int64")
BOOL = make_simple("bool")
STRING = make_simple("string")
STRING_N = make_simple("string", nullable=True)
T = make_simple("T")


def _rules(module: FIRModule) -> list[str]:
    try:
        module.validate()
    except IRVerificationError as e:
        return [v.rule_id for v in e.violations]
    return []


def _expect_rule(module: FIRModule, rule_id: str) -> None:
    rules = _rules(module)
    t.require(rule_id in rules, f"{rule_id} not in {rules}")


def _expect_clean(module: FIRModule) -> None:
    rules = _rules(module)
    t.require(rules == [], f"unexpected violations: {rules}")


def _fn(module, name, params=None, ret=None, generic=None, modes=None):
    f = FIRFunction(name, params=params, return_type=ret, generic_params=generic, param_modes=modes)
    module.add_function(f)
    return f, FIRBuilder(f)


# -- generic parameters are treated as unknown ------------------------------

def test_t1_logical_op_on_generic_params_is_skipped():
    module = FIRModule("firescript")
    f, b = _fn(module, "g", params=[("a", T), ("c", T)], ret=T, generic=["T"])
    a, c = f.param_value("a"), f.param_value("c")
    r = b.binary_op("&&", a, c, T)
    b.ret(r)
    _expect_clean(module)


def test_t1_logical_op_on_non_bool_is_rejected_without_generics():
    module = FIRModule("firescript")
    f, b = _fn(module, "g", params=[("a", INT32), ("c", INT32)], ret=INT32)
    r = b.binary_op("&&", f.param_value("a"), f.param_value("c"), INT32)
    b.ret(r)
    _expect_rule(module, "FIRV-T1")


def test_t2_unary_not_on_generic_param_is_skipped():
    module = FIRModule("firescript")
    f, b = _fn(module, "g", params=[("a", T)], ret=T, generic=["T"])
    r = b.unary_op("!", f.param_value("a"), T)
    b.ret(r)
    _expect_clean(module)


def test_t2_unary_not_on_int_is_rejected_without_generics():
    module = FIRModule("firescript")
    f, b = _fn(module, "g", params=[("a", INT32)], ret=INT32)
    r = b.unary_op("!", f.param_value("a"), INT32)
    b.ret(r)
    _expect_rule(module, "FIRV-T2")


def test_t5_call_to_generic_callee_skips_argument_checks():
    module = FIRModule("firescript")
    _, cb = _fn(module, "id", params=[("x", T)], ret=T, generic=["T"])
    callee = module.functions[0]
    cb.ret(callee.param_value("x"))
    _, b = _fn(module, "main", ret=None)
    one = b.int_literal("1", INT32)
    two = b.int_literal("2", INT32)
    # Wrong arity AND wrong type for a non-generic callee; skipped for generic.
    b.call("id", [one, two], ["own", "own"], INT32)
    b.ret()
    _expect_clean(module)


# -- FIRV-T5: array-size assignability in call arguments --------------------

def test_t5_array_argument_size_mismatch():
    module = FIRModule("firescript")
    _, cb = _fn(module, "take", params=[("a", ArrayType(INT32, 3))], ret=None)
    cb.ret()
    _, b = _fn(module, "main")
    arr = b.array_alloc(b.int_literal("2", INT32), ArrayType(INT32, 2))
    b.call("take", [arr], ["own"], None)
    b.ret()
    _expect_rule(module, "FIRV-T5")


def test_t5_array_argument_matching_size_is_clean():
    module = FIRModule("firescript")
    _, cb = _fn(module, "take", params=[("a", ArrayType(INT32, 3))], ret=None)
    cb.ret()
    _, b = _fn(module, "main")
    arr = b.array_alloc(b.int_literal("3", INT32), ArrayType(INT32, 3))
    b.call("take", [arr], ["own"], None)
    b.ret()
    t.require("FIRV-T5" not in _rules(module), "FIRV-T5 must not fire")


def test_t5_non_nullable_argument_accepted_for_nullable_parameter():
    module = FIRModule("firescript")
    _, cb = _fn(module, "take", params=[("s", STRING_N)], ret=None)
    cb.ret()
    _, b = _fn(module, "main")
    s = b.string_literal("hi", STRING)
    b.call("take", [s], ["own"], None)
    b.ret()
    t.require("FIRV-T5" not in _rules(module), "FIRV-T5 must not fire")


def test_t5_nullable_pointer_argument_accepted_for_plain_pointer_parameter():
    # A `string?`/`Class?` parameter keeps a plain FIR type (null is just the
    # zero pointer), so a nullable-typed pointer argument must be accepted
    # (B05: `fn f(s: string?)` called with a `string?` variable or `null`).
    module = FIRModule("firescript")
    _, cb = _fn(module, "take", params=[("s", STRING)], ret=None)
    cb.ret()
    _, b = _fn(module, "main")
    n = b.null_literal(STRING_N)
    b.call("take", [n], ["own"], None)
    b.ret()
    t.require("FIRV-T5" not in _rules(module), "FIRV-T5 must not fire")


def test_t5_nullable_scalar_argument_rejected_for_non_nullable_parameter():
    # Nullable scalars carry a has-value companion, so passing `int32?` to a
    # plain `int32` parameter stays a mismatch.
    module = FIRModule("firescript")
    _, cb = _fn(module, "take", params=[("v", INT32)], ret=None)
    cb.ret()
    _, b = _fn(module, "main")
    n = b.null_literal(make_simple("int32", nullable=True))
    b.call("take", [n], ["own"], None)
    b.ret()
    _expect_rule(module, "FIRV-T5")


# -- generic class fields ---------------------------------------------------

def _box_module() -> FIRModule:
    module = FIRModule("firescript")
    module.add_type(TypeDef("Box", "owned", fields=[("v", T)], generic_params=["T"]))
    return module


def test_t7_load_field_of_generic_typed_field_skips_result_check():
    module = _box_module()
    box_t = GenericInstanceType("Box", [INT32])
    f, b = _fn(module, "g", params=[("bx", box_t)], ret=INT32, modes=["borrow"])
    # Result type differs from the declared field type 'T', which is fine.
    v = b.load_field(f.param_value("bx"), "v", INT32)
    b.ret(v)
    _expect_clean(module)


def test_t7_load_field_result_type_mismatch_on_concrete_field():
    module = FIRModule("firescript")
    module.add_type(TypeDef("P", "owned", fields=[("x", INT32)]))
    p = make_simple("P")
    f, b = _fn(module, "g", params=[("p", p)], ret=INT64, modes=["borrow"])
    v = b.load_field(f.param_value("p"), "x", INT64)
    b.ret(v)
    _expect_rule(module, "FIRV-T7")


def test_t7_store_field_of_generic_typed_field_skips_value_check():
    module = _box_module()
    box_t = GenericInstanceType("Box", [INT32])
    f, b = _fn(module, "g", params=[("bx", box_t)], ret=None, modes=["borrow_mut"])
    b.store_field(f.param_value("bx"), "v", b.int_literal("1", INT32))
    b.ret()
    _expect_clean(module)


def test_t7_store_field_value_type_mismatch_on_concrete_field():
    module = FIRModule("firescript")
    module.add_type(TypeDef("P", "owned", fields=[("x", INT32)]))
    p = make_simple("P")
    f, b = _fn(module, "g", params=[("p", p)], ret=None, modes=["borrow_mut"])
    b.store_field(f.param_value("p"), "x", b.string_literal("no", STRING))
    b.ret()
    _expect_rule(module, "FIRV-T7")


def test_t9_allocate_with_generic_typed_field_skips_argument_check():
    module = _box_module()
    _, b = _fn(module, "main")
    b.allocate(GenericInstanceType("Box", [INT32]), [b.string_literal("x", STRING)])
    b.ret()
    # field type 'T' is unresolved generic: argument type is not compared.
    t.require("FIRV-T9" not in _rules(module), "FIRV-T9 must not fire for generic field")


def test_t9_allocate_argument_type_mismatch_on_concrete_field():
    module = FIRModule("firescript")
    module.add_type(TypeDef("P", "owned", fields=[("x", INT32)]))
    _, b = _fn(module, "main")
    b.allocate(make_simple("P"), [b.string_literal("x", STRING)])
    b.ret()
    _expect_rule(module, "FIRV-T9")


# -- FIRV-T8: ArrayAlloc / ArrayCopy ----------------------------------------

def test_t8_array_alloc_non_integer_count():
    module = FIRModule("firescript")
    _, b = _fn(module, "main")
    b.array_alloc(b.string_literal("n", STRING), ArrayType(INT32))
    b.ret()
    _expect_rule(module, "FIRV-T8")


def test_t8_array_alloc_non_array_result_type():
    module = FIRModule("firescript")
    _, b = _fn(module, "main")
    b.array_alloc(b.int_literal("3", INT32), INT32)
    b.ret()
    _expect_rule(module, "FIRV-T8")


def test_t8_array_alloc_valid():
    module = FIRModule("firescript")
    _, b = _fn(module, "main")
    b.array_alloc(b.int_literal("3", INT32), ArrayType(INT32))
    b.ret()
    _expect_clean(module)


def _two_arrays(module, dst_t, src_t):
    _, b = _fn(module, "main")
    n = b.int_literal("3", INT32)
    dst = b.array_alloc(n, dst_t)
    src = b.array_alloc(n, src_t)
    return b, dst, src, n


def test_t8_array_copy_element_type_mismatch():
    module = FIRModule("firescript")
    b, dst, src, n = _two_arrays(module, ArrayType(INT32), ArrayType(INT64))
    b.array_copy(dst, src, n)
    b.ret()
    _expect_rule(module, "FIRV-T8")


def test_t8_array_copy_valid():
    module = FIRModule("firescript")
    b, dst, src, n = _two_arrays(module, ArrayType(INT32), ArrayType(INT32))
    b.array_copy(dst, src, n)
    b.ret()
    _expect_clean(module)


def test_t8_array_copy_non_array_dst():
    module = FIRModule("firescript")
    b, dst, src, n = _two_arrays(module, ArrayType(INT32), ArrayType(INT32))
    b.array_copy(n, src, n)
    b.ret()
    _expect_rule(module, "FIRV-T8")


def test_t8_array_copy_non_array_src():
    module = FIRModule("firescript")
    b, dst, src, n = _two_arrays(module, ArrayType(INT32), ArrayType(INT32))
    b.array_copy(dst, n, n)
    b.ret()
    _expect_rule(module, "FIRV-T8")


def test_t8_array_copy_non_integer_count():
    module = FIRModule("firescript")
    b, dst, src, n = _two_arrays(module, ArrayType(INT32), ArrayType(INT32))
    b.array_copy(dst, src, b.string_literal("c", STRING))
    b.ret()
    _expect_rule(module, "FIRV-T8")


def test_t8_array_copy_generic_element_types_are_skipped():
    module = FIRModule("firescript")
    f, b = _fn(
        module, "g",
        params=[("d", ArrayType(T)), ("s", ArrayType(INT32))], ret=None, generic=["T"],
        modes=["borrow_mut", "borrow"],
    )
    b.array_copy(f.param_value("d"), f.param_value("s"), b.int_literal("1", INT32))
    b.ret()
    t.require("FIRV-T8" not in _rules(module), "generic element type must be skipped")


# -- FIRV-L2: StoreVar nullable assignment ----------------------------------

def _store_var_module(declared, value_maker):
    module = FIRModule("firescript")
    _, b = _fn(module, "main")
    b.declare_local("c", declared)
    b.store_var("c", value_maker(b))
    b.ret()
    return module


def test_l2_store_non_nullable_into_nullable_slot_is_allowed():
    module = _store_var_module(STRING_N, lambda b: b.string_literal("w", STRING))
    t.require("FIRV-L2" not in _rules(module), "string -> string? must be assignable")


def test_l2_store_nullable_into_non_nullable_slot_is_rejected():
    module = _store_var_module(STRING, lambda b: b.null_literal(STRING_N))
    _expect_rule(module, "FIRV-L2")


def test_l2_store_other_base_type_into_nullable_slot_is_rejected():
    module = _store_var_module(STRING_N, lambda b: b.int_literal("1", INT32))
    _expect_rule(module, "FIRV-L2")


# -- generic receiver / unresolved class ------------------------------------

def test_t6_method_call_on_generic_class_skips_argument_checks():
    module = _box_module()
    box_t = GenericInstanceType("Box", [INT32])
    m, mb = _fn(module, "Box.put", params=[("this", box_t), ("x", T)], ret=None)
    mb.ret()
    f, b = _fn(module, "g", params=[("bx", box_t)], ret=None, modes=["borrow_mut"])
    b.method_call(f.param_value("bx"), "put", [b.string_literal("s", STRING)], ["own"], None)
    b.ret()
    t.require("FIRV-T6" not in _rules(module), "generic receiver must skip T6 argument checks")


def test_t7_load_field_on_unknown_class_is_not_checked():
    module = FIRModule("firescript")
    ghost = make_simple("Ghost")
    f, b = _fn(module, "g", params=[("x", ghost)], ret=INT32, modes=["borrow"])
    v = b.load_field(f.param_value("x"), "any", INT32)
    b.ret(v)
    t.require("FIRV-T7" not in _rules(module), "unknown class must be skipped by Tier 1")

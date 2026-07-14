"""Unit tests for FIR Tier-1 structural rules (FIRV-S, FIRV-D) in
firescript/fir/verifier.py. The two original structural-validation cases
from tests/fir_unit_tests.py migrated here per
docs/internal/development/ir_verifier_spec.md section 9 (they now assert
IRVerificationError with the FIRV-S3/S4 rule ids instead of ValueError)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from errors import IRVerificationError  # noqa: E402
from fir import FIRBuilder, FIRFunction, FIRModule, TypeDef, make_simple  # noqa: E402
from fir.ir_module import GlobalConstant  # noqa: E402
from fir.ir_node import CallInst, FIRValue, IntLiteralInst, ParamValue  # noqa: E402
from fir.ir_types import GenericInstanceType  # noqa: E402

INT32 = make_simple("int32")


def _expect_rule(module: FIRModule, rule_id: str) -> None:
    try:
        module.validate()
        t.require(False, f"no error raised (expected {rule_id})")
    except IRVerificationError as e:
        t.require(any(v.rule_id == rule_id for v in e.violations), f"{rule_id} not in: {e}")


def test_validation_rejects_missing_terminator():
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction("broken", return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    builder.int_literal("1", int32)  # no terminator set

    try:
        module.validate()
        t.require(False, "no error raised")
    except IRVerificationError as e:
        t.require(any(v.rule_id == "FIRV-S3" for v in e.violations), str(e))


def test_validation_rejects_unknown_branch_target():
    module = FIRModule("firescript")
    func = FIRFunction("bad_branch", return_type=make_simple("int32"))
    module.add_function(func)
    builder = FIRBuilder(func)
    cond = builder.bool_literal(True, make_simple("bool"))
    builder.branch(cond, "block_99", "block_98")

    try:
        module.validate()
        t.require(False, "no error raised")
    except IRVerificationError as e:
        t.require(any(v.rule_id == "FIRV-S4" for v in e.violations), str(e))


def test_validation_rejects_duplicate_block_id():
    module = FIRModule("firescript")
    func = FIRFunction("dup_block", return_type=None)
    module.add_function(func)
    builder = FIRBuilder(func)
    builder.ret()
    block = func.new_block()
    block.id = func.blocks[0].id  # force a collision
    builder.position_at(block)
    builder.ret()

    try:
        module.validate()
        t.require(False, "no error raised")
    except IRVerificationError as e:
        t.require(any(v.rule_id == "FIRV-S2" for v in e.violations), str(e))


def test_validation_rejects_unreachable_block():
    module = FIRModule("firescript")
    func = FIRFunction("dead_block", return_type=None)
    module.add_function(func)
    builder = FIRBuilder(func)
    builder.ret()
    orphan = func.new_block()
    builder.position_at(orphan)
    builder.ret()

    try:
        module.validate()
        t.require(False, "no error raised")
    except IRVerificationError as e:
        t.require(any(v.rule_id == "FIRV-S5" for v in e.violations), str(e))


def test_validation_rejects_use_before_def():
    """A LoadVar of a local whose DeclareLocal is only in a sibling block
    (not dominating the use) must fail FIRV-L1."""
    module = FIRModule("firescript")
    int32 = make_simple("int32")
    func = FIRFunction("use_before_def", return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    entry = builder.current_block
    a = func.new_block()
    b = func.new_block()

    cond = builder.bool_literal(True, make_simple("bool"))
    builder.branch(cond, a.id, b.id)

    builder.position_at(a)
    one = builder.int_literal("1", int32)
    builder.declare_local("x", int32, one)
    builder.ret(one)

    builder.position_at(b)
    # "x" was never declared on this path.
    bad = builder.load_var("x", int32)
    builder.ret(bad)

    try:
        module.validate()
        t.require(False, "no error raised")
    except IRVerificationError as e:
        t.require(any(v.rule_id == "FIRV-L1" for v in e.violations), str(e))


def test_validation_accepts_clean_module():
    """A well-formed module produces no violations (no false positives)."""
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction("add_one", params=[("x", int32)], return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    one = builder.int_literal("1", int32)
    x = func.param_value("x")
    result = builder.binary_op("+", x, one, int32)
    builder.ret(result)

    module.validate()  # must not raise


# ---------------------------------------------------------------------------
# FIRV-S6: module-level duplicate names, malformed enum/type-reference rules.
# ---------------------------------------------------------------------------

def test_s6_duplicate_type_name():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Point", "owned", fields=[("x", INT32)]))
    module.add_type(TypeDef("Point", "owned", fields=[("y", INT32)]))
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    b.ret()
    _expect_rule(module, "FIRV-S6")


def test_s6_duplicate_function_name():
    module = FIRModule("firescript")
    f1 = FIRFunction("dup", return_type=None)
    b1 = FIRBuilder(f1)
    b1.ret()
    module.add_function(f1)
    f2 = FIRFunction("dup", return_type=None)
    b2 = FIRBuilder(f2)
    b2.ret()
    module.add_function(f2)
    _expect_rule(module, "FIRV-S6")


def test_s6_duplicate_constant_name():
    module = FIRModule("firescript")
    module.add_constant(GlobalConstant("K", INT32, "1"))
    module.add_constant(GlobalConstant("K", INT32, "2"))
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    b.ret()
    _expect_rule(module, "FIRV-S6")


def test_s6_enum_with_no_variants():
    module = FIRModule("firescript")
    module.add_type(TypeDef("E", "owned", kind="enum", variants=[]))
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    b.ret()
    _expect_rule(module, "FIRV-S6")


def test_s6_enum_must_not_have_base():
    from fir.ir_module import EnumVariantDef

    module = FIRModule("firescript")
    module.add_type(TypeDef("Base", "owned", fields=[]))
    module.add_type(TypeDef("E", "owned", kind="enum", base="Base", variants=[EnumVariantDef("A")]))
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    b.ret()
    _expect_rule(module, "FIRV-S6")


def test_s6_unresolved_base_type():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Derived", "owned", base="DoesNotExist"))
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    b.ret()
    _expect_rule(module, "FIRV-S6")


def test_s6_cyclic_base_chain():
    module = FIRModule("firescript")
    module.add_type(TypeDef("A", "owned", base="B"))
    module.add_type(TypeDef("B", "owned", base="A"))
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    b.ret()
    _expect_rule(module, "FIRV-S6")


def test_s6_generic_type_reference_omits_type_args():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Box", "owned", fields=[("v", INT32)], generic_params=["T"]))
    # "Holder" has a field of bare type "Box" -- Box is generic and needs
    # type arguments (GenericInstanceType), so a bare SimpleType reference
    # to it is malformed.
    module.add_type(TypeDef("Holder", "owned", fields=[("b", make_simple("Box"))]))
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    b.ret()
    _expect_rule(module, "FIRV-S6")


def test_s6_generic_instance_wrong_arg_count():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Box", "owned", fields=[("v", INT32)], generic_params=["T"]))
    bad_ref = GenericInstanceType("Box", [INT32, INT32])  # Box only takes 1
    module.add_type(TypeDef("Holder", "owned", fields=[("b", bad_ref)]))
    func = FIRFunction("f", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    b.ret()
    _expect_rule(module, "FIRV-S6")


# ---------------------------------------------------------------------------
# FIRV-D1-D3: operand resolution failures.
# ---------------------------------------------------------------------------

def test_d1_operand_foreign_to_function():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    # An instruction that was never added to any block of `func` (or any
    # function in the module): its FIRValue has no entry in def_positions.
    stray_inst = IntLiteralInst("1", INT32)
    stray_value = FIRValue(stray_inst)
    b.ret(stray_value)
    _expect_rule(module, "FIRV-D1")


def test_d1_operand_from_unreachable_block():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    entry = b.current_block
    orphan = func.new_block()  # nothing branches/jumps to it -- unreachable
    b.position_at(orphan)
    orphan_value = b.int_literal("1", INT32)
    b.ret(orphan_value)
    b.position_at(entry)
    b.ret(orphan_value)  # entry (reachable) uses orphan's (unreachable) value
    _expect_rule(module, "FIRV-D1")


def test_d2_paramvalue_unknown_name():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    bogus_param = ParamValue("does_not_exist", INT32)
    b.ret(bogus_param)
    _expect_rule(module, "FIRV-D2")


def test_d3_operand_has_void_result_type():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    # A void-result instruction: block.add_instruction() would normally
    # return None for it (has_result() is False), so build the FIRValue
    # directly via .result() and splice it into the block by hand to get
    # an operand whose producing instruction's result_type is void.
    void_inst = CallInst("does_not_exist", [], [], None)
    void_value = void_inst.result()
    b.current_block.instructions.append(void_inst)
    b.ret(void_value)  # used as if it produced a value
    _expect_rule(module, "FIRV-D3")


def test_d1_unsupported_operand_kind():
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    b.ret("not_a_value")  # neither ParamValue nor FIRValue
    _expect_rule(module, "FIRV-D1")

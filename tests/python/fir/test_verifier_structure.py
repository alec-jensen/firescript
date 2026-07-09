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
from fir import FIRBuilder, FIRFunction, FIRModule, make_simple  # noqa: E402


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

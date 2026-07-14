"""Unit tests for the FIR builder (firescript/fir/), migrated from
tests/fir_unit_tests.py (spec sec.4.4 migration table)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from fir import FIRBuilder, FIRFunction, FIRModule, make_simple  # noqa: E402
from fir.ir_node import ReturnInst  # noqa: E402


def test_block_rejects_second_terminator():
    # BasicBlock.set_terminator (ir_node.py) guards against a block being
    # sealed twice; FIRBuilder's own high-level `.ret()`/`.branch()`/etc.
    # helpers only ever call it once per block, so drive BasicBlock
    # directly to exercise the guard.
    int32 = make_simple("int32")
    func = FIRFunction("f", return_type=int32)
    builder = FIRBuilder(func)
    v0 = builder.int_literal("1", int32)
    block = func.blocks[0]
    builder.ret(v0)  # first terminator: succeeds

    try:
        block.set_terminator(ReturnInst(v0))
        t.require(False, "no error raised")
    except ValueError as e:
        t.require("terminator" in str(e), str(e))


def test_terminated_block_rejects_more_instructions():
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction("sealed", return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    v0 = builder.int_literal("1", int32)
    builder.ret(v0)

    try:
        builder.int_literal("2", int32)
        t.require(False, "no error raised")
    except ValueError as e:
        t.require("terminator" in str(e), str(e))


def test_unary_op_infers_result_type_from_operand():
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    x = builder.int_literal("1", int32)
    neg = builder.unary_op("-", x)  # no explicit result_type
    t.require_eq(neg.result_type, int32)
    builder.ret(neg)


def test_function_validate_wraps_in_throwaway_module():
    int32 = make_simple("int32")
    func = FIRFunction("standalone", return_type=int32)
    builder = FIRBuilder(func)
    builder.ret(builder.int_literal("1", int32))
    func.validate()  # must not raise


def test_borrow_produces_a_value():
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction("f", params=[("x", int32)], return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    from fir.ir_node import ParamValue

    borrowed = builder.borrow(ParamValue("x", int32), mutable=True)
    t.require(borrowed is not None)
    builder.ret(builder.int_literal("1", int32))

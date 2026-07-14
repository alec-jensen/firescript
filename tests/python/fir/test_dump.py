"""Unit tests for the FIR textual dump format (firescript/fir/), migrated
from tests/fir_unit_tests.py (spec sec.4.4 migration table)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT
from support.fir_fixtures import build_bump_or_reset

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from fir import FIRBuilder, FIRFunction, FIRModule, GeneratorType, dump_module, make_simple  # noqa: E402
from fir.ir_module import GlobalConstant  # noqa: E402

EXPECTED_BUMP_OR_RESET = """fir module firescript

type Counter owned {
  value: int32
}

function @bump_or_reset(counter: Counter, should_reset: bool) -> int32 {
  L0:
    %0 = loadfield.int32 counter, "value"
    br should_reset, L1, L2

  L1:
    %1 = const.int32 0
    storefield counter, "value", %1
    drop counter
    ret %1

  L2:
    %2 = const.int32 1
    %3 = binop "+", %0, %2
    storefield counter, "value", %3
    call @println(%3 borrow)
    drop counter
    ret %3
}
"""


def test_dump_matches_spec_example():
    module = build_bump_or_reset()
    module.validate()
    text = dump_module(module)
    t.require_eq(text, EXPECTED_BUMP_OR_RESET)


def test_dump_is_deterministic_for_same_module_object():
    module = build_bump_or_reset()
    first = dump_module(module)
    second = dump_module(module)
    t.require_eq(first, second)


def test_dump_is_deterministic_across_rebuilds():
    first = dump_module(build_bump_or_reset())
    second = dump_module(build_bump_or_reset())
    t.require_eq(first, second)


def test_generic_function_header():
    t_param = make_simple("T")
    module = FIRModule("firescript")
    func = FIRFunction(
        "unwrap_or_default",
        params=[("box", make_simple("Box")), ("fallback", t_param)],
        return_type=t_param,
        generic_params=["T"],
    )
    module.add_function(func)
    builder = FIRBuilder(func)
    builder.ret(func.param_value("fallback"))

    text = dump_module(module)
    t.require("function<T> @unwrap_or_default(box: Box, fallback: T) -> T {" in text, text)


def test_generator_function_header():
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction(
        "range",
        params=[("end", int32)],
        return_type=GeneratorType(int32),
        is_generator=True,
    )
    module.add_function(func)
    builder = FIRBuilder(func)
    v0 = builder.int_literal("0", int32)
    builder.yield_value(v0)
    builder.ret()

    text = dump_module(module)
    t.require("generator @range(end: int32) -> generator<int32> {" in text, text)
    t.require("    yield %0" in text, text)


def test_borrow_param_rendering():
    int32 = make_simple("int32")
    point = make_simple("Point")
    module = FIRModule("firescript")
    func = FIRFunction(
        "inspect",
        params=[("p", point), ("q", point)],
        return_type=int32,
        param_modes=["borrow", "borrow_mut"],
    )
    module.add_function(func)
    builder = FIRBuilder(func)
    v0 = builder.int_literal("0", int32)
    builder.ret(v0)

    text = dump_module(module)
    t.require("function @inspect(p: &Point, q: &mut Point) -> int32 {" in text, text)


def test_char_literal_dump_rendering():
    char_t = make_simple("char")
    module = FIRModule("firescript")
    func = FIRFunction("first_char", return_type=char_t)
    module.add_function(func)
    builder = FIRBuilder(func)
    v0 = builder.char_literal("A", char_t)
    builder.ret(v0)

    text = dump_module(module)
    t.require("cconst 'A'" in text, text)


def test_borrow_and_clone_dump_rendering():
    # `FIRBuilder.borrow()` / `.clone()` (ir_builder.py) exist and are
    # fully wired through the FIR verifier and FLIR lowering, but
    # ast_to_fir.py never actually calls them -- ownership lowering
    # represents borrows/moves some other way (e.g. call argument modes),
    # so BorrowInst/CloneInst are only reachable by constructing FIR
    # directly, same as the already-documented ".clone() not wired up"
    # gap (see MEMORY.md). Drive them directly here.
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction("touch", params=[("x", int32)], return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    x = func.param_value("x")
    builder.borrow(x, mutable=False)
    builder.borrow(x, mutable=True)
    cloned = builder.clone(x)
    builder.ret(cloned)

    text = dump_module(module)
    t.require("borrow x" in text, text)
    t.require("borrow x, mut" in text, text)
    t.require("clone x" in text, text)


def test_global_constant_dump_rendering():
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    module.add_constant(GlobalConstant("MAX_RETRIES", int32, "3"))

    text = dump_module(module)
    t.require("const MAX_RETRIES: int32 = 3" in text, text)


def test_resolve_rejects_unsupported_operand_kind():
    # `resolve()` inside the function formatter only understands
    # ParamValue and FIRValue; anything else (e.g. a bare object) can't
    # come from a real FIR instruction's operand list under normal
    # construction, but the defensive TypeError guard is still worth
    # exercising directly.
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction("f", return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    v0 = builder.int_literal("1", int32)
    builder.ret(v0)
    func.blocks[0].terminator.operands = [object()]

    try:
        dump_module(module)
        t.require(False, "no error raised")
    except TypeError as e:
        t.require("unsupported operand kind" in str(e), str(e))


def test_unreachable_terminator_dump_rendering():
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction("dead_end", return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    builder.unreachable()

    text = dump_module(module)
    t.require("unreachable" in text, text)


def test_foreign_value_rejected_in_dump():
    int32 = make_simple("int32")
    module = FIRModule("firescript")

    func_a = FIRFunction("a", return_type=int32)
    builder_a = FIRBuilder(func_a)
    foreign = builder_a.int_literal("1", int32)
    builder_a.ret(foreign)
    module.add_function(func_a)

    func_b = FIRFunction("b", return_type=int32)
    builder_b = FIRBuilder(func_b)
    builder_b.ret(foreign)
    module.add_function(func_b)

    try:
        dump_module(module)
        t.require(False, "no error raised")
    except ValueError as e:
        t.require("not in function" in str(e), str(e))

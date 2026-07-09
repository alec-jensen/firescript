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

EXPECTED_BUMP_OR_RESET = """module firescript

type Counter owned {
  value: int32
}

function bump_or_reset(counter: Counter, should_reset: bool) -> int32 {
  block_0:
    %0 = LoadField(counter, "value")
    Branch(should_reset, block_1, block_2)

  block_1:
    %1 = IntLiteral(0, int32)
    StoreField(counter, "value", %1)
    Drop(counter)
    Return(%1)

  block_2:
    %2 = IntLiteral(1, int32)
    %3 = BinaryOp("+", %0, %2)
    StoreField(counter, "value", %3)
    Call(println, [%3], ["borrow"])
    Return(%3)
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
    t.require("function<T> unwrap_or_default(box: Box, fallback: T) -> T {" in text, text)


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
    t.require("generator range(end: int32) -> generator<int32> {" in text, text)
    t.require("    Yield(%0)" in text, text)


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
    t.require("function inspect(p: &Point, q: &mut Point) -> int32 {" in text, text)


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

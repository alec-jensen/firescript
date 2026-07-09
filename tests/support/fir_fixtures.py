"""Shared FIR module fixtures used by tests/python/fir/* (spec sec.4.4)."""
from __future__ import annotations

import os
import sys

from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from fir import FIRBuilder, FIRFunction, FIRModule, TypeDef, make_simple  # noqa: E402


def build_bump_or_reset() -> FIRModule:
    """Build the bump_or_reset example from fir_spec.md by hand."""
    int32 = make_simple("int32")
    bool_t = make_simple("bool")
    counter_t = make_simple("Counter")

    module = FIRModule("firescript")
    module.add_type(TypeDef("Counter", "owned", fields=[("value", int32)]))

    func = FIRFunction(
        "bump_or_reset",
        params=[("counter", counter_t), ("should_reset", bool_t)],
        return_type=int32,
    )
    module.add_function(func)

    builder = FIRBuilder(func)
    entry = builder.current_block
    then_block = builder.new_block()
    else_block = builder.new_block()

    counter = func.param_value("counter")
    should_reset = func.param_value("should_reset")

    builder.position_at(entry)
    v0 = builder.load_field(counter, "value", int32)
    builder.branch(should_reset, then_block.id, else_block.id)

    builder.position_at(then_block)
    v1 = builder.int_literal("0", int32)
    builder.store_field(counter, "value", v1)
    builder.drop(counter)
    builder.ret(v1)

    builder.position_at(else_block)
    v2 = builder.int_literal("1", int32)
    v3 = builder.binary_op("+", v0, v2)
    builder.store_field(counter, "value", v3)
    builder.call("println", [v3], ["borrow"], None)
    builder.ret(v3)

    return module

"""Unit tests for the FIR infrastructure (firescript/fir/).

Run with: python tests/fir_unit_tests.py

Covers: builder construction, textual dump format, dump determinism,
and structural validation. These are pure-Python tests; no compilation
of firescript source is involved.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "firescript"))

from fir import (  # noqa: E402
    FIRBuilder,
    FIRFunction,
    FIRModule,
    GeneratorType,
    TypeDef,
    dump_module,
    make_simple,
)

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"[PASS  ] {name}")
    else:
        print(f"[FAIL  ] {name} {detail}")
        FAILURES.append(name)


def build_bump_or_reset() -> FIRModule:
    """Build the bump_or_reset example from FIR_fir_spec.md by hand."""
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


def test_dump_matches_spec_example() -> None:
    module = build_bump_or_reset()
    module.validate()
    text = dump_module(module)
    check(
        "dump matches spec example",
        text == EXPECTED_BUMP_OR_RESET,
        f"\n--- expected\n{EXPECTED_BUMP_OR_RESET}\n--- actual\n{text}",
    )


def test_dump_is_deterministic() -> None:
    module = build_bump_or_reset()
    first = dump_module(module)
    second = dump_module(module)
    check("dump is deterministic for same module object", first == second)

    rebuilt = dump_module(build_bump_or_reset())
    check("dump is deterministic across rebuilds", first == rebuilt)


def test_generic_function_header() -> None:
    int32 = make_simple("int32")
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
    check(
        "generic function header",
        "function<T> unwrap_or_default(box: Box, fallback: T) -> T {" in text,
        text,
    )
    del int32


def test_generator_function_header() -> None:
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
    check(
        "generator function header",
        "generator range(end: int32) -> generator<int32> {" in text,
        text,
    )
    check("yield renders without result", "    Yield(%0)" in text, text)


def test_borrow_param_rendering() -> None:
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
    check(
        "borrow params render with & and &mut",
        "function inspect(p: &Point, q: &mut Point) -> int32 {" in text,
        text,
    )


def test_validation_rejects_missing_terminator() -> None:
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction("broken", return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    builder.int_literal("1", int32)  # no terminator set

    try:
        module.validate()
        check("validation rejects missing terminator", False, "no error raised")
    except ValueError as e:
        check("validation rejects missing terminator", "no terminator" in str(e), str(e))


def test_validation_rejects_unknown_branch_target() -> None:
    int32 = make_simple("int32")
    bool_t = make_simple("bool")
    module = FIRModule("firescript")
    func = FIRFunction("bad_branch", return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    cond = builder.bool_literal(True, bool_t)
    builder.branch(cond, "block_99", "block_98")

    try:
        module.validate()
        check("validation rejects unknown branch target", False, "no error raised")
    except ValueError as e:
        check("validation rejects unknown branch target", "unknown block" in str(e), str(e))


def test_terminated_block_rejects_more_instructions() -> None:
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction("sealed", return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    v0 = builder.int_literal("1", int32)
    builder.ret(v0)

    try:
        builder.int_literal("2", int32)
        check("terminated block rejects more instructions", False, "no error raised")
    except ValueError as e:
        check("terminated block rejects more instructions", "terminator" in str(e), str(e))


def test_foreign_value_rejected_in_dump() -> None:
    int32 = make_simple("int32")
    module = FIRModule("firescript")

    func_a = FIRFunction("a", return_type=int32)
    builder_a = FIRBuilder(func_a)
    foreign = builder_a.int_literal("1", int32)
    builder_a.ret(foreign)
    module.add_function(func_a)

    func_b = FIRFunction("b", return_type=int32)
    builder_b = FIRBuilder(func_b)
    builder_b.ret(foreign)  # value from func_a used in func_b
    module.add_function(func_b)

    try:
        dump_module(module)
        check("dump rejects values from another function", False, "no error raised")
    except ValueError as e:
        check("dump rejects values from another function", "not in function" in str(e), str(e))


def main() -> int:
    test_dump_matches_spec_example()
    test_dump_is_deterministic()
    test_generic_function_header()
    test_generator_function_header()
    test_borrow_param_rendering()
    test_validation_rejects_missing_terminator()
    test_validation_rejects_unknown_branch_target()
    test_terminated_block_rejects_more_instructions()
    test_foreign_value_rejected_in_dump()

    total = 9
    passed = total - len(FAILURES)
    print(f"\nSummary: {passed}/{total} passed, {len(FAILURES)}/{total} failed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())

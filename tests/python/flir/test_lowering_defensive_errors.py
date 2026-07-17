"""Unit tests for the defensive `LoweringError`/`assert` branches in
firescript/flir/lowering.py -- internal invariant checks that guard against
malformed FIR the real compiler pipeline never produces (the frontend/FIR
verifier reject any source that would reach them). These are exercised by
driving FIRToFLIRLowering directly, calling its internal methods with
hand-crafted (and sometimes deliberately invalid) arguments rather than
going through the full compiler."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from fir import FIRBuilder, FIRFunction, FIRModule, make_simple  # noqa: E402
from fir.ir_node import BinaryOpInst, DropInst  # noqa: E402
from flir.ir import BOOL, F128, I32, PTR, FLIRFunction  # noqa: E402
from flir.lowering import FIRToFLIRLowering, LoweringError, _FuncCtx  # noqa: E402

INT32 = make_simple("int32")
STRING = make_simple("string")


def _lowering() -> FIRToFLIRLowering:
    return FIRToFLIRLowering(FIRModule("firescript"))


def _ctx(name: str = "f") -> tuple[_FuncCtx, FLIRFunction]:
    func = FLIRFunction(name, [], I32)
    ctx = _FuncCtx(func, {})
    ctx.block = func.new_block()
    return ctx, func


def _materialize(lowering: FIRToFLIRLowering, ctx: _FuncCtx, fir_value) -> None:
    """Lower a builder-produced FIRValue's instruction so ctx.values has an
    entry for it, letting a subsequent self.val(fir_value, ctx) succeed."""
    lowering.lower_inst(fir_value.instruction, ctx)


def test_lower_type_rejects_unknown_fir_type():
    class Weird:
        def render(self) -> str:
            return "weird"

    lowering = _lowering()
    try:
        lowering.lower_type(Weird(), {})
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("cannot lower FIR type" in str(e), str(e))


def test_ensure_struct_rejects_unknown_class():
    lowering = _lowering()
    try:
        lowering.ensure_struct("NoSuchClass", [])
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("unknown class" in str(e), str(e))


def test_request_function_rejects_unknown_function():
    lowering = _lowering()
    try:
        lowering.request_function("no_such_fn", [])
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("call to unknown function" in str(e), str(e))


def test_val_rejects_unsupported_operand_kind():
    lowering = _lowering()
    ctx, _ = _ctx()
    try:
        lowering.val(object(), ctx)  # not a ParamValue or FIRValue
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("unsupported FIR operand" in str(e), str(e))


def test_val_rejects_fir_value_with_no_lowered_value():
    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)  # never lowered / registered in ctx.values

    lowering = _lowering()
    ctx, _ = _ctx()
    try:
        lowering.val(x, ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("has no lowered value" in str(e), str(e))


def test_lower_inst_rejects_unsupported_instruction():
    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    y = b.int_literal("2", INT32)
    # DropInst is a valid instruction kind overall, but the dedicated
    # lower_drop() path only handles it via lower_inst's DropInst branch;
    # to hit the generic "cannot lower FIR instruction" fallback we need an
    # opcode lower_inst genuinely doesn't recognize at all. BinaryOpInst
    # *is* handled -- use a bespoke instruction stand-in instead.
    class FakeInst:
        opcode = "fake_op"

    lowering = _lowering()
    ctx, _ = _ctx()
    try:
        lowering.lower_inst(FakeInst(), ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("cannot lower FIR instruction" in str(e), str(e))


def test_lower_terminator_rejects_unsupported_terminator():
    class FakeTerm:
        opcode = "fake_term"

    lowering = _lowering()
    ctx, _ = _ctx()
    try:
        lowering.lower_terminator(FakeTerm(), ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("cannot lower terminator" in str(e), str(e))


def test_lower_binary_rejects_unsupported_string_operator():
    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=STRING)
    module.add_function(func)
    b = FIRBuilder(func)
    lhs = b.string_literal("a", STRING)
    rhs = b.string_literal("b", STRING)
    inst = BinaryOpInst("-", lhs, rhs, STRING)  # subtraction is not defined on strings

    lowering = _lowering()
    ctx, _ = _ctx()
    _materialize(lowering, ctx, lhs)
    _materialize(lowering, ctx, rhs)
    try:
        lowering.lower_binary(inst, ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("unsupported string operator" in str(e), str(e))


def test_lower_binary_rejects_unsupported_float128_operator():
    F128_T = make_simple("float128")
    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=F128_T)
    module.add_function(func)
    b = FIRBuilder(func)
    lhs = b.float_literal("2.0", F128_T)
    rhs = b.float_literal("3.0", F128_T)
    # "**" has no fs_rt_f128_* runtime entry point -- see also the
    # newly-discovered bug this documents: `float128 ** float128` in real
    # firescript source crashes the compiler the same way (not fixed here).
    inst = BinaryOpInst("**", lhs, rhs, F128_T)

    lowering = _lowering()
    ctx, func = _ctx()
    _materialize(lowering, ctx, lhs)
    _materialize(lowering, ctx, rhs)
    try:
        lowering.lower_binary(inst, ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("unsupported float128 operator" in str(e), str(e))


def test_lower_binary_rejects_unsupported_operator():
    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    lhs = b.int_literal("1", INT32)
    rhs = b.int_literal("2", INT32)
    inst = BinaryOpInst("^", lhs, rhs, INT32)  # bitwise xor: not a supported FIR binop

    lowering = _lowering()
    ctx, _ = _ctx()
    _materialize(lowering, ctx, lhs)
    _materialize(lowering, ctx, rhs)
    try:
        lowering.lower_binary(inst, ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("unsupported binary operator" in str(e), str(e))


def test_lower_unary_rejects_unsupported_operator():
    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    inst = b.unary_op("~", x, INT32)  # bitwise not: not a supported FIR unop

    lowering = _lowering()
    ctx, _ = _ctx()
    _materialize(lowering, ctx, x)
    try:
        lowering.lower_unary(inst.instruction, ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("unsupported unary operator" in str(e), str(e))


def test_to_string_rejects_unconvertible_source_type():
    lowering = _lowering()
    ctx, _ = _ctx()
    try:
        lowering._to_string(None, "SomeWeirdType", None, ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("cannot convert" in str(e), str(e))


def test_lower_load_var_rejects_undeclared_local():
    from fir.ir_node import LoadVarInst

    lowering = _lowering()
    ctx, func = _ctx()
    inst = LoadVarInst("never_declared", INT32)
    try:
        lowering.lower_load_var(inst, ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("load of undeclared local" in str(e), str(e))


def test_lower_conversion_call_rejects_unsupported_name():
    from fir.ir_node import CallInst

    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)

    lowering = _lowering()
    ctx, _ = _ctx()
    _materialize(lowering, ctx, x)
    lowered_x = lowering.val(x, ctx)
    inst = CallInst("bogusConv", [x], None, INT32)
    try:
        lowering.lower_conversion_call(inst, "bogusConv", [lowered_x], ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("unsupported conversion" in str(e), str(e))


def test_lower_method_call_rejects_unknown_method():
    from fir.ir_node import MethodCallInst

    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    recv = b.string_literal("x", STRING)
    inst = MethodCallInst(recv, "totallyBogusMethod", [], None, INT32)

    lowering = _lowering()
    ctx, _ = _ctx()
    try:
        lowering.lower_method_call(inst, ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("unknown method" in str(e), str(e))


def test_gen_slot_of_rejects_non_generator_operand():
    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)  # not a generator-local LoadVar/GenNew

    lowering = _lowering()
    ctx, _ = _ctx()
    try:
        lowering._gen_slot_of(x, ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("generator operand is not a generator local" in str(e), str(e))


def test_lower_yield_rejects_yield_outside_generator():
    from fir.ir_node import YieldInst

    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)
    inst = YieldInst(x)

    lowering = _lowering()
    ctx, _ = _ctx()
    t.require(ctx.frame_struct is None, "sanity: ctx must not look like a generator frame")
    try:
        lowering.lower_yield(inst, ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("yield outside generator" in str(e), str(e))


def test_array_length_call_rejects_unknown_size():
    from fir.ir_node import CallInst, LoadVarInst
    from fir.ir_types import ArrayType

    arr_type = ArrayType(INT32, size=None)
    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    # A LoadVar naming a slot with no tracked array_lens metadata: length is
    # genuinely unknowable at lowering time.
    arr_ref = b.load_var("untracked_array", arr_type)
    inst = CallInst("array_length", [arr_ref], None, INT32)

    lowering = _lowering()
    ctx, _ = _ctx()
    ctx.slot_types["untracked_array"] = PTR
    _materialize(lowering, ctx, arr_ref)
    try:
        lowering.lower_call(inst, ctx)
        t.require(False, "expected LoweringError")
    except LoweringError as e:
        t.require("array_length on array of unknown size" in str(e), str(e))


# ---------------------------------------------------------------------------
# Non-error branches that are nonetheless unreachable through the real
# compiler pipeline (ast_to_fir.py never constructs a MoveInst/BorrowInst/
# CloneInst, and "&&"/"||" are always lowered to control flow before
# reaching lower_binary) -- exercised directly for the same reason as the
# LoweringError branches above.
# ---------------------------------------------------------------------------


def test_val_loads_param_value_from_slot():
    # ParamValue is constructed by FIRFunction.param_value(), but
    # ast_to_fir.py never actually calls that method -- every real
    # function body reads its parameters back out through a LoadVarInst
    # slot instead. Exercised directly here.
    from fir.ir_node import ParamValue

    lowering = _lowering()
    ctx, func = _ctx()
    ctx.slot_types["p"] = I32
    pv = ParamValue("p", INT32)
    fv = lowering.val(pv, ctx)
    t.require(fv.instruction.opcode == "slotload", fv.instruction.opcode)


def test_fir_type_str_of_returns_void_for_none_result_type():
    class FakeVoidValue:
        result_type = None

    lowering = _lowering()
    ctx, _ = _ctx()
    t.require(lowering.fir_type_str_of(FakeVoidValue(), ctx) == "void")


def test_ensure_slot_is_idempotent():
    lowering = _lowering()
    ctx, func = _ctx()
    lowering.ensure_slot("x", I32, ctx)
    t.require(len(func.blocks[0].instructions) == 1, "first call should emit a SlotDecl")
    lowering.ensure_slot("x", I32, ctx)  # already declared -> early return, no duplicate SlotDecl
    t.require(len(func.blocks[0].instructions) == 1, "second call must not emit another SlotDecl")


def test_lower_inst_passes_through_move_borrow_clone():
    from fir.ir_node import BorrowInst, CloneInst, MoveInst

    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    x = b.int_literal("1", INT32)

    lowering = _lowering()
    ctx, _ = _ctx()
    _materialize(lowering, ctx, x)
    inner = lowering.val(x, ctx)

    for wrapper in (MoveInst(x), BorrowInst(x, False), CloneInst(x)):
        lowering.lower_inst(wrapper, ctx)
        t.require(ctx.values[id(wrapper)] is inner, "wrapper should pass through the inner FValue unchanged")


def test_lower_binary_non_short_circuit_and_or_fallback():
    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=None)
    module.add_function(func)
    b = FIRBuilder(func)
    bool_t = make_simple("bool")
    lhs = b.bool_literal(True, bool_t)
    rhs = b.bool_literal(False, bool_t)

    lowering = _lowering()
    ctx, _ = _ctx()
    _materialize(lowering, ctx, lhs)
    _materialize(lowering, ctx, rhs)

    and_inst = BinaryOpInst("&&", lhs, rhs, bool_t)
    lowering.lower_binary(and_inst, ctx)
    t.require(ctx.values[id(and_inst)].instruction.opcode == "binop", "should emit a BinOp")

    or_inst = BinaryOpInst("||", lhs, rhs, bool_t)
    lowering.lower_binary(or_inst, ctx)
    t.require(ctx.values[id(or_inst)].instruction.opcode == "binop", "should emit a BinOp")


def test_gen_slot_of_finds_slot_from_direct_gen_new():
    from fir.ir_node import GenNewInst

    module = FIRModule("firescript")
    func = FIRFunction("g", return_type=INT32)
    module.add_function(func)
    b = FIRBuilder(func)
    gen_type = make_simple("generator")
    gen_new = b.gen_new("some_generator", [], gen_type)

    lowering = _lowering()
    ctx, _ = _ctx()
    ctx.gen_slots["frame_slot"] = "lowered_some_generator"

    slot = lowering._gen_slot_of(gen_new, ctx)
    t.require(slot == "frame_slot", slot)


def test_lower_driver_skips_runtime_prefixed_and_generic_class_method_functions():
    from fir.ir_module import TypeDef

    module = FIRModule("firescript")
    # A function whose name starts with "fs_rt_": runtime implementations
    # lower on demand via rt_call, so the root-function scan must skip it.
    rt_func = FIRFunction("fs_rt_something", return_type=None)
    module.add_function(rt_func)

    # A method of a *generic* class: those lower per-instantiation instead
    # of as a root, keyed off metadata["class_name"].
    module.add_type(TypeDef("Box", category="owned", generic_params=["T"]))
    method_func = FIRFunction("Box.get", return_type=INT32)
    method_func.metadata["class_name"] = "Box"
    module.add_function(method_func)

    lowering = FIRToFLIRLowering(module)
    lowering.lower()
    t.require(("fs_rt_something", ()) not in lowering.lowered_names, "fs_rt_ function must not be a root")
    t.require(("Box.get", ()) not in lowering.lowered_names, "generic class method must not be a root")

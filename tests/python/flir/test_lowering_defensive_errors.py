"""Unit tests for firescript/flir/lowering.py internals driven directly with
hand-built FIR: the float128 `**` operator (currently a LoweringError that
reaches users as an uncaught traceback -- this test pins that known bug and
is expected to be rewritten when it is fixed), ensure_slot idempotence,
generator frame-slot lookup, and the root-function scan's skip rules."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from fir import FIRBuilder, FIRFunction, FIRModule, make_simple  # noqa: E402
from fir.ir_node import BinaryOpInst  # noqa: E402
from flir.ir import I32, FLIRFunction  # noqa: E402
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


def test_ensure_slot_is_idempotent():
    lowering = _lowering()
    ctx, func = _ctx()
    lowering.ensure_slot("x", I32, ctx)
    t.require(len(func.blocks[0].instructions) == 1, "first call should emit a SlotDecl")
    lowering.ensure_slot("x", I32, ctx)  # already declared -> early return, no duplicate SlotDecl
    t.require(len(func.blocks[0].instructions) == 1, "second call must not emit another SlotDecl")


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

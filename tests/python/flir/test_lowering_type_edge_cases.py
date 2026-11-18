"""Unit tests for FIRToFLIRLowering type-lowering branches that are awkward
to reach through the full compiler pipeline, exercised by driving the
lowering internals directly: lower_type/lower_type_str/render_concrete
branches for FIRType shapes that either can't be spelled directly in
firescript source in isolation (a bare, unsubstituted generic type
parameter reaching lowering; a generator/function type lowered outside its
special-cased slot/call handling) or are cheaper to build as a FIRType
directly than to force through the parser/semantic pipeline."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from fir import FIRModule, TypeDef, make_simple  # noqa: E402
from fir.ir_types import FunctionType, GeneratorType, GenericInstanceType  # noqa: E402
from flir.ir import PTR  # noqa: E402
from flir.lowering import FIRToFLIRLowering  # noqa: E402

INT32 = make_simple("int32")
STRING = make_simple("string")


def _lowering() -> FIRToFLIRLowering:
    # No runtime_module: self.typedefs has no "SyscallResult" entry, same
    # as the special-cased branches assume when they check `not in
    # self.typedefs`.
    return FIRToFLIRLowering(FIRModule("firescript"))


def test_lower_type_treats_unsubstituted_generic_param_as_ptr():
    # A bare type-parameter name (e.g. "T") with no entry in type_map --
    # the fallback the comment in lower_type describes as "unsubstituted
    # generic parameter or unknown named type: treat as pointer-sized
    # owned value."
    lowering = _lowering()
    flir_type = lowering.lower_type(make_simple("T"), {})
    t.require(flir_type == PTR, flir_type)


def test_lower_type_handles_generator_type_directly():
    # generator<T> lowered outside the special-cased generator-slot
    # handling (e.g. a struct field or nested type position) is just a
    # pointer -- generator locals only become meaningful through gen_slots.
    lowering = _lowering()
    flir_type = lowering.lower_type(GeneratorType(INT32), {})
    t.require(flir_type == PTR, flir_type)


def test_lower_type_handles_function_type_directly():
    lowering = _lowering()
    flir_type = lowering.lower_type(FunctionType([INT32], INT32), {})
    t.require(flir_type == PTR, flir_type)


def test_render_concrete_falls_back_to_render_for_function_type():
    lowering = _lowering()
    ft = FunctionType([INT32], STRING)
    text = lowering.render_concrete(ft, {})
    t.require(text == ft.render(), f"{text} != {ft.render()}")


def test_lower_type_str_handles_array_suffix():
    lowering = _lowering()
    flir_type = lowering.lower_type_str("int32[]", {})
    t.require(flir_type == PTR, flir_type)


def test_lower_type_str_handles_generator_prefix():
    lowering = _lowering()
    flir_type = lowering.lower_type_str("generator<int32>", {})
    t.require(flir_type == PTR, flir_type)


def test_lower_type_str_handles_generic_instance_text():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Pair", category="owned", fields=[("a", INT32), ("b", STRING)], generic_params=["A", "B"]))
    lowering = FIRToFLIRLowering(module)
    flir_type = lowering.lower_type_str("Pair<int32, string>", {})
    t.require(flir_type.kind == "ptr", flir_type.kind)
    t.require(lowering.flir.has_struct(flir_type.pointee), flir_type.pointee)


def test_lower_type_str_handles_copyable_generic_instance_text():
    # Same generic-instance-by-string path as
    # test_lower_type_str_handles_generic_instance_text, but for a
    # *copyable* generic class -- hits the struct_type(...) (by-value)
    # branch instead of ptr_to(...). Real firescript source can't spell a
    # generic array-of-generic-instance type directly (the parser doesn't
    # accept `CopyablePair<int32, int32>[N]` as a declaration), so this is
    # exercised directly instead.
    module = FIRModule("firescript")
    module.add_type(
        TypeDef("CopyablePair", category="copyable", fields=[("a", INT32), ("b", INT32)], generic_params=["A", "B"])
    )
    lowering = FIRToFLIRLowering(module)
    flir_type = lowering.lower_type_str("CopyablePair<int32, int32>", {})
    t.require(flir_type.kind == "struct", flir_type.kind)


def test_lower_type_str_falls_back_to_ptr_for_unknown_bare_name():
    # A bare name that isn't a scalar, "string", a typedef, "SyscallResult",
    # array-suffixed, generator-prefixed, or generic-instance-shaped --
    # e.g. an unsubstituted generic type parameter's name reaching
    # lower_type_str as plain text.
    lowering = _lowering()
    flir_type = lowering.lower_type_str("T", {})
    t.require(flir_type == PTR, flir_type)


def test_lower_type_handles_generic_instance_type_directly():
    module = FIRModule("firescript")
    module.add_type(TypeDef("Pair", category="owned", fields=[("a", INT32), ("b", STRING)], generic_params=["A", "B"]))
    lowering = FIRToFLIRLowering(module)
    git = GenericInstanceType("Pair", [INT32, STRING])
    flir_type = lowering.lower_type(git, {})
    t.require(flir_type.kind == "ptr", flir_type.kind)

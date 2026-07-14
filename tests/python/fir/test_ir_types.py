"""Direct unit tests for fir.ir_types: FIRType equality/hashing and the
FunctionType signature type, which no current pass constructs but which is
part of the public FIR type API."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from fir.ir_types import FunctionType, SimpleType, make_simple  # noqa: E402


def test_is_copyable_true_for_copyable_category():
    t.require(make_simple("int32").is_copyable())
    t.require(not make_simple("int32").is_owned())


def test_repr_includes_class_name_and_render():
    ty = make_simple("int32")
    r = repr(ty)
    t.require("SimpleType" in r and "int32" in r, r)


def test_hash_allows_use_in_sets_and_dicts():
    a = make_simple("int32")
    b = make_simple("int32")
    s = {a, b}
    t.require_eq(len(s), 1)
    d = {a: "value"}
    t.require_eq(d[b], "value")


def test_function_type_render_with_params_and_return():
    int32 = make_simple("int32")
    fn = FunctionType([int32, int32], return_type=int32)
    t.require_eq(fn.render(), "(int32, int32) -> int32")
    t.require_eq(fn.param_borrowing, [False, False])
    t.require(fn.is_copyable())


def test_function_type_render_void_return():
    int32 = make_simple("int32")
    fn = FunctionType([int32])
    t.require_eq(fn.render(), "(int32) -> void")


def test_function_type_explicit_param_borrowing():
    int32 = make_simple("int32")
    fn = FunctionType([int32, int32], return_type=int32, param_borrowing=[True, False])
    t.require_eq(fn.param_borrowing, [True, False])


def test_base_render_raises_not_implemented():
    from fir.ir_types import FIRType

    class _Bare(FIRType):
        pass

    try:
        _Bare().render()
        t.require(False, "expected NotImplementedError")
    except NotImplementedError:
        pass

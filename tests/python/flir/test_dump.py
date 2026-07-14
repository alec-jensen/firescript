"""Unit tests for the FLIR textual dump format (firescript/flir/textual.py).
FLIR modules are built directly from flir.ir objects (there is no
FLIRBuilder helper -- see test_verifier_structure.py/test_verifier_types.py
for the established pattern)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from flir.ir import (  # noqa: E402
    ConstInt,
    FLIRFunction,
    FLIRModule,
    FValue,
    I32,
    Ret,
)
from flir.textual import dump_flir_module  # noqa: E402


def test_dump_module_with_mutable_global():
    module = FLIRModule("firescript")
    module.mutable_globals.append(("counter", I32))
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    zero = entry.add(ConstInt("0", I32))
    entry.instructions.append(Ret(zero))

    text = dump_flir_module(module)
    t.require("global mut counter: i32 = 0" in text, text)


def test_dump_module_with_immutable_global():
    module = FLIRModule("firescript")
    module.globals.append(("MAX", I32, "100"))
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    zero = entry.add(ConstInt("0", I32))
    entry.instructions.append(Ret(zero))

    text = dump_flir_module(module)
    t.require("global MAX: i32 = 100" in text, text)


def test_foreign_value_rejected_in_flir_dump():
    module = FLIRModule("firescript")

    func_a = FLIRFunction("a", return_type=I32)
    module.add_function(func_a)
    block_a = func_a.new_block()
    foreign = block_a.add(ConstInt("1", I32))
    block_a.instructions.append(Ret(foreign))

    func_b = FLIRFunction("b", return_type=I32)
    module.add_function(func_b)
    block_b = func_b.new_block()
    block_b.instructions.append(Ret(foreign))  # value produced in func_a, used in func_b

    try:
        dump_flir_module(module)
        t.require(False, "no error raised")
    except ValueError as e:
        t.require("not in function" in str(e), str(e))

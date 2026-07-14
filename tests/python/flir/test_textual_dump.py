"""Direct unit tests for the FLIR textual dump format (flir/textual.py)
and the FLIRFunction.validate() convenience wrapper (flir/ir.py), driven
directly with hand-built FLIR objects (no shipped test currently exercises
`dump_flir_module` at all)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from flir.ir import ConstInt, FLIRFunction, FLIRModule, I32, Ret  # noqa: E402
from flir.textual import dump_flir_module  # noqa: E402


def test_global_constant_dump_rendering():
    module = FLIRModule("firescript")
    module.globals.append(("MAX_RETRIES", I32, "3"))

    text = dump_flir_module(module)
    t.require("global MAX_RETRIES: i32 = 3" in text, text)


def test_resolve_rejects_foreign_value():
    module = FLIRModule("firescript")

    func_a = FLIRFunction("a", return_type=I32)
    block_a = func_a.new_block()
    foreign = block_a.add(ConstInt("1", I32))
    block_a.add(Ret(foreign))
    module.add_function(func_a)

    func_b = FLIRFunction("b", return_type=I32)
    block_b = func_b.new_block()
    block_b.add(Ret(foreign))
    module.add_function(func_b)

    try:
        dump_flir_module(module)
        t.require(False, "no error raised")
    except ValueError as e:
        t.require("not in function" in str(e), str(e))


def test_function_validate_wraps_self_in_throwaway_module():
    func = FLIRFunction("standalone", return_type=I32)
    block = func.new_block()
    v0 = block.add(ConstInt("1", I32))
    block.add(Ret(v0))

    func.validate()  # must not raise: a clean, terminated function is valid

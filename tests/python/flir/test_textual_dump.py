"""Direct unit test for the FLIR textual dump's rejection of a value defined
in another function (flir/textual.py), driven with hand-built FLIR objects.
Dump formatting itself is covered by test_ir_analysis_edges.py and the
tests/snapshots/**/*.flir snapshots."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from flir.ir import ConstInt, FLIRFunction, FLIRModule, I32, Ret  # noqa: E402
from flir.textual import dump_flir_module  # noqa: E402


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

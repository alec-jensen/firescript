"""Unit tests for the FIR builder (firescript/fir/), migrated from
tests/fir_unit_tests.py (spec sec.4.4 migration table)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from fir import FIRBuilder, FIRFunction, FIRModule, make_simple  # noqa: E402


def test_terminated_block_rejects_more_instructions():
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction("sealed", return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    v0 = builder.int_literal("1", int32)
    builder.ret(v0)

    try:
        builder.int_literal("2", int32)
        t.require(False, "no error raised")
    except ValueError as e:
        t.require("terminator" in str(e), str(e))

"""Unit tests for FIR structural validation (firescript/fir/), migrated from
tests/fir_unit_tests.py (spec sec.4.4 migration table)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from fir import FIRBuilder, FIRFunction, FIRModule, make_simple  # noqa: E402


def test_validation_rejects_missing_terminator():
    int32 = make_simple("int32")
    module = FIRModule("firescript")
    func = FIRFunction("broken", return_type=int32)
    module.add_function(func)
    builder = FIRBuilder(func)
    builder.int_literal("1", int32)  # no terminator set

    try:
        module.validate()
        t.require(False, "no error raised")
    except ValueError as e:
        t.require("no terminator" in str(e), str(e))


def test_validation_rejects_unknown_branch_target():
    module = FIRModule("firescript")
    func = FIRFunction("bad_branch", return_type=make_simple("int32"))
    module.add_function(func)
    builder = FIRBuilder(func)
    cond = builder.bool_literal(True, make_simple("bool"))
    builder.branch(cond, "block_99", "block_98")

    try:
        module.validate()
        t.require(False, "no error raised")
    except ValueError as e:
        t.require("unknown block" in str(e), str(e))

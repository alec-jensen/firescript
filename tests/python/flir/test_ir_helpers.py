"""Unit tests for small standalone helpers in firescript/flir/ir.py
(FLIRType struct size/align without a module, ConstF128 formatting,
block/function guard clauses) not otherwise exercised by the verifier/dump
test suites."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from flir.ir import (  # noqa: E402
    ConstF128,
    ConstInt,
    F128_STRUCT_NAME,
    FLIRFunction,
    FLIRModule,
    FLIRType,
    I32,
    Ret,
)


def test_flir_type_struct_size_and_align_require_module_context():
    struct_t = FLIRType("struct", struct_name="Point")
    for query in (struct_t.size, struct_t.align):
        try:
            query()
            t.require(False, "no error raised")
        except ValueError as e:
            t.require("requires module context" in str(e), str(e))


def test_const_f128_format():
    inst = ConstF128(0x1122334455667788, 0x99AABBCCDDEEFF00, FLIRType("struct", struct_name=F128_STRUCT_NAME))
    text = inst.format(lambda v: "?")
    t.require(text.startswith("f128const 0x"), text)
    t.require("1122334455667788" in text and "99aabbccddeeff00" in text, text)


def test_block_add_after_terminated_raises():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    block = func.new_block()
    zero = block.add(ConstInt("0", I32))
    block.instructions.append(Ret(zero))
    try:
        block.add(ConstInt("1", I32))
        t.require(False, "no error raised")
    except ValueError as e:
        t.require("already terminated" in str(e), str(e))


def test_flir_function_validate_wraps_single_function():
    func = FLIRFunction("f", return_type=I32)
    entry = func.new_block()
    zero = entry.add(ConstInt("0", I32))
    entry.instructions.append(Ret(zero))
    func.validate()  # must not raise

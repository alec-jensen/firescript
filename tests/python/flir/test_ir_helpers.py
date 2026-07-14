"""Unit tests for small standalone helpers in firescript/flir/ir.py
(FLIRType predicates/dunder methods, FLIRStruct.field, FInst's default
format(), block/function guard clauses) not otherwise exercised by the
verifier/dump test suites."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from flir.ir import (  # noqa: E402
    BOOL,
    ConstF128,
    ConstInt,
    F128_STRUCT_NAME,
    FInst,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    FLIRType,
    I8,
    I32,
    I64,
    Ret,
    Unreachable,
    U8,
)


def test_flir_type_struct_size_requires_module_context():
    struct_t = FLIRType("struct", struct_name="Point")
    try:
        struct_t.size()
        t.require(False, "no error raised")
    except ValueError as e:
        t.require("requires module context" in str(e), str(e))


def test_flir_type_struct_align_requires_module_context():
    struct_t = FLIRType("struct", struct_name="Point")
    try:
        struct_t.align()
        t.require(False, "no error raised")
    except ValueError as e:
        t.require("requires module context" in str(e), str(e))


def test_flir_type_struct_size_and_align_with_module():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Point", kind="class")
    struct.fields = [("x", I32, 0), ("y", I32, 4)]
    struct.size = 8
    struct.align = 4
    module.add_struct(struct)
    struct_t = FLIRType("struct", struct_name="Point")
    t.require_eq(struct_t.size(module), 8)
    t.require_eq(struct_t.align(module), 4)


def test_flir_type_signed_and_unsigned_predicates():
    t.require(I8.is_signed_int())
    t.require(I64.is_signed_int())
    t.require(not U8.is_signed_int())
    t.require(U8.is_unsigned_int())
    t.require(not I8.is_unsigned_int())


def test_flir_type_hash_and_repr():
    t.require_eq(hash(I32), hash(FLIRType("i32")))
    t.require("i32" in repr(I32), repr(I32))
    # Usable as a dict key (exercises __hash__ in practice too).
    d = {I32: "int32 type"}
    t.require_eq(d[FLIRType("i32")], "int32 type")


def test_flir_struct_field_lookup_unknown_field_raises():
    struct = FLIRStruct("Point", kind="class")
    struct.fields = [("x", I32, 0)]
    try:
        struct.field("y")
        t.require(False, "no error raised")
    except KeyError as e:
        t.require("has no field y" in str(e), str(e))


def test_finst_default_format_joins_resolved_operands():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    a = entry.add(ConstInt("1", I32))
    b = entry.add(ConstInt("2", I32))
    # No concrete FInst subclass in flir/ir.py actually relies on the base
    # class's default format() (every one of them overrides it) -- this
    # exercises that shared base-class behavior directly.
    generic = FInst(operands=[a, b], result_type=I32)
    text = generic.format(lambda v: f"%{id(v.instruction) % 100}")
    t.require(text.startswith("inst "), text)
    t.require("," in text, text)


def test_unreachable_format():
    inst = Unreachable()
    t.require_eq(inst.format(lambda v: "?"), "unreachable")


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

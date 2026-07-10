"""Unit tests for FLIR Tier-1 structural rules (FLIRV-S) in
firescript/flir/verifier.py. FLIR modules are built directly from
flir.ir objects (there is no FLIRBuilder helper)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from errors import IRVerificationError  # noqa: E402
from flir.ir import (  # noqa: E402
    BOOL,
    Br,
    ConstBool,
    ConstInt,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    I32,
    Jmp,
    Ret,
    VOID,
    ptr_to,
)


def _expect_rule(module: FLIRModule, rule_id: str) -> None:
    try:
        module.validate()
        t.require(False, f"no error raised (expected {rule_id})")
    except IRVerificationError as e:
        t.require(any(v.rule_id == rule_id for v in e.violations), f"{rule_id} not in: {e}")


def test_s1_rejects_missing_terminator():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    block = func.new_block()
    block.instructions.append(ConstInt("1", I32))  # never terminated
    _expect_rule(module, "FLIRV-S1")


def test_s1_rejects_duplicate_block_id():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    b0 = func.new_block()
    b0.instructions.append(Ret())
    b1 = func.new_block()
    b1.id = b0.id
    b1.instructions.append(Ret())
    _expect_rule(module, "FLIRV-S1")


def test_s1_rejects_unknown_branch_target():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    block = func.new_block()
    cond = block.add(ConstBool(True))
    block.instructions.append(Br(cond, "L99", "L98"))
    _expect_rule(module, "FLIRV-S1")


def test_s1_rejects_unreachable_block():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    entry.instructions.append(Ret())
    orphan = func.new_block()
    orphan.instructions.append(Ret())
    _expect_rule(module, "FLIRV-S1")


def test_s1_rejects_terminator_mid_block():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    block = func.new_block()
    block.instructions.append(Ret())
    block.instructions.append(Ret())  # terminator not last
    _expect_rule(module, "FLIRV-S1")


def test_s2_rejects_duplicate_function_name():
    module = FLIRModule("firescript")
    f1 = FLIRFunction("dup", return_type=VOID)
    f1.new_block().instructions.append(Ret())
    f2 = FLIRFunction("dup", return_type=VOID)
    f2.new_block().instructions.append(Ret())
    module.add_function(f1)
    module.add_function(f2)
    _expect_rule(module, "FLIRV-S2")


def test_s2_rejects_unresolved_entry_function():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    module.entry_function = "does_not_exist"
    _expect_rule(module, "FLIRV-S2")


def test_s3_rejects_overlapping_fields():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Bad", kind="class")
    struct.fields = [("a", I32, 0), ("b", I32, 2)]  # overlaps a
    struct.size = 8
    struct.align = 4
    module.add_struct(struct)
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    _expect_rule(module, "FLIRV-S3")


def test_s3_rejects_misaligned_field():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Bad", kind="class")
    struct.fields = [("a", I32, 1)]  # i32 needs 4-byte alignment
    struct.size = 8
    struct.align = 4
    module.add_struct(struct)
    func = FLIRFunction("f", return_type=VOID)
    func.new_block().instructions.append(Ret())
    module.add_function(func)
    _expect_rule(module, "FLIRV-S3")


def test_verifier_structure_accepts_clean_module():
    module = FLIRModule("firescript")
    struct = FLIRStruct("Point", kind="class")
    struct.fields = [("x", I32, 0), ("y", I32, 4)]
    struct.size = 8
    struct.align = 4
    module.add_struct(struct)

    func = FLIRFunction("f", return_type=I32)
    module.add_function(func)
    entry = func.new_block()
    then_block = func.new_block()
    else_block = func.new_block()
    cond = entry.add(ConstBool(True))
    entry.instructions.append(Br(cond, then_block.id, else_block.id))
    one = then_block.add(ConstInt("1", I32))
    then_block.instructions.append(Ret(one))
    zero = else_block.add(ConstInt("0", I32))
    else_block.instructions.append(Ret(zero))
    module.entry_function = "f"

    module.validate()  # must not raise

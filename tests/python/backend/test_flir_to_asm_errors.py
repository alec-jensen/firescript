"""Unit tests for firescript/codegen/x86_64/flir_to_asm.py branches that
are impractical (or, in a couple of documented cases, impossible without
tripping an unrelated known bug -- see comments below) to reach through a
full .fire -> compile pipeline. FLIR modules/functions/instructions are
built directly from flir.ir objects, mirroring
tests/python/flir/test_verifier_structure.py's "no builder helper"
pattern, then handed straight to FLIRToAsmBackend -- no compilation
pipeline, no execution of the resulting assembly."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from flir.ir import (  # noqa: E402
    BOOL,
    BinOp,
    ConstBool,
    ConstFloat,
    ConstInt,
    F32,
    F64,
    FInst,
    FLIRFunction,
    FLIRModule,
    I32,
    Ret,
    U64,
    VOID,
)
from codegen.x86_64.flir_to_asm import AsmError, FLIRToAsmBackend  # noqa: E402


def test_mutable_global_emits_bss_section():
    """FLIRModule.mutable_globals is only ever populated by
    flir/lowering.py's _ensure_state_cell() (backing the
    runtime_state_get/runtime_state_set intrinsics gated behind
    `directive enable_lowlevel_runtime;`) -- exercised here directly since
    driving it through actual .fire source and *running* the resulting
    binary currently segfaults (a separate, pre-existing bug in how the
    mutable-global .bss cell is set up/addressed, out of scope to fix
    here). Generating the assembly text itself (this test) is unaffected
    and exercises _emit_mutable_globals()'s ".section .bss" + ".space"
    emission."""
    module = FLIRModule("test")
    module.mutable_globals.append(("__fs_runtime_state", U64))
    func = FLIRFunction("fs_main", return_type=VOID)
    module.add_function(func)
    block = func.new_block()
    block.add(Ret())
    asm = FLIRToAsmBackend(module).generate()
    t.require(".section .bss" in asm, asm)
    t.require("fsg_mut___fs_runtime_state:" in asm, asm)
    t.require(".space 8" in asm, asm)


def test_f32_and_f64_globals_use_distinct_encoding_paths():
    """_emit_globals() has a dedicated branch for f32 globals (pack as a
    4-byte float, store in the low half of the qword slot) distinct from
    the f64/int branches -- both are exercised together here since a
    single .fire const declaration test only ever reaches one type at a
    time."""
    module = FLIRModule("test")
    module.globals.append(("SCALE", F32, "1.5"))
    module.globals.append(("RATIO", F64, "2.5"))
    module.globals.append(("COUNT", I32, "42"))
    func = FLIRFunction("fs_main", return_type=VOID)
    module.add_function(func)
    block = func.new_block()
    block.add(Ret())
    asm = FLIRToAsmBackend(module).generate()
    t.require("fsg_SCALE:" in asm, asm)
    t.require("fsg_RATIO:" in asm, asm)
    t.require("fsg_COUNT:" in asm, asm)
    t.require("    .quad 42" in asm, asm)


def test_emit_inst_rejects_unknown_instruction_opcode():
    """_emit_inst()'s final `raise AsmError(...)` is a catch-all for an
    FInst subclass with no matching `isinstance` branch -- every real
    opcode flir/lowering.py can produce is handled, so this is purely
    defensive. Exercised directly with a throwaway FInst subclass."""

    class _BogusInst(FInst):
        opcode = "bogus"

        def format(self, resolve):
            return "bogus"

    module = FLIRModule("test")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    block = func.new_block()
    block.instructions.append(_BogusInst())
    block.instructions.append(Ret())
    try:
        FLIRToAsmBackend(module).generate()
        t.require(False, "expected AsmError")
    except AsmError as e:
        t.require("bogus" in str(e), str(e))


def test_emit_binop_rejects_unsupported_float_op():
    """_emit_binop()'s float path only supports add/sub/mul/div and the
    comparison ops; BinOp's `op` string isn't validated by the FLIR
    verifier, so an unsupported op (e.g. "xor" on floats, meaningless for
    IEEE floats) reaches the `raise AsmError(f"float binop {op}")`
    fallback."""
    module = FLIRModule("test")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    block = func.new_block()
    a = block.add(ConstFloat("1.0", F32))
    b = block.add(ConstFloat("2.0", F32))
    block.instructions.append(BinOp("xor", F32, a, b, F32))
    block.add(Ret())
    try:
        FLIRToAsmBackend(module).generate()
        t.require(False, "expected AsmError")
    except AsmError as e:
        t.require("float binop" in str(e), str(e))


def test_emit_binop_rejects_unsupported_int_op():
    """Same as above for the integer path: an op outside add/sub/mul/
    div/mod/and/or/the comparison set reaches the `raise AsmError(f"int
    binop {op}")` fallback."""
    module = FLIRModule("test")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    block = func.new_block()
    a = block.add(ConstInt("1", I32))
    b = block.add(ConstInt("2", I32))
    block.instructions.append(BinOp("xor", I32, a, b, I32))
    block.add(Ret())
    try:
        FLIRToAsmBackend(module).generate()
        t.require(False, "expected AsmError")
    except AsmError as e:
        t.require("int binop" in str(e), str(e))


def test_stack_spilled_parameters_beyond_fourth():
    """_emit_function()'s parameter-spill loop has a >4-index branch
    (reads the 5th+ incoming argument from its Win64 stack slot at
    `[rbp + 16 + arg_index*8]` instead of an argument register) for both
    the integer and float parameter cases -- a free function with 5+
    parameters is straightforward via .fire source and is covered
    end-to-end elsewhere for the integer case; this isolates the *float*
    5th-parameter spill path directly, which is harder to force
    (mixed int/float parameter lists still consume only 4 total
    registers in this backend's simplified Win64-like convention)."""
    module = FLIRModule("test")
    params = [(f"p{i}", I32) for i in range(4)] + [("p4", F64)]
    func = FLIRFunction("many_params", params=params, return_type=VOID)
    module.add_function(func)
    block = func.new_block()
    block.add(Ret())
    asm = FLIRToAsmBackend(module).generate()
    # The 5th parameter (index 4, a float) must be read from its incoming
    # stack slot rather than a register.
    t.require("qword ptr [rbp + 48]" in asm, asm)

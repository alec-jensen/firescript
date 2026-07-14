"""Coverage-focused unit tests for firescript/codegen/x86_64/flir_to_asm.py.

FLIR modules are built directly from flir.ir objects (there is no
FLIRBuilder helper), following tests/python/flir/test_verifier_heap.py's
pattern. FLIRToAsmBackend.generate() is driven directly -- these tests
never invoke the assembler, so they can exercise codegen paths (e.g. the
uint64<->float conversions) that are known to fail *assembly* later in the
pipeline (see docs/internal/development/ and tests/sources/known_issues/)
without hitting that unrelated, already-documented bug.
"""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from flir.ir import (  # noqa: E402
    BOOL,
    BinOp,
    Call,
    ConstBool,
    ConstFloat,
    ConstInt,
    Cvt,
    F32,
    F64,
    FInst,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    I64,
    I8,
    PTR,
    Ret,
    SlotAddr,
    SlotDecl,
    SlotLoad,
    SlotStore,
    Store,
    Load,
    U32,
    U64,
    U8,
    VOID,
    ptr_to,
    struct_type,
)
from codegen.x86_64.flir_to_asm import AsmError, FLIRToAsmBackend  # noqa: E402


def _module_with_struct(struct_name="S", field_type=I64):
    module = FLIRModule("firescript")
    s = FLIRStruct(struct_name)
    module.add_struct(s)
    s.add_field("x", field_type, module)
    s.finalize()
    return module


# -- _escape_asciz: every branch of the escape-mapping loop -----------------

def test_escape_asciz_known_escapes():
    out = FLIRToAsmBackend._escape_asciz("a\\nb\\tc\\rd\\0e")
    t.require("\\n" in out and "\\t" in out and "\\r" in out and "\\0" in out, out)


def test_escape_asciz_escaped_backslash():
    out = FLIRToAsmBackend._escape_asciz("a\\\\b")
    t.require(out == "a\\\\b", out)


def test_escape_asciz_escaped_quote():
    out = FLIRToAsmBackend._escape_asciz('a\\"b')
    t.require(out == 'a\\"b', out)


def test_escape_asciz_escaped_apostrophe():
    out = FLIRToAsmBackend._escape_asciz("a\\'b")
    t.require(out == "a'b", out)


def test_escape_asciz_unknown_escape():
    out = FLIRToAsmBackend._escape_asciz("a\\qb")
    t.require(out == "a\\\\qb", out)


def test_escape_asciz_trailing_backslash():
    out = FLIRToAsmBackend._escape_asciz("a\\")
    t.require(out == "a\\\\", out)


def test_escape_asciz_literal_quote_and_control_char():
    out = FLIRToAsmBackend._escape_asciz('a"b\x01c')
    t.require(out == 'a\\"b\\001c', out)


def test_escape_asciz_plain_text():
    out = FLIRToAsmBackend._escape_asciz("plain")
    t.require(out == "plain", out)


# -- globals: float128 and f32 module-level constants ------------------------

def test_emit_globals_f128_and_f32():
    module = FLIRModule("firescript")
    from flir.ir import F128
    module.globals.append(("g128", F128, "1.5"))
    module.globals.append(("g32", F32, "2.5"))
    backend = FLIRToAsmBackend(module)
    asm = backend.generate()
    t.require("fsg_g128" in asm, asm)
    t.require("fsg_g32" in asm, asm)


# -- function frame: struct/float params spilled from the stack (5th+ arg) --

def test_struct_param_via_stack():
    module = _module_with_struct("S", I64)
    func = FLIRFunction(
        "f",
        params=[("a0", I64), ("a1", I64), ("a2", I64), ("a3", I64), ("a4", struct_type("S"))],
        return_type=VOID,
    )
    module.add_function(func)
    entry = func.new_block()
    entry.add(Ret())
    asm = FLIRToAsmBackend(module).generate()
    t.require("fsf_f:" in asm, asm)


def test_float_param_via_stack():
    module = FLIRModule("firescript")
    func = FLIRFunction(
        "g",
        params=[("a0", I64), ("a1", I64), ("a2", I64), ("a3", I64), ("a4", F64)],
        return_type=VOID,
    )
    module.add_function(func)
    entry = func.new_block()
    entry.add(Ret())
    asm = FLIRToAsmBackend(module).generate()
    t.require("fsf_g:" in asm, asm)


# -- dangling-value defensive branch: _val_off raises when a value's owning
# instruction was never assigned a frame slot (malformed FLIR: operand
# references an instruction that isn't part of any block in the function) --

def test_val_off_missing_slot_raises():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    dangling = ConstInt("1", I64)  # never added to any block
    entry.add(Ret(dangling.result()))
    try:
        FLIRToAsmBackend(module).generate()
        t.require(False, "expected AsmError")
    except AsmError:
        pass


# -- unhandled instruction opcode fallback -----------------------------------

class _BogusInst(FInst):
    opcode = "bogus"


def test_unhandled_instruction_raises():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    entry.instructions.append(_BogusInst())
    try:
        FLIRToAsmBackend(module).generate()
        t.require(False, "expected AsmError")
    except AsmError:
        pass


# -- binop defensive branches: unsupported float op / unsupported int op ----

def test_binop_unsupported_float_op_raises():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    lhs = entry.add(ConstFloat("1.0", F64))
    rhs = entry.add(ConstFloat("2.0", F64))
    entry.add(BinOp("mod", F64, lhs, rhs, F64))
    entry.add(Ret())
    try:
        FLIRToAsmBackend(module).generate()
        t.require(False, "expected AsmError")
    except AsmError:
        pass


def test_binop_unsupported_int_op_raises():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    lhs = entry.add(ConstInt("1", I64))
    rhs = entry.add(ConstInt("2", I64))
    entry.add(BinOp("pow", I64, lhs, rhs, I64))
    entry.add(Ret())
    try:
        FLIRToAsmBackend(module).generate()
        t.require(False, "expected AsmError")
    except AsmError:
        pass


def test_binop_int_and_or():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=I64)
    module.add_function(func)
    entry = func.new_block()
    lhs = entry.add(ConstInt("1", I64))
    rhs = entry.add(ConstInt("2", I64))
    r1 = entry.add(BinOp("and", I64, lhs, rhs, I64))
    r2 = entry.add(BinOp("or", I64, lhs, r1, I64))
    entry.add(Ret(r2))
    asm = FLIRToAsmBackend(module).generate()
    t.require("and rax, rcx" in asm, asm)
    t.require("or rax, rcx" in asm, asm)


# -- conversions: int->bool, u64<->float, narrow float->int -----------------

def test_cvt_int_to_bool():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=BOOL)
    module.add_function(func)
    entry = func.new_block()
    v = entry.add(ConstInt("5", I64))
    r = entry.add(Cvt(v, I64, BOOL))
    entry.add(Ret(r))
    asm = FLIRToAsmBackend(module).generate()
    t.require("setne al" in asm, asm)


def test_cvt_u64_to_f64():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=F64)
    module.add_function(func)
    entry = func.new_block()
    v = entry.add(ConstInt("5", U64))
    r = entry.add(Cvt(v, U64, F64))
    entry.add(Ret(r))
    asm = FLIRToAsmBackend(module).generate()
    t.require("cvtsi2sd" in asm, asm)


def test_cvt_f64_to_u64():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=U64)
    module.add_function(func)
    entry = func.new_block()
    v = entry.add(ConstFloat("5.0", F64))
    r = entry.add(Cvt(v, F64, U64))
    entry.add(Ret(r))
    asm = FLIRToAsmBackend(module).generate()
    t.require("cvttsd2si" in asm, asm)


def test_cvt_f32_to_u64():
    """f32 -> u64 needs an extra cvtss2sd widening step before the >= 2^63
    subtract trick (f64 -> u64, exercised above, skips it)."""
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=U64)
    module.add_function(func)
    entry = func.new_block()
    v = entry.add(ConstFloat("5.0", F32))
    r = entry.add(Cvt(v, F32, U64))
    entry.add(Ret(r))
    asm = FLIRToAsmBackend(module).generate()
    t.require("cvtss2sd xmm0, xmm0" in asm, asm)


def test_cvt_float_to_narrow_int_kinds():
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    v = entry.add(ConstFloat("5.0", F64))
    entry.add(Cvt(v, F64, I8))
    entry.add(Cvt(v, F64, U8))
    entry.add(Cvt(v, F64, U32))
    entry.add(Ret())
    asm = FLIRToAsmBackend(module).generate()
    t.require("movsx rax" in asm, asm)
    t.require("movzx eax" in asm, asm)
    t.require("mov eax, eax" in asm, asm)


def test_cvt_struct_to_ptr_bitcast_fallback():
    """Not a conversion the real lowering pass ever emits -- struct/void
    source or destination kinds fall through every typed branch in
    _emit_cvt to the final ptr/int-bitcast fallback. Constructed directly
    to exercise that defensive fallback."""
    module = _module_with_struct("S", I64)
    func = FLIRFunction("f", return_type=PTR)
    module.add_function(func)
    entry = func.new_block()
    entry.add(SlotDecl("s", struct_type("S")))
    sv = entry.add(SlotLoad("s", struct_type("S")))
    r = entry.add(Cvt(sv, struct_type("S"), PTR))
    entry.add(Ret(r))
    asm = FLIRToAsmBackend(module).generate()
    t.require("fsf_f:" in asm, asm)


# -- memory: Load/Store of a struct-typed value at an offset ----------------

def test_load_struct_value():
    module = _module_with_struct("S", I64)
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    entry.add(SlotDecl("p", ptr_to("S")))
    base = entry.add(SlotLoad("p", ptr_to("S")))
    entry.add(Load(struct_type("S"), base, 0))
    entry.add(Ret())
    asm = FLIRToAsmBackend(module).generate()
    t.require("fsf_f:" in asm, asm)


def test_store_struct_value():
    module = _module_with_struct("S", I64)
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    entry.add(SlotDecl("p", ptr_to("S")))
    entry.add(SlotDecl("s", struct_type("S")))
    base = entry.add(SlotLoad("p", ptr_to("S")))
    val = entry.add(SlotLoad("s", struct_type("S")))
    entry.add(Store(struct_type("S"), base, 0, val))
    entry.add(Ret())
    asm = FLIRToAsmBackend(module).generate()
    t.require("fsf_f:" in asm, asm)


# -- calls: extern float arg (also loaded into the matching int register)
# and a struct argument passed on the stack (5th+ positional argument) -----

def test_call_extern_float_arg():
    module = FLIRModule("firescript")
    module.externs["ExternFn"] = ("kernel32.dll", VOID, [F64])
    func = FLIRFunction("f", return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    v = entry.add(ConstFloat("1.0", F64))
    entry.add(Call("ExternFn", [v], VOID))
    entry.add(Ret())
    asm = FLIRToAsmBackend(module).generate()
    t.require("movsd xmm0" in asm, asm)
    t.require("call ExternFn" in asm, asm)


def test_call_struct_arg_on_stack():
    module = _module_with_struct("S", I64)
    func = FLIRFunction("callee", params=[(f"p{i}", I64) for i in range(4)] + [("p4", struct_type("S"))],
                         return_type=VOID)
    module.add_function(func)
    entry = func.new_block()
    entry.add(Ret())

    caller = FLIRFunction("caller", return_type=VOID)
    module.add_function(caller)
    cb = caller.new_block()
    ints = [cb.add(ConstInt(str(i), I64)) for i in range(4)]
    cb.add(SlotDecl("s", struct_type("S")))
    sv = cb.add(SlotLoad("s", struct_type("S")))
    cb.add(Call("callee", ints + [sv], VOID))
    cb.add(Ret())

    asm = FLIRToAsmBackend(module).generate()
    t.require("fsf_caller:" in asm, asm)
    t.require("lea rax, [rbp" in asm, asm)

"""Unit tests for firescript/codegen/x86_64/flir_to_asm.py's emitted assembly
text for conversions, struct values, stack-passed arguments and the
`_escape_asciz` helper.

FLIR modules are built directly from flir.ir objects (there is no
FLIRBuilder helper), following tests/python/flir/test_verifier_heap.py's
pattern. FLIRToAsmBackend.generate() is driven directly -- these tests
never invoke the assembler, so they assert the generated instruction
sequences, not that the result assembles or runs. (Note: the uint64 -> float
sequence uses `js`/`shr`, which the in-tree assembler does not encode yet, so
a `uint64 as float64` .fire program currently fails at assembly.)
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
    ConstFloat,
    ConstInt,
    Cvt,
    F32,
    F64,
    FLIRFunction,
    FLIRModule,
    FLIRStruct,
    I64,
    I8,
    Ret,
    SlotDecl,
    SlotLoad,
    Store,
    Load,
    U32,
    U64,
    U8,
    VOID,
    ptr_to,
    struct_type,
)
from codegen.x86_64.flir_to_asm import FLIRToAsmBackend  # noqa: E402


def _module_with_struct(struct_name="S", field_type=I64):
    module = FLIRModule("firescript")
    s = FLIRStruct(struct_name)
    module.add_struct(s)
    s.add_field("x", field_type, module)
    s.finalize()
    return module


def _body(asm: str, name: str) -> list[str]:
    """The instruction lines of function `name` (labels and blanks dropped,
    leading whitespace stripped), prologue included."""
    lines = asm.split("\n")
    start = lines.index(f"fsf_{name}:")
    out = []
    for ln in lines[start + 1:]:
        if ln.startswith(".globl") or ln.startswith(".section"):
            break
        ln = ln.strip()
        if not ln or (ln.endswith(":") and not ln.startswith("mov")):
            continue
        out.append(ln)
    return out


def _require_sequence(body: list[str], expected: list[str]) -> None:
    """`expected` must appear in `body` as one consecutive run of instructions."""
    n = len(expected)
    t.require(
        any(body[i:i + n] == expected for i in range(len(body) - n + 1)),
        f"expected consecutive instructions {expected} in:\n" + "\n".join(body),
    )


def _single_function_asm(return_type, build) -> list[str]:
    module = FLIRModule("firescript")
    func = FLIRFunction("f", return_type=return_type)
    module.add_function(func)
    build(func.new_block())
    return _body(FLIRToAsmBackend(module).generate(), "f")


# -- _escape_asciz: every branch of the escape-mapping loop -----------------

@t.params([
    ("a\\nb\\tc\\rd\\0e", "a\\nb\\tc\\rd\\0e"),    # known escapes pass through
    ("a\\\\b", "a\\\\b"),                          # escaped backslash
    ('a\\"b', 'a\\"b'),                            # escaped double quote
    ("a\\'b", "a'b"),                              # escaped apostrophe
    ("a\\qb", "a\\\\qb"),                          # unknown escape: backslash is escaped
    ("a\\", "a\\\\"),                              # trailing backslash
    ('a"b\x01c', 'a\\"b\\001c'),                   # literal quote and control char
    ("plain", "plain"),
])
def test_escape_asciz(case):
    source, expected = case
    t.require_eq(FLIRToAsmBackend._escape_asciz(source), expected)


# -- function frame: struct params spilled from the stack (5th+ arg) --------

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
    body = _body(FLIRToAsmBackend(module).generate(), "f")
    # The 5th argument arrives in its Win64 stack slot, [rbp + 16 + 4*8].
    _require_sequence(body, ["mov r10, qword ptr [rbp + 48]", "mov rax, qword ptr [r10 + 0]"])


# -- binops -------------------------------------------------------------------

def test_binop_int_and_or():
    def build(b):
        lhs = b.add(ConstInt("1", I64))
        rhs = b.add(ConstInt("2", I64))
        r1 = b.add(BinOp("and", I64, lhs, rhs, I64))
        r2 = b.add(BinOp("or", I64, lhs, r1, I64))
        b.add(Ret(r2))

    body = _single_function_asm(I64, build)
    t.require("and rax, rcx" in body, str(body))
    t.require("or rax, rcx" in body, str(body))


# -- conversions: int->bool, u64<->float, narrow float->int -----------------

def test_cvt_int_to_bool():
    def build(b):
        v = b.add(ConstInt("5", I64))
        b.add(Ret(b.add(Cvt(v, I64, BOOL))))

    _require_sequence(_single_function_asm(BOOL, build), ["test rax, rax", "setne al", "movzx eax, al"])


@t.params([
    # IEEE 754: comparisons involving a NaN (unordered: ZF=PF=CF=1) are false
    # except `!=`. lt/le swap operands so CF-based seta/setae are false when
    # unordered; eq/ne additionally fold in the parity flag (regression B01).
    ("eq", "sd", ["comisd xmm0, xmm1", "sete al", "setnp cl", "and eax, ecx", "movzx eax, al"]),
    ("ne", "sd", ["comisd xmm0, xmm1", "setne al", "setp cl", "or eax, ecx", "movzx eax, al"]),
    ("lt", "sd", ["comisd xmm1, xmm0", "seta al", "movzx eax, al"]),
    ("le", "sd", ["comisd xmm1, xmm0", "setae al", "movzx eax, al"]),
    ("gt", "sd", ["comisd xmm0, xmm1", "seta al", "movzx eax, al"]),
    ("ge", "sd", ["comisd xmm0, xmm1", "setae al", "movzx eax, al"]),
    ("eq", "ss", ["comiss xmm0, xmm1", "sete al", "setnp cl", "and eax, ecx", "movzx eax, al"]),
    ("lt", "ss", ["comiss xmm1, xmm0", "seta al", "movzx eax, al"]),
])
def test_float_compare_handles_unordered(case):
    op, suffix, expected = case
    ftype = F32 if suffix == "ss" else F64

    def build(b):
        a = b.add(ConstFloat("1.0", ftype))
        c = b.add(ConstFloat("2.0", ftype))
        b.add(Ret(b.add(BinOp(op, ftype, a, c, BOOL))))

    _require_sequence(_single_function_asm(BOOL, build), expected)


def test_cvt_u64_to_f64():
    def build(b):
        v = b.add(ConstInt("5", U64))
        b.add(Ret(b.add(Cvt(v, U64, F64))))

    # Values below 2^63 convert directly; at or above 2^63 the value is
    # halved with its low bit OR-ed back in (the sticky bit, so rounding
    # stays correct), converted, then doubled.
    _require_sequence(_single_function_asm(F64, build), [
        "test rax, rax",
        "js .Lu2f0",
        "cvtsi2sd xmm0, rax",
        "jmp .Lu2fd0",
        "mov rcx, rax",
        "shr rax, 1",
        "and rcx, 1",
        "or rax, rcx",
        "cvtsi2sd xmm0, rax",
        "addsd xmm0, xmm0",
    ])


def test_cvt_f64_to_u64():
    def build(b):
        v = b.add(ConstFloat("5.0", F64))
        b.add(Ret(b.add(Cvt(v, F64, U64))))

    # Compare against 2^63 (0x43E0000000000000); at or above it, subtract
    # 2^63, truncate, and flip the top bit back in.
    _require_sequence(_single_function_asm(U64, build), [
        "mov rax, 4890909195324358656",
        "movq xmm1, rax",
        "comisd xmm0, xmm1",
        "jae .Lf2u0",
        "cvttsd2si rax, xmm0",
        "jmp .Lf2ud0",
        "subsd xmm0, xmm1",
        "cvttsd2si rax, xmm0",
        "mov rcx, -9223372036854775808",
        "xor rax, rcx",
    ])


def test_cvt_f32_to_u64():
    """f32 -> u64 needs an extra cvtss2sd widening step before the >= 2^63
    subtract trick (f64 -> u64, exercised above, skips it)."""
    def build(b):
        v = b.add(ConstFloat("5.0", F32))
        b.add(Ret(b.add(Cvt(v, F32, U64))))

    body = _single_function_asm(U64, build)
    t.require("cvtss2sd xmm0, xmm0" in body, str(body))


def test_cvt_float_to_narrow_int_kinds():
    def build(b):
        v = b.add(ConstFloat("5.0", F64))
        b.add(Cvt(v, F64, I8))
        b.add(Cvt(v, F64, U8))
        b.add(Cvt(v, F64, U32))
        b.add(Ret())

    body = _single_function_asm(VOID, build)
    # Each conversion truncates to 64 bits, then narrows with the extension
    # matching the target: sign-extend i8, zero-extend u8, zero-extend u32.
    for narrow in ("movsx rax, al", "movzx eax, al", "mov eax, eax"):
        _require_sequence(body, ["cvttsd2si rax, xmm0", narrow, "mov qword ptr [rbp-%d], rax" % {
            "movsx rax, al": 16, "movzx eax, al": 24, "mov eax, eax": 32}[narrow]])


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
    # The struct is copied by value, qword by qword, from [base+0] into the
    # result's frame slot.
    _require_sequence(_body(FLIRToAsmBackend(module).generate(), "f"), [
        "lea r10, [rcx + 0]",
        "lea r11, [rbp-24]",
        "mov rax, qword ptr [r10 + 0]",
        "mov qword ptr [r11 + 0], rax",
    ])


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
    # ... and stored by value into [base+0] from the value's frame slot.
    _require_sequence(_body(FLIRToAsmBackend(module).generate(), "f"), [
        "lea r10, [rbp-32]",
        "lea r11, [rcx + 0]",
        "mov rax, qword ptr [r10 + 0]",
        "mov qword ptr [r11 + 0], rax",
    ])


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
    # The first float argument goes in xmm0 AND is mirrored into rcx.
    _require_sequence(_body(FLIRToAsmBackend(module).generate(), "f"), [
        "movsd xmm0, qword ptr [rbp-8]",
        "mov rcx, qword ptr [rbp-8]",
        "call ExternFn",
    ])


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

    # The struct (5th argument) is passed by address in the first stack
    # argument slot above the 32-byte shadow space.
    _require_sequence(_body(FLIRToAsmBackend(module).generate(), "caller"), [
        "lea rax, [rbp-48]",
        "mov qword ptr [rsp + 32], rax",
        "call fsf_callee",
    ])

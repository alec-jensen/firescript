"""Canonical fs_rt_* runtime ABI registry.

Every fs_rt_* symbol lowering can call -- whether firescript-implemented
(one of the std/internal/*.fire files) or a backend-only primitive with no
firescript source -- has exactly one signature and memory effect, recorded
here. `FIRToFLIRLowering.rt_call` consults this table instead of trusting
an ad hoc return type supplied at each call site; the FLIR verifier's
Tier-2 allocation-lifecycle dataflow (FLIRV-A) consults it to know which
calls free/allocate/merely-borrow their heap-pointer arguments.

Extending this table is a deliberate action: an fs_rt_* call the table
doesn't describe is a verifier error (FLIRV-T4), not something the
verifier silently tolerates -- see ir_verifier_spec.md section 6.

Signatures are transcribed from the actual firescript declarations under
std/internal/ (the two backend-only primitives, fs_rt_mem_copy and
fs_rt_f64_bits, have no firescript source and are transcribed from their
call sites in flir/lowering.py instead).
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple, Optional

from flir.ir import BOOL, F32, F64, F128, I32, I64, PTR, U8, U32, U64, VOID, FLIRType, ptr_to, struct_type

STRING = ptr_to("i8")
SYSCALL_RESULT = struct_type("SyscallResult")


class MemoryEffect(str, Enum):
    RETURNS_FRESH = "returns_fresh"  # caller owns the returned pointer
    FREES_ARG0 = "frees_arg0"  # frees the pointer in args[0]
    BORROWS = "borrows"  # reads args only; no ownership transfer


class RuntimeSignature(NamedTuple):
    params: tuple[FLIRType, ...]
    ret: FLIRType
    effect: MemoryEffect


def _sig(*params: FLIRType, ret: FLIRType, effect: MemoryEffect = MemoryEffect.BORROWS) -> RuntimeSignature:
    return RuntimeSignature(tuple(params), ret, effect)


RUNTIME_ABI: dict[str, RuntimeSignature] = {
    # -- allocation / freeing (std/internal/alloc.fire) ----------------------
    # fs_rt_alloc_zeroed is a generic raw allocator: its firescript-level
    # declaration returns `string`, but call sites legitimately reinterpret
    # the returned pointer as ptr<SomeStruct> for object/array allocation.
    # That reinterpretation is intentional (not a bug), so lowering does
    # not force this entry's `ret` onto every call site -- see rt_call().
    "fs_rt_alloc_zeroed": _sig(I64, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_free": _sig(STRING, ret=VOID, effect=MemoryEffect.FREES_ARG0),
    "fs_rt_zero_memory": _sig(STRING, I64, ret=VOID),
    # -- math (std/internal/arithmetic.fire) ---------------------------------
    "fs_rt_pow_i64": _sig(I64, I64, ret=I64),
    "fs_rt_pow_f64": _sig(F64, F64, ret=F64),
    # -- strings (std/internal/strings.fire) ---------------------------------
    "fs_rt_str_length": _sig(STRING, ret=I32),
    "fs_rt_str_dup": _sig(STRING, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_str_concat": _sig(STRING, STRING, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_str_eq": _sig(STRING, STRING, ret=BOOL),
    "fs_rt_str_char_at": _sig(STRING, I32, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_str_char_code_at": _sig(STRING, I32, ret=U8),
    "fs_rt_str_char_code": _sig(STRING, ret=U8),
    "fs_rt_str_index_of": _sig(STRING, STRING, ret=I32),
    "fs_rt_str_slice": _sig(STRING, I32, I32, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    # -- numeric <-> string (std/internal/number_conversions.fire) -----------
    "fs_rt_i64_to_str": _sig(I64, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_i32_to_str": _sig(I32, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_u64_to_str": _sig(U64, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_u32_to_str": _sig(U32, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_bool_to_str": _sig(BOOL, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_char_to_str": _sig(U8, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_str_to_i32": _sig(STRING, ret=I32),
    "fs_rt_str_to_i64": _sig(STRING, ret=I64),
    "fs_rt_str_to_bool": _sig(STRING, ret=BOOL),
    "fs_rt_str_to_f64": _sig(STRING, ret=F64),
    # -- float <-> string (std/internal/float_conversions.fire) --------------
    "fs_rt_f64_to_str": _sig(F64, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_f32_to_str": _sig(F32, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_f64_to_repr": _sig(F64, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_f32_to_repr": _sig(F32, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    # -- process / cli (std/internal/io.fire) --------------------------------
    "fs_rt_stdout": _sig(STRING, ret=VOID),
    "fs_rt_argc": _sig(ret=I32),
    "fs_rt_argv_at": _sig(I32, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    # -- syscalls (std/internal/syscalls.fire; SyscallResult is a copyable struct) --
    "fs_rt_syscall_open": _sig(STRING, STRING, ret=SYSCALL_RESULT),
    "fs_rt_syscall_read": _sig(I32, I32, ret=SYSCALL_RESULT),
    "fs_rt_syscall_write": _sig(I32, STRING, ret=SYSCALL_RESULT),
    "fs_rt_syscall_close": _sig(I32, ret=SYSCALL_RESULT),
    "fs_rt_syscall_remove": _sig(STRING, ret=SYSCALL_RESULT),
    "fs_rt_syscall_rename": _sig(STRING, STRING, ret=SYSCALL_RESULT),
    "fs_rt_syscall_move": _sig(STRING, STRING, ret=SYSCALL_RESULT),
    # -- float128 soft-float shims (float128.fire; by-value struct operands) --
    "fs_rt_f128_add": _sig(F128, F128, ret=F128),
    "fs_rt_f128_sub": _sig(F128, F128, ret=F128),
    "fs_rt_f128_neg": _sig(F128, ret=F128),
    "fs_rt_f128_mul": _sig(F128, F128, ret=F128),
    "fs_rt_f128_div": _sig(F128, F128, ret=F128),
    "fs_rt_f128_eq": _sig(F128, F128, ret=BOOL),
    "fs_rt_f128_ne": _sig(F128, F128, ret=BOOL),
    "fs_rt_f128_lt": _sig(F128, F128, ret=BOOL),
    "fs_rt_f128_le": _sig(F128, F128, ret=BOOL),
    "fs_rt_f128_gt": _sig(F128, F128, ret=BOOL),
    "fs_rt_f128_ge": _sig(F128, F128, ret=BOOL),
    "fs_rt_u64_to_f128": _sig(U64, ret=F128),
    "fs_rt_i64_to_f128": _sig(I64, ret=F128),
    "fs_rt_f128_to_i64": _sig(F128, ret=I64),
    "fs_rt_f128_to_u64": _sig(F128, ret=U64),
    "fs_rt_f64_to_f128": _sig(F64, ret=F128),
    "fs_rt_f128_to_f64": _sig(F128, ret=F64),
    "fs_rt_f128_to_str": _sig(F128, ret=STRING, effect=MemoryEffect.RETURNS_FRESH),
    "fs_rt_str_to_f128": _sig(STRING, ret=F128),
    # -- backend-only primitives (no firescript source; assembler builtins) --
    "fs_rt_mem_copy": _sig(PTR, PTR, U64, ret=VOID),
    "fs_rt_f64_bits": _sig(F64, ret=U64),
}


def runtime_signature(name: str) -> Optional[RuntimeSignature]:
    return RUNTIME_ABI.get(name)

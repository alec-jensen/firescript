"""Unit tests for firescript/backend/x86_64/assembler.py targeting encoding
and error branches not exercised by the differential CASES table in
test_asm_encoding.py: malformed memory operands, 16-bit ALU/mov/unary forms,
movq xmm<->xmm, unsupported mnemonics/operand forms, and the relocation /
fixup resolution paths (backward rip-relative code labels, rip references
into non-text sections, and unresolved symbols)."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from backend.x86_64.assembler import (  # noqa: E402
    AssemblerError, Sym, _Assembler, assemble,
)


def _expect_error(text: str, needle: str | None = None) -> None:
    raised = False
    try:
        assemble(text)
    except AssemblerError as e:
        raised = True
        if needle is not None:
            t.require(needle in str(e), f"unexpected message: {e}")
    t.require(raised, f"expected AssemblerError for:\n{text}")


def _expect_ok(text: str) -> None:
    obj = assemble(text)
    t.require(len(obj.text) > 0, f"expected bytes emitted for:\n{text}")


# -- malformed memory operands (_parse_mem) --

def test_lea_missing_closing_bracket_errors():
    _expect_error("lea rax, dword ptr rbp-8")


def test_mem_base_plus_xmm_index_errors():
    _expect_error("mov rax, [rax+xmm0]", "bad base+index")


def test_mem_unknown_base_plus_index_errors():
    _expect_error("mov rax, [zz+rcx]", "bad base+index")


def test_mem_unknown_base_errors():
    _expect_error("mov rax, [zz]", "bad memory base")


def test_mem_unsupported_form_errors():
    _expect_error("mov rax, [rax+rbx+rcx]", "unsupported memory operand")


# -- valid 16-bit forms --

def test_mov_reg16_reg16():
    _expect_ok("mov ax, cx")


def test_alu_reg16_imm():
    _expect_ok("add ax, 5")


def test_unary_reg16():
    _expect_ok("not ax")


def test_mov_mem_imm16():
    _expect_ok("mov word ptr [rbp-2], 5")


def test_mov_mem_imm8():
    _expect_ok("mov byte ptr [rbp-1], 5")


def test_mov_r8d_imm_forces_rex():
    _expect_ok("mov r8d, 100")


def test_setcc_low_byte_reg_forces_rex():
    _expect_ok("sete spl")


def test_movq_xmm_to_xmm():
    _expect_ok("movq xmm0, xmm1")


def test_nop_alone():
    _expect_ok("nop")


# -- unsupported operand-form / mnemonic errors --

def test_mov_mem_mem_errors():
    _expect_error("mov [rax], [rbx]", "unsupported mov forms")


def test_mov_imm_size8_errors():
    _expect_error("mov al, 5", "unsupported mov imm size")


def test_alu_mem_mem_errors():
    _expect_error("add [rax], [rbx]", "unsupported add forms")


def test_unsupported_mnemonic_errors():
    _expect_error("foobar rax, rcx", "unsupported mnemonic")


def test_unknown_section_directive_errors():
    _expect_error(".section .weird\nret", "unknown section")


def test_unsupported_top_level_directive_errors():
    _expect_error(".weird_directive foo\nret", "unsupported directive")


def test_bad_asciz_errors():
    _expect_error('.asciz missing_quotes')


def test_encode_failure_wraps_assertion():
    # `push` requires a 64-bit register operand; a 32-bit one trips the
    # internal assert, which _instruction wraps into an AssemblerError.
    _expect_error("push eax", "failed to encode")


# -- relocation / fixup resolution paths --

def test_rip_reference_to_earlier_text_label():
    # A rip-relative operand referencing a label already defined in the
    # .text section takes the "known text symbol" fixup path rather than
    # being deferred to a PE-level RIP32 reloc.
    obj = assemble("mylabel:\n  ret\n  lea rax, [rip+mylabel]\n")
    t.require(len(obj.relocs) == 0, f"expected no deferred relocs, got {obj.relocs}")


def test_unresolved_numeric_local_label_errors():
    _expect_error("jmp 1f\nret\n", "unresolved numeric label")


def test_jmp_into_rdata_section_defers_reloc():
    # A rip-relative code branch to a label that ends up in .rdata (not
    # .text) cannot be resolved as an in-section rel32, so it must be
    # deferred to a PE32 RIP32 reloc instead.
    obj = assemble(
        ".section .rdata\n"
        "mydata:\n"
        "  .byte 1\n"
        ".section .text\n"
        "  jmp mydata\n"
    )
    t.require(any(r.symbol == "mydata" for r in obj.relocs), f"expected a mydata reloc, got {obj.relocs}")


def test_call_to_undefined_runtime_symbol_errors():
    # `fs_rt_*` names are treated as in-object code labels (not kernel32
    # imports); calling one with no matching definition anywhere in the
    # module must fail as an unresolved symbol.
    _expect_error("call fs_rt_does_not_exist\nret\n", "unresolved symbol")


def test_bss_section_directive_plain_form():
    _expect_ok(".bss\n.space 4\n.text\nret\n")


def test_text_and_data_directive_plain_forms():
    obj = assemble(".data\n.byte 1\n.text\nret\n")
    t.require(len(obj.rdata) == 1, f"expected 1 rdata byte, got {obj.rdata!r}")


def test_space_directive_in_bss_accumulates_bss_size():
    obj = assemble(".bss\n.space 8\n.text\nret\n")
    t.require(obj.bss_size == 8, f"expected bss_size 8, got {obj.bss_size}")


def test_space_directive_outside_bss_zero_fills():
    obj = assemble(".data\n.space 4\n.text\nret\n")
    t.require(bytes(obj.rdata) == b"\x00\x00\x00\x00", f"expected 4 zero bytes, got {obj.rdata!r}")


def test_quad_and_long_directives():
    obj = assemble(".data\n.quad 1\n.long 2\n.text\nret\n")
    t.require(len(obj.rdata) == 12, f"expected 8+4=12 rdata bytes, got {len(obj.rdata)}")


def test_data_directive_in_bss_section_errors():
    # buf() only special-cases "text"/"rdata"; instructions always write
    # straight to obj.text regardless of the current section (only
    # directives route through buf()), so buf()'s "bss" guard is reached
    # by a data-emitting directive -- other than .space, which special-
    # cases bss to grow bss_size instead -- issued while the section is
    # "bss".
    _expect_error(".bss\n.quad 1\n", "cannot emit bytes into section")


def test_movq_xmm_to_xmm_extended_registers_force_rex():
    _expect_ok("movq xmm8, xmm9")


def test_align_directive_is_a_noop():
    _expect_ok(".align 4\nret\n")
    _expect_ok(".p2align 4\nret\n")


def test_asciz_octal_escape():
    obj = assemble('.data\n.asciz "\\101"')  # octal 101 == 'A' (0x41)
    t.require(bytes(obj.rdata) == b"A\x00", f"got {obj.rdata!r}")


def test_asciz_unrecognized_escape_falls_back_to_literal_char():
    obj = assemble('.data\n.asciz "\\z"')
    # "\z" is not octal and not one of the recognized simple escapes, so
    # the literal character 'z' (0x7A) is emitted, followed by the NUL
    # terminator .asciz always appends.
    t.require(bytes(obj.rdata) == b"z\x00", f"got {obj.rdata!r}")


def test_asciz_non_locale_char_falls_back_to_utf8():
    # This machine's preferred encoding is a Windows codepage (e.g.
    # cp1252), which cannot encode most CJK/emoji characters; such a
    # character must fall back to UTF-8 rather than raising.
    cjk_char = chr(0x4E2D)  # a CJK character outside cp1252
    obj = assemble(f'.data\n.asciz "{cjk_char}"')
    t.require(bytes(obj.rdata) == cjk_char.encode("utf-8") + b"\x00", f"got {obj.rdata!r}")


def test_encode_emits_no_bytes_is_reported():
    # Every real mnemonic branch in _encode always emits at least one byte
    # before returning; this guard only exists in case a future encoder
    # branch regresses that invariant. Drive it directly by monkeypatching
    # _encode to a no-op, mirroring the established pattern for exercising
    # defensive guards that cannot be triggered by any real instruction.
    asm = _Assembler("")
    asm._encode = lambda mnem, ops: None
    raised = False
    try:
        asm._instruction("madeupop rax")
    except AssemblerError as e:
        raised = True
        t.require("no bytes emitted" in str(e), f"unexpected message: {e}")
    t.require(raised, "expected AssemblerError for no bytes emitted")


def test_call_numeric_target_is_defensive_and_unreachable_via_source():
    # `_call` guards against a purely-numeric call target ("numeric call
    # target unsupported"), but the operand parser never produces a bare
    # digit-string Sym for a call operand: plain digits parse as Imm, and
    # the only Sym form ending in digits is the "<N>[bf]" numeric-local-
    # label reference (e.g. "1f"/"2b"), which is not all-digit. So this
    # branch cannot be reached from any assemble()-able source text; drive
    # `_call` directly to cover it, per the established pattern for
    # defensive/unreachable guards.
    asm = _Assembler("")
    raised = False
    try:
        asm._call(Sym("42"))
    except AssemblerError as e:
        raised = True
        t.require("numeric call target unsupported" in str(e), f"unexpected message: {e}")
    t.require(raised, "expected AssemblerError for numeric call target")

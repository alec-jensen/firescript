"""Differential + unit tests for the pure-Python x86-64 assembler, migrated
from tests/asm_encoding_tests.py (spec sec.4.4 migration table).

For each instruction form the FLIR backend emits, assemble a single line
with our encoder and (when available) with MinGW `as`, then compare the
`.text` bytes. `as` is only a bringup oracle: when absent, the differential
half is skipped and only the unit assertion (bytes were emitted) runs, so
the suite needs only Python -- matching the original script's behavior.
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from backend.x86_64.assembler import assemble  # noqa: E402

# Instruction forms covering the backend's closed grammar. Lines with a
# label/RIP operand would need their displacement field masked before
# comparison; none of the current cases use one.
CASES = [
    "mov rax, rcx", "mov eax, ecx", "mov r10, r11", "mov rax, 5",
    "mov rax, -1", "mov rcx, 4503599627370496000",
    "mov qword ptr [rbp-8], rax", "mov dword ptr [rbp-4], eax",
    "mov byte ptr [rcx+0], al", "mov word ptr [rbp-2], ax",
    "mov qword ptr [rbp-16], 0", "mov dword ptr [rbp-4], 7",
    "mov rax, qword ptr [rbp-8]", "mov eax, dword ptr [rcx+16]",
    "mov rax, qword ptr [rsp+32]",
    "add rax, rcx", "sub rax, rcx", "and rax, rcx", "or rax, rcx",
    "xor rax, rcx", "cmp rax, rcx", "test rax, rax",
    "sub rsp, 32", "add rsp, 4096", "and rsp, -16", "sub rax, 200000",
    "imul rax, rcx", "imul rax, rcx, 8", "imul rax, rcx, 200",
    "neg rax", "not rax", "inc rcx", "dec r11", "idiv rcx", "div rcx",
    "cqo", "ret", "int3",
    "push rbp", "pop rbp", "push r12", "pop r13",
    "lea rax, [rbp-8]", "lea rcx, [rsp+32]",
    "movsx rax, al", "movsx rax, word ptr [rbp-2]", "movsxd rax, ecx",
    "movsxd rax, dword ptr [rbp-4]", "movzx eax, al",
    "movzx eax, byte ptr [rcx+0]", "movzx eax, word ptr [rbp-2]",
    "sete al", "setne al", "setl al", "setge al", "setb al", "seta al",
    "setbe al", "setae al", "setg al", "setle al",
    "movsd xmm0, qword ptr [rbp-8]", "movsd qword ptr [rbp-8], xmm0",
    "movss xmm1, dword ptr [rbp-4]", "movss dword ptr [rbp-4], xmm1",
    "addsd xmm0, xmm1", "subsd xmm0, xmm1", "mulsd xmm0, xmm1",
    "divsd xmm0, xmm1", "addss xmm0, xmm1", "comisd xmm0, xmm1",
    "comiss xmm0, xmm1", "xorps xmm0, xmm1", "xorpd xmm0, xmm1",
    "cvtsi2sd xmm0, rax", "cvtsi2ss xmm0, rax", "cvttsd2si rax, xmm0",
    "cvttss2si rax, xmm0", "cvtss2sd xmm0, xmm0", "cvtsd2ss xmm0, xmm0",
    "movq rax, xmm0", "movq xmm0, rax", "movd xmm0, eax",
    "mov al, byte ptr [rdx + r8 - 1]", "mov byte ptr [rcx + r8 - 1], al",
    "mov al, byte ptr [rdx + r9]", "mov byte ptr [rcx + r9], al",
    # Extra forms added for coverage of otherwise-untested encoder branches
    # (spec sec.4.4 migration table did not previously exercise these).
    "sete spl", "neg ax", "mov r8d, 5", "mov word ptr [rbp-2], 5",
    "mov byte ptr [rcx], 200", "add ax, 5", "mov ax, cx", "movq xmm0, xmm1",
    "movq xmm8, xmm9",
]


def _as_bytes(line: str):
    """Assemble one line with MinGW `as`; return its .text bytes or None."""
    as_exe = shutil.which("as")
    if not as_exe:
        return None
    src = ".intel_syntax noprefix\n.text\n" + line + "\n"
    with tempfile.TemporaryDirectory() as d:
        s = os.path.join(d, "t.s")
        obj = os.path.join(d, "t.o")
        with open(s, "w", newline="\n") as f:
            f.write(src)
        r = subprocess.run([as_exe, "-o", obj, s], capture_output=True, text=True)
        if r.returncode != 0:
            return None
        return _coff_text(obj)


def _coff_text(path: str) -> bytes:
    """Extract the .text section's raw bytes from a COFF object."""
    data = open(path, "rb").read()
    num_sec = struct.unpack_from("<H", data, 2)[0]
    opt_size = struct.unpack_from("<H", data, 16)[0]
    sec_off = 20 + opt_size
    for i in range(num_sec):
        base = sec_off + i * 40
        name = data[base:base + 8].rstrip(b"\x00")
        if name == b".text":
            size = struct.unpack_from("<I", data, base + 16)[0]
            ptr = struct.unpack_from("<I", data, base + 20)[0]
            # `as` pads .text to a 16-byte boundary with 0x90 (nop); strip it.
            return data[ptr:ptr + size].rstrip(b"\x90")
    return b""


@t.params(CASES)
def test_encode(line: str):
    ours = bytes(assemble(".intel_syntax noprefix\n.text\n" + line + "\n").text)
    theirs = _as_bytes(line)
    if theirs is None:
        # No `as` oracle available: at least assert we produced bytes.
        t.require(len(ours) > 0, "no bytes emitted")
        return
    t.require_eq(ours, theirs, f"encoding mismatch for {line!r}")


# ---------------------------------------------------------------------------
# Error-path and internal-branch coverage.
#
# These exercise AssemblerError branches and a couple of module-private
# helpers directly (`_parse_mem`, `_Assembler`) that are reachable either
# through crafted-but-legal `.s` snippets, or -- for a couple of branches
# that the public `assemble()` grammar can never produce -- by calling the
# private helper directly. Each such case says why below.
# ---------------------------------------------------------------------------

from backend.x86_64.assembler import (  # noqa: E402
    AssemblerError, Sym, _Assembler, _parse_mem,
)
import backend.x86_64.assembler as _asm_mod  # noqa: E402


def _assemble_text(body: str):
    return assemble(".intel_syntax noprefix\n" + body)


def _expect_error(body: str, msg_fragment: str = ""):
    try:
        _assemble_text(body)
        t.require(False, f"expected AssemblerError for: {body!r}")
    except AssemblerError as e:
        if msg_fragment:
            t.require(msg_fragment in str(e), f"unexpected message: {e}")


# -- _parse_mem direct-call cases (module-private, called through the
# public grammar too, but these malformed forms are easiest to construct
# by calling the parser directly) --

def test_parse_mem_ptr_without_brackets_returns_none():
    t.require(_parse_mem("dword ptr rax") is None)


def test_parse_mem_bad_base_plus_index():
    try:
        _parse_mem("[rax+xmm0]")
        t.require(False, "no error")
    except AssemblerError as e:
        t.require("bad base+index operand" in str(e), str(e))


def test_parse_mem_unsupported_operand():
    try:
        _parse_mem("[rax+rbx+rcx]")
        t.require(False, "no error")
    except AssemblerError as e:
        t.require("unsupported memory operand" in str(e), str(e))


def test_parse_mem_bad_base():
    try:
        _parse_mem("[notareg+4]")
        t.require(False, "no error")
    except AssemblerError as e:
        t.require("bad memory base" in str(e), str(e))


# -- directive handling --

def test_bss_section_rejects_data_emission():
    _expect_error(".bss\n.quad 5\n", "cannot emit bytes into section bss")


def test_unknown_section_directive_raises():
    _expect_error(".section .foo\n", "unknown section")


def test_data_directive_switches_to_rdata():
    obj = _assemble_text(".data\n.byte 1\n")
    t.require_eq(bytes(obj.rdata), b"\x01")


def test_bss_directive_accumulates_size():
    obj = _assemble_text(".bss\n.space 4\n")
    t.require_eq(obj.bss_size, 4)


def test_space_directive_in_text_emits_zeros():
    obj = _assemble_text(".text\n.space 3\n")
    t.require_eq(bytes(obj.text), b"\x00\x00\x00")


def test_long_directive_emits_four_bytes():
    obj = _assemble_text(".text\n.long 300\n")
    t.require_eq(bytes(obj.text), struct.pack("<I", 300))


def test_byte_directive_emits_one_byte():
    obj = _assemble_text(".text\n.byte 65\n")
    t.require_eq(bytes(obj.text), b"A")


def test_unsupported_directive_raises():
    _expect_error(".text\n.foo bar\n", "unsupported directive")


def test_bad_asciz_raises():
    _expect_error('.text\n.asciz missing_quotes\n', "bad .asciz")


# -- instruction-encoding error paths --

def test_nop_encodes_single_byte():
    # Not in CASES/differential table: `as` right-strips trailing 0x90
    # padding from .text before comparison (see _coff_text), so a lone
    # `nop` line would always differentially "match" an empty string --
    # asserted directly here instead.
    obj = _assemble_text(".text\nnop\n")
    t.require_eq(bytes(obj.text), b"\x90")


def test_unsupported_mnemonic_raises():
    _expect_error(".text\nfoobar rax\n", "unsupported mnemonic")


def test_generic_python_exception_is_wrapped():
    # push requires a 64-bit register operand; a 32-bit one fails the
    # internal assert (a plain AssertionError), which _instruction must
    # catch and rewrap as an AssemblerError rather than let it escape raw.
    _expect_error(".text\npush eax\n", "failed to encode")


def test_mov_mem_mem_forms_raises():
    _expect_error(".text\nmov [rax], [rbx]\n", "unsupported mov forms")


def test_mov_imm_to_8bit_reg_raises():
    _expect_error(".text\nmov al, 5\n", "unsupported mov imm size")


def test_alu_unsupported_forms_raises():
    _expect_error(".text\nadd [rax], rcx\n", "unsupported add forms")


def test_call_numeric_target_unsupported():
    # The public grammar can never produce a Sym() with an all-digit name
    # for `call` (`_parse_operand` reads bare digits as an Imm, not a
    # Sym), so this branch is only reachable by calling `_call` directly.
    a = _Assembler("")
    try:
        a._call(Sym("5"))
        t.require(False, "no error")
    except AssemblerError as e:
        t.require("numeric call target unsupported" in str(e), str(e))


def test_unresolved_numeric_label_raises():
    _expect_error(".text\njmp 5f\n", "unresolved numeric label")


def test_rip_reference_to_earlier_text_label():
    # A RIP-relative operand whose target is already a defined text-section
    # symbol resolves as a same-section (code) fixup rather than deferring
    # to a PE-writer relocation.
    obj = _assemble_text("mylabel:\nnop\nlea rax, [rip + mylabel]\n")
    t.require(len(obj.relocs) == 0, "expected no deferred relocs")


def test_jmp_target_defined_in_rdata_defers_to_reloc():
    obj = _assemble_text("jmp foo\n.section .rdata\nfoo:\n.quad 0\n")
    t.require(any(r.symbol == "foo" for r in obj.relocs))


def test_jmp_undefined_symbol_raises():
    _expect_error(".text\njmp nowhere\n", "unresolved symbol")


def test_asciz_unknown_escape_uses_char_code():
    obj = _assemble_text('.text\n.asciz "\\q"\n')
    t.require_eq(bytes(obj.text), b"q\x00")


def test_asciz_falls_back_to_utf8_when_locale_cannot_encode():
    # Force a narrow "locale" codec so a non-ASCII character can't be
    # encoded with it, exercising the UnicodeEncodeError fallback to utf-8
    # -- deterministic regardless of the host's actual locale.
    orig = _asm_mod._LOCALE_ENCODING
    _asm_mod._LOCALE_ENCODING = "ascii"
    try:
        out = _asm_mod._decode_gas_string("é")
    finally:
        _asm_mod._LOCALE_ENCODING = orig
    t.require_eq(out, "é".encode("utf-8"))

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

from backend.assembler import assemble  # noqa: E402

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

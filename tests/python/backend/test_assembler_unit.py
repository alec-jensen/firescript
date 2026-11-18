"""Unit tests for firescript/backend/x86_64/assembler.py that
test_asm_encoding.py (the differential CASES table plus its error-path and
directive tests) does not already cover: an unknown base register in a
base+index memory operand, calls to an undefined runtime symbol, exact
`.quad`/`.long` data emission, `.align`/`.p2align` emitting no bytes, and
octal `.asciz` escapes."""
from __future__ import annotations

import os
import sys

from harness import pyunit as t
from harness.config import REPO_ROOT

sys.path.insert(0, os.path.join(REPO_ROOT, "firescript"))

from backend.x86_64.assembler import AssemblerError, assemble  # noqa: E402


def _expect_error(text: str, needle: str | None = None) -> None:
    raised = False
    try:
        assemble(text)
    except AssemblerError as e:
        raised = True
        if needle is not None:
            t.require(needle in str(e), f"unexpected message: {e}")
    t.require(raised, f"expected AssemblerError for:\n{text}")


def test_mem_unknown_base_plus_index_errors():
    _expect_error("mov rax, [zz+rcx]", "bad base+index")


def test_call_to_undefined_runtime_symbol_errors():
    # `fs_rt_*` names are treated as in-object code labels (not kernel32
    # imports); calling one with no matching definition anywhere in the
    # module must fail as an unresolved symbol.
    _expect_error("call fs_rt_does_not_exist\nret\n", "unresolved symbol")


def test_quad_and_long_directives():
    obj = assemble(".data\n.quad 1\n.long 2\n.text\nret\n")
    t.require_eq(bytes(obj.rdata), b"\x01\x00\x00\x00\x00\x00\x00\x00" + b"\x02\x00\x00\x00")


def test_align_directives_emit_no_bytes():
    for directive in (".align 4", ".p2align 4"):
        with t.subtest(directive):
            obj = assemble(f"{directive}\nret\n")
            t.require_eq(bytes(obj.text), b"\xc3")


def test_asciz_octal_escape():
    obj = assemble('.data\n.asciz "\\101"')  # octal 101 == 'A' (0x41)
    t.require(bytes(obj.rdata) == b"A\x00", f"got {obj.rdata!r}")
